/**
 * Script: render-smoke-check.mjs
 * Purpose: Open imported Grafana dashboards in a browser and fail on rendered panel errors.
 * Version: 2026.04.15.1
 * Last modified: 2026-04-15
 */
import path from "node:path";
import { chromium } from "playwright";
import {
  loadEnvFile,
  optionalEnv,
  parseArg,
  readJson,
  requireEnv,
} from "./_lib.mjs";

loadEnvFile(parseArg("env", ".env"));

const baseUrl = requireEnv("GRAFANA_URL").replace(/\/$/, "");
const username = requireEnv("GRAFANA_USERNAME");
const password = requireEnv("GRAFANA_PASSWORD");
const manifestPath = parseArg("manifest", "tests/artifacts/import-manifest-set.json");
const orgId = optionalEnv("GRAFANA_ORG_ID", "1");
const waitMs = Number(parseArg("wait-ms", optionalEnv("GRAFANA_RENDER_SMOKE_WAIT_MS", optionalEnv("GRAFANA_SCREENSHOT_WAIT_MS", "3500"))));
const failNoData = parseArg("fail-no-data", "true") !== "false";
const failQueryErrors = parseArg("fail-query-errors", "true") !== "false";
const failPageErrors = parseArg("fail-page-errors", "false") === "true";
const requireCriticalPanels = parseArg("require-critical-panels", "true") !== "false";

const renderedErrorTexts = [
  "No numeric fields found",
  "Bar charts require a string or time field",
  "Panel plugin not found",
  "Dashboard not found",
  "Datasource named",
  "Datasource was not found",
  "Templating init failed",
  "Query error",
  "parse error",
  "execution error",
  "bad_data",
  "An unexpected error happened",
];

const emptyPanelTexts = [
  "No data",
  "No series",
  "No fields found",
  "No value",
];

const criticalPanelsByFile = {
  "VM_ EVCC_ All-time.json": [
    { id: 12, title: "Energy totals" },
    { id: 24, title: "Metric gauges" },
    { id: 28, title: "Monthly costs" },
    { id: 38, title: "Days with highest yield" },
  ],
  "VM_ EVCC_ Jahr.json": [
    { id: 41, title: "Energy totals" },
    { id: 44, title: "Metric gauges" },
    { id: 47, title: "Energy" },
    { id: 66, title: "Home: Energy consumption" },
    { id: 70, title: "Home: Energy distribution" },
  ],
  "VM_ EVCC_ Monat.json": [
    { id: 19, title: "Monthly energy totals" },
    { id: 24, title: "Metric gauges" },
    { id: 25, title: "Energy" },
    { id: 31, title: "Home: Energy consumption" },
    { id: 37, title: "Total: Energy distribution" },
  ],
  "VM_ EVCC_ Today - Details.json": [
    { id: 2, title: "PV energy" },
    { id: 35, title: "Forecast" },
    { id: 11, title: "Charge currents/phase" },
    { id: 15, title: "Phases" },
  ],
  "VM_ EVCC_ Today - Mobile.json": [
    { id: 74, title: "Power" },
  ],
  "VM_ EVCC_ Today.json": [
    { id: 74, title: "Power" },
  ],
};

function sourceFileName(dashboard) {
  return String(dashboard.sourceFile || "").replace(/^.*[\\/]/, "");
}

function dashboardPath(dashboard) {
  if (dashboard.url) {
    return dashboard.url;
  }
  return `/d/${encodeURIComponent(dashboard.uid)}`;
}

function soloPanelPath(dashboard) {
  const fullPath = dashboardPath(dashboard);
  if (fullPath.startsWith("/d/")) {
    return fullPath.replace(/^\/d\//, "/d-solo/");
  }
  return `/d-solo/${encodeURIComponent(dashboard.uid)}`;
}

function readSourceTime(dashboard) {
  if (!dashboard.sourceFile) {
    return {};
  }
  const sourcePath = path.resolve(dashboard.sourceFile);
  try {
    const source = readJson(sourcePath);
    return {
      from: source?.time?.from || "",
      to: source?.time?.to || "",
    };
  } catch {
    return {};
  }
}

function queryString(params) {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") {
      query.set(key, String(value));
    }
  }
  return query.toString();
}

function dashboardUrl(dashboard) {
  const range = readSourceTime(dashboard);
  const query = queryString({
    kiosk: "",
    orgId,
    from: range.from,
    to: range.to,
  });
  return `${baseUrl}${dashboardPath(dashboard)}?${query}`;
}

function panelUrl(dashboard, panelId) {
  const range = readSourceTime(dashboard);
  const query = queryString({
    orgId,
    panelId,
    from: range.from,
    to: range.to,
    theme: "dark",
  });
  return `${baseUrl}${soloPanelPath(dashboard)}?${query}`;
}

function findTextHits(text, candidates) {
  return candidates.filter((candidate) => text.includes(candidate));
}

function isGrafanaDataRequest(url) {
  return (
    url.includes("/api/ds/query") ||
    url.includes("/api/tsdb/query") ||
    url.includes("/api/datasources/proxy")
  );
}

async function withPageDiagnostics(page, action) {
  const diagnostics = [];
  const onResponse = (response) => {
    if (!failQueryErrors || response.status() < 400 || !isGrafanaDataRequest(response.url())) {
      return;
    }
    diagnostics.push(`HTTP ${response.status()} ${response.url()}`);
  };
  const onRequestFailed = (request) => {
    if (!failQueryErrors || !isGrafanaDataRequest(request.url())) {
      return;
    }
    const failure = request.failure();
    diagnostics.push(`request failed ${request.url()}: ${failure?.errorText || "unknown error"}`);
  };
  const onPageError = (error) => {
    if (!failPageErrors) {
      return;
    }
    diagnostics.push(`browser page error: ${error.message || error}`);
  };

  page.on("response", onResponse);
  page.on("requestfailed", onRequestFailed);
  page.on("pageerror", onPageError);
  try {
    const result = await action();
    return { result, diagnostics };
  } finally {
    page.off("response", onResponse);
    page.off("requestfailed", onRequestFailed);
    page.off("pageerror", onPageError);
  }
}

async function waitForDashboardSettled(page) {
  await page.waitForTimeout(waitMs);
  try {
    await page.waitForLoadState("networkidle", { timeout: 5000 });
  } catch {
    // Grafana keeps some long-polling/background requests open. The fixed wait
    // above is the primary settling mechanism; networkidle is best-effort.
  }
}

async function login(page) {
  await page.goto(`${baseUrl}/login`, { waitUntil: "domcontentloaded" });
  await page.fill('input[name="user"]', username);
  await page.fill('input[name="password"]', password);
  await page.click('button[type="submit"]');
  await page.waitForLoadState("domcontentloaded");
  await page.waitForTimeout(1000);
}

async function pageState(page) {
  return page.evaluate(() => {
    const bodyText = (document.body?.textContent || "").replace(/\s+/g, " ").trim();
    const numericMatches = bodyText.match(/[-+]?\d+(?:[.,]\d+)?\s*(?:kWh|MWh|Wh|kW|W|%|€|ct|km|A|kWh\/kWp)?/g) || [];
    return {
      text: bodyText,
      panelCount: document.querySelectorAll(".react-grid-item").length,
      canvasCount: document.querySelectorAll("canvas").length,
      svgCount: document.querySelectorAll("svg").length,
      tableRowCount: document.querySelectorAll("tbody tr, [role='row']").length,
      alertCount: document.querySelectorAll("[role='alert']").length,
      loadingCount: [...document.querySelectorAll("*")].filter((node) => (node.textContent || "").trim() === "Loading...").length,
      numericTextCount: numericMatches.length,
    };
  });
}

async function checkFullDashboard(page, dashboard) {
  const { diagnostics } = await withPageDiagnostics(page, async () => {
    await page.goto(dashboardUrl(dashboard), { waitUntil: "domcontentloaded" });
    await waitForDashboardSettled(page);
  });
  if (diagnostics.length > 0) {
    throw new Error(`dashboard data request error(s): ${diagnostics.slice(0, 3).join(" | ")}`);
  }
  const state = await pageState(page);
  const errorHits = findTextHits(state.text, renderedErrorTexts);
  if (errorHits.length > 0) {
    throw new Error(`rendered dashboard error(s): ${errorHits.join(", ")}`);
  }
  if (state.panelCount === 0) {
    throw new Error("rendered dashboard contains no panel grid items");
  }
  if (state.alertCount > 0) {
    throw new Error(`rendered dashboard contains ${state.alertCount} alert element(s)`);
  }
}

async function checkSoloPanel(page, dashboard, panel) {
  const { diagnostics } = await withPageDiagnostics(page, async () => {
    await page.goto(panelUrl(dashboard, panel.id), { waitUntil: "domcontentloaded" });
    await waitForDashboardSettled(page);
  });
  if (diagnostics.length > 0) {
    throw new Error(`panel ${panel.id} '${panel.title}' data request error(s): ${diagnostics.slice(0, 3).join(" | ")}`);
  }
  const state = await pageState(page);
  const errorHits = findTextHits(state.text, renderedErrorTexts);
  if (errorHits.length > 0) {
    throw new Error(`panel ${panel.id} '${panel.title}' rendered error(s): ${errorHits.join(", ")}`);
  }
  const emptyHits = findTextHits(state.text, emptyPanelTexts);
  if (failNoData && emptyHits.length > 0) {
    throw new Error(`panel ${panel.id} '${panel.title}' rendered empty state(s): ${emptyHits.join(", ")}`);
  }
  if (state.alertCount > 0) {
    throw new Error(`panel ${panel.id} '${panel.title}' contains ${state.alertCount} alert element(s)`);
  }
  if (state.loadingCount > 0) {
    throw new Error(`panel ${panel.id} '${panel.title}' still shows loading text after ${waitMs}ms`);
  }
  if (state.canvasCount + state.svgCount + state.tableRowCount === 0 && state.numericTextCount === 0) {
    throw new Error(
      `panel ${panel.id} '${panel.title}' rendered without visual/table/numeric content ` +
      `(canvas=${state.canvasCount}, svg=${state.svgCount}, rows=${state.tableRowCount}, numbers=${state.numericTextCount})`,
    );
  }
}

async function main() {
  const manifest = readJson(manifestPath);
  let failures = 0;
  let checkedPanels = 0;

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1728, height: 900 } });
  const page = await context.newPage();

  try {
    await login(page);

    for (const dashboard of manifest.dashboards || []) {
      const fileName = sourceFileName(dashboard);
      const criticalPanels = criticalPanelsByFile[fileName] || [];
      try {
        if (requireCriticalPanels && criticalPanels.length === 0) {
          throw new Error(`no critical panel rules configured for source file '${fileName}'`);
        }
        await checkFullDashboard(page, dashboard);
        for (const panel of criticalPanels) {
          await checkSoloPanel(page, dashboard, panel);
          checkedPanels += 1;
        }
        console.log(`OK ${dashboard.uid} | criticalPanels=${criticalPanels.length} | title=${dashboard.title}`);
      } catch (error) {
        failures += 1;
        console.error(`FAIL ${dashboard.uid} | ${error.message || error}`);
      }
    }
  } finally {
    await browser.close();
  }

  if (failures > 0) {
    console.error(`Render smoke check failed: ${failures} dashboard(s), criticalPanels=${checkedPanels}`);
    process.exit(1);
  }

  console.log(`Render smoke check passed: dashboards=${(manifest.dashboards || []).length}, criticalPanels=${checkedPanels}`);
}

main().catch((error) => {
  console.error(error.message || error);
  process.exit(1);
});
