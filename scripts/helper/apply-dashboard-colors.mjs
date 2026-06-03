/**
 * Script: apply-dashboard-colors.mjs
 * Purpose: Apply the central semantic color palette to original EVCC VM dashboards.
 * Version: 2026.06.03.13
 * Last modified: 2026-06-03
 */
import fs from "node:fs";
import path from "node:path";
import { dashboardColors, fixedColor, thresholds } from "./dashboard-colors.mjs";

const repoRoot = process.cwd();
const sourceDir = path.join(repoRoot, "dashboards", "original", "en");

const exactColorByName = new Map([
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
  ["Battery SOC", dashboardColors.storageSocDark],
  ["Active phases", dashboardColors.gridImport],
  ["Autarky", dashboardColors.autarky],
  ["Autarkie", dashboardColors.autarky],
  ["Self-consumption", dashboardColors.selfConsumption],
  ["Purchased", dashboardColors.purchase],
  ["Sold", dashboardColors.sold],
]);

const regexpColorRules = [
  { pattern: /PV/i, color: dashboardColors.pv },
  { pattern: /Grid import|Netzbezug/i, color: dashboardColors.gridImport },
  { pattern: /Feed-in|Einspeisung/i, color: dashboardColors.feedIn },
  { pattern: /Home|Haus/i, color: dashboardColors.home },
  { pattern: /Battery|Speicher/i, color: dashboardColors.storage },
];

const gaugeThresholdsByMatcher = new Map([
  ["PV", thresholds("percentage", [
    { color: dashboardColors.neutral, value: 0 },
    { color: dashboardColors.pvLow, value: 1 },
    { color: dashboardColors.pv, value: 50 },
    { color: dashboardColors.pvDark, value: 80 },
  ])],
  ["gridPower", thresholds("absolute", [
    { color: dashboardColors.gridFeedLow, value: -11 },
    { color: dashboardColors.gridImport, value: -1 },
    { color: dashboardColors.neutral, value: -0.001 },
    { color: dashboardColors.gridImport, value: 0.001 },
    { color: dashboardColors.gridImportHigh, value: 1 },
    { color: dashboardColors.gridImportDanger, value: 8 },
  ])],
  ["batteryPower", thresholds("absolute", [
    { color: dashboardColors.storageChargeLow, value: -11 },
    { color: dashboardColors.storageCharge, value: -1 },
    { color: dashboardColors.neutral, value: -0.001 },
    { color: dashboardColors.storageDischarge, value: 0.001 },
    { color: dashboardColors.storageDark, value: 1 },
    { color: dashboardColors.storageDanger, value: 8 },
  ])],
  ["homePower", thresholds("absolute", [
    { color: dashboardColors.neutral, value: 0 },
    { color: dashboardColors.homeLight, value: 0.001 },
    { color: dashboardColors.home, value: 5 },
    { color: dashboardColors.homeHigh, value: 8 },
    { color: dashboardColors.homeDanger, value: 10 },
  ])],
  ["Autarky", thresholds("absolute", [
    { color: dashboardColors.autarkyLow, value: null },
    { color: dashboardColors.autarkyMid, value: 0.25 },
    { color: dashboardColors.autarky, value: 0.5 },
    { color: dashboardColors.autarkyDark, value: 0.75 },
  ])],
  ["Self-consumption", thresholds("absolute", [
    { color: dashboardColors.selfConsumptionLow, value: null },
    { color: dashboardColors.selfConsumptionMid, value: 0.25 },
    { color: dashboardColors.selfConsumption, value: 0.5 },
    { color: dashboardColors.selfConsumptionDark, value: 0.75 },
  ])],
  ["Battery SOC", thresholds("absolute", [
    { color: dashboardColors.storageSocLow, value: null },
    { color: dashboardColors.storageSocMid, value: 15 },
    { color: dashboardColors.storageSoc, value: 35 },
    { color: dashboardColors.storageSocDark, value: 80 },
  ])],
  ["minSoc", thresholds("absolute", [
    { color: dashboardColors.storageSocLow, value: null },
    { color: dashboardColors.storageSocMid, value: 15 },
    { color: dashboardColors.storageSoc, value: 35 },
    { color: dashboardColors.storageSocDark, value: 80 },
  ])],
  ["maxSoc", thresholds("absolute", [
    { color: dashboardColors.storageSocLow, value: null },
    { color: dashboardColors.storageSocMid, value: 15 },
    { color: dashboardColors.storageSoc, value: 35 },
    { color: dashboardColors.storageSocDark, value: 80 },
  ])],
]);

const loadpointDefaults = thresholds("absolute", [
  { color: dashboardColors.neutral, value: 0 },
  { color: dashboardColors.loadpointLight, value: 0.001 },
  { color: dashboardColors.loadpoint, value: 5 },
  { color: dashboardColors.loadpointHigh, value: 8 },
  { color: dashboardColors.loadpointDanger, value: 10 },
]);

const mobilePowerFixedColorsByMatcher = new Map([
  ["gridPower", dashboardColors.grid],
  ["batteryPower", dashboardColors.storage],
  ["PV", dashboardColors.pv],
  ["homePower", dashboardColors.home],
]);

const signedPowerGaugeMatchers = new Set(["gridPower", "batteryPower"]);

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, "utf8"));
}

function writeJson(filePath, value) {
  const data = `${JSON.stringify(value, null, 2)}\n`;
  const tmp = `${filePath}.tmp`;
  fs.writeFileSync(tmp, data, "utf8");
  fs.renameSync(tmp, filePath);
}

function propertyMap(properties) {
  return new Map((properties || []).map((property) => [property.id, property]));
}

function setProperty(override, id, value) {
  override.properties ||= [];
  const properties = propertyMap(override.properties);
  if (properties.has(id)) {
    properties.get(id).value = value;
    return;
  }
  override.properties.push({ id, value });
}

function hasProperty(override, id) {
  return (override.properties || []).some((property) => property.id === id);
}

function removeProperty(override, id) {
  const before = override.properties?.length || 0;
  override.properties = (override.properties || []).filter((property) => property.id !== id);
  return override.properties.length !== before;
}

function removeGaugeOnlyThreshold(override) {
  const thresholdsProperty = (override.properties || []).find((property) => property.id === "thresholds");
  const steps = thresholdsProperty?.value?.steps || [];
  const looksLikePvGaugeThreshold = thresholdsProperty?.value?.mode === "percentage" && steps.some((step) => step.color === dashboardColors.pvDark);
  if (looksLikePvGaugeThreshold) {
    return removeProperty(override, "thresholds");
  }
  return false;
}
function matcherOption(override) {
  return override?.matcher?.options;
}

function colorForOverride(override, panelTitle = "") {
  const option = matcherOption(override);
  if (typeof option !== "string") {
    return null;
  }
  if (exactColorByName.has(option)) {
    return exactColorByName.get(option);
  }
  if (option === "Total" && /battery|batteries|storage/i.test(panelTitle)) {
    return dashboardColors.storage;
  }
  if (option === "Total" && /power\/phase/i.test(panelTitle)) {
    return dashboardColors.gridImport;
  }
  if (override.matcher?.id === "byRegexp") {
    const rule = regexpColorRules.find((item) => item.pattern.test(option));
    return rule?.color || null;
  }
  return null;
}

function panelFieldConfigs(dashboard) {
  const configs = [];

  function visitClassic(panel) {
    if (!panel || typeof panel !== "object") {
      return;
    }
    if (panel.fieldConfig) {
      configs.push({ panel, fieldConfig: panel.fieldConfig, kind: panel.type || "" });
    }
    for (const nested of panel.panels || []) {
      visitClassic(nested);
    }
  }

  if (Array.isArray(dashboard.panels)) {
    for (const panel of dashboard.panels) {
      visitClassic(panel);
    }
  }

  for (const element of Object.values(dashboard.spec?.elements || dashboard.elements || {})) {
    const fieldConfig = element?.spec?.vizConfig?.spec?.fieldConfig;
    if (fieldConfig) {
      configs.push({ panel: element, fieldConfig, kind: element.spec?.vizConfig?.group || "" });
    }
  }

  return configs;
}

function isPowerGaugePanel(panel) {
  const panelId = panel.id || panel.spec?.id;
  const title = panel.title || panel.spec?.title || "";
  return panelId === 74 && title === "Power";
}

function isPowerStatPanel(panel, kind) {
  return kind === "stat" && isPowerGaugePanel(panel);
}

function applyPowerGaugeDefaults(fieldConfig, panel, kind) {
  if (!isPowerGaugePanel(panel) || !["gauge", "stat"].includes(kind)) {
    return false;
  }
  fieldConfig.defaults ||= {};
  fieldConfig.defaults.color = { mode: "thresholds" };
  fieldConfig.defaults.thresholds = loadpointDefaults;
  if (kind === "gauge") {
    fieldConfig.defaults.custom ||= {};
    fieldConfig.defaults.custom.neutral = 0;
  }
  return true;
}

function applyFieldConfig(fieldConfig, panel, kind) {
  const panelTitle = panel.title || panel.spec?.title || "";
  if (/battery|batteries|storage/i.test(panelTitle) && fieldConfig.defaults?.color?.mode === "fixed") {
    fieldConfig.defaults.color = fixedColor(dashboardColors.storage);
  }
  let changed = applyPowerGaugeDefaults(fieldConfig, panel, kind);
  for (const override of fieldConfig.overrides || []) {
    const option = matcherOption(override);
    if (typeof option !== "string") {
      continue;
    }

    const isGauge = kind === "gauge" || isPowerGaugePanel(panel);
    if (isPowerStatPanel(panel, kind) && mobilePowerFixedColorsByMatcher.has(option)) {
      setProperty(override, "color", fixedColor(mobilePowerFixedColorsByMatcher.get(option)));
      changed = removeProperty(override, "thresholds") || true;
      continue;
    }
    if (gaugeThresholdsByMatcher.has(option) && isGauge) {
      setProperty(override, "thresholds", gaugeThresholdsByMatcher.get(option));
      setProperty(override, "color", { mode: "thresholds" });
      if (kind === "gauge" && signedPowerGaugeMatchers.has(option)) {
        setProperty(override, "custom.neutral", 0);
      }
      changed = true;
    } else if (gaugeThresholdsByMatcher.has(option)) {
      changed = removeProperty(override, "thresholds") || changed;
    }

    if (!isGauge && option === "PV") {
      changed = removeGaugeOnlyThreshold(override) || changed;
    }

    const color = colorForOverride(override, panelTitle);
    if (!color) {
      continue;
    }

    const isThresholdDrivenGauge = isGauge && (hasProperty(override, "thresholds") || gaugeThresholdsByMatcher.has(option));
    if (isThresholdDrivenGauge) {
      setProperty(override, "color", { mode: "thresholds" });
      changed = true;
    } else {
      setProperty(override, "color", fixedColor(color));
      changed = true;
    }
  }
  return changed;
}

function main() {
  let changedFiles = 0;
  const files = fs.readdirSync(sourceDir).filter((item) => item.endsWith(".json")).sort();
  for (const file of files) {
    const filePath = path.join(sourceDir, file);
    const dashboard = readJson(filePath);
    let changed = false;
    for (const { panel, fieldConfig, kind } of panelFieldConfigs(dashboard)) {
      changed = applyFieldConfig(fieldConfig, panel, kind) || changed;
    }
    if (changed) {
      writeJson(filePath, dashboard);
      changedFiles += 1;
      console.log(`Updated ${file}`);
    }
  }
  console.log(`Dashboard color update complete: ${changedFiles} file(s) changed.`);
}

main();





