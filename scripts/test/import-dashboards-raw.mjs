import path from "node:path";
import {
  buildUid,
  deepReplaceDataSourcePlaceholders,
  grafanaApi,
  listJsonFiles,
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
  parseFamilyArg,
  readLanguagesConfig,
  resolveDashboardFamily,
} from "../_dashboard-family.mjs";

loadEnvFile(parseArg("env", ".env"));
const family = resolveDashboardFamily(parseFamilyArg());

function defaultSourceFromConfig() {
  const { sourceLanguage, targetLanguages } = readLanguagesConfig(family);
  const firstTarget = targetLanguages.find(Boolean) || sourceLanguage;
  return path.relative(process.cwd(), familyTranslationDir(family, firstTarget));
}

const baseUrl = requireEnv("GRAFANA_URL");
const token = requireEnv("GRAFANA_API_TOKEN");
const source = parseArg("source", defaultSourceFromConfig());
const tag = sanitizeTag(parseArg("tag", path.basename(path.resolve(source))));
const folderUid = optionalEnv("GRAFANA_TEST_FOLDER_UID", "evcc");
const folderTitle = optionalEnv("GRAFANA_TEST_FOLDER_TITLE", "EVCC");
const manifestOut = parseArg("manifest", `tests/artifacts/import-manifest-${tag}.json`);
const titlePrefix = optionalEnv("GRAFANA_DASHBOARD_TITLE_PREFIX", "");

const legacyAggUid = optionalEnv("GRAFANA_DS_EVCC_AGGREGRATIONS_UID", "");
const canonicalAggUid = optionalEnv("GRAFANA_DS_EVCC_AGGREGATIONS_UID", "");
if (legacyAggUid && !canonicalAggUid) {
  console.warn("WARN using legacy env var GRAFANA_DS_EVCC_AGGREGRATIONS_UID. Prefer GRAFANA_DS_EVCC_AGGREGATIONS_UID.");
}

const dsMap =
  family.name === "influx-legacy"
    ? {
        DS_EVCC_INFLUXDB: optionalEnv("GRAFANA_DS_EVCC_INFLUXDB_UID", ""),
        DS_EVCC_AGGREGRATIONS: legacyAggUid || canonicalAggUid,
      }
    : {
        "DS_VM-EVCC": optionalEnv("GRAFANA_DS_VM_EVCC_UID", "vm-evcc"),
      };

function buildInputs(raw) {
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

async function ensureFolder() {
  try {
    await grafanaApi(`/api/folders/${folderUid}`, { token, baseUrl });
    return;
  } catch {
    // create below
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

function prepareDashboard(raw, filePath) {
  const dashboard = JSON.parse(JSON.stringify(raw));
  const sourceUid = dashboard.uid || path.basename(filePath, ".json");
  dashboard.uid = buildUid(tag, sourceUid, path.basename(filePath, ".json"));

  const prefix = titlePrefix ? `${titlePrefix.trim()} ` : `[${tag.toUpperCase()}] `;
  dashboard.title = `${prefix}${dashboard.title || path.basename(filePath, ".json")}`;
  return dashboard;
}

function collectLibraryElements(rawDashboards) {
  const byUid = new Map();

  for (const raw of rawDashboards) {
    const elements = raw?.__elements;
    if (!elements || typeof elements !== "object") {
      continue;
    }

    for (const element of Object.values(elements)) {
      if (!element || typeof element.uid !== "string" || !element.uid) {
        continue;
      }
      byUid.set(element.uid, JSON.parse(JSON.stringify(element)));
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

async function main() {
  const files = listJsonFiles(source);
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

    imported.push({
      sourceFile: path.relative(process.cwd(), file),
      uid: result.uid || dashboard.uid,
      url: result.importedUrl || result.url || "",
      status: result.status,
      title: dashboard.title,
    });

    console.log(`Imported: ${path.basename(file)} -> ${dashboard.uid}`);
  }

  const manifest = {
    createdAt: new Date().toISOString(),
    family: family.name,
    tag,
    source: path.relative(process.cwd(), path.resolve(source)),
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
