import path from "node:path";
import { spawnSync } from "node:child_process";
import { loadEnvFile, parseArg, sanitizeTag } from "./_lib.mjs";
import {
  familySourceDir,
  familyTranslationDir,
  parseFamilyArg,
  readLanguagesConfig,
  resolveDashboardFamily,
} from "../_dashboard-family.mjs";

loadEnvFile(parseArg("env", ".env"));

const withScreenshots = parseArg("screenshots", "false") === "true";
const withPrepare = parseArg("prepare", "true") !== "false";
const withFinalCleanup = parseArg("cleanup-final", "false") === "true";
const repoRoot = process.cwd();
const family = resolveDashboardFamily(parseFamilyArg());
const { sourceLanguage, targetLanguages } = readLanguagesConfig(family);
const familyTagPrefix = `${sanitizeTag(family.tagPrefix)}-`;
const sets = [
  {
    tag: `${familyTagPrefix}original-${sanitizeTag(sourceLanguage)}`,
    source: path.relative(repoRoot, familySourceDir(family, sourceLanguage)),
  },
  ...targetLanguages.map((lang) => ({
    tag: `${familyTagPrefix}${sanitizeTag(lang)}-gen`,
    source: path.relative(repoRoot, familyTranslationDir(family, lang)),
  })),
];

function run(script, args = []) {
  const cmd = ["node", script, ...args];
  console.log(`\n$ ${cmd.join(" ")}`);
  const res = spawnSync(cmd[0], cmd.slice(1), { stdio: "inherit" });
  if (res.status !== 0) process.exit(res.status || 1);
}

if (withPrepare) {
  run("scripts/localization/generate-localized-dashboards.mjs", [`--family=${family.name}`]);
  run("scripts/localization/apply-safe-display-translations.mjs", [`--family=${family.name}`]);
}

for (const set of sets) {
  const manifest = `tests/artifacts/import-manifest-${set.tag}.json`;
  if (withScreenshots) {
    run("scripts/test/cleanup-grafana.mjs");
  }
  run("scripts/test/import-dashboards-raw.mjs", [
    `--family=${family.name}`,
    `--source=${set.source}`,
    `--tag=${set.tag}`,
    `--manifest=${manifest}`,
  ]);
  run("scripts/test/smoke-check.mjs", [`--manifest=${manifest}`]);
  if (withScreenshots) {
    run("scripts/test/capture-screenshots.mjs", [`--manifest=${manifest}`]);
  }
}

if (withFinalCleanup) {
  run("scripts/test/cleanup-grafana.mjs");
}

console.log(`\nGrafana dashboard test suite finished for family '${family.name}'.`);
