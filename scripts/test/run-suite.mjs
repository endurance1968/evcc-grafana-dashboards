import fs from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { loadEnvFile, parseArg, sanitizeTag } from "./_lib.mjs";

loadEnvFile(parseArg("env", ".env"));

const withScreenshots = parseArg("screenshots", "false") === "true";
const repoRoot = process.cwd();
const configPath = path.join(repoRoot, "dashboards", "localization", "languages.json");

function readLanguagesConfig() {
  if (!fs.existsSync(configPath)) {
    return { sourceLanguage: "de", targetLanguages: ["de", "en"] };
  }

  const parsed = JSON.parse(fs.readFileSync(configPath, "utf8"));
  const sourceLanguage = String(parsed.sourceLanguage || "de").trim();
  const configuredTargets = Array.isArray(parsed.targetLanguages)
    ? parsed.targetLanguages.map((x) => String(x).trim()).filter(Boolean)
    : [];

  const targetLanguages = [...new Set(configuredTargets.length ? configuredTargets : [sourceLanguage])];
  if (!targetLanguages.includes(sourceLanguage)) {
    targetLanguages.unshift(sourceLanguage);
  }

  return { sourceLanguage, targetLanguages };
}

const { sourceLanguage, targetLanguages } = readLanguagesConfig();
const sets = [
  { tag: `src-${sanitizeTag(sourceLanguage)}`, source: `dashboards/src/${sourceLanguage}` },
  ...targetLanguages.map((lang) => ({ tag: sanitizeTag(lang), source: `dashboards/${lang}` })),
];

function run(script, args = []) {
  const cmd = ["node", script, ...args];
  console.log(`\n$ ${cmd.join(" ")}`);
  const res = spawnSync(cmd[0], cmd.slice(1), { stdio: "inherit", shell: true });
  if (res.status !== 0) process.exit(res.status || 1);
}

for (const set of sets) {
  const manifest = `tests/artifacts/import-manifest-${set.tag}.json`;
  run("scripts/test/import-dashboards.mjs", [`--source=${set.source}`, `--tag=${set.tag}`, `--manifest=${manifest}`]);
  run("scripts/test/smoke-check.mjs", [`--manifest=${manifest}`]);
  if (withScreenshots) {
    run("scripts/test/capture-screenshots.mjs", [`--manifest=${manifest}`]);
  }
}

console.log("\nGrafana localization test suite finished.");
