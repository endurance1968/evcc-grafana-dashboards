/**
 * Script: localization-idempotency-check.mjs
 * Purpose: Verify generated dashboard translations are reproducible from dashboards/original without creating diffs.
 * Version: 2026.04.22.1
 * Last modified: 2026-04-22
 */
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";
import {
  familySourceDir,
  portableRelative,
  familyTranslationDir,
  readLanguagesConfig,
  resolveDashboardFamily,
} from "../helper/_dashboard-family.mjs";

const repoRoot = process.cwd();
const family = resolveDashboardFamily();

function run(command, args) {
  console.log(`$ ${[command, ...args].join(" ")}`);
  const result = spawnSync(command, args, { cwd: repoRoot, stdio: "inherit" });
  if (result.error) {
    throw result.error;
  }
  if (result.status !== 0) {
    throw new Error(`${command} failed with exit code ${result.status}`);
  }
}

function collectJsonFiles(dirPath) {
  if (!fs.existsSync(dirPath)) {
    return [];
  }
  const out = [];
  for (const entry of fs.readdirSync(dirPath, { withFileTypes: true })) {
    const fullPath = path.join(dirPath, entry.name);
    if (entry.isDirectory()) {
      out.push(...collectJsonFiles(fullPath));
    } else if (entry.isFile() && entry.name.toLowerCase().endsWith(".json")) {
      out.push(fullPath);
    }
  }
  return out.sort((a, b) => a.localeCompare(b));
}

function fileHash(filePath) {
  return crypto.createHash("sha256").update(fs.readFileSync(filePath)).digest("hex");
}

function snapshotTranslationFiles() {
  const files = collectJsonFiles(family.translationRoot);
  return new Map(files.map((filePath) => [portableRelative(repoRoot, filePath), fileHash(filePath)]));
}

function changedFiles(before, after) {
  const paths = [...new Set([...before.keys(), ...after.keys()])].sort((a, b) => a.localeCompare(b));
  return paths.filter((filePath) => before.get(filePath) !== after.get(filePath));
}

function canonicalJson(filePath) {
  return JSON.stringify(JSON.parse(fs.readFileSync(filePath, "utf8")));
}

function assertSourceLanguageCopy() {
  const { sourceLanguage } = readLanguagesConfig(family);
  const sourceDir = familySourceDir(family, sourceLanguage);
  const generatedDir = familyTranslationDir(family, sourceLanguage);
  const mismatches = [];

  for (const sourceFile of collectJsonFiles(sourceDir)) {
    const relative = portableRelative(sourceDir, sourceFile);
    const generatedFile = path.join(generatedDir, relative);
    if (!fs.existsSync(generatedFile)) {
      mismatches.push(portableRelative(repoRoot, generatedFile));
      continue;
    }
    if (canonicalJson(sourceFile) !== canonicalJson(generatedFile)) {
      mismatches.push(portableRelative(repoRoot, generatedFile));
    }
  }

  if (mismatches.length > 0) {
    throw new Error(
      `Source language translations are not reproducible copies of originals: ${mismatches.slice(0, 10).join(", ")}`,
    );
  }
}

function main() {
  const before = snapshotTranslationFiles();
  run(process.execPath, ["scripts/localization/generate-localized-dashboards.mjs"]);
  run(process.execPath, ["scripts/localization/apply-safe-display-translations.mjs"]);
  const after = snapshotTranslationFiles();
  const changed = changedFiles(before, after);
  assertSourceLanguageCopy();

  if (changed.length > 0) {
    throw new Error(
      `Localization generation is not idempotent; regenerate and commit these files: ${changed.slice(0, 20).join(", ")}`,
    );
  }

  console.log("Localization idempotency check");
  console.log("==============================");
  console.log("Script:        localization-idempotency-check.mjs");
  console.log("Version:       2026.04.22.1");
  console.log("Last modified: 2026-04-22");
  console.log("");
  console.log("Result");
  console.log("------");
  console.log(`OK: generated translations for '${family.name}' are reproducible and idempotent.`);
}

try {
  main();
} catch (error) {
  console.error(error.message || error);
  process.exit(1);
}
