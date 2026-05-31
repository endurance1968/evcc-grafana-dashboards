/**
 * Script: deploy-manifest.mjs
 * Purpose: Resolve the fixed deployable dashboard file list from the shared manifest.
 * Version: 2026.05.31.2
 * Last modified: 2026-05-31
 */
import fs from "node:fs";
import path from "node:path";

export function deployManifestPath(repoRoot = process.cwd()) {
  return path.join(repoRoot, "dashboards", "deploy-manifest.json");
}

export function readDeployManifest(repoRoot = process.cwd()) {
  const manifestPath = deployManifestPath(repoRoot);
  return JSON.parse(fs.readFileSync(manifestPath, "utf8"));
}

export function resolveDashboardFiles(manifest) {
  const files = manifest?.files;
  if (!Array.isArray(files) || files.length === 0) {
    throw new Error("dashboards/deploy-manifest.json is missing a non-empty files array");
  }
  return files.map((file) => String(file));
}

export function manifestFilesUnion(manifest) {
  return resolveDashboardFiles(manifest);
}
