/**
 * Script: dashboard-colors.mjs
 * Purpose: Central semantic color palette for EVCC VictoriaMetrics dashboards.
 * Version: 2026.06.03.4
 * Last modified: 2026-06-03
 */

export const dashboardColors = Object.freeze({
  neutral: "#7A7A7A4D",
  pvLow: "#A8DDB5",
  pv: "#2F8F5B",
  pvDark: "#1B5E20",
  pvLight: "#73BF69",
  pvForecast: "#2F8F5B",
  grid: "#E0B400",
  gridFeedLow: "#F8E7A1",
  gridImport: "#E0B400",
  gridImportHigh: "#C98200",
  gridImportDanger: "#B85C2A",
  feedIn: "#F8E7A1",
  storage: "#3274D9",
  storageChargeLow: "#A8CBFF",
  storageCharge: "#73A7F2",
  storageDischarge: "#3274D9",
  storageDark: "#1F60A8",
  storageDanger: "#174A7C",
  homeLight: "#CDB6F6",
  home: "#9F7AEA",
  homeHigh: "#7C5BD6",
  homeDanger: "#A44C9C",
  loadpointLight: "#FFC078",
  loadpoint: "#FF9830",
  loadpointHigh: "#E66A00",
  loadpointDanger: "#B84A1C",
  danger: "red",
  warning: "orange",
  caution: "yellow",
  success: "green",
  selfConsumptionLow: "#F5D8F1",
  selfConsumptionMid: "#DFA8D8",
  selfConsumption: "#A44C9C",
  selfConsumptionDark: "#7C3A75",
  autarkyLow: "#D8F3DC",
  autarkyMid: "#A8DDB5",
  autarky: "#73BF69",
  autarkyDark: "#2F8F5B",
  storageSocLow: "#D6E8FF",
  storageSocMid: "#A8CBFF",
  storageSoc: "#73A7F2",
  storageSocDark: "#3274D9",
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
