import fs from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";
import {
  grafanaApi,
  loadEnvFile,
  optionalEnv,
  parseArg,
  requireEnv,
  sanitizeTag,
} from "./_lib.mjs";

loadEnvFile(parseArg("env", ".env"));

const baseUrl = requireEnv("GRAFANA_URL");
const token = requireEnv("GRAFANA_API_TOKEN");
const language = parseArg("language", "de").trim().toLowerCase();
const variant = parseArg("variant", "generated").trim().toLowerCase();
const sourceOverride = parseArg("source", "").trim();
const purgeLanguage = parseArg("purge", "false") === "true";
const withSmoke = parseArg("smoke", "true") !== "false";
const folderUid = optionalEnv("GRAFANA_TEST_FOLDER_UID", "evcc-l10n-test");
const envArg = parseArg("env", ".env");

if (!["orig", "generated"].includes(variant)) {
  throw new Error("Invalid --variant. Use orig|generated");
}

const source =
  sourceOverride ||
  (variant === "orig"
    ? `dashboards/original/${language}`
    : `dashboards/translation/${language}`);
const defaultTag = `${language}-${variant === "orig" ? "orig" : "gen"}`;
const tag = sanitizeTag(parseArg("tag", defaultTag));
const manifest = parseArg("manifest", `tests/artifacts/import-manifest-${tag}.json`);

function run(script, args = []) {
  const cmd = ["node", script, ...args];
  console.log(`\n$ ${cmd.join(" ")}`);
  const res = spawnSync(cmd[0], cmd.slice(1), { stdio: "inherit" });
  if (res.status !== 0) {
    process.exit(res.status || 1);
  }
}

async function listDashboardsInFolder() {
  const query = `/api/search?type=dash-db&limit=5000&folderUIDs=${encodeURIComponent(folderUid)}`;
  return await grafanaApi(query, { token, baseUrl });
}

async function listAllLibraryElements() {
  const all = [];
  let page = 1;

  while (true) {
    const res = await grafanaApi(`/api/library-elements?page=${page}&perPage=500`, {
      token,
      baseUrl,
    });
    const chunk = res?.result?.elements || [];
    all.push(...chunk);
    if (!chunk.length || chunk.length < 500) {
      break;
    }
    page += 1;
  }

  return all;
}

function matchesLanguageDashboard(item) {
  const uidPrefix = `${tag}-`;
  const titlePrefix = `[${tag.toUpperCase()}] `;
  return (
    (typeof item.uid === "string" && item.uid.startsWith(uidPrefix)) ||
    (typeof item.title === "string" && item.title.startsWith(titlePrefix))
  );
}

async function purgeForLanguage() {
  console.log(`Purging dashboards/panels for language tag '${tag}' in folder '${folderUid}'...`);

  const dashboards = await listDashboardsInFolder();
  const toDelete = dashboards.filter(matchesLanguageDashboard);

  for (const d of toDelete) {
    await grafanaApi(`/api/dashboards/uid/${encodeURIComponent(d.uid)}`, {
      method: "DELETE",
      token,
      baseUrl,
    });
    console.log(`Deleted dashboard: ${d.uid} | ${d.title}`);
  }

  const libraryElements = await listAllLibraryElements();
  const orphanedInFolder = libraryElements.filter(
    (el) =>
      el.folderUid === folderUid &&
      Number(el?.meta?.connectedDashboards || 0) === 0,
  );

  for (const el of orphanedInFolder) {
    await grafanaApi(`/api/library-elements/${encodeURIComponent(el.uid)}`, {
      method: "DELETE",
      token,
      baseUrl,
    });
    console.log(`Deleted orphan library panel: ${el.uid} | ${el.name}`);
  }

  console.log(
    `Purge done. Dashboards removed=${toDelete.length}, orphan library panels removed=${orphanedInFolder.length}`,
  );
}

async function main() {
  if (!language) {
    throw new Error("Missing --language=<code>");
  }
  if (!fs.existsSync(path.resolve(source))) {
    throw new Error(`Source path not found: ${source}`);
  }

  if (purgeLanguage) {
    await purgeForLanguage();
  }

  run("scripts/test/import-dashboards-raw.mjs", [
    `--env=${envArg}`,
    `--source=${source}`,
    `--tag=${tag}`,
    `--manifest=${manifest}`,
  ]);

  if (withSmoke) {
    run("scripts/test/smoke-check.mjs", [
      `--env=${envArg}`,
      `--manifest=${manifest}`,
    ]);
  }

  console.log(`\nDashboard deploy finished for '${language}' (variant='${variant}', tag='${tag}', source='${source}').`);
}

main().catch((err) => {
  console.error(err.message || err);
  process.exit(1);
});
