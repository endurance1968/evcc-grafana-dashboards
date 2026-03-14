import { spawnSync } from "node:child_process";

const args = process.argv.slice(2);
console.warn("WARN scripts/test/deploy-language.mjs is deprecated. Use scripts/test/deploy-dashboards.mjs");
const res = spawnSync("node", ["scripts/test/deploy-dashboards.mjs", ...args], { stdio: "inherit" });
process.exit(res.status ?? 1);
