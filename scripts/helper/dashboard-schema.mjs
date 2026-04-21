/**
 * Script: dashboard-schema.mjs
 * Purpose: Normalize classic Grafana dashboard JSON and Grafana v2 dashboard resources for test and deploy helpers.
 * Version: 2026.04.20.1
 * Last modified: 2026-04-20
 */

export function isV2Dashboard(dashboard) {
  return Boolean(
    dashboard &&
      typeof dashboard === "object" &&
      dashboard.kind === "Dashboard" &&
      String(dashboard.apiVersion || "").startsWith("dashboard.grafana.app/v2"),
  );
}

export function dashboardTitle(dashboard) {
  return isV2Dashboard(dashboard)
    ? String(dashboard?.spec?.title || "")
    : String(dashboard?.title || "");
}

export function dashboardUid(dashboard) {
  return isV2Dashboard(dashboard)
    ? String(dashboard?.metadata?.name || "")
    : String(dashboard?.uid || "");
}

export function dashboardTimeSettings(dashboard) {
  return isV2Dashboard(dashboard)
    ? dashboard?.spec?.timeSettings || {}
    : dashboard?.time || {};
}

export function dashboardLinks(dashboard) {
  return isV2Dashboard(dashboard)
    ? dashboard?.spec?.links || []
    : dashboard?.links || [];
}

export function dashboardVariables(dashboard) {
  return isV2Dashboard(dashboard)
    ? dashboard?.spec?.variables || []
    : dashboard?.templating?.list || [];
}

export function dashboardLayoutKind(dashboard) {
  return isV2Dashboard(dashboard)
    ? String(dashboard?.spec?.layout?.kind || "")
    : "Classic";
}

function normalizeClassicTarget(target) {
  return {
    ...target,
    expr: String(target?.expr || target?.expression || target?.query || ""),
    group: String(target?.datasource?.type || ""),
    datasource: target?.datasource || null,
  };
}

function normalizeV2Target(query) {
  const dataQuery = query?.spec?.query || {};
  return {
    expr: String(dataQuery?.spec?.expr || dataQuery?.spec?.expression || dataQuery?.spec?.query || ""),
    group: String(dataQuery?.group || ""),
    datasource: dataQuery?.datasource || null,
    refId: String(query?.spec?.refId || ""),
    raw: query,
  };
}

function normalizeClassicPanel(panel) {
  return {
    ...panel,
    id: panel?.id,
    title: panel?.title || String(panel?.id || ""),
    type: panel?.type || "",
    targets: Array.isArray(panel?.targets) ? panel.targets.map(normalizeClassicTarget) : [],
    options: panel?.options || {},
    fieldConfig: panel?.fieldConfig || {},
    libraryPanel: Boolean(panel?.libraryPanel),
  };
}

function normalizeV2PanelElement(element) {
  const spec = element?.spec || {};
  const queryGroup = spec?.data?.spec || {};
  return {
    id: spec?.id,
    title: spec?.title || String(spec?.id || ""),
    type: spec?.vizConfig?.group || "",
    targets: Array.isArray(queryGroup?.queries) ? queryGroup.queries.map(normalizeV2Target) : [],
    options: spec?.vizConfig?.spec?.options || {},
    fieldConfig: spec?.vizConfig?.spec?.fieldConfig || {},
    libraryPanel: element?.kind === "LibraryPanel",
    rawElement: element,
  };
}

export function collectDashboardPanels(dashboard) {
  if (isV2Dashboard(dashboard)) {
    return Object.values(dashboard?.spec?.elements || {})
      .filter((element) => element && typeof element === "object" && ["Panel", "LibraryPanel"].includes(element.kind))
      .map(normalizeV2PanelElement);
  }

  const out = [];
  function walk(panels) {
    for (const panel of panels || []) {
      out.push(normalizeClassicPanel(panel));
      walk(panel?.panels);
    }
  }
  walk(dashboard?.panels);
  return out;
}