/**
 * Script: dashboard-query-readback.mjs
 * Purpose: Execute original VM dashboard MetricsQL targets against VictoriaMetrics after Grafana macro substitution.
 * Version: 2026.04.22.1
 * Last modified: 2026-04-22
 */
import fs from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { portableRelative } from "../helper/_dashboard-family.mjs";
import {
  collectDashboardPanels,
  dashboardTimeSettings,
  dashboardVariables,
  isV2Dashboard,
} from "../helper/dashboard-schema.mjs";

const repoRoot = process.cwd();
const defaultSourceDir = path.join(repoRoot, "dashboards", "original", "en");
const defaultDockerImage = "victoriametrics/victoria-metrics:v1.110.0";
const defaultDockerPort = "18431";
const defaultNow = "2026-04-14T12:00:00Z";
const fallbackVariables = {
  VAR_ENERGYSAMPLEINTERVAL: "30s",
  VAR_EVCCURL: "http://evcc.local/",
  VAR_INVERTERPORTALTITLE: "VRM",
  VAR_INVERTERPORTALURL: "https://vrm.victronenergy.com/",
  VAR_LOADPOINTBLOCKLIST: "^none$",
  VAR_PEAKPOWERLIMIT: "30000",
  VAR_TARIFFPRICEINTERVAL: "15m",
  VAR_VEHICLEBLOCKLIST: "^none$",
  auxBlocklist: "^none$",
  dashboardBuild: "query-readback",
  energySampleInterval: "30s",
  extBlocklist: "^none$",
  heatPumpLoadpointRegex: "(?i).*(daikin-wp|wp|warmepumpe|wärmepumpe|heat pump).*$",
  installedWattPeak: "20",
  loadpoint: "LP1",
  loadpointBlocklist: "^none$",
  peakPowerLimit: "30000",
  tariffPriceInterval: "15m",
  vehicle: "Vehicle1",
  vehicleBlocklist: "^none$",
};

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
  const result = spawnSync(command, args, { encoding: "utf8", ...options });
  if (result.error) {
    throw result.error;
  }
  return result;
}

function collectFiles(dir, predicate) {
  const out = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      out.push(...collectFiles(fullPath, predicate));
    } else if (entry.isFile() && predicate(fullPath)) {
      out.push(fullPath);
    }
  }
  return out.sort((a, b) => a.localeCompare(b));
}

function targetExpr(target) {
  return String(target?.expr || target?.expression || target?.query || "");
}

function isVmTarget(target) {
  return String(target?.group || "") === "victoriametrics-metrics-datasource" && targetExpr(target).trim() !== "";
}

function datePartsInBerlin(date) {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Europe/Berlin",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).formatToParts(date);
  const value = (type) => parts.find((part) => part.type === type)?.value || "00";
  return {
    YYYY: value("year"),
    MM: value("month"),
    DD: value("day"),
    HH: value("hour"),
    mm: value("minute"),
    ss: value("second"),
  };
}

function parseDurationSeconds(value) {
  const match = String(value || "").match(/^(\d+)(ms|s|m|h|d|w|M|y)$/);
  if (!match) {
    return 0;
  }
  const amount = Number(match[1]);
  const unitSeconds = {
    ms: 0.001,
    s: 1,
    m: 60,
    h: 3600,
    d: 86400,
    w: 604800,
    M: 2678400,
    y: 31622400,
  };
  return Math.max(1, Math.round(amount * unitSeconds[match[2]]));
}

function durationString(seconds) {
  if (seconds % 604800 === 0) {
    return `${seconds / 604800}w`;
  }
  if (seconds % 86400 === 0) {
    return `${seconds / 86400}d`;
  }
  if (seconds % 3600 === 0) {
    return `${seconds / 3600}h`;
  }
  if (seconds % 60 === 0) {
    return `${seconds / 60}m`;
  }
  return `${Math.max(1, seconds)}s`;
}

function floorUtc(date, unit) {
  const out = new Date(date.getTime());
  if (unit === "y") {
    out.setUTCMonth(0, 1);
  } else if (unit === "M") {
    out.setUTCDate(1);
  }
  if (["y", "M", "d"].includes(unit)) {
    out.setUTCHours(0, 0, 0, 0);
  } else if (unit === "h") {
    out.setUTCMinutes(0, 0, 0);
  } else if (unit === "m") {
    out.setUTCSeconds(0, 0);
  }
  return out;
}

function addUtc(date, amount, unit) {
  const out = new Date(date.getTime());
  if (unit === "y") {
    out.setUTCFullYear(out.getUTCFullYear() + amount);
  } else if (unit === "M") {
    out.setUTCMonth(out.getUTCMonth() + amount);
  } else if (unit === "w") {
    out.setUTCDate(out.getUTCDate() + amount * 7);
  } else if (unit === "d") {
    out.setUTCDate(out.getUTCDate() + amount);
  } else if (unit === "h") {
    out.setUTCHours(out.getUTCHours() + amount);
  } else if (unit === "m") {
    out.setUTCMinutes(out.getUTCMinutes() + amount);
  }
  return out;
}

function resolveRelativeTime(expr, now) {
  if (!expr || expr === "now") {
    return new Date(now.getTime());
  }
  const match = String(expr).match(/^now(?:(?<sign>[+-])(?<amount>\d+)(?<offsetUnit>[yMwdhm]))?(?:\/(?<floorUnit>[yMwdhm]))?$/);
  if (!match) {
    const absolute = new Date(expr);
    if (Number.isNaN(absolute.getTime())) {
      throw new Error(`Unsupported dashboard time expression: ${expr}`);
    }
    return absolute;
  }
  const groups = match.groups || {};
  let out = new Date(now.getTime());
  if (groups.sign && groups.amount && groups.offsetUnit) {
    out = addUtc(out, Number(groups.amount) * (groups.sign === "-" ? -1 : 1), groups.offsetUnit);
  }
  if (groups.floorUnit) {
    out = floorUtc(out, groups.floorUnit);
  }
  return out;
}

function impliedRangeSeconds(fromExpr, toExpr, fromDate, toDate) {
  const rawSeconds = Math.round((toDate.getTime() - fromDate.getTime()) / 1000);
  if (rawSeconds > 0) {
    return rawSeconds;
  }
  const rounded = String(fromExpr || toExpr || "").match(/\/([yMwdhm])$/);
  if (!rounded) {
    return 86400;
  }
  return {
    y: 31622400,
    M: 2678400,
    w: 604800,
    d: 86400,
    h: 3600,
    m: 60,
  }[rounded[1]] || 86400;
}

function dashboardRange(dashboard, now) {
  const timeSettings = dashboardTimeSettings(dashboard);
  const fromExpr = timeSettings?.from || "now-1d";
  const toExpr = timeSettings?.to || "now";
  const fromDate = resolveRelativeTime(fromExpr, now);
  const toDate = resolveRelativeTime(toExpr, now);
  const rangeSeconds = impliedRangeSeconds(fromExpr, toExpr, fromDate, toDate);
  return { fromExpr, toExpr, fromDate, toDate, rangeSeconds };
}

function variableQueryValue(variable) {
  if (isV2Dashboard({ apiVersion: "dashboard.grafana.app/v2", kind: "Dashboard", spec: { variables: [variable] } })) {
    // never reached; helper trick avoided below
  }
  return "";
}

function variableCurrentValue(variable, v2 = false) {
  const current = v2 ? variable?.spec?.current?.value : variable?.current?.value;
  if (current && current !== "$__all" && !String(current).startsWith("${VAR_")) {
    return String(current);
  }
  const query = v2 ? variable?.spec?.query : variable?.query;
  if (typeof query === "string" && query && !query.startsWith("${VAR_")) {
    return query;
  }
  return "";
}

function resolvedDashboardVariables(dashboard) {
  const values = { ...fallbackVariables };
  for (const variable of dashboardVariables(dashboard)) {
    if (isV2Dashboard(dashboard)) {
      const name = variable?.spec?.name;
      if (!name) {
        continue;
      }
      values[name] = variableCurrentValue(variable, true) || values[name] || ".*";
      continue;
    }

    const name = variable?.name;
    if (!name) {
      continue;
    }
    values[name] = variableCurrentValue(variable, false) || values[name] || ".*";
  }

  let changed = true;
  while (changed) {
    changed = false;
    for (const [key, value] of Object.entries(values)) {
      const expanded = replaceVariables(String(value), values);
      if (expanded !== value) {
        values[key] = expanded;
        changed = true;
      }
    }
  }
  return values;
}

function replaceDateMacro(match, source, format, range) {
  const parts = datePartsInBerlin(source === "__to" ? range.toDate : range.fromDate);
  return String(format)
    .replaceAll("YYYY", parts.YYYY)
    .replaceAll("MM", parts.MM)
    .replaceAll("DD", parts.DD)
    .replaceAll("HH", parts.HH)
    .replaceAll("mm", parts.mm)
    .replaceAll("ss", parts.ss);
}

function replaceVariables(value, variables) {
  let out = value;
  out = out.replace(/\$\{([A-Za-z][A-Za-z0-9_]*)\}/g, (_match, name) => variables[name] ?? fallbackVariables[name] ?? "");
  out = out.replace(/\$([A-Za-z][A-Za-z0-9_]*)/g, (_match, name) => variables[name] ?? fallbackVariables[name] ?? "");
  return out;
}

function substituteQuery(expr, dashboard, now) {
  const range = dashboardRange(dashboard, now);
  const variables = resolvedDashboardVariables(dashboard);
  const rangeText = durationString(range.rangeSeconds);
  let out = String(expr);
  out = out.replace(/\$\{(__from|__to):date:([^}]+)\}/g, (match, source, format) => replaceDateMacro(match, source, format, range));
  out = out.replaceAll("$__range_ms", String(range.rangeSeconds * 1000));
  out = out.replaceAll("$__range_s", String(range.rangeSeconds));
  out = out.replaceAll("$__range", rangeText);
  out = out.replaceAll("$__interval_ms", String(parseDurationSeconds(variables.energySampleInterval || "30s") * 1000));
  out = out.replaceAll("$__interval", variables.energySampleInterval || "30s");
  out = out.replaceAll("$__rate_interval", variables.energySampleInterval || "30s");
  out = replaceVariables(out, variables);
  return { query: out, time: range.toDate.toISOString().replace(".000Z", "Z") };
}

function unresolvedToken(query) {
  const match = query.match(/\$\{[^}]+\}|\$[A-Za-z_][A-Za-z0-9_]*/);
  return match ? match[0] : "";
}

async function postQuery(baseUrl, query, time) {
  const body = new URLSearchParams({ query, time, nocache: "1" });
  const response = await fetch(`${baseUrl.replace(/\/$/, "")}/api/v1/query`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });
  const text = await response.text();
  let payload = {};
  try {
    payload = text ? JSON.parse(text) : {};
  } catch {
    throw new Error(`non-JSON VM response HTTP ${response.status}: ${text.slice(0, 500)}`);
  }
  if (!response.ok || payload.status !== "success") {
    const message = payload.error || payload.errorType || text;
    throw new Error(`HTTP ${response.status}: ${message}`);
  }
  return payload;
}

async function waitForVm(baseUrl) {
  const deadline = Date.now() + 30000;
  let lastError = "";
  while (Date.now() < deadline) {
    try {
      const response = await fetch(`${baseUrl.replace(/\/$/, "")}/health`);
      if (response.ok) {
        return;
      }
      lastError = `HTTP ${response.status}`;
    } catch (error) {
      lastError = error.message || String(error);
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw new Error(`VictoriaMetrics did not become healthy at ${baseUrl}: ${lastError}`);
}

function startDockerVm(image, port) {
  const name = `evcc-dashboard-query-readback-${process.pid}`;
  const result = run("docker", [
    "run",
    "--rm",
    "-d",
    "--name",
    name,
    "-p",
    `127.0.0.1:${port}:8428`,
    image,
    "-retentionPeriod=100y",
  ]);
  if (result.status !== 0) {
    throw new Error(`docker run failed: ${result.stderr.trim() || result.stdout.trim()}`);
  }
  return { name, baseUrl: `http://127.0.0.1:${port}` };
}

function stopDockerVm(name) {
  if (!name) {
    return;
  }
  run("docker", ["stop", name]);
}

function readTargets(sourceDir) {
  const files = collectFiles(sourceDir, (file) => file.endsWith(".json"));
  const targets = [];
  for (const file of files) {
    const dashboard = JSON.parse(fs.readFileSync(file, "utf8"));
    for (const panel of collectDashboardPanels(dashboard)) {
      for (const target of panel.targets || []) {
        if (!isVmTarget(target)) {
          continue;
        }
        targets.push({
          file,
          fileName: portableRelative(sourceDir, file),
          dashboard,
          panelId: panel.id,
          panelTitle: panel.title || String(panel.id),
          refId: target.refId || "",
          expr: targetExpr(target),
        });
      }
    }
  }
  return targets;
}

async function checkTargets(baseUrl, targets, now) {
  const failures = [];
  const countsByFile = new Map();
  for (const target of targets) {
    countsByFile.set(target.fileName, (countsByFile.get(target.fileName) || 0) + 1);
    let query = "";
    let time = "";
    try {
      const substituted = substituteQuery(target.expr, target.dashboard, now);
      query = substituted.query;
      time = substituted.time;
      const token = unresolvedToken(query);
      if (token) {
        throw new Error(`unresolved Grafana token ${token}`);
      }
      await postQuery(baseUrl, query, time);
    } catch (error) {
      failures.push({
        fileName: target.fileName,
        panelId: target.panelId,
        panelTitle: target.panelTitle,
        refId: target.refId,
        error: error.message || String(error),
        query,
      });
    }
  }
  return { failures, countsByFile };
}

async function main() {
  const sourceDir = path.resolve(parseArg("source-dir", defaultSourceDir));
  const docker = hasFlag("docker");
  const dockerImage = parseArg("docker-image", defaultDockerImage);
  const dockerPort = parseArg("docker-port", defaultDockerPort);
  const keepDocker = hasFlag("keep-docker");
  const now = new Date(parseArg("now", defaultNow));
  if (Number.isNaN(now.getTime())) {
    throw new Error("--now must be an ISO timestamp");
  }

  let baseUrl = parseArg("base-url", process.env.QUERY_READBACK_VM_BASE_URL || "");
  let containerName = "";
  if (docker) {
    const dockerVm = startDockerVm(dockerImage, dockerPort);
    baseUrl = dockerVm.baseUrl;
    containerName = dockerVm.name;
  }
  if (!baseUrl) {
    throw new Error("Pass --docker or --base-url/QUERY_READBACK_VM_BASE_URL.");
  }

  try {
    await waitForVm(baseUrl);
    const targets = readTargets(sourceDir);
    const { failures, countsByFile } = await checkTargets(baseUrl, targets, now);

    console.log("Dashboard query readback");
    console.log("========================");
    console.log("Script:        dashboard-query-readback.mjs");
    console.log("Version:       2026.04.22.1");
    console.log("Last modified: 2026-04-22");
    console.log(`VM base URL:   ${baseUrl}`);
    console.log(`Source dir:    ${sourceDir}`);
    console.log(`Query time:    ${now.toISOString().replace(".000Z", "Z")}`);
    console.log(`Targets:       ${targets.length}`);
    for (const [fileName, count] of [...countsByFile.entries()].sort((a, b) => a[0].localeCompare(b[0]))) {
      console.log(`- ${fileName}: ${count}`);
    }

    if (failures.length > 0) {
      console.log("");
      console.log("Failures");
      console.log("--------");
      for (const failure of failures) {
        console.log(`- ${failure.fileName} panel=${failure.panelId} ref=${failure.refId} title=${failure.panelTitle}: ${failure.error}`);
        console.log(`  query=${failure.query.slice(0, 500).replace(/\s+/g, " ")}`);
      }
      throw new Error(`Dashboard query readback failed with ${failures.length} failing target(s).`);
    }

    console.log("");
    console.log("Result");
    console.log("------");
    console.log("OK: all VM dashboard MetricsQL targets executed successfully.");
  } finally {
    if (containerName && !keepDocker) {
      stopDockerVm(containerName);
    }
  }
}

main().catch((error) => {
  console.error(error.message || error);
  process.exit(1);
});
