/**
 * Script: dashboard-colors.mjs
 * Purpose: Central semantic color palette for EVCC VictoriaMetrics dashboards.
 * Version: 2026.06.03.1
 * Last modified: 2026-06-03
 */

export const dashboardColors = Object.freeze({
  neutral: "#7A7A7A4D",
  pv: "#2F8F5B",
  pvDark: "#1B5E20",
  pvLight: "#73BF69",
  pvForecast: "#2F8F5B",
  grid: "#E0B400",
  gridImport: "#E0B400",
  feedIn: "#14B8A6",
  storage: "#3274D9",
  storageCharge: "#73A7F2",
  storageDischarge: "#3274D9",
  storageDark: "#1F60A8",
  home: "#9F7AEA",
  loadpoint: "#FF9830",
  loadpointHigh: "#E66A00",
  danger: "red",
  warning: "orange",
  caution: "yellow",
  success: "green",
  selfConsumption: "#14B8A6",
  autarky: "#73BF69",
  purchase: "red",
  sold: "green",
  text: "text",
});

export function fixedColor(color) {
  return { mode: "fixed", fixedColor: color };
}

export function thresholds(mode, steps) {
  return { mode, steps };
}
