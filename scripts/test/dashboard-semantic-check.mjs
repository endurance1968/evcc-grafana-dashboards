/**
 * Script: dashboard-semantic-check.mjs
 * Purpose: Validate static dashboard semantics that basic JSON parsing cannot catch.
 * Version: 2026.04.14.1
 * Last modified: 2026-04-14
 */
import fs from "node:fs";
import path from "node:path";

const repoRoot = process.cwd();
const sourceDir = path.join(repoRoot, "dashboards", "original", "en");
const forbiddenTexts = [
  "No numeric fields found",
  "Bar charts require a string or time field",
  "Panel plugin not found",
];

const expectedTimes = {
  "VM_ EVCC_ All-time.json": { from: "2024-12-31T23:00:00Z", to: "now" },
  "VM_ EVCC_ Jahr.json": { from: "now/y", to: "now/y" },
  "VM_ EVCC_ Monat.json": { from: "now/M", to: "now/M" },
  "VM_ EVCC_ Today - Details.json": { from: "now/d", to: "now/d" },
  "VM_ EVCC_ Today - Mobile.json": { from: "now/d", to: "now/d" },
  "VM_ EVCC_ Today.json": { from: "now/d", to: "now/d" },
};

const expectedLinks = {
  "VM_ EVCC_ All-time.json": [
    { title: "Year", from: "now%2Fy", to: "now" },
    { title: "Month", from: "now%2FM", to: "now" },
  ],
  "VM_ EVCC_ Jahr.json": [
    { title: "Year", from: "now%2Fy", to: "now%2Fy" },
    { title: "Previous year", from: "now-1y%2Fy", to: "now-1y%2Fy" },
    { title: "2 years ago", from: "now-2y%2Fy", to: "now-2y%2Fy" },
  ],
  "VM_ EVCC_ Monat.json": [
    { title: "Month", from: "now%2FM", to: "now%2FM" },
    { title: "Previous month", from: "now-1M%2FM", to: "now-1M%2FM" },
    { title: "2 months ago", from: "now-2M%2FM", to: "now-2M%2FM" },
  ],
  "VM_ EVCC_ Today - Details.json": [
    { title: "Today", from: "now%2Fd", to: "now%2Fd" },
    { title: "Yesterday", from: "now-1d%2Fd", to: "now-1d%2Fd" },
    { title: "Day before yesterday", from: "now-2d%2Fd", to: "now-2d%2Fd" },
  ],
  "VM_ EVCC_ Today - Mobile.json": [
    { title: "Today", from: "now%2Fd", to: "now%2Fd" },
    { title: "Yesterday", from: "now-1d%2Fd", to: "now-1d%2Fd" },
    { title: "Day before yesterday", from: "now-2d%2Fd", to: "now-2d%2Fd" },
  ],
  "VM_ EVCC_ Today.json": [
    { title: "Today", from: "now%2Fd", to: "now%2Fd" },
    { title: "Yesterday", from: "now-1d%2Fd", to: "now-1d%2Fd" },
    { title: "Day before yesterday", from: "now-2d%2Fd", to: "now-2d%2Fd" },
  ],
};

const criticalPanels = {
  "VM_ EVCC_ All-time.json": [
    { id: 12, title: "Energy totals", type: "bargauge", minTargets: 5 },
    { id: 24, title: "Metric gauges", type: "gauge", minTargets: 7 },
    { id: 28, title: "Monthly costs", type: "barchart", minTargets: 2 },
    { id: 38, title: "Days with highest yield", type: "table", minTargets: 1 },
  ],
  "VM_ EVCC_ Jahr.json": [
    { id: 41, title: "Energy totals", type: "bargauge", minTargets: 5 },
    { id: 44, title: "Metric gauges", type: "gauge", minTargets: 7 },
    { id: 47, title: "Energy", type: "barchart", minTargets: 1, xField: "month" },
    { id: 66, title: "Home: Energy consumption", type: "barchart", minTargets: 1, xField: "month", monthLabels: true },
    { id: 70, title: "Home: Energy distribution", type: "barchart", minTargets: 1, xField: "month", batterySplit: true },
  ],
  "VM_ EVCC_ Monat.json": [
    { id: 19, title: "Monthly energy totals", type: "bargauge", minTargets: 10 },
    { id: 24, title: "Metric gauges", type: "gauge", minTargets: 12 },
    { id: 25, title: "Energy", type: "barchart", minTargets: 5, xField: "Time" },
    { id: 31, title: "Home: Energy consumption", type: "barchart", minTargets: 6, xField: "Time" },
    { id: 37, title: "Total: Energy distribution", type: "barchart", minTargets: 1, xField: "Time", batterySplit: true },
  ],
  "VM_ EVCC_ Today - Details.json": [
    { id: 2, title: "PV energy", type: "barchart", minTargets: 3, xField: "__panel_axis" },
    { id: 35, title: "Forecast", type: "barchart", minTargets: 3, xField: "__panel_axis" },
    { id: 11, title: "Charge currents/phase: $loadpoint", type: "stat", minTargets: 3 },
    { id: 15, title: "Phases: $loadpoint", type: "timeseries", minTargets: 1 },
  ],
  "VM_ EVCC_ Today - Mobile.json": [
    { id: 74, title: "Power", type: "stat", minTargets: 5 },
  ],
  "VM_ EVCC_ Today.json": [
    { id: 74, title: "Power", type: "gauge", minTargets: 5 },
  ],
};

function collectPanels(dashboard) {
  const out = [];
  function add(panels) {
    for (const panel of panels || []) {
      out.push(panel);
      if (Array.isArray(panel.panels)) {
        add(panel.panels);
      }
    }
  }
  add(dashboard.panels);
  return out;
}

function isRenderablePanel(panel) {
  return Boolean(panel.type) && !["row"].includes(panel.type);
}

function targetExpr(target) {
  return String(target?.expr || target?.expression || target?.query || "");
}

function panelTargetCount(panel) {
  return Array.isArray(panel.targets) ? panel.targets.length : 0;
}

function hasInfluxShape(target) {
  return target.rawQuery === false || Boolean(target.policy) || Boolean(target.measurement) || Boolean(target.select);
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

function assert(condition, failures, message) {
  if (!condition) {
    failures.push(message);
  }
}

function validateDashboard(fileName, dashboard) {
  const failures = [];
  const rawJson = JSON.stringify(dashboard);
  const panels = collectPanels(dashboard);

  for (const text of forbiddenTexts) {
    assert(!rawJson.includes(text), failures, `${fileName}: forbidden Grafana error text is present: ${text}`);
  }

  const expectedTime = expectedTimes[fileName];
  assert(Boolean(expectedTime), failures, `${fileName}: no expected time contract configured`);
  if (expectedTime) {
    assert(dashboard.time?.from === expectedTime.from, failures, `${fileName}: expected time.from=${expectedTime.from}, got ${dashboard.time?.from}`);
    assert(dashboard.time?.to === expectedTime.to, failures, `${fileName}: expected time.to=${expectedTime.to}, got ${dashboard.time?.to}`);
  }

  for (const expected of expectedLinks[fileName] || []) {
    const link = (dashboard.links || []).find((item) => item.title === expected.title);
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
  const files = fs.readdirSync(sourceDir).filter((file) => file.endsWith(".json")).sort((a, b) => a.localeCompare(b));
  const allFailures = [];
  let panelCount = 0;
  let targetCount = 0;

  for (const fileName of files) {
    const dashboard = JSON.parse(fs.readFileSync(path.join(sourceDir, fileName), "utf8"));
    const panels = collectPanels(dashboard);
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
