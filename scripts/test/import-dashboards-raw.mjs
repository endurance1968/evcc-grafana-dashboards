/**
 * Script: import-dashboards-raw.mjs
 * Purpose: Import raw dashboard JSON files into Grafana and emit an import manifest.
 * Version: 2026.04.20.2
 * Last modified: 2026-04-20
 */
import fs from "node:fs";
import path from "node:path";
import {
  buildUid,
  deepReplaceDataSourcePlaceholders,
  grafanaApi,
  loadEnvFile,
  optionalEnv,
  parseArg,
  readJson,
  requireEnv,
  sanitizeTag,
  writeJson,
} from "./_lib.mjs";
import {
  familyTranslationDir,
  readLanguagesConfig,
  resolveDashboardFamily,
} from "../helper/_dashboard-family.mjs";
import {
  readDeployManifest,
  resolveDashboardSet,
} from "../helper/deploy-manifest.mjs";
import {
  dashboardTitle,
  dashboardUid,
  isV2Dashboard,
} from "../helper/dashboard-schema.mjs";

loadEnvFile(parseArg("env", ".env"));
const family = resolveDashboardFamily();

function defaultSourceFromConfig() {
  const { sourceLanguage, targetLanguages } = readLanguagesConfig(family);
  const firstTarget = targetLanguages.find(Boolean) || sourceLanguage;
  return path.relative(process.cwd(), familyTranslationDir(family, firstTarget));
}

const baseUrl = requireEnv("GRAFANA_URL");
const token = requireEnv("GRAFANA_API_TOKEN");
const source = parseArg("source", defaultSourceFromConfig());
const dashboardSetArg = parseArg("dashboard-set", optionalEnv("DASHBOARD_SET", "")).trim();
const tag = sanitizeTag(parseArg("tag", path.basename(path.resolve(source))));
const folderUid = optionalEnv("GRAFANA_TEST_FOLDER_UID", "evcc-test");
const folderTitle = optionalEnv("GRAFANA_TEST_FOLDER_TITLE", "EVCC Test");
const manifestOut = parseArg("manifest", `tests/artifacts/import-manifest-${tag}.json`);
const titlePrefix = optionalEnv("GRAFANA_DASHBOARD_TITLE_PREFIX", "");

const dsMap = {
  "DS_VM-EVCC": optionalEnv("GRAFANA_DS_VM_EVCC_UID", "vm-evcc"),
};

function buildInputs(raw) {
  if (isV2Dashboard(raw)) {
    return [];
  }

  const list = Array.isArray(raw.__inputs) ? raw.__inputs : [];
  const out = [];

  for (const input of list) {
    if (!input || !input.name || !input.type) {
      continue;
    }

    if (input.type === "datasource") {
      const mappedUid = dsMap[input.name] || (input.pluginId === "__expr__" ? "__expr__" : "");
      if (!mappedUid) {
        throw new Error(`Missing datasource UID for input ${input.name}`);
      }
      out.push({
        name: input.name,
        type: input.type,
        pluginId: input.pluginId,
        value: mappedUid,
      });
      continue;
    }

    out.push({
      name: input.name,
      type: input.type,
      value: input.value ?? "",
    });
  }

  return out;
}

function resolveSourceFiles(inputPath) {
  const resolved = path.resolve(inputPath);
  const stat = fs.statSync(resolved);
  if (stat.isFile()) {
    return {
      dashboardSet: "single-file",
      files: [resolved],
    };
  }

  const { setName, files } = resolveDashboardSet(readDeployManifest(process.cwd()), dashboardSetArg);
  const resolvedFiles = files.map((fileName) => path.join(resolved, fileName));
  const missing = resolvedFiles.filter((file) => !fs.existsSync(file));
  if (missing.length > 0) {
    throw new Error(
      `Dashboard set '${setName}' is missing file(s) in ${inputPath}: ${missing.map((file) => path.basename(file)).join(", ")}`,
    );
  }

  return {
    dashboardSet: setName,
    files: resolvedFiles,
  };
}

async function ensureFolder() {
  const existing = await grafanaApi(`/api/folders/${folderUid}`, { token, baseUrl, allow404: true });
  if (existing) {
    return;
  }

  await grafanaApi("/api/folders", {
    method: "POST",
    token,
    baseUrl,
    body: {
      uid: folderUid,
      title: folderTitle,
    },
  });
}

function namespaceLibraryUid(uid, name = "") {
  return buildUid(tag, uid || name || "library");
}

function namespaceLibraryName(name = "", uid = "") {
  const prefix = titlePrefix ? `${titlePrefix.trim()} ` : `[${tag.toUpperCase()}] `;
  return `${prefix}${name || uid || "Library panel"}`;
}

function namespaceLibraryRefs(node) {
  if (Array.isArray(node)) {
    for (const item of node) {
      namespaceLibraryRefs(item);
    }
    return;
  }

  if (!node || typeof node !== "object") {
    return;
  }

  if (node.libraryPanel && typeof node.libraryPanel === "object") {
    node.libraryPanel = {
      ...node.libraryPanel,
      uid: namespaceLibraryUid(node.libraryPanel.uid, node.libraryPanel.name),
      name: namespaceLibraryName(node.libraryPanel.name, node.libraryPanel.uid),
    };
  }

  for (const value of Object.values(node)) {
    namespaceLibraryRefs(value);
  }
}

function prepareClassicDashboard(raw, filePath) {
  const dashboard = JSON.parse(JSON.stringify(raw));
  const sourceUid = dashboard.uid || path.basename(filePath, ".json");
  dashboard.uid = buildUid(tag, sourceUid, path.basename(filePath, ".json"));

  const prefix = titlePrefix ? `${titlePrefix.trim()} ` : `[${tag.toUpperCase()}] `;
  dashboard.title = `${prefix}${dashboard.title || path.basename(filePath, ".json")}`;
  namespaceLibraryRefs(dashboard);
  return dashboard;
}

function prepareV2Dashboard(raw, filePath) {
  const dashboard = JSON.parse(JSON.stringify(raw));
  const sourceUid = dashboardUid(dashboard) || path.basename(filePath, ".json");
  const prefix = titlePrefix ? `${titlePrefix.trim()} ` : `[${tag.toUpperCase()}] `;

  dashboard.metadata ||= {};
  dashboard.metadata.name = buildUid(tag, sourceUid, path.basename(filePath, ".json"));
  dashboard.metadata.annotations = {
    ...(dashboard.metadata.annotations || {}),
    "grafana.app/folder": folderUid,
  };
  dashboard.spec ||= {};
  dashboard.spec.title = `${prefix}${dashboardTitle(dashboard) || path.basename(filePath, ".json")}`;
  return dashboard;
}

function prepareDashboard(raw, filePath) {
  return isV2Dashboard(raw) ? prepareV2Dashboard(raw, filePath) : prepareClassicDashboard(raw, filePath);
}

function collectLibraryElements(rawDashboards) {
  const byUid = new Map();

  for (const raw of rawDashboards) {
    if (isV2Dashboard(raw)) {
      continue;
    }
    const elements = raw?.__elements;
    if (!elements || typeof elements !== "object") {
      continue;
    }

    for (const element of Object.values(elements)) {
      if (!element || typeof element.uid !== "string" || !element.uid) {
        continue;
      }
      const cloned = JSON.parse(JSON.stringify(element));
      const namespacedUid = namespaceLibraryUid(cloned.uid, cloned.name);
      cloned.uid = namespacedUid;
      cloned.name = namespaceLibraryName(cloned.name, element.uid);
      byUid.set(namespacedUid, cloned);
    }
  }

  return [...byUid.values()].sort((a, b) => a.uid.localeCompare(b.uid));
}

async function ensureLibraryElements(rawDashboards) {
  const elements = collectLibraryElements(rawDashboards);
  if (!elements.length) {
    return;
  }

  for (const element of elements) {
    const body = {
      uid: element.uid,
      name: element.name,
      kind: element.kind ?? 1,
      folderUid,
      model: deepReplaceDataSourcePlaceholders(element.model, dsMap),
    };

    await grafanaApi("/api/library-elements", {
      method: "POST",
      token,
      baseUrl,
      body,
    });

    console.log(`Imported library panel: ${element.name} -> ${element.uid}`);
  }
}

async function importClassicDashboard(dashboard, inputs) {
  const result = await grafanaApi("/api/dashboards/import", {
    method: "POST",
    token,
    baseUrl,
    body: {
      dashboard,
      folderUid,
      overwrite: true,
      message: `Dashboard test import (${tag})`,
      inputs,
    },
  });

  return {
    uid: result.uid || dashboard.uid,
    url: result.importedUrl || result.url || "",
    status: result.status,
    title: dashboard.title,
  };
}

async function importV2Dashboard(dashboard) {
  const uid = dashboardUid(dashboard);
  const pathV2 = `/apis/dashboard.grafana.app/v2/namespaces/default/dashboards/${encodeURIComponent(uid)}`;
  const existing = await grafanaApi(pathV2, { token, baseUrl, allow404: true });
  if (existing?.metadata?.resourceVersion) {
    dashboard.metadata = {
      ...(dashboard.metadata || {}),
      resourceVersion: existing.metadata.resourceVersion,
    };
  }

  const result = existing
    ? await grafanaApi(pathV2, {
        method: "PUT",
        token,
        baseUrl,
        body: dashboard,
      })
    : await grafanaApi("/apis/dashboard.grafana.app/v2/namespaces/default/dashboards", {
        method: "POST",
        token,
        baseUrl,
        body: dashboard,
      });

  return {
    uid,
    url: result?.metadata?.name || uid,
    status: existing ? "updated" : "created",
    title: dashboardTitle(dashboard),
  };
}

async function main() {
  const { dashboardSet, files } = resolveSourceFiles(source);
  if (!files.length) throw new Error(`No JSON files found in ${source}`);

  await ensureFolder();

  const rawDashboards = files.map((file) => ({
    file,
    raw: readJson(file),
  }));
  await ensureLibraryElements(rawDashboards.map((entry) => entry.raw));

  const imported = [];
  for (const { file, raw } of rawDashboards) {
    const dashboard = prepareDashboard(raw, file);
    const inputs = buildInputs(raw);
    const result = isV2Dashboard(dashboard)
      ? await importV2Dashboard(dashboard)
      : await importClassicDashboard(dashboard, inputs);

    imported.push({
      sourceFile: path.relative(process.cwd(), file),
      uid: result.uid,
      url: result.url,
      status: result.status,
      title: result.title,
    });

    console.log(`Imported: ${path.basename(file)} -> ${result.uid}`);
  }

  const manifest = {
    createdAt: new Date().toISOString(),
    family: family.name,
    tag,
    source: path.relative(process.cwd(), path.resolve(source)),
    dashboardSet,
    grafanaUrl: baseUrl,
    folderUid,
    dashboards: imported,
  };
  writeJson(manifestOut, manifest);
  console.log(`Manifest written: ${manifestOut}`);
}

main().catch((err) => {
  console.error(err.message || err);
  process.exit(1);
});