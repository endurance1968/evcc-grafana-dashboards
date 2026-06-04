/**
 * Script: generate-docs-screenshots.mjs
 * Purpose: Generate curated documentation screenshots from a local Grafana instance.
 * Version: 2026.06.04.4
 * Last modified: 2026-06-04
 */
import { spawnSync } from "node:child_process";
import path from "node:path";
import { parseArg, sanitizeTag } from "./_lib.mjs";

const SCRIPT_VERSION = "2026.06.04.4";
const SCRIPT_LAST_MODIFIED = "2026-06-04";

const envFile = parseArg("env", ".env.local");
const language = parseArg("language", "de").trim().toLowerCase();
const outDir = parseArg("out", "docs/screenshots");
const tag = sanitizeTag(parseArg("tag", `vm-docs-${language}`));
const manifest = parseArg("manifest", `tests/artifacts/import-manifest-${tag}.json`);
const source = parseArg("source", path.posix.join("dashboards", "translation", language));
const prepare = parseArg("prepare", "true") !== "false";
const cleanupBefore = parseArg("cleanup-before", "true") !== "false";
const cleanupFinal = parseArg("cleanup-final", "false") === "true";
const smoke = parseArg("smoke", "true") !== "false";
const deleteExisting = parseArg("delete-existing", "true") !== "false";
const theme = parseArg("theme", "light");
const dryRun = parseArg("dry-run", "false") === "true";

console.log(`generate-docs-screenshots.mjs v${SCRIPT_VERSION} (last modified ${SCRIPT_LAST_MODIFIED}, run ${new Date().toISOString()})`);
console.log(`Language: ${language}`);
console.log(`Source:   ${source}`);
console.log(`Manifest: ${manifest}`);
console.log(`Output:   ${outDir}`);

if (language !== "de") {
  throw new Error("This docs screenshot workflow currently supports only --language=de because docs/screenshots is the German release gallery.");
}

function run(script, args = []) {
  const cmd = ["node", script, ...args];
  console.log(`\n$ ${cmd.join(" ")}`);
  const result = spawnSync(cmd[0], cmd.slice(1), {
    cwd: process.cwd(),
    stdio: "inherit",
    env: process.env,
  });
  if (result.error) {
    throw result.error;
  }
  if (result.status !== 0) {
    throw new Error(`${cmd.join(" ")} failed with exit code ${result.status}`);
  }
}

if (prepare) {
  run("scripts/localization/generate-localized-dashboards.mjs");
  run("scripts/localization/apply-safe-display-translations.mjs");
}

process.env.GRAFANA_TEST_FOLDER_UID ||= `evcc-docs-${language}`;
process.env.GRAFANA_TEST_FOLDER_TITLE ||= "EVCC";
process.env.GRAFANA_DASHBOARD_TITLE_PREFIX_MODE ||= "none";

let workflowError;
try {
  run("scripts/test/deploy-dashboards.mjs", [
    `--env=${envFile}`,
    `--language=${language}`,
    "--variant=generated",
    "--source-mode=localdir",
    `--source=${source}`,
    `--tag=${tag}`,
    `--manifest=${manifest}`,
    `--purge=${cleanupBefore ? "true" : "false"}`,
    `--smoke=${smoke ? "true" : "false"}`,
  ]);

  run("scripts/test/capture-docs-screenshots.mjs", [
    `--env=${envFile}`,
    `--manifest=${manifest}`,
    `--out=${outDir}`,
    `--theme=${theme}`,
    `--delete-existing=${deleteExisting}`,
    ...(dryRun ? ["--dry-run=true"] : []),
  ]);
} catch (error) {
  workflowError = error;
} finally {
  if (cleanupFinal) {
    try {
      run("scripts/test/cleanup-grafana.mjs", [`--env=${envFile}`]);
    } catch (cleanupError) {
      if (workflowError) {
        console.error(`Cleanup after failed screenshot workflow also failed: ${cleanupError.message || cleanupError}`);
      } else {
        workflowError = cleanupError;
      }
    }
  }
}

if (workflowError) {
  throw workflowError;
}

console.log("\nDocs screenshot workflow finished.");

