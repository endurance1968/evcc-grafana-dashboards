/**
 * Script: dashboard-semantic-check.mjs
 * Purpose: Validate static dashboard semantics that basic JSON parsing cannot catch.
 * Version: 2026.04.24.1
 * Last modified: 2026-04-24
 */
import fs from "node:fs";
import path from "node:path";
import { manifestFilesUnion, readDeployManifest } from "../helper/deploy-manifest.mjs";
import {
  collectDashboardPanels,
  dashboardLayoutKind,
  dashboardLinks,
  dashboardTimeSettings,
  isV2Dashboard,
} from "../helper/dashboard-schema.mjs";

const repoRoot = process.cwd();
const sourceDir = path.join(repoRoot, "dashboards", "original", "en");
const forbiddenTexts = [
  "No numeric fields found",
  "Bar charts require a string or time field",
  "Panel plugin not found",
];

const expectedTimes = {
  "VM_EVCC_All-time.json": { from: "2024-12-31T23:00:00Z", to: "now" },
  "VM_EVCC_TAB_All-time.json": { from: "2024-12-31T23:00:00Z", to: "now" },
  "VM_EVCC_Jahr.json": { from: "now/y", to: "now/y" },
  "VM_EVCC_TAB_Jahr.json": { from: "now/y", to: "now/y" },
  "VM_EVCC_Monat.json": { from: "now/M", to: "now/M" },
  "VM_EVCC_TAB_Monat.json": { from: "now/M", to: "now/M" },
  "VM_EVCC_Today-Details.json": { from: "now/d", to: "now/d" },
  "VM_EVCC_TAB_Today-Details.json": { from: "now/d", to: "now/d" },
  "VM_EVCC_Today-Mobile.json": { from: "now/d", to: "now/d" },
  "VM_EVCC_Today.json": { from: "now/d", to: "now/d" },
};

const expectedLinks = {
  "VM_EVCC_All-time.json": [
    { title: "Year", from: "now%2Fy", to: "now" },
    { title: "Month", from: "now%2FM", to: "now" },
  ],
  "VM_EVCC_TAB_All-time.json": [
    { title: "Year", from: "now%2Fy", to: "now" },
    { title: "Month", from: "now%2FM", to: "now" },
  ],
  "VM_EVCC_Jahr.json": [
    { title: "Year", from: "now%2Fy", to: "now%2Fy" },
    { title: "Previous year", from: "now-1y%2Fy", to: "now-1y%2Fy" },
    { title: "2 years ago", from: "now-2y%2Fy", to: "now-2y%2Fy" },
  ],
  "VM_EVCC_TAB_Jahr.json": [
    { title: "Year", from: "now%2Fy", to: "now%2Fy" },
    { title: "Previous year", from: "now-1y%2Fy", to: "now-1y%2Fy" },
    { title: "2 years ago", from: "now-2y%2Fy", to: "now-2y%2Fy" },
  ],
  "VM_EVCC_Monat.json": [
    { title: "Month", from: "now%2FM", to: "now%2FM" },
    { title: "Previous month", from: "now-1M%2FM", to: "now-1M%2FM" },
    { title: "2 months ago", from: "now-2M%2FM", to: "now-2M%2FM" },
  ],
  "VM_EVCC_TAB_Monat.json": [
    { title: "Month", from: "now%2FM", to: "now%2FM" },
    { title: "Previous month", from: "now-1M%2FM", to: "now-1M%2FM" },
    { title: "2 months ago", from: "now-2M%2FM", to: "now-2M%2FM" },
  ],
  "VM_EVCC_Today-Details.json": [
    { title: "Today", from: "now%2Fd", to: "now%2Fd" },
    { title: "Yesterday", from: "now-1d%2Fd", to: "now-1d%2Fd" },
    { title: "Day before yesterday", from: "now-2d%2Fd", to: "now-2d%2Fd" },
  ],
  "VM_EVCC_TAB_Today-Details.json": [
    { title: "Today", from: "now%2Fd", to: "now%2Fd" },
    { title: "Yesterday", from: "now-1d%2Fd", to: "now-1d%2Fd" },
    { title: "Day before yesterday", from: "now-2d%2Fd", to: "now-2d%2Fd" },
  ],
  "VM_EVCC_Today-Mobile.json": [
    { title: "Today", from: "now%2Fd", to: "now%2Fd" },
    { title: "Yesterday", from: "now-1d%2Fd", to: "now-1d%2Fd" },
    { title: "Day before yesterday", from: "now-2d%2Fd", to: "now-2d%2Fd" },
  ],
  "VM_EVCC_Today.json": [
    { title: "Today", from: "now%2Fd", to: "now%2Fd" },
    { title: "Yesterday", from: "now-1d%2Fd", to: "now-1d%2Fd" },
    { title: "Day before yesterday", from: "now-2d%2Fd", to: "now-2d%2Fd" },
  ],
};

const criticalPanels = {
  "VM_EVCC_All-time.json": [
    { id: 12, title: "Energy totals", type: "bargauge", minTargets: 5 },
    { id: 24, title: "Metric gauges", type: "gauge", minTargets: 7 },
    { id: 28, title: "Monthly costs", type: "barchart", minTargets: 1 },
    { id: 38, title: "Days with highest yield", type: "table", minTargets: 1 },
  ],
  "VM_EVCC_TAB_All-time.json": [
    { id: 12, title: "Energy totals", type: "bargauge", minTargets: 5 },
    { id: 24, title: "Metric gauges", type: "gauge", minTargets: 7 },
    { id: 28, title: "Monthly costs", type: "barchart", minTargets: 1 },
    { id: 38, title: "Days with highest yield", type: "table", minTargets: 1 },
  ],
  "VM_EVCC_Jahr.json": [
    { id: 41, title: "Energy totals", type: "bargauge", minTargets: 5 },
    { id: 44, title: "Metric gauges", type: "gauge", minTargets: 7 },
    { id: 47, title: "Energy", type: "barchart", minTargets: 1, xField: "month" },
    { id: 66, title: "Home: Energy consumption", type: "barchart", minTargets: 1, xField: "month", monthLabels: true },
    { id: 70, title: "Home: Energy distribution", type: "barchart", minTargets: 1, xField: "month", batterySplit: true },
  ],
  "VM_EVCC_TAB_Jahr.json": [
    { id: 41, title: "Energy totals", type: "bargauge", minTargets: 5 },
    { id: 44, title: "Metric gauges", type: "gauge", minTargets: 7 },
    { id: 47, title: "Energy", type: "barchart", minTargets: 1, xField: "month" },
    { id: 66, title: "Home: Energy consumption", type: "barchart", minTargets: 1, xField: "month", monthLabels: true },
    { id: 70, title: "Home: Energy distribution", type: "barchart", minTargets: 1, xField: "month", batterySplit: true },
  ],
  "VM_EVCC_Monat.json": [
    { id: 19, title: "Monthly energy totals", type: "bargauge", minTargets: 10 },
    { id: 24, title: "Metric gauges", type: "gauge", minTargets: 12 },
    { id: 25, title: "Energy", type: "barchart", minTargets: 5, xField: "Time" },
    { id: 31, title: "Home: Energy consumption", type: "barchart", minTargets: 6, xField: "Time" },
    { id: 37, title: "Total: Energy distribution", type: "barchart", minTargets: 1, xField: "Time", batterySplit: true },
  ],
  "VM_EVCC_TAB_Monat.json": [
    { id: 19, title: "Monthly energy totals", type: "bargauge", minTargets: 10 },
    { id: 24, title: "Metric gauges", type: "gauge", minTargets: 12 },
    { id: 25, title: "Energy", type: "barchart", minTargets: 5, xField: "Time" },
    { id: 31, title: "Home: Energy consumption", type: "barchart", minTargets: 6, xField: "Time" },
    { id: 37, title: "Total: Energy distribution", type: "barchart", minTargets: 1, xField: "Time", batterySplit: true },
  ],
  "VM_EVCC_Today-Details.json": [
    { id: 2, title: "PV energy", type: "barchart", minTargets: 3, xField: "__panel_axis" },
    { id: 35, title: "Forecast", type: "barchart", minTargets: 3, xField: "__panel_axis" },
    { id: 11, title: "Charge currents/phase: $loadpoint", type: "stat", minTargets: 3 },
    { id: 15, title: "Phases: $loadpoint", type: "timeseries", minTargets: 1 },
  ],
  "VM_EVCC_TAB_Today-Details.json": [
    { id: 2, title: "PV energy", type: "barchart", minTargets: 3, xField: "__panel_axis" },
    { id: 35, title: "Forecast", type: "barchart", minTargets: 3, xField: "__panel_axis" },
    { id: 11, title: "Charge currents/phase: $loadpoint", type: "stat", minTargets: 3 },
    { id: 15, title: "Phases: $loadpoint", type: "timeseries", minTargets: 1 },
  ],
  "VM_EVCC_Today-Mobile.json": [
    { id: 74, title: "Power", type: "stat", minTargets: 5 },
  ],
  "VM_EVCC_Today.json": [
    { id: 74, title: "Power", type: "gauge", minTargets: 5 },
  ],
};

function isRenderablePanel(panel) {
  return Boolean(panel.type) && !["row", "library-panel"].includes(panel.type);
}

function targetExpr(target) {
  return String(target?.expr || target?.expression || target?.query || "");
}

function panelTargetCount(panel) {
  return Array.isArray(panel.targets) ? panel.targets.length : 0;
}

function hasInfluxShape(target) {
  return (
    target?.rawQuery === false ||
    Boolean(target?.policy) ||
    Boolean(target?.measurement) ||
    Boolean(target?.select) ||
    String(target?.group || "").toLowerCase().includes("influx")
  );
}

function findPanelByRule(panels, rule) {
  return panels.find((panel) => panel.id === rule.id && panel.title === rule.title && panel.type === rule.type);
}

function propertyValue(panel, matcherOption, propertyId) {
  for (const override of panel.fieldConfig?.overrides || []) {
    if (override?.matcher?.options !== matcherOption) {
      continue;
    }
    const prop = (override.properties || []).find((item) => item.id === propertyId);
    if (prop) {
      return prop.value;
    }
  }
  return undefined;
}

function hasMonthLabels(panel) {
  const mapping = propertyValue(panel, "month", "mappings");
  const mappings = Array.isArray(mapping) ? mapping : [];
  return mappings.some((item) => item?.type === "value" && item.options?.["1"]?.text === "01" && item.options?.["12"]?.text === "12");
}

function hasBatterySplit(panel) {
  const expr = (panel.targets || []).map(targetExpr).join("\n");
  const dischargeStacking = propertyValue(panel, "Battery discharge", "custom.stacking");
  const dischargeColor = propertyValue(panel, "Battery discharge", "color");
  const chargeColor = propertyValue(panel, "Battery charge", "color");

  return (
    expr.includes("Battery charge") &&
    expr.includes("Battery discharge") &&
    dischargeStacking?.group === "batteryNegative" &&
    dischargeStacking?.mode === "normal" &&
    dischargeColor?.mode === "fixed" &&
    chargeColor?.mode === "fixed"
  );
}

function hasDashedDarkGreenForecast(panel) {
  const color = propertyValue(panel, "Forecast", "color");
  const lineStyle = propertyValue(panel, "Forecast", "custom.lineStyle");
  const fillOpacity = propertyValue(panel, "Forecast", "custom.fillOpacity");
  const lineWidth = propertyValue(panel, "Forecast", "custom.lineWidth");

  return (
    color?.mode === "fixed" &&
    color?.fixedColor === "#2F8F5B" &&
    lineStyle?.fill === "dash" &&
    Array.isArray(lineStyle?.dash) &&
    lineStyle.dash[0] === 8 &&
    lineStyle.dash[1] === 6 &&
    fillOpacity === 0 &&
    lineWidth === 2
  );
}

function assert(condition, failures, message) {
  if (!condition) {
    failures.push(message);
  }
}

function validateDeployManifest(manifest) {
  const failures = [];
  const files = manifest?.files;
  assert(Array.isArray(files) && files.length > 0, failures, "deploy manifest: missing non-empty files array");
  assert(!Object.hasOwn(manifest || {}, "sets"), failures, "deploy manifest: dashboard sets must not be configured");
  assert(!Object.hasOwn(manifest || {}, "defaultSet"), failures, "deploy manifest: defaultSet must not be configured");

  const seen = new Set();
  for (const file of files || []) {
    const fileName = String(file);
    assert(fileName.endsWith(".json"), failures, `deploy manifest: '${fileName}' is not a JSON dashboard`);
    assert(!fileName.includes("\\") && !fileName.includes("/"), failures, `deploy manifest: '${fileName}' must be a file name only`);
    assert(!seen.has(fileName), failures, `deploy manifest: duplicate '${fileName}'`);
    seen.add(fileName);
  }

  const deployFiles = new Set(files || []);
  assert(deployFiles.has("VM_EVCC_TAB_All-time.json"), failures, "deploy manifest: must include TAB All-time dashboard");
  assert(deployFiles.has("VM_EVCC_TAB_Jahr.json"), failures, "deploy manifest: must include TAB Year dashboard");
  assert(deployFiles.has("VM_EVCC_TAB_Monat.json"), failures, "deploy manifest: must include TAB Month dashboard");
  assert(deployFiles.has("VM_EVCC_TAB_Today-Details.json"), failures, "deploy manifest: must include TAB Today Details dashboard");
  assert(deployFiles.has("VM_EVCC_Today.json"), failures, "deploy manifest: must keep the normal Today dashboard");
  assert(deployFiles.has("VM_EVCC_Today-Mobile.json"), failures, "deploy manifest: must keep the normal Today Mobile dashboard");

  return failures;
}

function validateDashboard(fileName, dashboard) {
  const failures = [];
  const rawJson = JSON.stringify(dashboard);
  const panels = collectDashboardPanels(dashboard);

  for (const text of forbiddenTexts) {
    assert(!rawJson.includes(text), failures, `${fileName}: forbidden Grafana error text is present: ${text}`);
  }

  const expectedTime = expectedTimes[fileName];
  const timeSettings = dashboardTimeSettings(dashboard);
  assert(Boolean(expectedTime), failures, `${fileName}: no expected time contract configured`);
  if (expectedTime) {
    assert(timeSettings?.from === expectedTime.from, failures, `${fileName}: expected time.from=${expectedTime.from}, got ${timeSettings?.from}`);
    assert(timeSettings?.to === expectedTime.to, failures, `${fileName}: expected time.to=${expectedTime.to}, got ${timeSettings?.to}`);
  }

  if (["VM_EVCC_TAB_All-time.json", "VM_EVCC_TAB_Monat.json", "VM_EVCC_TAB_Jahr.json", "VM_EVCC_TAB_Today-Details.json"].includes(fileName)) {
    assert(isV2Dashboard(dashboard), failures, `${fileName}: expected a Grafana v2 dashboard resource`);
    assert(dashboardLayoutKind(dashboard) === "TabsLayout", failures, `${fileName}: expected layout.kind=TabsLayout, got ${dashboardLayoutKind(dashboard)}`);
  }

  if (fileName === "VM_EVCC_TAB_Today-Details.json") {
    const loadpointTab = dashboard.spec?.layout?.spec?.tabs?.find((tab) => tab.spec?.title === "Loadpoints");
    const loadpointRows = loadpointTab?.spec?.layout?.spec?.rows || [];
    assert(loadpointTab?.spec?.layout?.kind === "RowsLayout", failures, `${fileName}: loadpoint tab must use RowsLayout so panels repeat as a group`);
    assert(loadpointRows.length === 1, failures, `${fileName}: loadpoint tab must contain exactly one repeated row`);
    const loadpointRow = loadpointRows[0];
    const repeat = loadpointRow?.spec?.repeat;
    assert(repeat?.mode === "variable" && repeat?.value === "loadpoint", failures, `${fileName}: loadpoint row must repeat by loadpoint`);
    const loadpointItems = loadpointRow?.spec?.layout?.spec?.items || [];
    assert(loadpointItems.length === 4, failures, `${fileName}: repeated loadpoint row must contain the four loadpoint panels`);
    for (const item of loadpointItems) {
      assert(!item.spec?.repeat, failures, `${fileName}: loadpoint panel item ${item.spec?.element?.name || "?"} must not repeat independently`);
    }

    const pvPowerPanel = dashboard.spec?.elements?.["panel-27"]?.spec;
    const pvPowerQueries = pvPowerPanel?.data?.spec?.queries || [];
    const pvPowerRefs = pvPowerQueries.map((query) => query.spec?.refId);
    assert(pvPowerRefs.includes("pvPowerPerString"), failures, `${fileName}: PV power panel must include per-string PV target`);
    assert(!pvPowerRefs.includes("pvPowerTotal"), failures, `${fileName}: PV power panel must not include separate Total target when strings are stacked`);
    const pvStacking = pvPowerPanel?.vizConfig?.spec?.fieldConfig?.defaults?.custom?.stacking;
    assert(pvStacking?.mode === "normal", failures, `${fileName}: PV power panel must stack PV strings additively`);

    const forecastPanel = panels.find((panel) => panel.id === 16 && panel.title === "Forecast" && panel.type === "timeseries");
    assert(Boolean(forecastPanel), failures, `${fileName}: missing PV tab timeseries Forecast panel`);
    if (forecastPanel) {
      assert(hasDashedDarkGreenForecast(forecastPanel), failures, `${fileName}: PV tab Forecast series must be dark green, dashed, and unfilled`);
    }
  }

  if (["VM_EVCC_Today.json", "VM_EVCC_Today-Mobile.json"].includes(fileName)) {
    const powerHistoryTargets = dashboard.__elements?.afc1nq1oy29s0a?.model?.targets || [];
    assert(powerHistoryTargets.some((target) => target.refId === "pvForecast" && String(target.expr || "").includes("tariffSolar_value")), failures, `${fileName}: embedded Power history library panel must include PV forecast target`);
    const powerHistoryOverrides = dashboard.__elements?.afc1nq1oy29s0a?.model?.fieldConfig?.overrides || [];
    const forecastOverride = powerHistoryOverrides.find((override) => override?.matcher?.id === "byName" && override?.matcher?.options === "PV forecast");
    const forecastProperties = new Map((forecastOverride?.properties || []).map((property) => [property.id, property.value]));
    assert(forecastProperties.get("color")?.mode === "fixed" && forecastProperties.get("color")?.fixedColor === "#2F8F5B", failures, `${fileName}: PV forecast must be fixed dark green`);
    assert(forecastProperties.get("custom.lineStyle")?.fill === "dash", failures, `${fileName}: PV forecast must be dashed`);
    assert(forecastProperties.get("custom.fillOpacity") === 0, failures, `${fileName}: PV forecast must not use area fill`);
  }

  for (const expected of expectedLinks[fileName] || []) {
    const link = dashboardLinks(dashboard).find((item) => item.title === expected.title);
    assert(Boolean(link), failures, `${fileName}: missing link '${expected.title}'`);
    if (!link) {
      continue;
    }
    assert(link.url.includes(`from=${expected.from}`), failures, `${fileName}: link '${expected.title}' has wrong from range: ${link.url}`);
    assert(link.url.includes(`to=${expected.to}`), failures, `${fileName}: link '${expected.title}' has wrong to range: ${link.url}`);
  }

  for (const panel of panels) {
    if (panel.libraryPanel) {
      continue;
    }
    if (isRenderablePanel(panel)) {
      assert(panelTargetCount(panel) > 0, failures, `${fileName}: renderable panel '${panel.title || panel.id}' has no targets`);
    }
    for (const target of panel.targets || []) {
      assert(!hasInfluxShape(target), failures, `${fileName}: panel '${panel.title || panel.id}' contains an Influx-style target`);
    }
    if (panel.type === "barchart") {
      assert(Boolean(panel.options?.xField), failures, `${fileName}: barchart '${panel.title || panel.id}' has no xField`);
    }
  }

  for (const rule of criticalPanels[fileName] || []) {
    const panel = findPanelByRule(panels, rule);
    assert(Boolean(panel), failures, `${fileName}: missing critical panel ${rule.id} '${rule.title}' (${rule.type})`);
    if (!panel) {
      continue;
    }
    assert(panelTargetCount(panel) >= rule.minTargets, failures, `${fileName}: critical panel '${rule.title}' has ${panelTargetCount(panel)} target(s), expected >= ${rule.minTargets}`);
    if (rule.xField) {
      assert(panel.options?.xField === rule.xField, failures, `${fileName}: critical panel '${rule.title}' expected xField=${rule.xField}, got ${panel.options?.xField}`);
    }
    if (rule.monthLabels) {
      assert(hasMonthLabels(panel), failures, `${fileName}: critical panel '${rule.title}' is missing 01..12 month value mappings`);
    }
    if (rule.batterySplit) {
      assert(hasBatterySplit(panel), failures, `${fileName}: critical panel '${rule.title}' is missing battery charge/discharge split or negative stack group`);
    }
  }

  return failures;
}

function main() {
  const manifest = readDeployManifest(repoRoot);
  const files = manifestFilesUnion(manifest).sort((a, b) => a.localeCompare(b));
  const allFailures = validateDeployManifest(manifest);
  let panelCount = 0;
  let targetCount = 0;

  for (const fileName of files) {
    const dashboardPath = path.join(sourceDir, fileName);
    if (!fs.existsSync(dashboardPath)) {
      allFailures.push(`${fileName}: dashboard file is missing from dashboards/original/en`);
      continue;
    }
    const dashboard = JSON.parse(fs.readFileSync(dashboardPath, "utf8"));
    const panels = collectDashboardPanels(dashboard);
    panelCount += panels.length;
    targetCount += panels.reduce((sum, panel) => sum + panelTargetCount(panel), 0);
    allFailures.push(...validateDashboard(fileName, dashboard));
  }

  console.log(`Dashboard semantic check: files=${files.length}, panels=${panelCount}, targets=${targetCount}`);
  if (allFailures.length > 0) {
    for (const failure of allFailures) {
      console.error(`- ${failure}`);
    }
    throw new Error(`Dashboard semantic check failed with ${allFailures.length} issue(s).`);
  }
}

try {
  main();
} catch (error) {
  console.error(error.message || error);
  process.exit(1);
}
