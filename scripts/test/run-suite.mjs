import { spawnSync } from "node:child_process";
import { loadEnvFile, parseArg } from "./_lib.mjs";

loadEnvFile(parseArg("env", ".env"));

const withScreenshots = parseArg("screenshots", "false") === "true";
const sets = [
  { tag: "src-de", source: "dashboards/src/de" },
  { tag: "de", source: "dashboards/de" },
  { tag: "en", source: "dashboards/en" },
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
