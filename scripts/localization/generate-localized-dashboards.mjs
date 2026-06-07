/**
 * Script: generate-localized-dashboards.mjs
 * Purpose: Renders localized dashboard JSON files from dashboards/original by using the language mappings.
 * Version: 2026.06.07.1
 * Last modified: 2026-06-07
 */
import fs from "node:fs";
import path from "node:path";
import {
  familyMappingPath,
  portableRelative,
  familySourceDir,
  familyTranslationDir,
  readLanguagesConfig,
  resolveDashboardFamily,
} from "../helper/_dashboard-family.mjs";

const repoRoot = process.cwd();
const family = resolveDashboardFamily();

const translatableKeys = new Set([
  "title",
  "description",
  "label",
  "name",
  "text",
  "content",
  "displayName",
  "legendFormat",
  "emptyMessage",
]);

function collectJsonFiles(dirPath) {
  const entries = fs.readdirSync(dirPath, { withFileTypes: true });
  const files = [];
  for (const entry of entries) {
    const fullPath = path.join(dirPath, entry.name);
    if (entry.isDirectory()) {
      files.push(...collectJsonFiles(fullPath));
    } else if (entry.isFile() && entry.name.toLowerCase().endsWith(".json")) {
      files.push(fullPath);
    }
  }
  return files;
}

function ensureDir(dirPath) {
  fs.mkdirSync(dirPath, { recursive: true });
}

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, "utf8"));
}

function writeJson(filePath, jsonData) {
  const content = `${JSON.stringify(jsonData, null, 2)}\n`;
  const tmpPath = `${filePath}.tmp-${process.pid}`;
  fs.writeFileSync(tmpPath, content, "utf8");
  fs.rmSync(filePath, { force: true });
  fs.renameSync(tmpPath, filePath);
}

function readMapping(sourceLanguage, targetLanguage) {
  const filePath = familyMappingPath(family, sourceLanguage, targetLanguage);
  if (!fs.existsSync(filePath)) {
    return { exact: {}, contains: [] };
  }
  const parsed = readJson(filePath);
  return {
    exact: parsed.exact ?? {},
    contains: Array.isArray(parsed.contains) ? parsed.contains : [],
  };
}

function translateString(input, mapping) {
  if (Object.hasOwn(mapping.exact, input)) {
    return mapping.exact[input];
  }

  let output = input;
  for (const pair of mapping.contains) {
    if (!pair || typeof pair.from !== "string" || typeof pair.to !== "string") {
      continue;
    }
    output = output.split(pair.from).join(pair.to);
  }
  return output;
}

function translatePromQlSeriesLabels(input, mapping) {
  return input.replace(/("(?:series|title)"\s*,\s*")([^"\n]+)(")/g, (match, prefix, label, suffix) => {
    return prefix + translateString(label, mapping) + suffix;
  });
}

function translateJsonNode(node, mapping) {
  if (Array.isArray(node)) {
    return node.map((item) => translateJsonNode(item, mapping));
  }

  if (node && typeof node === "object") {
    const result = {};
    for (const [key, value] of Object.entries(node)) {
      const isSafeName = key !== "name" || (typeof value === "string" && value.startsWith("EVCC:"));
      const isPropertyValueForTranslatableId =
        key === "value" && typeof node.id === "string" && translatableKeys.has(node.id);

      if (
        typeof value === "string" &&
        ((translatableKeys.has(key) && isSafeName) || isPropertyValueForTranslatableId)
      ) {
        result[key] = translateString(value, mapping);
      } else if (key === "expr" && typeof value === "string") {
        result[key] = translatePromQlSeriesLabels(value, mapping);
      } else {
        result[key] = translateJsonNode(value, mapping);
      }
    }
    return result;
  }

  return node;
}

function grafanaTabSlug(title) {
  return String(title || "")
    .normalize("NFKD")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function stabilizeTabTitle(sourceTitle, localizedTitle, seenSlugs) {
  const localizedSlug = grafanaTabSlug(localizedTitle);
  if (localizedSlug && !seenSlugs.has(localizedSlug)) {
    seenSlugs.add(localizedSlug);
    return localizedTitle;
  }

  const sourceSlug = grafanaTabSlug(sourceTitle);
  const fallbackBase =
    sourceTitle && sourceTitle !== localizedTitle
      ? `${sourceTitle} - ${localizedTitle}`
      : `${localizedTitle || sourceTitle || "Tab"} ${seenSlugs.size + 1}`;
  let fallback = fallbackBase;
  let fallbackSlug = grafanaTabSlug(fallback);
  let suffix = 2;

  while (!fallbackSlug || seenSlugs.has(fallbackSlug)) {
    fallback = sourceSlug ? `${sourceTitle} ${suffix} - ${localizedTitle}` : `${fallbackBase} ${suffix}`;
    fallbackSlug = grafanaTabSlug(fallback);
    suffix += 1;
  }

  seenSlugs.add(fallbackSlug);
  return fallback;
}

function topLevelTabSlugMap(sourceDashboard, localizedDashboard) {
  const sourceTabs = sourceDashboard?.spec?.layout?.spec?.tabs || [];
  const localizedTabs = localizedDashboard?.spec?.layout?.spec?.tabs || [];
  const out = new Map();
  for (let i = 0; i < Math.min(sourceTabs.length, localizedTabs.length); i += 1) {
    const sourceSlug = grafanaTabSlug(sourceTabs[i]?.spec?.title);
    const localizedSlug = grafanaTabSlug(localizedTabs[i]?.spec?.title);
    if (sourceSlug && localizedSlug) {
      out.set(sourceSlug, localizedSlug);
    }
  }
  return out;
}

function localizeTabUrlParams(node, tabSlugMap) {
  if (!tabSlugMap || tabSlugMap.size === 0) {
    return;
  }

  if (Array.isArray(node)) {
    for (const item of node) {
      localizeTabUrlParams(item, tabSlugMap);
    }
    return;
  }

  if (!node || typeof node !== "object") {
    return;
  }

  for (const [key, value] of Object.entries(node)) {
    if (key === "url" && typeof value === "string" && value.includes("dtab=")) {
      node[key] = value.replace(/([?&]dtab=)([a-z0-9-]+)/g, (match, prefix, slug) => {
        return `${prefix}${tabSlugMap.get(slug) || slug}`;
      });
      continue;
    }
    localizeTabUrlParams(value, tabSlugMap);
  }
}
function stabilizeLocalizedTabTitles(sourceNode, localizedNode) {
  if (Array.isArray(sourceNode) && Array.isArray(localizedNode)) {
    for (let i = 0; i < Math.min(sourceNode.length, localizedNode.length); i += 1) {
      stabilizeLocalizedTabTitles(sourceNode[i], localizedNode[i]);
    }
    return;
  }

  if (!sourceNode || !localizedNode || typeof sourceNode !== "object" || typeof localizedNode !== "object") {
    return;
  }

  if (
    sourceNode.kind === "TabsLayout" &&
    localizedNode.kind === "TabsLayout" &&
    Array.isArray(sourceNode.spec?.tabs) &&
    Array.isArray(localizedNode.spec?.tabs)
  ) {
    const seenSlugs = new Set();
    for (let i = 0; i < Math.min(sourceNode.spec.tabs.length, localizedNode.spec.tabs.length); i += 1) {
      const sourceTab = sourceNode.spec.tabs[i];
      const localizedTab = localizedNode.spec.tabs[i];
      if (typeof localizedTab?.spec?.title === "string") {
        localizedTab.spec.title = stabilizeTabTitle(sourceTab?.spec?.title, localizedTab.spec.title, seenSlugs);
      }
      stabilizeLocalizedTabTitles(sourceTab?.spec?.layout, localizedTab?.spec?.layout);
    }
    return;
  }

  for (const [key, value] of Object.entries(sourceNode)) {
    if (Object.hasOwn(localizedNode, key)) {
      stabilizeLocalizedTabTitles(value, localizedNode[key]);
    }
  }
}

function main() {
  const { sourceLanguage, targetLanguages } = readLanguagesConfig(family);
  const sourceDir = familySourceDir(family, sourceLanguage);

  if (!fs.existsSync(sourceDir)) {
    throw new Error(`Source directory does not exist: ${sourceDir}`);
  }

  const files = collectJsonFiles(sourceDir);
  const mappingCache = new Map();

  for (const targetLanguage of targetLanguages) {
    const outDir = familyTranslationDir(family, targetLanguage);
    ensureDir(outDir);

    const mapping =
      targetLanguage === sourceLanguage
        ? { exact: {}, contains: [] }
        : (mappingCache.get(targetLanguage) || readMapping(sourceLanguage, targetLanguage));

    mappingCache.set(targetLanguage, mapping);

    const detailsSourceFile = files.find((sourceFile) => path.basename(sourceFile) === "VM_EVCC_Today-Details.json");
    const sourceDetailsJson = detailsSourceFile ? readJson(detailsSourceFile) : null;
    const localizedDetailsJson = sourceDetailsJson
      ? (targetLanguage === sourceLanguage ? sourceDetailsJson : translateJsonNode(sourceDetailsJson, mapping))
      : null;
    if (sourceDetailsJson && localizedDetailsJson && targetLanguage !== sourceLanguage) {
      stabilizeLocalizedTabTitles(sourceDetailsJson, localizedDetailsJson);
    }
    const tabSlugMap = topLevelTabSlugMap(sourceDetailsJson, localizedDetailsJson);

    let count = 0;
    for (const sourceFile of files) {
      const relative = portableRelative(sourceDir, sourceFile);
      const targetFile = path.join(outDir, relative);
      ensureDir(path.dirname(targetFile));

      const sourceJson = readJson(sourceFile);
      const localizedJson =
        targetLanguage === sourceLanguage
          ? sourceJson
          : translateJsonNode(sourceJson, mapping);

      if (targetLanguage !== sourceLanguage) {
        stabilizeLocalizedTabTitles(sourceJson, localizedJson);
      }
      localizeTabUrlParams(localizedJson, tabSlugMap);

      writeJson(targetFile, localizedJson);
      count += 1;
    }

    console.log(`Generated ${count} dashboard files for '${targetLanguage}'.`);
    console.log(`Output: ${portableRelative(repoRoot, outDir)}`);
    if (targetLanguage !== sourceLanguage) {
      console.log(
        `Mapping: ${portableRelative(repoRoot, familyMappingPath(family, sourceLanguage, targetLanguage))}`,
      );
    }
  }
}

main();
