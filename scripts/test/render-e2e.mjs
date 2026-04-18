/**
 * Script: render-e2e.mjs
 * Purpose: Run Grafana render smoke against disposable Grafana and VictoriaMetrics with fixture data.
 * Version: 2026.04.18.1
 * Last modified: 2026-04-18
 */
import { spawnSync } from "node:child_process";
import path from "node:path";

const repoRoot = process.cwd();
const defaultGrafanaImage = "grafana/grafana:13.0.1";
const defaultVmImage = "victoriametrics/victoria-metrics:v1.110.0";
const defaultGrafanaPort = "13031";
const defaultVmPort = "18433";
const datasourceUid = "vm-evcc";
const datasourceName = "VM-EVCC";

function parseArg(name, fallback = "") {
  const prefix = `--${name}=`;
  const inline = process.argv.find((arg) => arg.startsWith(prefix));
  if (inline) {
    return inline.slice(prefix.length);
  }
  const index = process.argv.indexOf(`--${name}`);
  if (index >= 0 && process.argv[index + 1] && !process.argv[index + 1].startsWith("--")) {
    return process.argv[index + 1];
  }
  return fallback;
}

function hasFlag(name) {
  return process.argv.includes(`--${name}`);
}

function run(command, args, options = {}) {
  console.log(`$ ${[command, ...args].join(" ")}`);
  const result = spawnSync(command, args, {
    cwd: repoRoot,
    encoding: "utf8",
    stdio: options.capture ? "pipe" : "inherit",
    env: options.env || process.env,
  });
  if (result.error) {
    throw result.error;
  }
  if (result.status !== 0) {
    const details = options.capture ? `${result.stdout || ""}${result.stderr || ""}`.trim() : "";
    throw new Error(`${command} failed with exit code ${result.status}${details ? `: ${details}` : ""}`);
  }
  return result;
}

async function waitForHttp(url, timeoutMs = 90000) {
  const deadline = Date.now() + timeoutMs;
  let lastError = "";
  while (Date.now() < deadline) {
    try {
      const response = await fetch(url);
      if (response.ok) {
        return;
      }
      lastError = `HTTP ${response.status}`;
    } catch (error) {
      lastError = error.message || String(error);
    }
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
  throw new Error(`Timeout waiting for ${url}: ${lastError}`);
}

function basicAuthHeader(username, password) {
  return `Basic ${Buffer.from(`${username}:${password}`).toString("base64")}`;
}

async function grafanaApi(baseUrl, pathName, { method = "GET", body, username, password, token = "" } = {}) {
  const headers = {
    Accept: "application/json",
  };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  } else {
    headers.Authorization = basicAuthHeader(username, password);
  }
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
  }
  const response = await fetch(`${baseUrl.replace(/\/$/, "")}${pathName}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const text = await response.text();
  let data = {};
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    data = { raw: text };
  }
  if (!response.ok) {
    throw new Error(`${method} ${pathName} failed (${response.status}): ${JSON.stringify(data)}`);
  }
  return data;
}

async function createServiceToken(baseUrl, username, password) {
  const suffix = Date.now();
  const serviceAccount = await grafanaApi(baseUrl, "/api/serviceaccounts", {
    method: "POST",
    username,
    password,
    body: {
      name: `render-e2e-${suffix}`,
      role: "Admin",
    },
  });
  const token = await grafanaApi(baseUrl, `/api/serviceaccounts/${serviceAccount.id}/tokens`, {
    method: "POST",
    username,
    password,
    body: {
      name: `render-e2e-token-${suffix}`,
    },
  });
  return token.key;
}

async function createDatasource(baseUrl, token, vmContainerName) {
  await grafanaApi(baseUrl, "/api/datasources", {
    method: "POST",
    token,
    body: {
      name: datasourceName,
      uid: datasourceUid,
      type: "victoriametrics-metrics-datasource",
      access: "proxy",
      url: `http://${vmContainerName}:8428`,
      isDefault: true,
      jsonData: {
        prometheusType: "Prometheus",
        prometheusVersion: "2.49.0",
      },
    },
  });
}

function toMs(date) {
  return date.getTime();
}

function pad2(value) {
  return String(value).padStart(2, "0");
}

function localLabels(date) {
  return {
    local_year: String(date.getUTCFullYear()),
    local_month: pad2(date.getUTCMonth() + 1),
  };
}

function uniqueDays(now) {
  const today = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()));
  const allTimeStart = new Date(Date.UTC(Math.max(2025, now.getUTCFullYear() - 1), 0, 1));
  const days = [];
  for (let day = allTimeStart; day <= today; day = new Date(Date.UTC(day.getUTCFullYear(), day.getUTCMonth() + 1, 1))) {
    days.push(new Date(day));
  }
  const monthStart = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), 1));
  for (let day = monthStart; day <= today; day = new Date(day.getTime() + 86400000)) {
    days.push(new Date(day));
  }
  return [...new Map(days.map((day) => [day.toISOString().slice(0, 10), day])).values()].sort((a, b) => a - b);
}

function addSeries(series, metric, labels, values) {
  series.push({
    metric: {
      __name__: metric,
      ...labels,
    },
    values: values.map((item) => item.value),
    timestamps: values.map((item) => item.timestamp),
  });
}

function addDailyRollupSeries(series, metric, labels, days, valueForDay) {
  const groups = new Map();
  for (const [index, day] of days.entries()) {
    const groupLabels = { ...labels, ...localLabels(day) };
    const key = JSON.stringify(groupLabels);
    if (!groups.has(key)) {
      groups.set(key, { labels: groupLabels, values: [] });
    }
    groups.get(key).values.push({
      timestamp: toMs(day),
      value: valueForDay(day, index),
    });
  }
  for (const group of groups.values()) {
    addSeries(series, metric, group.labels, group.values);
  }
}

function dailyShape(base, day, index) {
  const monthFactor = 1 + (day.getUTCMonth() % 4) * 0.04;
  const dayFactor = 1 + (index % 7) * 0.01;
  return Math.round(base * monthFactor * dayFactor * 1000) / 1000;
}

function fixtureSeries(now) {
  const series = [];
  const days = uniqueDays(now);
  const dailyValues = [
    ["evcc_pv_energy_daily_wh", {}, 24000],
    ["evcc_grid_import_daily_wh", {}, 6000],
    ["evcc_home_energy_daily_wh", {}, 12000],
    ["evcc_loadpoint_energy_daily_wh", { loadpoint: "LP1" }, 2400],
    ["evcc_grid_export_daily_wh", {}, 3000],
    ["evcc_grid_import_cost_daily_eur", {}, 1.8],
    ["evcc_grid_export_credit_daily_eur", {}, 0.24],
    ["evcc_ext_energy_daily_wh", { title: "Server" }, 2500],
    ["evcc_aux_energy_daily_wh", { title: "Aux" }, 500],
    ["evcc_battery_charge_daily_wh", {}, 1800],
    ["evcc_battery_discharge_daily_wh", {}, 900],
    ["evcc_battery_soc_daily_min_pct", {}, 35],
    ["evcc_battery_soc_daily_max_pct", {}, 95],
    ["evcc_grid_import_price_avg_daily_ct_per_kwh", {}, 30],
    ["evcc_grid_import_price_effective_daily_ct_per_kwh", {}, 31],
    ["evcc_grid_import_price_min_daily_ct_per_kwh", {}, 22],
    ["evcc_grid_import_price_max_daily_ct_per_kwh", {}, 42],
    ["evcc_loadpoint_energy_from_pv_daily_wh", { loadpoint: "LP1" }, 1400],
    ["evcc_loadpoint_energy_from_battery_daily_wh", { loadpoint: "LP1" }, 400],
    ["evcc_loadpoint_energy_from_grid_daily_wh", { loadpoint: "LP1" }, 600],
    ["evcc_loadpoint_energy_from_pv_daily_wh", { loadpoint: "Heat pump" }, 700],
    ["evcc_loadpoint_energy_from_battery_daily_wh", { loadpoint: "Heat pump" }, 200],
    ["evcc_loadpoint_energy_from_grid_daily_wh", { loadpoint: "Heat pump" }, 1100],
    ["evcc_vehicle_energy_daily_wh", { vehicle: "EV1" }, 9000],
    ["evcc_vehicle_distance_daily_km", { vehicle: "EV1" }, 45],
    ["evcc_vehicle_charge_cost_daily_eur", { vehicle: "EV1" }, 2.1],
    ["evcc_potential_vehicle_charge_cost_daily_eur", { vehicle: "EV1" }, 4.5],
    ["evcc_potential_home_cost_daily_eur", {}, 3.6],
    ["evcc_potential_loadpoint_cost_daily_eur", {}, 1.2],
    ["evcc_battery_discharge_value_daily_eur", {}, 0.27],
    ["evcc_battery_charge_feedin_cost_daily_eur", {}, 0.14],
  ];

  for (const [metric, labels, value] of dailyValues) {
    addDailyRollupSeries(series, metric, labels, days, (day, index) => dailyShape(value, day, index));
  }

  const yearlyDays = [...new Map(days.map((day) => [day.getUTCFullYear(), new Date(Date.UTC(day.getUTCFullYear(), 0, 1))])).values()];
  addDailyRollupSeries(series, "evcc_pv_top30_mean_yearly_wh", {}, yearlyDays, (day, index) => dailyShape(28000, day, index));
  const monthStartDays = [...new Map(days.map((day) => [`${day.getUTCFullYear()}-${day.getUTCMonth()}`, new Date(Date.UTC(day.getUTCFullYear(), day.getUTCMonth(), 1))])).values()];
  addDailyRollupSeries(series, "evcc_pv_top5_mean_monthly_wh", {}, monthStartDays, (day, index) => dailyShape(30000, day, index));

  const rawStart = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()));
  const rawStepMs = 5 * 60 * 1000;
  const rawTimestamps = Array.from(
    { length: Math.max(1, Math.floor((now.getTime() - rawStart.getTime()) / rawStepMs) + 1) },
    (_item, index) => rawStart.getTime() + index * rawStepMs,
  );
  if (rawTimestamps[rawTimestamps.length - 1] < now.getTime()) {
    rawTimestamps.push(now.getTime());
  }
  const rawValues = (value) => rawTimestamps.map((timestamp, index) => ({ timestamp, value: value + index }));
  addSeries(series, "pvPower_value", { id: "", title: "Gesamt" }, rawValues(5000));
  addSeries(series, "pvPower_value", { id: "pv1", title: "PV 1" }, rawValues(2200));
  addSeries(series, "pvPower_value", { id: "pv2", title: "PV 2" }, rawValues(1800));
  addSeries(series, "pvPower_value", { id: "pv3", title: "" }, rawValues(900));
  addSeries(series, "gridPower_value", {}, rawValues(800));
  addSeries(series, "homePower_value", {}, rawValues(-1600));
  addSeries(series, "batteryPower_value", { id: "" }, rawValues(400));
  addSeries(series, "batterySoc_value", { id: "", title: "Total" }, rawValues(76));
  addSeries(series, "batterySoc_value", { id: "bat1", title: "Battery" }, rawValues(80));
  addSeries(series, "chargePower_value", { loadpoint: "LP1" }, rawValues(-700));
  addSeries(series, "tariffSolar_value", {}, rawValues(6500));
  addSeries(series, "tariffGrid_value", {}, rawValues(0.3));
  addSeries(series, "tariffFeedIn_value", {}, rawValues(0.08));
  addSeries(series, "tariffCo2_value", {}, rawValues(320));
  addSeries(series, "extPower_value", { title: "Server" }, rawValues(350));
  addSeries(series, "extPower_value", { title: "KWL" }, rawValues(180));
  addSeries(series, "auxPower_value", { title: "Aux" }, rawValues(90));
  addSeries(series, "gridCurrents_l1", {}, rawValues(2));
  addSeries(series, "gridCurrents_l2", {}, rawValues(3));
  addSeries(series, "gridCurrents_l3", {}, rawValues(4));
  addSeries(series, "gridPowers_l1", {}, rawValues(250));
  addSeries(series, "gridPowers_l2", {}, rawValues(270));
  addSeries(series, "gridPowers_l3", {}, rawValues(280));
  addSeries(series, "chargeCurrents_l1", { loadpoint: "LP1" }, rawValues(6));
  addSeries(series, "chargeCurrents_l2", { loadpoint: "LP1" }, rawValues(6));
  addSeries(series, "chargeCurrents_l3", { loadpoint: "LP1" }, rawValues(6));
  addSeries(series, "vehicleOdometer_value", { vehicle: "EV1" }, rawValues(12345));
  addSeries(series, "sessionPricePerKWh_value", { vehicle: "EV1" }, rawValues(0.25));
  addSeries(series, "sessionSolarPercentage_value", { vehicle: "EV1" }, rawValues(65));
  return series;
}

async function importVmFixture(baseUrl, now) {
  const body = fixtureSeries(now).map((item) => JSON.stringify(item)).join("\n") + "\n";
  const response = await fetch(`${baseUrl.replace(/\/$/, "")}/api/v1/import`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body,
  });
  if (!response.ok) {
    throw new Error(`VM fixture import failed (${response.status}): ${await response.text()}`);
  }
}

function startDockerEnvironment(args) {
  const suffix = `${process.pid}`;
  const networkName = `evcc-render-e2e-${suffix}`;
  const vmContainerName = `evcc-render-vm-${suffix}`;
  const grafanaContainerName = `evcc-render-grafana-${suffix}`;

  run("docker", ["network", "create", networkName]);
  run("docker", [
    "run",
    "--rm",
    "-d",
    "--name",
    vmContainerName,
    "--network",
    networkName,
    "-p",
    `127.0.0.1:${args.vmPort}:8428`,
    args.vmImage,
    "-retentionPeriod=100y",
  ]);
  run("docker", [
    "run",
    "--rm",
    "-d",
    "--name",
    grafanaContainerName,
    "--network",
    networkName,
    "-p",
    `127.0.0.1:${args.grafanaPort}:3000`,
    "-e",
    `GF_SECURITY_ADMIN_USER=${args.grafanaUser}`,
    "-e",
    `GF_SECURITY_ADMIN_PASSWORD=${args.grafanaPassword}`,
    "-e",
    "GF_INSTALL_PLUGINS=victoriametrics-metrics-datasource",
    args.grafanaImage,
  ]);

  return { networkName, vmContainerName, grafanaContainerName };
}

function stopDockerEnvironment(env, keepDocker) {
  if (keepDocker) {
    return;
  }
  if (env.grafanaContainerName) {
    run("docker", ["stop", env.grafanaContainerName], { capture: true });
  }
  if (env.vmContainerName) {
    run("docker", ["stop", env.vmContainerName], { capture: true });
  }
  if (env.networkName) {
    run("docker", ["network", "rm", env.networkName], { capture: true });
  }
}

function childEnv(baseUrl, token, username, password) {
  return {
    ...process.env,
    GRAFANA_URL: baseUrl,
    GRAFANA_USERNAME: username,
    GRAFANA_PASSWORD: password,
    GRAFANA_API_TOKEN: token,
    GRAFANA_DS_VM_EVCC_UID: datasourceUid,
    GRAFANA_TEST_FOLDER_UID: "evcc-render-e2e",
    GRAFANA_TEST_FOLDER_TITLE: "EVCC Render E2E",
  };
}

async function main() {
  const args = {
    grafanaImage: parseArg("grafana-image", defaultGrafanaImage),
    vmImage: parseArg("vm-image", defaultVmImage),
    grafanaPort: parseArg("grafana-port", defaultGrafanaPort),
    vmPort: parseArg("vm-port", defaultVmPort),
    grafanaUser: parseArg("grafana-user", "admin"),
    grafanaPassword: parseArg("grafana-password", "admin"),
    source: parseArg("source", "dashboards/original/en"),
    tag: parseArg("tag", "vm-render-e2e"),
    manifest: parseArg("manifest", "tests/artifacts/import-manifest-vm-render-e2e.json"),
    waitMs: parseArg("wait-ms", "5000"),
    keepDocker: hasFlag("keep-docker"),
  };
  const now = new Date(parseArg("fixture-now", new Date().toISOString()));
  if (Number.isNaN(now.getTime())) {
    throw new Error("--fixture-now must be an ISO timestamp");
  }

  const dockerEnv = startDockerEnvironment(args);
  const grafanaBaseUrl = `http://127.0.0.1:${args.grafanaPort}`;
  const vmBaseUrl = `http://127.0.0.1:${args.vmPort}`;
  try {
    await waitForHttp(`${vmBaseUrl}/health`);
    await waitForHttp(`${grafanaBaseUrl}/api/health`, 120000);
    await importVmFixture(vmBaseUrl, now);
    const token = await createServiceToken(grafanaBaseUrl, args.grafanaUser, args.grafanaPassword);
    await createDatasource(grafanaBaseUrl, token, dockerEnv.vmContainerName);
    const env = childEnv(grafanaBaseUrl, token, args.grafanaUser, args.grafanaPassword);

    run("node", [
      "scripts/test/import-dashboards-raw.mjs",
      "--family=vm",
      `--source=${args.source}`,
      `--tag=${args.tag}`,
      `--manifest=${args.manifest}`,
    ], { env });
    run("node", [
      "scripts/test/render-smoke-check.mjs",
      `--manifest=${args.manifest}`,
      "--from=now-7d",
      "--to=now",
      `--wait-ms=${args.waitMs}`,
    ], { env });

    console.log("Render E2E");
    console.log("==========");
    console.log("Script:        render-e2e.mjs");
    console.log("Version:       2026.04.18.1");
    console.log("Last modified: 2026-04-18");
    console.log("");
    console.log("Result");
    console.log("------");
    console.log("OK: disposable Grafana rendered VM dashboards against fixture VictoriaMetrics data.");
  } finally {
    stopDockerEnvironment(dockerEnv, args.keepDocker);
  }
}

main().catch((error) => {
  console.error(error.message || error);
  process.exit(1);
});
