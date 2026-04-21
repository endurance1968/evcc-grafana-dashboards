/**
 * Script: deploy-manifest.mjs
 * Purpose: Resolve deployable dashboard sets from the shared manifest.
 * Version: 2026.04.20.1
 * Last modified: 2026-04-20
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

export function resolveDashboardSet(manifest, requestedSet = "") {
  const setName = String(requestedSet || manifest?.defaultSet || "default").trim() || "default";
  const files = manifest?.sets?.[setName];
  if (!Array.isArray(files) || files.length === 0) {
    throw new Error(`Dashboard set '${setName}' not found or empty in dashboards/deploy-manifest.json`);
  }
  return {
    setName,
    files: files.map((file) => String(file)),
  };
}

export function manifestFilesUnion(manifest) {
  const files = [];
  const seen = new Set();
  for (const setFiles of Object.values(manifest?.sets || {})) {
    if (!Array.isArray(setFiles)) {
      continue;
    }
    for (const file of setFiles) {
      const normalized = String(file);
      if (seen.has(normalized)) {
        continue;
      }
      seen.add(normalized);
      files.push(normalized);
    }
  }
  return files;
}