/**
 * Script: dashboard-semantic-check.mjs
 * Purpose: Validate static dashboard semantics that basic JSON parsing cannot catch.
 * Version: 2026.06.10.2
 * Last modified: 2026-06-10
 */
import fs from "node:fs";
import path from "node:path";
import { manifestFilesUnion, readDeployManifest } from "../helper/deploy-manifest.mjs";
import {
  collectDashboardPanels,
  dashboardLayoutKind,
  dashboardLinks,
  dashboardTimeSettings,
  dashboardVariables,
  isV2Dashboard,
} from "../helper/dashboard-schema.mjs";
import { dashboardColors } from "../helper/dashboard-colors.mjs";

const repoRoot = process.cwd();
const sourceDir = path.join(repoRoot, "dashboards", "original", "en");
const forbiddenTexts = [
  "No numeric fields found",
  "Bar charts require a string or time field",
  "Panel plugin not found",
];
const forbiddenRuntimeDefaults = [
  "Solarman",
  "globalhome.solarmanpv.com",
];
const forbiddenUserSpecificMatchers = new Set([
  "Garage",
  "Stellplatz",
  "Gast: Garage",
  "Gast: Stellplatz",
  "Heizlüfter",
  "Tesla",
  "Ioniq 5",
]);

const expectedTimes = {
  "VM_EVCC_All-time.json": {
    "from": "2024-12-31T23:00:00Z",
    "to": "now"
  },
  "VM_EVCC_Year.json": {
    "from": "now/y",
    "to": "now/y"
  },
  "VM_EVCC_Month.json": {
    "from": "now/M",
    "to": "now/M"
  },
  "VM_EVCC_Today-Details.json": {
    "from": "now/d",
    "to": "now/d"
  },
  "VM_EVCC_Today-Mobile.json": {
    "from": "now/d",
    "to": "now/d"
  },
  "VM_EVCC_Today.json": {
    "from": "now/d",
    "to": "now/d"
  }
};

const expectedLinks = {
  "VM_EVCC_All-time.json": [
    {
      "title": "Year",
      "from": "now%2Fy",
      "to": "now"
    },
    {
      "title": "Month",
      "from": "now%2FM",
      "to": "now"
    }
  ],
  "VM_EVCC_Year.json": [
    {
      "title": "Year",
      "from": "now%2Fy",
      "to": "now%2Fy"
    },
    {
      "title": "Previous year",
      "from": "now-1y%2Fy",
      "to": "now-1y%2Fy"
    },
    {
      "title": "2 years ago",
      "from": "now-2y%2Fy",
      "to": "now-2y%2Fy"
    }
  ],
  "VM_EVCC_Month.json": [
    {
      "title": "Month",
      "from": "now%2FM",
      "to": "now%2FM"
    },
    {
      "title": "Previous month",
      "from": "now-1M%2FM",
      "to": "now-1M%2FM"
    },
    {
      "title": "2 months ago",
      "from": "now-2M%2FM",
      "to": "now-2M%2FM"
    }
  ],
  "VM_EVCC_Today-Details.json": [
    {
      "title": "Today",
      "from": "now%2Fd",
      "to": "now%2Fd"
    },
    {
      "title": "Yesterday",
      "from": "now-1d%2Fd",
      "to": "now-1d%2Fd"
    },
    {
      "title": "Day before yesterday",
      "from": "now-2d%2Fd",
      "to": "now-2d%2Fd"
    }
  ],
  "VM_EVCC_Today-Mobile.json": [
    {
      "title": "Today",
      "from": "now%2Fd",
      "to": "now%2Fd"
    },
    {
      "title": "Yesterday",
      "from": "now-1d%2Fd",
      "to": "now-1d%2Fd"
    },
    {
      "title": "Day before yesterday",
      "from": "now-2d%2Fd",
      "to": "now-2d%2Fd"
    }
  ],
  "VM_EVCC_Today.json": [
    {
      "title": "Today",
      "from": "now%2Fd",
      "to": "now%2Fd"
    },
    {
      "title": "Yesterday",
      "from": "now-1d%2Fd",
      "to": "now-1d%2Fd"
    },
    {
      "title": "Day before yesterday",
      "from": "now-2d%2Fd",
      "to": "now-2d%2Fd"
    }
  ]
};

const criticalPanels = {
  "VM_EVCC_All-time.json": [
    {
      "id": 12,
      "title": "Energy totals",
      "type": "bargauge",
      "minTargets": 5
    },
    {
      "id": 24,
      "title": "Metric gauges",
      "type": "gauge",
      "minTargets": 2
    },
    {
      "id": 28,
      "title": "Monthly costs",
      "type": "barchart",
      "minTargets": 1
    },
    {
      "id": 38,
      "title": "Days with highest yield",
      "type": "table",
      "minTargets": 1
    },
    {
      "id": 58,
      "title": "PV energy/year by source",
      "type": "barchart",
      "minTargets": 1,
      "xField": "source",
      "exprIncludes": "evcc_pv_energy_by_title_yearly_wh"
    },
    {
      "id": 59,
      "title": "PV specific yield/year by source",
      "type": "barchart",
      "minTargets": 1,
      "xField": "source",
      "exprIncludes": "evcc_pv_specific_yield_yearly_kwh_per_kwp"
    }
  ],
  "VM_EVCC_Year.json": [
    {
      "id": 41,
      "title": "Energy totals",
      "type": "bargauge",
      "minTargets": 5
    },
    {
      "id": 44,
      "title": "Metric gauges",
      "type": "gauge",
      "minTargets": 2
    },
    {
      "id": 47,
      "title": "Energy",
      "type": "barchart",
      "minTargets": 1,
      "xField": "month"
    },
    {
      "id": 66,
      "title": "Home: Energy consumption",
      "type": "barchart",
      "minTargets": 1,
      "xField": "month",
      "monthLabels": true
    },
    {
      "id": 70,
      "title": "Home: Energy distribution",
      "type": "barchart",
      "minTargets": 1,
      "xField": "month",
      "batterySplit": true
    },
    {
      "id": 77,
      "title": "PV generation costs",
      "type": "bargauge",
      "minTargets": 1,
      "exprIncludes": "evcc_pv_lcoe_yearly_ct_per_kwh"
    },
    {
      "id": 78,
      "title": "PV generation cost/week (ct/kWh)",
      "type": "timeseries",
      "minTargets": 1,
      "exprIncludes": "evcc_pv_lcoe_rolling_7d_ct_per_kwh"
    },
    {
      "id": 79,
      "title": "PV specific yield (kWh/kWp)",
      "type": "bargauge",
      "minTargets": 1,
      "exprIncludes": "evcc_pv_specific_yield_yearly_with_coverage_kwh_per_kwp"
    },
    {
      "id": 80,
      "title": "PV specific yield/week (kWh/kWp)",
      "type": "timeseries",
      "minTargets": 1,
      "exprIncludes": "evcc_pv_specific_yield_rolling_7d_kwh_per_kwp"
    }

  ],
  "VM_EVCC_Month.json": [
    {
      "id": 19,
      "title": "Monthly energy totals",
      "type": "bargauge",
      "minTargets": 10
    },
    {
      "id": 24,
      "title": "Metric gauges",
      "type": "gauge",
      "minTargets": 2
    },
    {
      "id": 25,
      "title": "Energy",
      "type": "barchart",
      "minTargets": 5,
      "xField": "Time"
    },
    {
      "id": 31,
      "title": "Home: Energy consumption",
      "type": "barchart",
      "minTargets": 6,
      "xField": "Time"
    },
    {
      "id": 37,
      "title": "Total: Energy distribution",
      "type": "barchart",
      "minTargets": 1,
      "xField": "Time",
      "batterySplit": true
    }
  ],
  "VM_EVCC_Today-Details.json": [
    {
      "id": 2,
      "title": "PV energy",
      "type": "barchart",
      "minTargets": 2,
      "xField": "__panel_axis"
    },
    {
      "id": 35,
      "title": "Forecast",
      "type": "barchart",
      "minTargets": 3,
      "xField": "__panel_axis"
    },
    {
      "id": 11,
      "title": "Charge currents/phase: $loadpoint",
      "type": "stat",
      "minTargets": 3
    },
    {
      "id": 15,
      "title": "Phases: $loadpoint",
      "type": "timeseries",
      "minTargets": 1
    }
  ],
  "VM_EVCC_Today-Mobile.json": [
    {
      "id": 74,
      "title": "Power",
      "type": "stat",
      "minTargets": 5
    }
  ],
  "VM_EVCC_Today.json": [
    {
      "id": 74,
      "title": "Power",
      "type": "gauge",
      "minTargets": 5
    }
  ]
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
function dashboardGridPositionsById(dashboard) {
  const out = new Map();
  if (isV2Dashboard(dashboard)) {
    const collectItems = (layout) => {
      if (!layout || typeof layout !== "object") return;
      if (layout.kind === "GridLayout") {
        for (const item of layout.spec?.items || []) {
          const spec = item?.spec || {};
          const name = spec.element?.name || "";
          const match = /^panel-(\d+)$/.exec(name);
          if (match) {
            out.set(Number(match[1]), {
              x: spec.x || 0,
              y: spec.y || 0,
              w: spec.width || 0,
              h: spec.height || 0,
            });
          }
        }
        return;
      }
      if (layout.kind === "TabsLayout") {
        for (const tab of layout.spec?.tabs || []) collectItems(tab?.spec?.layout);
        return;
      }
      if (layout.kind === "RowsLayout") {
        for (const row of layout.spec?.rows || []) collectItems(row?.spec?.layout);
      }
    };
    collectItems(dashboard.spec?.layout);
    return out;
  }

  for (const panel of dashboard.panels || []) {
    if (panel?.id && panel.gridPos) out.set(panel.id, panel.gridPos);
  }
  return out;
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



function assertFixedColor(fileName, panel, matcherOption, expectedColor, failures) {
  const color = propertyValue(panel, matcherOption, "color");
  if (!color) {
    return;
  }
  if (color.mode === "thresholds" && propertyValue(panel, matcherOption, "thresholds")) {
    return;
  }
  assert(color.mode === "fixed" && color.fixedColor === expectedColor, failures, `${fileName}: panel '${panel.title || panel.id}' matcher '${matcherOption}' must use semantic color ${expectedColor}`);
}

function assertThresholdContains(fileName, panel, matcherOption, expectedColors, failures) {
  const steps = propertyValue(panel, matcherOption, "thresholds")?.steps || [];
  if (steps.length === 0) {
    return;
  }
  for (const color of expectedColors) {
    assert(steps.some((step) => step.color === color), failures, `${fileName}: panel '${panel.title || panel.id}' matcher '${matcherOption}' thresholds must include semantic color ${color}`);
  }
}

function validateSemanticColors(fileName, panel, failures) {
  const expectedFixedColors = new Map([
    ["PV", dashboardColors.pv],
    ["PV/day", dashboardColors.pv],
    ["PV forecast", dashboardColors.pvForecast],
    ["Forecast", dashboardColors.pvForecast],
    ["Grid", dashboardColors.grid],
    ["Grid import", dashboardColors.gridImport],
    ["Grid import/day", dashboardColors.gridImport],
    ["Feed-in", dashboardColors.feedIn],
    ["Home", dashboardColors.home],
    ["Battery", dashboardColors.storage],
    ["Battery charge", dashboardColors.storageCharge],
    ["Battery discharge", dashboardColors.storageDischarge],
    ["batteryChargeTotal", dashboardColors.storageCharge],
    ["batteryDischargeTotal", dashboardColors.storageDischarge],
    ["batteryEfficiency", dashboardColors.storage],
    ["chargedEnergy", dashboardColors.storageCharge],
    ["dischargedEnergy", dashboardColors.storageDischarge],
    ["minSoc", dashboardColors.storageSocDark],
    ["maxSoc", dashboardColors.storageSocDark],
    ["Autarky", dashboardColors.autarky],
    ["Self-consumption", dashboardColors.selfConsumption],
    ["Battery SOC", dashboardColors.storageSocDark],
    ["Purchased", dashboardColors.purchase],
    ["Sold", dashboardColors.sold],
  ]);

  for (const [matcherOption, color] of expectedFixedColors) {
    assertFixedColor(fileName, panel, matcherOption, color, failures);
  }

  assertThresholdContains(fileName, panel, "PV", [dashboardColors.pvLow, dashboardColors.pv, dashboardColors.pvDark], failures);
  assertThresholdContains(fileName, panel, "gridPower", [dashboardColors.gridFeedLow, dashboardColors.gridImport, dashboardColors.gridImportHigh, dashboardColors.gridImportDanger], failures);
  assertThresholdContains(fileName, panel, "batteryPower", [dashboardColors.storageChargeLow, dashboardColors.storageCharge, dashboardColors.storageDischarge, dashboardColors.storageDark, dashboardColors.storageDanger], failures);
  assertThresholdContains(fileName, panel, "homePower", [dashboardColors.homeLight, dashboardColors.home, dashboardColors.homeHigh, dashboardColors.homeDanger], failures);
  assertThresholdContains(fileName, panel, "Autarky", [dashboardColors.autarkyLow, dashboardColors.autarkyMid, dashboardColors.autarky, dashboardColors.autarkyDark], failures);
  assertThresholdContains(fileName, panel, "Self-consumption", [dashboardColors.selfConsumptionLow, dashboardColors.selfConsumptionMid, dashboardColors.selfConsumption, dashboardColors.selfConsumptionDark], failures);
  assertThresholdContains(fileName, panel, "Battery SOC", [dashboardColors.storageSocLow, dashboardColors.storageSocMid, dashboardColors.storageSoc, dashboardColors.storageSocDark], failures);
  assertThresholdContains(fileName, panel, "minSoc", [dashboardColors.storageSocLow, dashboardColors.storageSocMid, dashboardColors.storageSoc, dashboardColors.storageSocDark], failures);
  assertThresholdContains(fileName, panel, "maxSoc", [dashboardColors.storageSocLow, dashboardColors.storageSocMid, dashboardColors.storageSoc, dashboardColors.storageSocDark], failures);

  if (panel.id === 74 && panel.title === "Power") {
    assert(panel.fieldConfig?.defaults?.color?.mode === "thresholds", failures, `${fileName}: Power gauge defaults must use threshold color mode`);
    const defaultThresholds = panel.fieldConfig?.defaults?.thresholds?.steps || [];
    assert(defaultThresholds.some((step) => step.color === dashboardColors.loadpointLight), failures, `${fileName}: Power gauge dynamic loadpoints must use light-loadpoint orange threshold color`);
    assert(defaultThresholds.some((step) => step.color === dashboardColors.loadpoint), failures, `${fileName}: Power gauge dynamic loadpoints must use loadpoint orange threshold color`);
    assert(defaultThresholds.some((step) => step.color === dashboardColors.loadpointHigh), failures, `${fileName}: Power gauge dynamic loadpoints must use high-loadpoint orange threshold color`);
    assert(defaultThresholds.some((step) => step.color === dashboardColors.loadpointDanger), failures, `${fileName}: Power gauge dynamic loadpoints must use danger-loadpoint orange threshold color`);
  }
}function hasMonthLabels(panel) {
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
    color?.fixedColor === dashboardColors.pvForecast &&
    lineStyle?.fill === "dash" &&
    Array.isArray(lineStyle?.dash) &&
    lineStyle.dash[0] === 8 &&
    lineStyle.dash[1] === 6 &&
    fillOpacity === 0 &&
    lineWidth === 2
  );
}
function panelDescription(panel) {
  return String(panel?.description || panel?.rawElement?.spec?.description || "");
}

function hasEvccForecastDescription(panel) {
  const description = panelDescription(panel);
  return (
    description.includes("EVCC") &&
    description.includes("tariffSolar_value") &&
    description.includes("does not fetch") &&
    description.includes("Forecast.Solar") &&
    description.includes("Solcast") &&
    description.includes("Open-Meteo")
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
  assert(deployFiles.has("VM_EVCC_All-time.json"), failures, "deploy manifest: must include All-time dashboard");
  assert(deployFiles.has("VM_EVCC_Year.json"), failures, "deploy manifest: must include Year dashboard");
  assert(deployFiles.has("VM_EVCC_Month.json"), failures, "deploy manifest: must include Month dashboard");
  assert(deployFiles.has("VM_EVCC_Today-Details.json"), failures, "deploy manifest: must include Today Details dashboard");
  assert(deployFiles.has("VM_EVCC_Today.json"), failures, "deploy manifest: must include the Today dashboard");
  assert(!deployFiles.has("VM_EVCC_Today-Gauges.json"), failures, "deploy manifest: Today Gauges must be folded into Today, not deployed separately");
  assert(deployFiles.has("VM_EVCC_Today-Mobile.json"), failures, "deploy manifest: must keep the normal Today Mobile dashboard");

  return failures;
}

function grafanaTabSlug(title) {
  return String(title || "")
    .normalize("NFKD")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function validateGrafanaTabSlugs(fileName, layout, failures, pathLabel = "layout") {
  if (!layout || typeof layout !== "object") {
    return;
  }

  if (layout.kind === "TabsLayout") {
    const tabs = layout.spec?.tabs || [];
    const seen = new Map();
    tabs.forEach((tab, index) => {
      const title = tab?.spec?.title || "";
      const slug = grafanaTabSlug(title);
      const tabLabel = `${pathLabel}.tabs[${index}] '${title}'`;
      assert(Boolean(slug), failures, `${fileName}: ${tabLabel} produces an empty Grafana URL slug`);
      if (slug) {
        assert(!seen.has(slug), failures, `${fileName}: ${tabLabel} duplicates Grafana URL slug '${slug}' from '${seen.get(slug)}'`);
        seen.set(slug, title);
      }
      validateGrafanaTabSlugs(fileName, tab?.spec?.layout, failures, `${tabLabel}.layout`);
    });
    return;
  }

  if (layout.kind === "RowsLayout") {
    for (const row of layout.spec?.rows || []) {
      validateGrafanaTabSlugs(fileName, row?.spec?.layout, failures, `${pathLabel}.row`);
    }
    return;
  }

  for (const item of layout.spec?.items || []) {
    validateGrafanaTabSlugs(fileName, item?.spec?.layout, failures, `${pathLabel}.item`);
  }
}

function validateTodayPaletteFallbacks(fileName, dashboard, failures) {
  if (!["VM_EVCC_Today.json", "VM_EVCC_Today-Mobile.json"].includes(fileName)) {
    return;
  }

  const panels = collectDashboardPanels(dashboard);
  const powerGaugePanel = panels.find((panel) => panel.id === 74);
  assert(
    powerGaugePanel?.fieldConfig?.defaults?.color?.mode === "thresholds",
    failures,
    `${fileName}: Power gauge must use threshold colors as default fallback for dynamic loadpoint labels`,
  );
  const dynamicColorPanels = [
    { label: "Power history", panel: panels.find((panel) => panel.id === 2) },
    { label: "Battery levels", panel: panels.find((panel) => panel.id === 66) },
    { label: "Energy", panel: panels.find((panel) => panel.title === "Energy") },
    { label: "Power distribution", panel: panels.find((panel) => panel.id === 75) },
  ];

  for (const item of dynamicColorPanels) {
    assert(
      item.panel?.fieldConfig?.defaults?.color?.mode === "palette-classic",
      failures,
      `${fileName}: ${item.label} must use palette-classic as default color fallback for dynamic labels`,
    );
  }
}

function validateGrafana13GaugeOptions(fileName, panel, failures) {
  assert(panel.options?.sparkline === true, failures, `${fileName}: gauge panel '${panel.title || panel.id}' must use Grafana 13 sparkline gauges`);
  assert(panel.options?.shape === "gauge", failures, `${fileName}: gauge panel '${panel.title || panel.id}' must use arc gauge shape`);
  assert(!Object.hasOwn(panel.options || {}, "graphMode"), failures, `${fileName}: gauge panel '${panel.title || panel.id}' must not use legacy graphMode option`);
  assert(!Object.hasOwn(panel.fieldConfig?.defaults?.custom || {}, "graphMode"), failures, `${fileName}: gauge panel '${panel.title || panel.id}' must not use legacy custom.graphMode option`);
}

function validateAutarkyGaugeThresholds(fileName, panel, failures) {
  if (panel.type !== "gauge") {
    return;
  }
  const autarkyOverride = (panel.fieldConfig?.overrides || []).find((override) => override?.matcher?.id === "byFrameRefID" && override?.matcher?.options === "Autarky");
  if (!autarkyOverride) {
    return;
  }
  const properties = new Map((autarkyOverride.properties || []).map((property) => [property.id, property.value]));
  const steps = properties.get("thresholds")?.steps || [];
  assert(properties.get("unit") === "percentunit", failures, `${fileName}: gauge panel '${panel.title}' Autarky must use percentunit`);
  assert(properties.get("min") === 0 && properties.get("max") === 1, failures, `${fileName}: gauge panel '${panel.title}' Autarky must use 0..1 scale`);
  assert(JSON.stringify(steps) === JSON.stringify([
    { color: dashboardColors.autarkyLow, value: null },
    { color: dashboardColors.autarkyMid, value: 0.25 },
    { color: dashboardColors.autarky, value: 0.5 },
    { color: dashboardColors.autarkyDark, value: 0.75 },
  ]), failures, `${fileName}: gauge panel '${panel.title}' Autarky thresholds must stay within the green autarky color family`);
  assert(properties.get("color")?.mode === "thresholds", failures, `${fileName}: gauge panel '${panel.title}' Autarky must use threshold color mode`);
  assert((panel.fieldConfig?.overrides || []).some((override) => override?.matcher?.id === "byFrameRefID" && override?.matcher?.options === "Self-consumption"), failures, `${fileName}: gauge panel '${panel.title}' Self-consumption override must match stable query refId`);
}

function validateMetricHistoryOverrides(fileName, panel, failures) {
  if (fileName !== "VM_EVCC_Today.json" || panel.id !== 76 || panel.title !== "Metric history") {
    return;
  }
  const expected = new Map([
    ["Autarky", dashboardColors.autarky],
    ["Self-consumption", dashboardColors.selfConsumption],
  ]);
  for (const [refId, color] of expected) {
    const override = (panel.fieldConfig?.overrides || []).find((item) => item?.matcher?.id === "byFrameRefID" && item?.matcher?.options === refId);
    const properties = new Map((override?.properties || []).map((property) => [property.id, property.value]));
    assert(Boolean(override), failures, `${fileName}: Metric history ${refId} override must match stable query refId`);
    assert(properties.get("color")?.mode === "fixed" && properties.get("color")?.fixedColor === color, failures, `${fileName}: Metric history ${refId} must use semantic fixed color ${color}`);
  }
}

function validateMetricGaugeTimeSeries(fileName, panel, failures) {
  for (const refId of ["Autarky", "Self-consumption"]) {
    const target = panel.targets?.find((item) => item.refId === refId);
    const querySpec = target?.raw?.spec?.query?.spec || {};
    assert(Boolean(target), failures, `${fileName}: Metric gauges must query ${refId}`);
    assert(target?.group === "victoriametrics-metrics-datasource", failures, `${fileName}: Metric gauges ${refId} must use VictoriaMetrics directly, not an expression`);
    assert(querySpec.range === true, failures, `${fileName}: Metric gauges ${refId} must be a range query so Grafana can render a sparkline`);
    assert(querySpec.format === "time_series", failures, `${fileName}: Metric gauges ${refId} must return time_series data`);
    assert(querySpec.interval === "1d", failures, `${fileName}: Metric gauges ${refId} must use a deterministic 1d sparkline interval`);
    assert(String(querySpec.expr || "").includes("running_sum("), failures, `${fileName}: Metric gauges ${refId} must use cumulative range data so the reduced value still represents the selected period`);
  }
}
function findRowsWithPanelIds(layout, requiredPanelIds) {
  const matches = [];
  const requiredNames = new Set(requiredPanelIds.map((id) => "panel-" + id));

  function visit(currentLayout) {
    if (!currentLayout || typeof currentLayout !== "object") {
      return;
    }
    if (currentLayout.kind === "TabsLayout") {
      for (const tab of currentLayout.spec?.tabs || []) {
        visit(tab?.spec?.layout);
      }
      return;
    }
    if (currentLayout.kind === "RowsLayout") {
      for (const row of currentLayout.spec?.rows || []) {
        const itemNames = new Set((row?.spec?.layout?.spec?.items || []).map((item) => item?.spec?.element?.name));
        const hasAllPanels = [...requiredNames].every((name) => itemNames.has(name));
        if (hasAllPanels) {
          matches.push(row);
        }
        visit(row?.spec?.layout);
      }
      return;
    }
    for (const item of currentLayout.spec?.items || []) {
      visit(item?.spec?.layout);
    }
  }

  visit(layout);
  return matches;
}

function validateInvestmentConditionalRow(fileName, dashboard, failures) {
  const expectedRows = new Map([
    ["VM_EVCC_Year.json", [
      { title: "PV generation costs", panelIds: [77, 78, 79, 80] },
    ]],
    ["VM_EVCC_All-time.json", [
      { title: "PV generation costs", panelIds: [56, 57] },
      { title: "PV source yearly output", panelIds: [58, 59] },
    ]],
  ]);
  const expectedRowSpecs = expectedRows.get(fileName);
  if (!expectedRowSpecs) {
    return;
  }

  const variable = dashboardVariables(dashboard).find((item) => dashboardVariableName(item) === "hasInvestmentData");
  const spec = variable?.spec || {};
  assert(variable?.kind === "QueryVariable", failures, fileName + ": investment visibility helper must be a QueryVariable");
  assert(spec.hide === "hideVariable", failures, fileName + ": investment visibility helper must be hidden");
  assert(spec.skipUrlSync === true, failures, fileName + ": investment visibility helper must stay out of dashboard URLs");
  assert(spec.includeAll === true, failures, fileName + ": investment visibility helper must include All so Grafana initializes conditional rows reliably");
  assert(spec.current?.value === "$__all", failures, fileName + ": investment visibility helper must default to $__all");
  assert(spec.query?.spec?.query === "label_values(evcc_pv_lcoe_yearly_ct_per_kwh, title)", failures, fileName + ": investment visibility helper must detect investment rollup data by title label");

  for (const expected of expectedRowSpecs) {
    const rows = findRowsWithPanelIds(dashboard.spec?.layout, expected.panelIds);
    assert(rows.length === 1, failures, fileName + ": investment panels " + expected.panelIds.join(", ") + " must be grouped into exactly one conditional row");
    const row = rows[0];
    assert(row?.spec?.title === expected.title, failures, fileName + ": investment row must be titled " + expected.title);
    const condition = row?.spec?.conditionalRendering;
    const item = condition?.spec?.items?.[0];
    assert(condition?.kind === "ConditionalRenderingGroup", failures, fileName + ": investment row " + expected.title + " must use Grafana conditional rendering");
    assert(condition?.spec?.visibility === "show" && condition?.spec?.condition === "and", failures, fileName + ": investment row " + expected.title + " must only show when the helper variable has data");
    assert(item?.kind === "ConditionalRenderingVariable", failures, fileName + ": investment row " + expected.title + " conditional must be variable-based");
    assert(item?.spec?.variable === "hasInvestmentData" && item?.spec?.operator === "matches" && item?.spec?.value === ".+", failures, fileName + ": investment row " + expected.title + " must match non-empty investment data helper values");
  }
}
function dashboardVariableName(variable) {
  return variable?.spec ? String(variable.spec.name || "") : String(variable?.name || "");
}

function dashboardVariableValue(variable) {
  return variable?.spec
    ? String(variable.spec.current?.value ?? variable.spec.query ?? "")
    : String(variable?.current?.value ?? variable?.query ?? "");
}

function isPortalDashboardLink(link) {
  return String(link?.url || "") === "$inverterPortalUrl" || String(link?.title || "") === "$inverterPortalTitle";
}

function validateDashboard(fileName, dashboard) {
  const failures = [];
  const rawJson = JSON.stringify(dashboard);
  const panels = collectDashboardPanels(dashboard);

  for (const text of forbiddenTexts) {
    assert(!rawJson.includes(text), failures, `${fileName}: forbidden Grafana error text is present: ${text}`);
  }
  for (const text of forbiddenRuntimeDefaults) {
    assert(!rawJson.includes(text), failures, `${fileName}: private or vendor-specific runtime default is present: ${text}`);
  }
  assert(!rawJson.includes("vm-today-gauges-en-orig"), failures, `${fileName}: Today Gauges legacy UID must not be referenced`);
  assert(!dashboardLinks(dashboard).some(isPortalDashboardLink), failures, `${fileName}: optional portal link must not be visible by default`);
  for (const variable of dashboardVariables(dashboard)) {
    const name = dashboardVariableName(variable);
    if (["inverterPortalTitle", "inverterPortalUrl"].includes(name)) {
      assert(dashboardVariableValue(variable) === "", failures, `${fileName}: ${name} must default to an empty value`);
    }
  }

  const expectedTime = expectedTimes[fileName];
  const timeSettings = dashboardTimeSettings(dashboard);
  assert(Boolean(expectedTime), failures, `${fileName}: no expected time contract configured`);
  if (expectedTime) {
    assert(timeSettings?.from === expectedTime.from, failures, `${fileName}: expected time.from=${expectedTime.from}, got ${timeSettings?.from}`);
    assert(timeSettings?.to === expectedTime.to, failures, `${fileName}: expected time.to=${expectedTime.to}, got ${timeSettings?.to}`);
  }

  if (["VM_EVCC_All-time.json", "VM_EVCC_Month.json", "VM_EVCC_Year.json", "VM_EVCC_Today-Details.json", "VM_EVCC_Today.json"].includes(fileName)) {
    assert(isV2Dashboard(dashboard), failures, `${fileName}: expected a Grafana v2 dashboard resource`);
    const expectedLayout = ["VM_EVCC_Today.json"].includes(fileName) ? "GridLayout" : "TabsLayout";
    assert(dashboardLayoutKind(dashboard) === expectedLayout, failures, `${fileName}: expected layout.kind=${expectedLayout}, got ${dashboardLayoutKind(dashboard)}`);
    for (const [elementName, element] of Object.entries(dashboard.spec?.elements || {})) {
      if (element?.kind === "Panel") {
        assert(Array.isArray(element.spec?.data?.spec?.transformations), failures, `${fileName}: ${elementName} must set data.spec.transformations to an array for Grafana 13 v2 deserialization`);
      }
    }
  }

  validateGrafanaTabSlugs(fileName, dashboard.spec?.layout, failures);
  validateInvestmentConditionalRow(fileName, dashboard, failures);
  validateTodayPaletteFallbacks(fileName, dashboard, failures);
  for (const panel of panels) {
    validateSemanticColors(fileName, panel, failures);
    for (const override of panel.fieldConfig?.overrides || []) {
      assert(!(override?.matcher?.id === "byName" && forbiddenUserSpecificMatchers.has(override?.matcher?.options)), failures, `${fileName}: panel '${panel.title}' must not contain user-specific byName matcher '${override?.matcher?.options}'`);
    }
  }

  if (["VM_EVCC_All-time.json", "VM_EVCC_Month.json", "VM_EVCC_Year.json"].includes(fileName)) {
    const metricGaugePanel = panels.find((panel) => panel.title === "Metric gauges" && panel.type === "gauge");
    assert(Boolean(metricGaugePanel), failures, `${fileName}: missing Metric gauges panel`);
    if (metricGaugePanel) {
      validateGrafana13GaugeOptions(fileName, metricGaugePanel, failures);
      validateMetricGaugeTimeSeries(fileName, metricGaugePanel, failures);
    }
  }

  if (fileName === "VM_EVCC_Today-Details.json") {
    const topLevelTabs = dashboard.spec?.layout?.spec?.tabs?.map((tab) => tab.spec?.title) || [];
    assert(topLevelTabs.includes("Home"), failures, `${fileName}: Today Details must use Home as the house tab title`);
    assert(!topLevelTabs.includes("Consumption"), failures, `${fileName}: Today Details must not use the old Consumption tab title`);


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

    const forecastStatusPanel = panels.find((panel) => panel.id === 44 || panel.title === "Solar forecast status");
    assert(!forecastStatusPanel, failures, `${fileName}: PV tab must not use a separate Solar forecast status panel`);

    const forecastBarPanel = panels.find((panel) => panel.id === 35 && panel.title === "Forecast" && panel.type === "barchart");
    assert(Boolean(forecastBarPanel), failures, `${fileName}: missing PV tab Forecast bar panel`);
    if (forecastBarPanel) {
      const fallbackTarget = forecastBarPanel.targets?.find((target) => target.refId === "noForecast");
      const actualTarget = forecastBarPanel.targets?.find((target) => target.refId === "pvStringEnergy");
      const forecastEnergyTarget = forecastBarPanel.targets?.find((target) => target.refId === "pvEnergy");
      const fallbackOverride = (forecastBarPanel.fieldConfig?.overrides || []).find((override) => override?.matcher?.id === "byName" && override?.matcher?.options === "No EVCC forecast data");
      assert(Boolean(fallbackTarget), failures, `${fileName}: Forecast bar panel must include noForecast fallback target`);
      assert(String(fallbackTarget?.expr || "").includes("unless") && String(fallbackTarget?.expr || "").includes("present_over_time(tariffSolar_value[24h])"), failures, `${fileName}: Forecast bar fallback must only appear when EVCC tariffSolar_value is absent`);
      assert(String(actualTarget?.expr || "").includes("present_over_time(tariffSolar_value[24h])"), failures, `${fileName}: Forecast bar Actual series must be hidden when EVCC forecast data is absent`);
      assert(String(forecastEnergyTarget?.expr || "").includes("present_over_time(tariffSolar_value[24h])"), failures, `${fileName}: Forecast bar Forecast series must be guarded by EVCC forecast data presence`);
      assert(JSON.stringify(fallbackOverride).includes("No EVCC forecast data"), failures, `${fileName}: Forecast bar panel must show the no-forecast text in the existing forecast panel`);
    }

    const forecastPanel = panels.find((panel) => panel.id === 16 && panel.title === "Forecast" && panel.type === "timeseries");
    assert(Boolean(forecastPanel), failures, `${fileName}: missing PV tab timeseries Forecast panel`);
    if (forecastPanel) {
      assert(hasDashedDarkGreenForecast(forecastPanel), failures, `${fileName}: PV tab Forecast series must be dark green, dashed, and unfilled`);
      assert(hasEvccForecastDescription(forecastPanel), failures, `${fileName}: PV tab Forecast panel must explain EVCC tariffSolar_value source and optional no-data behavior`);
    }
  }

  if (["VM_EVCC_Today.json", "VM_EVCC_Today-Mobile.json"].includes(fileName)) {
    assert(!rawJson.includes('"libraryPanel"'), failures, `${fileName}: deployed dashboards must not use Grafana library panels`);
    assert(!Object.hasOwn(dashboard, "__elements"), failures, `${fileName}: deployed dashboards must not embed Grafana library panel elements`);
    const powerHistoryPanel = panels.find((panel) => panel.id === 2);
    const powerHistoryTargets = powerHistoryPanel?.targets || [];
    assert(powerHistoryTargets.some((target) => target.refId === "pvForecast" && String(target.expr || "").includes("tariffSolar_value")), failures, `${fileName}: Power history panel must include PV forecast target`);
    assert(hasEvccForecastDescription(powerHistoryPanel), failures, `${fileName}: Power history panel must explain EVCC tariffSolar_value source and optional no-data behavior`);
    const powerHistoryOverrides = powerHistoryPanel?.fieldConfig?.overrides || [];
    const forecastOverride = powerHistoryOverrides.find((override) => override?.matcher?.id === "byName" && override?.matcher?.options === "PV forecast");
    const forecastProperties = new Map((forecastOverride?.properties || []).map((property) => [property.id, property.value]));
    assert(forecastProperties.get("color")?.mode === "fixed" && forecastProperties.get("color")?.fixedColor === dashboardColors.pvForecast, failures, `${fileName}: PV forecast must use the central PV forecast color`);
    assert(forecastProperties.get("custom.lineStyle")?.fill === "dash", failures, `${fileName}: PV forecast must be dashed`);
    assert(forecastProperties.get("custom.fillOpacity") === 0, failures, `${fileName}: PV forecast must not use area fill`);

    for (const panel of panels.filter((item) => item.type === "gauge")) {
      validateGrafana13GaugeOptions(fileName, panel, failures);
      validateAutarkyGaugeThresholds(fileName, panel, failures);
    }
    for (const panel of panels.filter((item) => fileName === "VM_EVCC_Today.json" && item.id === 76 && item.title === "Metric history")) {
      validateMetricHistoryOverrides(fileName, panel, failures);
    }

    const powerPanel = panels.find((panel) => panel.id === 74);
    const expectedPowerGaugeMatchers = new Map([
      ["PV", "PV"],
      ["gridPower", "Grid"],
      ["batteryPower", "Battery"],
      ["homePower", "Home"],
    ]);
    assert(Boolean(powerPanel), failures, `${fileName}: missing Power gauge panel`);
    if (powerPanel) {
      const powerDefaults = powerPanel.fieldConfig?.defaults || {};
      assert(powerDefaults.min === -11 && powerDefaults.max === 0, failures, `${fileName}: Power gauge defaults must use a negative -11..0 kW scale for dynamic loadpoint series`);
      assert(powerDefaults.color?.mode === "thresholds", failures, `${fileName}: Power gauge defaults must use threshold color mode for dynamic loadpoint series`);
      const defaultThresholds = powerDefaults.thresholds?.steps || [];
      assert(defaultThresholds.length >= 5 && defaultThresholds.some((step) => step.color === dashboardColors.loadpointDanger && step.value === null), failures, `${fileName}: Power gauge dynamic loadpoints must use multiple negative absolute threshold steps in the loadpoint color family`);
      const powerGaugeTargetOrder = (powerPanel.targets || []).map((target) => target.refId);
      assert(powerGaugeTargetOrder.slice(0, 5).join(",") === "gridPower,batteryPower,PV,homePower,loadpointPowers", failures, `${fileName}: Power gauge order must be Grid, Battery, PV, Home, then dynamic loadpoints`);
      const loadpointTarget = (powerPanel.targets || []).find((target) => target.refId === "loadpointPowers");
      assert(Boolean(loadpointTarget), failures, `${fileName}: Power gauge must include loadpointPowers target`);
      if (loadpointTarget) {
        const expr = String(loadpointTarget.expr || "");
        assert(expr.includes("chargePower_value / -1000"), failures, `${fileName}: Power gauge loadpoints must render as negative consumer power`);
        assert(!expr.includes("chargePower_value / 1000"), failures, `${fileName}: Power gauge loadpoints must not render as positive charging power`);
      }
      const stalePowerGaugeMatchers = new Set(["Garage", "Stellplatz", "Grid", "Battery", "Home"]);
      const powerGaugeOverrides = powerPanel.fieldConfig?.overrides || [];
      for (const override of powerGaugeOverrides) {
        assert(!(override?.matcher?.id === "byName" && stalePowerGaugeMatchers.has(override?.matcher?.options)), failures, `${fileName}: Power gauge must not use stale byName matcher '${override?.matcher?.options}'`);
      }
      const isMobilePowerPanel = fileName === "VM_EVCC_Today-Mobile.json";
      const expectedMobilePowerColors = new Map([
        ["PV", dashboardColors.pv],
        ["gridPower", dashboardColors.grid],
        ["batteryPower", dashboardColors.storage],
        ["homePower", dashboardColors.home],
      ]);
      for (const [refId, label] of expectedPowerGaugeMatchers) {
        assert(powerGaugeOverrides.some((override) => override?.matcher?.id === "byFrameRefID" && override?.matcher?.options === refId), failures, `${fileName}: Power gauge ${label} override must match stable query refId '${refId}'`);
        const color = propertyValue(powerPanel, refId, "color");
        if (isMobilePowerPanel) {
          assert(color?.mode === "fixed" && color.fixedColor === expectedMobilePowerColors.get(refId), failures, `${fileName}: Power stat ${label} must use fixed semantic color ${expectedMobilePowerColors.get(refId)}`);
        } else {
          assert(color?.mode === "thresholds", failures, `${fileName}: Power gauge ${label} must use threshold color mode so compact gauge views keep semantic colors`);
        }
      }
      const homeTarget = (powerPanel.targets || []).find((target) => target.refId === "homePower");
      assert(/homePower_value\)?\s*\/\s*-1000/.test(String(homeTarget?.expr || "")), failures, `${fileName}: Power gauge Home must render as negative house consumption`);
      assert(dashboardVariables(dashboard).some((variable) => dashboardVariableName(variable) === "installedWattPeak"), failures, `${fileName}: Power gauge PV max is deploy-patched from installedWattPeak dashboard variable`);
      const pvMin = propertyValue(powerPanel, "PV", "min");
      const pvMax = propertyValue(powerPanel, "PV", "max");
      assert(pvMin === 0 && pvMax === 20, failures, `${fileName}: Power gauge PV must use a numeric 0..20 kW default scale so Grafana does not auto-scale it as full`);
      const pvThresholds = propertyValue(powerPanel, "PV", "thresholds");
      if (!isMobilePowerPanel) {
        assert(pvThresholds?.mode === "percentage" && (pvThresholds.steps || []).length >= 3, failures, `${fileName}: Power gauge PV must use percentage thresholds relative to its numeric max`);
      }
      assert(propertyValue(powerPanel, "homePower", "min") === -11 && propertyValue(powerPanel, "homePower", "max") === 0, failures, `${fileName}: Power gauge Home must use a negative -11..0 kW scale`);
      const homeThresholds = propertyValue(powerPanel, "homePower", "thresholds")?.steps || [];
      if (!isMobilePowerPanel) {
        assert(homeThresholds.length >= 5 && homeThresholds.some((step) => step.color === dashboardColors.homeDanger && step.value === null), failures, `${fileName}: Power gauge Home must use multiple negative absolute threshold steps in the home color family`);
      }
      const expectedSignedGaugeRanges = new Map([
        ["gridPower", [-11, 11]],
        ["batteryPower", [-11, 11]],
      ]);
      if (!isMobilePowerPanel) {
        assert(powerPanel.options?.neutral === 0, failures, `${fileName}: Power gauge must use Grafana gauge neutral option at zero`);
        assert(!Object.hasOwn(powerPanel.fieldConfig?.defaults?.custom || {}, "neutral"), failures, `${fileName}: Power gauge neutral must not use field custom neutral`);
      }
      for (const [matcherOption, [min, max]] of expectedSignedGaugeRanges) {
        const label = expectedPowerGaugeMatchers.get(matcherOption) || matcherOption;
        assert(propertyValue(powerPanel, matcherOption, "min") === min && propertyValue(powerPanel, matcherOption, "max") === max, failures, `${fileName}: Power gauge ${label} must keep signed ${min}..${max} kW scale`);
        const thresholds = propertyValue(powerPanel, matcherOption, "thresholds")?.steps || [];
        if (!isMobilePowerPanel) {
          assert(thresholds.length >= 4 && thresholds.some((step) => step.value < 0) && thresholds.some((step) => step.value > 0), failures, `${fileName}: Power gauge ${label} must use multiple signed threshold steps around zero`);
        }
      }
    }
    const expectedDetailTabs = new Map([
      ["PV", "dtab=pv"],
      ["gridPower", "dtab=grid"],
      ["homePower", "dtab=home"],
      ["batteryPower", "dtab=pv"],
    ]);
    for (const [matcherOption, tabParam] of expectedDetailTabs) {
      const label = expectedPowerGaugeMatchers.get(matcherOption) || matcherOption;
      const links = propertyValue(powerPanel, matcherOption, "links") || [];
      assert(links.some((link) => String(link.url || "").includes(tabParam) && link.targetBlank === true), failures, `${fileName}: Power gauge ${label} must open Today Details with ${tabParam} in a new tab`);
    }
  }

  if (fileName === "VM_EVCC_Today.json") {
    const byId = dashboardGridPositionsById(dashboard);
    const bottom = (gridPos) => (gridPos?.y || 0) + (gridPos?.h || 0);
    assert(byId.get(74)?.h === 27, failures, `${fileName}: Power gauge column must align to bottom row height 27`);
    assert(byId.get(2)?.h === 24, failures, `${fileName}: Power history panel must leave room for bottom distribution strip`);
    assert(byId.get(76)?.h === 4, failures, `${fileName}: Metric history panel must be four grid rows high`);
    assert(byId.get(77)?.y === 16, failures, `${fileName}: Energy panel must start below enlarged Metric history panel`);
    assert(byId.get(75)?.y === 24, failures, `${fileName}: Power distribution panel must align with right column lower section`);
    assert(byId.get(73)?.y === 25, failures, `${fileName}: Costs panel must align below Energy panel`);
    assert(bottom(byId.get(74)) === 27 && bottom(byId.get(75)) === 27 && bottom(byId.get(73)) === 27, failures, `${fileName}: left, middle, and right columns must share the same bottom edge`);
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
    assert(!panel.libraryPanel, failures, `${fileName}: panel '${panel.title || panel.id}' must not be a Grafana library panel reference`);
    if (isRenderablePanel(panel)) {
      assert(panelTargetCount(panel) > 0, failures, `${fileName}: renderable panel '${panel.title || panel.id}' has no targets`);
    }
    for (const target of panel.targets || []) {
      assert(!hasInfluxShape(target), failures, `${fileName}: panel '${panel.title || panel.id}' contains an Influx-style target`);
    }
    if (panel.type === "barchart") {
      assert(Boolean(panel.options?.xField), failures, `${fileName}: barchart '${panel.title || panel.id}' has no xField`);
    }
    validateTransformationFieldReferences(fileName, panel, failures);
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
    if (rule.exprIncludes) {
      const expr = (panel.targets || []).map(targetExpr).join("\n");
      assert(expr.includes(rule.exprIncludes), failures, `${fileName}: critical panel '${rule.title}' query must include ${rule.exprIncludes}`);
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

function fieldsFromOrganizeOptions(options) {
  const renameByName = options.renameByName || {};
  const sourceNames = new Set([
    ...Object.keys(options.indexByName || {}),
    ...Object.keys(renameByName),
  ]);
  if (sourceNames.size === 0) {
    return null;
  }
  return new Set([...sourceNames].map((field) => renameByName[field] || field));
}

function validateKnownField(fileName, panel, failures, fields, field, context) {
  if (!fields || !field) {
    return;
  }
  assert(fields.has(field), failures, `${fileName}: panel '${panel.title}' ${context} references missing transformed field '${field}'`);
}

function validateTransformationFieldReferences(fileName, panel, failures) {
  const transformations = panel.rawElement?.spec?.data?.spec?.transformations || [];
  if (!Array.isArray(transformations) || transformations.length === 0) {
    return;
  }

  let fields = null;
  for (const transformation of transformations) {
    const group = transformation?.group || transformation?.kind || "";
    const options = transformation?.spec?.options || transformation?.options || {};

    if (group === "organize") {
      fields = fieldsFromOrganizeOptions(options);
      continue;
    }

    if (group === "filterFieldsByName") {
      const includeNames = options.include?.names;
      if (Array.isArray(includeNames)) {
        for (const name of includeNames) {
          validateKnownField(fileName, panel, failures, fields, name, "filterFieldsByName");
        }
        fields = fields ? new Set(includeNames.filter((name) => fields.has(name))) : new Set(includeNames);
      }
      continue;
    }

    if (group === "sortBy") {
      for (const sort of options.sort || []) {
        validateKnownField(fileName, panel, failures, fields, sort?.field, "sortBy");
      }
      continue;
    }

    if (group === "groupingToMatrix") {
      for (const [role, field] of [["rowField", options.rowField], ["columnField", options.columnField], ["valueField", options.valueField]]) {
        validateKnownField(fileName, panel, failures, fields, field, `groupingToMatrix ${role}`);
      }
      fields = new Set(options.rowField ? [options.rowField] : []);
    }
  }

  if (panel.options?.xField && fields) {
    assert(fields.has(panel.options.xField), failures, `${fileName}: panel '${panel.title}' xField '${panel.options.xField}' is not available after transformations`);
  }
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

  const translationRoot = path.join(repoRoot, "dashboards", "translation");
  if (fs.existsSync(translationRoot)) {
    for (const language of fs.readdirSync(translationRoot, { withFileTypes: true }).filter((entry) => entry.isDirectory()).map((entry) => entry.name).sort()) {
      for (const fileName of files) {
        const dashboardPath = path.join(translationRoot, language, fileName);
        if (!fs.existsSync(dashboardPath)) {
          allFailures.push(`${language}/${fileName}: dashboard file is missing from dashboards/translation`);
          continue;
        }
        const rawDashboard = fs.readFileSync(dashboardPath, "utf8");
        if (language === "de") {
          assert(!rawDashboard.includes("Netzbezug"), allFailures, `${language}/${fileName}: use 'Bezug' for explicit grid import labels, not 'Netzbezug'`);
          assert(!rawDashboard.includes("Grid import"), allFailures, `${language}/${fileName}: German dashboards must not expose the English grid import label`);
          assert(!/"(title|label|legendFormat|value|description|displayName|text|content)"\s*:\s*"[^"]*Batterie/.test(rawDashboard), allFailures, `${language}/${fileName}: use 'Speicher' for visible storage labels, not 'Batterie'`);
        }
        const dashboard = JSON.parse(rawDashboard);
        for (const panel of collectDashboardPanels(dashboard)) {
          validateTransformationFieldReferences(`${language}/${fileName}`, panel, allFailures);
        }
        validateGrafanaTabSlugs(`${language}/${fileName}`, dashboard.spec?.layout, allFailures);
      }
    }
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
