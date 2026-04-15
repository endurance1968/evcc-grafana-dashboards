/**
 * Script: rollup-path-check.mjs
 * Purpose: Run the complete deterministic rollup validation path as one reproducible check.
 * Version: 2026.04.15.3
 * Last modified: 2026-04-15
 */
import { spawnSync } from "node:child_process";

const scriptName = "rollup-path-check.mjs";
const version = "2026.04.15.3";
const lastModified = "2026-04-15";

function parseArg(name, fallback = "") {
  const prefix = `--${name}=`;
  const inline = process.argv.find((arg) => arg.startsWith(prefix));
  if (inline) {
    return inline.slice(prefix.length);
  }
  const index = process.argv.indexOf(`--${name}`);
  if (index >= 0 && process.argv[index + 1] && !process.argv[index + 1].startsWith("--")) {
    return process.argv[index + 1];
  }
  return fallback;
}

function hasFlag(name) {
  return process.argv.includes(`--${name}`);
}

function stepDuration(startedAt) {
  return ((Date.now() - startedAt) / 1000).toFixed(1);
}

function run(command, args, stepName) {
  console.log(`\n[${stepName}]`);
  console.log(`$ ${[command, ...args].join(" ")}`);
  const startedAt = Date.now();
  const result = spawnSync(command, args, {
    cwd: process.cwd(),
    env: process.env,
    stdio: "inherit",
  });
  if (result.error) {
    throw result.error;
  }
  if (result.status !== 0) {
    throw new Error(`${stepName} failed with exit code ${result.status}`);
  }
  return stepDuration(startedAt);
}

function runNodeScript(script, stepName, extraArgs = []) {
  return run(process.execPath, [script, ...extraArgs], stepName);
}

function energyValidationArgs() {
  const args = [];
  const strict = hasFlag("strict-energy") || process.env.ENERGY_VALIDATION_STRICT === "1";
  const vmBaseUrl = parseArg(
    "vm-base-url",
    process.env.ENERGY_VALIDATION_VM_BASE_URL || process.env.VM_BASE_URL || "",
  );

  if (strict) {
    args.push("--require-cache", "tibber-vm");
    args.push("--require-cache", "tibber-influx");
    args.push("--require-cache", "vrm");
  }
  if (vmBaseUrl) {
    args.push("--vm-base-url", vmBaseUrl);
    if (strict) {
      args.push("--require-cache", "vrm-vm");
    }
  }
  return args;
}

function main() {
  console.log(`${scriptName} v${version} (last modified ${lastModified})`);
  console.log("Complete EVCC VM rollup path validation");
  console.log("========================================");
  console.log("This check validates static dashboard semantics, external energy comparisons,");
  console.log("MetricsQL readback, disposable Grafana rendering, and disposable VM rollup replace idempotency.");

  const skipRender = hasFlag("skip-render");
  const results = [];
  const startedAt = Date.now();

  results.push(["Static/unit/dashboard checks", runNodeScript("scripts/test/local-checks.mjs", "Static/unit/dashboard checks")]);
  results.push(["External energy validation", runNodeScript("scripts/test/energy-validation.mjs", "External energy validation", energyValidationArgs())]);
  results.push(["Dashboard query readback", runNodeScript("scripts/test/dashboard-query-readback.mjs", "Dashboard query readback", ["--docker"])]);
  if (skipRender) {
    results.push(["Grafana render smoke E2E", "SKIP (--skip-render)"]);
  } else {
    results.push(["Grafana render smoke E2E", runNodeScript("scripts/test/render-e2e.mjs", "Grafana render smoke E2E")]);
  }
  results.push(["Rollup replace E2E", runNodeScript("scripts/test/local-checks.mjs", "Rollup replace E2E", ["--rollup-e2e"])]);

  console.log("\nSummary");
  console.log("-------");
  for (const [name, duration] of results) {
    console.log(`OK   ${name}: ${duration}s`);
  }
  console.log(`\nResult: OK - complete deterministic rollup path passed in ${stepDuration(startedAt)}s.`);
}

try {
  main();
} catch (error) {
  console.error(`\nResult: FAILED - ${error.message || error}`);
  process.exit(1);
}
