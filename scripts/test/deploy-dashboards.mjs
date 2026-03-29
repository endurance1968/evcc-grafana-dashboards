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
import {
  familySourceDir,
  familyTranslationDir,
  parseFamilyArg,
  resolveDashboardFamily,
} from "../_dashboard-family.mjs";

loadEnvFile(parseArg("env", ".env"));

const baseUrl = requireEnv("GRAFANA_URL");
const token = requireEnv("GRAFANA_API_TOKEN");
const family = resolveDashboardFamily(parseFamilyArg());
const language = parseArg("language", "en").trim().toLowerCase();
const variant = parseArg("variant", "orig").trim().toLowerCase();
const sourceOverride = parseArg("source", "").trim();
const sourceMode = parseArg("source-mode", parseArg("sourceMode", sourceOverride ? "local" : "github")).trim().toLowerCase();
const githubRepoArg = parseArg("github-repo", "").trim();
const githubRef = parseArg("github-ref", "main").trim() || "main";
const overridesArg = parseArg("overrides", "").trim();
const purgeLanguage = parseArg("purge", "true") === "true";
const withSmoke = parseArg("smoke", "true") !== "false";
const folderUid = optionalEnv("GRAFANA_TEST_FOLDER_UID", "evcc-test");
const envArg = parseArg("env", ".env");
const repoRoot = process.cwd();

if (!["orig", "generated"].includes(variant)) {
  throw new Error("Invalid --variant. Use orig|generated");
}
if (!["local", "github"].includes(sourceMode)) {
  throw new Error("Invalid --source-mode. Use local|github");
}

const defaultTag = `${family.tagPrefix}-${language}-${variant === "orig" ? "orig" : "gen"}`;
const tag = sanitizeTag(parseArg("tag", defaultTag));
const manifest = parseArg("manifest", `tests/artifacts/import-manifest-${tag}.json`);
const stagedSource = path.resolve(parseArg("staged-source", `tests/artifacts/deploy-source/${tag}`));
const rawGitHubSource = path.resolve(parseArg("raw-source", `tests/artifacts/deploy-source-raw/${tag}`));

function run(script, args = []) {
  const cmd = ["node", script, ...args];
  console.log(`\n$ ${cmd.join(" ")}`);
  const res = spawnSync(cmd[0], cmd.slice(1), { stdio: "inherit" });
  if (res.status !== 0) {
    process.exit(res.status || 1);
  }
}

function listJsonFilesRecursive(inputPath) {
  const resolved = path.resolve(inputPath);
  const stat = fs.statSync(resolved);
  if (stat.isFile()) {
    return resolved.toLowerCase().endsWith(".json") ? [resolved] : [];
  }
  const entries = fs.readdirSync(resolved, { withFileTypes: true });
  const files = [];
  for (const entry of entries) {
    const fullPath = path.join(resolved, entry.name);
    if (entry.isDirectory()) {
      files.push(...listJsonFilesRecursive(fullPath));
    } else if (entry.isFile() && entry.name.toLowerCase().endsWith(".json")) {
      files.push(fullPath);
    }
  }
  return files;
}

function collectSourceLibraryUids(sourceDir) {
  const files = listJsonFilesRecursive(sourceDir);
  const uids = new Set();

  for (const file of files) {
    const raw = JSON.parse(fs.readFileSync(file, "utf8"));
    const elements = raw?.__elements;
    if (!elements || typeof elements !== "object") {
      continue;
    }

    for (const element of Object.values(elements)) {
      if (element && typeof element.uid === "string" && element.uid) {
        uids.add(element.uid);
      }
    }
  }

  return uids;
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

async function purgeForLanguage(sourcePath) {
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
  const sourceLibraryUids = collectSourceLibraryUids(sourcePath);
  const ownedLibraryPanels = libraryElements.filter(
    (el) =>
      el.folderUid === folderUid &&
      typeof el.uid === "string" &&
      sourceLibraryUids.has(el.uid),
  );
  const orphanedInFolder = libraryElements.filter(
    (el) =>
      el.folderUid === folderUid &&
      Number(el?.meta?.connectedDashboards || 0) === 0,
  );

  const toDeleteLibraries = new Map();
  for (const el of ownedLibraryPanels) {
    toDeleteLibraries.set(el.uid, el);
  }
  for (const el of orphanedInFolder) {
    toDeleteLibraries.set(el.uid, el);
  }

  for (const el of toDeleteLibraries.values()) {
    await grafanaApi(`/api/library-elements/${encodeURIComponent(el.uid)}`, {
      method: "DELETE",
      token,
      baseUrl,
    });
    console.log(`Deleted library panel: ${el.uid} | ${el.name}`);
  }

  console.log(
    `Purge done. Dashboards removed=${toDelete.length}, library panels removed=${toDeleteLibraries.size}`,
  );
}

function repoSubdirForSelection() {
  return variant === "orig"
    ? path.posix.join("dashboards", "original", language)
    : path.posix.join("dashboards", "translation", language);
}

function defaultLocalSource() {
  return path.relative(
    repoRoot,
    variant === "orig" ? familySourceDir(family, language) : familyTranslationDir(family, language),
  );
}

function readGitHubRemoteSlug() {
  try {
    const configPath = path.join(repoRoot, ".git", "config");
    if (!fs.existsSync(configPath)) return "";
    const text = fs.readFileSync(configPath, "utf8");
    const match = text.match(/\[remote \"github\"\][\s\S]*?url\s*=\s*(.+)/i);
    if (!match) return "";
    return normalizeGitHubRepo(match[1].trim());
  } catch {
    return "";
  }
}

function normalizeGitHubRepo(input) {
  const value = String(input || "").trim();
  if (!value) return "";
  const ssh = value.match(/^git@github\.com:([^/]+)\/([^/]+?)(?:\.git)?$/i);
  if (ssh) return `${ssh[1]}/${ssh[2]}`;
  const https = value.match(/^https?:\/\/github\.com\/([^/]+)\/([^/]+?)(?:\.git)?(?:\/.*)?$/i);
  if (https) return `${https[1]}/${https[2]}`;
  const simple = value.match(/^([^/]+)\/([^/]+)$/);
  if (simple) return `${simple[1]}/${simple[2].replace(/\.git$/i, "")}`;
  throw new Error(`Unsupported github repo format: ${input}`);
}

async function fetchJson(url, headers = {}) {
  const res = await fetch(url, { headers: { Accept: "application/json", ...headers } });
  const text = await res.text();
  let data;
  try {
    data = JSON.parse(text);
  } catch {
    data = text;
  }
  if (!res.ok) {
    throw new Error(`GET ${url} failed (${res.status}): ${typeof data === "string" ? data : JSON.stringify(data)}`);
  }
  return data;
}

async function fetchText(url, headers = {}) {
  const res = await fetch(url, { headers });
  const text = await res.text();
  if (!res.ok) {
    throw new Error(`GET ${url} failed (${res.status}): ${text}`);
  }
  return text;
}

async function populateFromGitHub(targetDir, repoSlug, ref, subPath) {
  fs.rmSync(targetDir, { recursive: true, force: true });
  fs.mkdirSync(targetDir, { recursive: true });
  const ghToken = optionalEnv("GITHUB_TOKEN", "");
  const headers = ghToken ? { Authorization: `Bearer ${ghToken}` } : {};
  const queue = [subPath.replace(/\\/g, "/").replace(/^\/+/, "")];
  while (queue.length) {
    const current = queue.shift();
    const apiUrl = `https://api.github.com/repos/${repoSlug}/contents/${current}?ref=${encodeURIComponent(ref)}`;
    const entries = await fetchJson(apiUrl, headers);
    const list = Array.isArray(entries) ? entries : [entries];
    for (const entry of list) {
      if (entry.type === "dir") {
        queue.push(entry.path);
        continue;
      }
      if (entry.type !== "file") continue;
      if (!entry.name.toLowerCase().endsWith(".json") && entry.name !== "README.md") continue;
      const text = await fetchText(entry.download_url, headers);
      const rel = entry.path.slice(subPath.length).replace(/^\/+/, "") || entry.name;
      const out = path.join(targetDir, rel);
      fs.mkdirSync(path.dirname(out), { recursive: true });
      fs.writeFileSync(out, text, "utf8");
    }
  }
}

function resolveOverridesPath() {
  if (overridesArg.toLowerCase() === "none") {
    return "";
  }
  if (overridesArg) {
    return path.resolve(overridesArg);
  }
  const local = path.resolve("scripts/test/deploy-overrides.local.json");
  if (fs.existsSync(local)) return local;
  const fallback = path.resolve(`scripts/test/deploy-overrides.${family.name}.default.json`);
  if (fs.existsSync(fallback)) return fallback;
  return "";
}

function ensureColorProperty(properties, fixedColor) {
  const existing = properties.find((prop) => prop?.id === "color");
  if (existing) {
    existing.value = { fixedColor, mode: "fixed" };
    return;
  }
  properties.push({ id: "color", value: { fixedColor, mode: "fixed" } });
}

function applyColorOverrides(node, colorMap) {
  if (!node || typeof node !== "object") return;
  if (Array.isArray(node)) {
    for (const item of node) applyColorOverrides(item, colorMap);
    return;
  }

  const overrides = node?.fieldConfig?.overrides;
  if (Array.isArray(overrides)) {
    for (const override of overrides) {
      const name = override?.matcher?.id === "byName" ? override?.matcher?.options : "";
      if (!name || !(name in colorMap)) continue;
      override.properties ||= [];
      ensureColorProperty(override.properties, colorMap[name]);
    }
  }

  for (const value of Object.values(node)) {
    applyColorOverrides(value, colorMap);
  }
}

function applyVariableDefaults(raw, variableMap) {
  const list = raw?.templating?.list;
  if (!Array.isArray(list)) return;
  for (const variable of list) {
    const desired = variableMap?.[variable?.name];
    if (desired === undefined) continue;
    variable.current = {
      selected: desired === "$__all",
      text: desired === "$__all" ? "All" : desired,
      value: desired,
    };
    if (Array.isArray(variable.options)) {
      for (const option of variable.options) {
        option.selected = option?.value === desired;
      }
    }
  }
}

function applyOverridesToDashboard(raw, overrides) {
  if (!overrides || typeof overrides !== "object") return raw;
  const clone = JSON.parse(JSON.stringify(raw));
  if (overrides.variables) applyVariableDefaults(clone, overrides.variables);
  if (overrides.colors) applyColorOverrides(clone, overrides.colors);
  return clone;
}

function stageDashboards(sourceInput, targetDir, overridesPath) {
  fs.rmSync(targetDir, { recursive: true, force: true });
  fs.mkdirSync(targetDir, { recursive: true });
  const files = listJsonFilesRecursive(sourceInput);
  const sourceRoot = fs.statSync(path.resolve(sourceInput)).isFile()
    ? path.dirname(path.resolve(sourceInput))
    : path.resolve(sourceInput);
  const overrides = overridesPath ? JSON.parse(fs.readFileSync(overridesPath, "utf8")) : null;

  for (const file of files) {
    const raw = JSON.parse(fs.readFileSync(file, "utf8"));
    const patched = applyOverridesToDashboard(raw, overrides);
    const rel = path.relative(sourceRoot, file);
    const out = path.join(targetDir, rel);
    fs.mkdirSync(path.dirname(out), { recursive: true });
    fs.writeFileSync(out, `${JSON.stringify(patched, null, 2)}\n`, "utf8");
  }
  const sourceReadme = path.join(sourceRoot, "README.md");
  if (fs.existsSync(sourceReadme)) {
    fs.copyFileSync(sourceReadme, path.join(targetDir, "README.md"));
  }
}

async function resolveRawSource() {
  const relativeSource = sourceOverride || repoSubdirForSelection();
  if (sourceMode === "github") {
    const repoSlug = normalizeGitHubRepo(githubRepoArg || readGitHubRemoteSlug());
    if (!repoSlug) {
      throw new Error("No GitHub repo configured. Use --github-repo=<owner/repo> or configure git remote 'github'.");
    }
    await populateFromGitHub(rawGitHubSource, repoSlug, githubRef, relativeSource);
    return { rawSource: rawGitHubSource, sourceLabel: `github:${repoSlug}@${githubRef}/${relativeSource}` };
  }

  const localInput = path.resolve(sourceOverride || defaultLocalSource());
  if (!fs.existsSync(localInput)) {
    throw new Error(`Local source not found: ${localInput}`);
  }
  return { rawSource: localInput, sourceLabel: path.relative(repoRoot, localInput) };
}

async function main() {
  if (!language) {
    throw new Error("Missing --language=<code>");
  }

  const overridesPath = resolveOverridesPath();
  const { rawSource, sourceLabel } = await resolveRawSource();
  stageDashboards(rawSource, stagedSource, overridesPath);

  if (purgeLanguage) {
    await purgeForLanguage(stagedSource);
  }

  run("scripts/test/import-dashboards-raw.mjs", [
    `--env=${envArg}`,
    `--family=${family.name}`,
    `--source=${stagedSource}`,
    `--tag=${tag}`,
    `--manifest=${manifest}`,
  ]);

  if (withSmoke) {
    run("scripts/test/smoke-check.mjs", [
      `--env=${envArg}`,
      `--manifest=${manifest}`,
    ]);
  }

  console.log(
    `\nDashboard deploy finished for family='${family.name}', language='${language}' (variant='${variant}', tag='${tag}', source='${sourceLabel}', overrides='${overridesPath || "none"}').`,
  );
}

main().catch((err) => {
  console.error(err.message || err);
  process.exit(1);
});
