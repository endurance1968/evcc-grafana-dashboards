/**
 * Script: _dashboard-family.mjs
 * Purpose: Shared helper for resolving the fixed VM dashboard paths, language config, and workflow directories.
 * Version: 2026.04.22.1
 * Last modified: 2026-04-22
 */
import fs from "node:fs";
import path from "node:path";

const repoRoot = process.cwd();

function ensureNoLegacyFamilyArg(argv = process.argv) {
  const legacyArg = argv.find((entry) => entry === "--family" || entry.startsWith("--family="));
  if (legacyArg) {
    throw new Error("The --family option was removed. This repository always uses the VM dashboards.");
  }
}

export function toPortablePath(filePath) {
  return String(filePath).replace(/\\/g, "/");
}

export function portableRelative(fromPath, toPath) {
  return toPortablePath(path.relative(fromPath, toPath));
}

export function resolveDashboardFamily() {
  ensureNoLegacyFamilyArg();
  const dashboardsRoot = path.join(repoRoot, "dashboards");

  return {
    name: "vm",
    tagPrefix: "vm",
    dashboardsRoot,
    originalRoot: path.join(dashboardsRoot, "original"),
    translationRoot: path.join(dashboardsRoot, "translation"),
    localizationRoot: path.join(dashboardsRoot, "localization"),
    languagesConfigPath: path.join(dashboardsRoot, "localization", "languages.json"),
  };
}

export function readLanguagesConfig(family) {
  const fallback = { sourceLanguage: "en", targetLanguages: ["de"] };

  if (!fs.existsSync(family.languagesConfigPath)) {
    return fallback;
  }

  const parsed = JSON.parse(fs.readFileSync(family.languagesConfigPath, "utf8"));
  const sourceLanguage = String(parsed.sourceLanguage || fallback.sourceLanguage).trim();
  const configuredTargets = Array.isArray(parsed.targetLanguages)
    ? parsed.targetLanguages.map((entry) => String(entry).trim()).filter(Boolean)
    : [];

  const targetLanguages = [...new Set(configuredTargets.length ? configuredTargets : [sourceLanguage])];
  if (!targetLanguages.includes(sourceLanguage)) {
    targetLanguages.unshift(sourceLanguage);
  }

  return { sourceLanguage, targetLanguages };
}

export function familySourceDir(family, sourceLanguage) {
  return path.join(family.originalRoot, sourceLanguage);
}

export function familyTranslationDir(family, language) {
  return path.join(family.translationRoot, language);
}

export function familyMappingPath(family, sourceLanguage, targetLanguage) {
  return path.join(family.localizationRoot, `${sourceLanguage}_to_${targetLanguage}.json`);
}

export function familyReportPath(family, sourceLanguage, targetLanguage) {
  return path.join(family.localizationRoot, `missing-${sourceLanguage}_to_${targetLanguage}.exact.json`);
}
