import fs from "node:fs";
import path from "node:path";
import {
  buildUid,
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

loadEnvFile(parseArg("env", ".env"));

function defaultSourceFromConfig() {
  const configPath = path.join(process.cwd(), "dashboards", "localization", "languages.json");
  if (!fs.existsSync(configPath)) {
    return "dashboards/de";
  }

  const parsed = JSON.parse(fs.readFileSync(configPath, "utf8"));
  const sourceLanguage = String(parsed.sourceLanguage || "de").trim();
  const targetLanguages = Array.isArray(parsed.targetLanguages)
    ? parsed.targetLanguages.map((x) => String(x).trim()).filter(Boolean)
    : [];

  const firstTarget = targetLanguages.find(Boolean) || sourceLanguage;
  return `dashboards/${firstTarget}`;
}

const baseUrl = requireEnv("GRAFANA_URL");
const token = requireEnv("GRAFANA_API_TOKEN");
const source = parseArg("source", defaultSourceFromConfig());
const tag = sanitizeTag(parseArg("tag", path.basename(path.resolve(source))));
const folderUid = optionalEnv("GRAFANA_TEST_FOLDER_UID", "evcc-l10n-test");
const folderTitle = optionalEnv("GRAFANA_TEST_FOLDER_TITLE", "EVCC Localization Test");
const manifestOut = parseArg("manifest", `tests/artifacts/import-manifest-${tag}.json`);
const titlePrefix = optionalEnv("GRAFANA_DASHBOARD_TITLE_PREFIX", "");

const legacyAggUid = optionalEnv("GRAFANA_DS_EVCC_AGGREGRATIONS_UID", "");
const canonicalAggUid = optionalEnv("GRAFANA_DS_EVCC_AGGREGATIONS_UID", "");
if (legacyAggUid && !canonicalAggUid) {
  console.warn("WARN using legacy env var GRAFANA_DS_EVCC_AGGREGRATIONS_UID. Prefer GRAFANA_DS_EVCC_AGGREGATIONS_UID.");
}

const dsMap = {
  DS_EVCC_INFLUXDB: optionalEnv("GRAFANA_DS_EVCC_INFLUXDB_UID", ""),
  DS_EVCC_AGGREGRATIONS: legacyAggUid || canonicalAggUid,
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

async function main() {
  const files = listJsonFiles(source);
  if (!files.length) throw new Error(`No JSON files found in ${source}`);

  await ensureFolder();

  const imported = [];
  for (const file of files) {
    const raw = readJson(file);
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
        message: `Localization test import (${tag})`,
        inputs,
      },
    });

    imported.push({
      sourceFile: path.relative(process.cwd(), file),
      uid: result.uid || dashboard.uid,
      url: result.url,
      status: result.status,
      title: dashboard.title,
    });

    console.log(`Imported: ${path.basename(file)} -> ${dashboard.uid}`);
  }

  const manifest = {
    createdAt: new Date().toISOString(),
    tag,
    source: path.resolve(source),
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
