/**
 * Script: local-checks.mjs
 * Purpose: Run the local deterministic validation checks for this repository.
 * Version: 2026.04.18.1
 * Last modified: 2026-04-18
 */
import fs from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";

const repoRoot = process.cwd();
const pythonScripts = [
  "scripts/helper/check_data.py",
  "scripts/helper/compare_import_coverage.py",
  "scripts/helper/compare_labelsets.py",
  "scripts/helper/compare_tibber_vm.py",
  "scripts/helper/fetch_vrm_kwh_cache.py",
  "scripts/helper/validate_energy_comparison.py",
  "scripts/helper/vm-rewrite-drop-label.py",
  "scripts/rollup/evcc-vm-rollup.py",
  "scripts/test/rollup-e2e.py",
];

function logHeader() {
  console.log("local-checks.mjs v2026.04.18.1 (last modified 2026-04-18)");
}

function commandExists(command, args = ["--version"]) {
  const result = spawnSync(command, args, { encoding: "utf8", stdio: "pipe" });
  return result.status === 0;
}

function pythonMeetsMinimumVersion(command) {
  const result = spawnSync(
    command,
    ["-c", "import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)"],
    { encoding: "utf8", stdio: "pipe" },
  );
  return result.status === 0;
}

function findPython() {
  const candidates = [
    process.env.PYTHON,
    process.platform === "win32" ? path.join(process.env.LOCALAPPDATA || "", "Python", "bin", "python.exe") : "",
    process.platform === "win32" ? path.join(process.env.USERPROFILE || "", "AppData", "Local", "Python", "bin", "python.exe") : "",
    "python3",
    "python",
  ].filter(Boolean);

  for (const candidate of candidates) {
    if (commandExists(candidate) && pythonMeetsMinimumVersion(candidate)) {
      return candidate;
    }
  }
  throw new Error("No Python >= 3.12 interpreter found. Set PYTHON to the intended interpreter.");
}

function run(command, args, options = {}) {
  console.log(`\n$ ${[command, ...args].join(" ")}`);
  const result = spawnSync(command, args, { stdio: "inherit", ...options });
  if (result.error) {
    throw result.error;
  }
  if (result.status !== 0) {
    throw new Error(`Command failed with exit code ${result.status}: ${command}`);
  }
}

function collectFiles(dir, predicate) {
  const out = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      out.push(...collectFiles(fullPath, predicate));
    } else if (entry.isFile() && predicate(fullPath)) {
      out.push(fullPath);
    }
  }
  return out.sort((a, b) => a.localeCompare(b));
}

function walkJson(node, visitor) {
  if (Array.isArray(node)) {
    for (const item of node) {
      walkJson(item, visitor);
    }
    return;
  }
  if (!node || typeof node !== "object") {
    return;
  }
  visitor(node);
  for (const value of Object.values(node)) {
    walkJson(value, visitor);
  }
}

function validateDashboardJson() {
  const files = collectFiles(path.join(repoRoot, "dashboards"), (file) => file.endsWith(".json"));
  for (const file of files) {
    JSON.parse(fs.readFileSync(file, "utf8"));
  }
  console.log(`Dashboard JSON parsed: ${files.length}`);
}

function auditOriginalQueries() {
  const files = collectFiles(path.join(repoRoot, "dashboards", "original"), (file) => file.endsWith(".json"));
  let panels = 0;
  let targets = 0;
  let longQueries = 0;
  let influxStyleTargets = 0;

  for (const file of files) {
    const dashboard = JSON.parse(fs.readFileSync(file, "utf8"));
    walkJson(dashboard, (node) => {
      if (node.type) {
        panels += 1;
      }
      if (!Array.isArray(node.targets)) {
        return;
      }
      for (const target of node.targets) {
        targets += 1;
        const expr = target.expr || target.query || "";
        if (expr.length > 250) {
          longQueries += 1;
        }
        if (target.rawQuery === false || target.policy || target.measurement || target.select) {
          influxStyleTargets += 1;
        }
      }
    });
  }

  console.log(
    `Original query audit: files=${files.length}, panels=${panels}, targets=${targets}, long>250=${longQueries}, influxStyle=${influxStyleTargets}`,
  );
  if (influxStyleTargets > 0) {
    throw new Error(`Found ${influxStyleTargets} Influx-style dashboard target(s) in VM originals.`);
  }
}

function runNodeSyntaxChecks() {
  const files = collectFiles(path.join(repoRoot, "scripts"), (file) => file.endsWith(".mjs"));
  for (const file of files) {
    run(process.execPath, ["--check", file]);
  }
}

function runLocalizationIdempotencyCheck() {
  run(process.execPath, ["scripts/test/localization-idempotency-check.mjs", "--family=vm"]);
}

function runCrossPlatformAudit() {
  run(process.execPath, ["scripts/test/cross-platform-audit.mjs"]);
}

function runPowerShellDeployerCompatCheck() {
  run(process.execPath, ["scripts/test/powershell-deployer-compat.mjs"]);
}

function findBashForSyntaxChecks() {
  const candidates = [
    process.env.BASH,
    "bash",
    process.platform === "win32" ? "C:\\Program Files\\Git\\bin\\bash.exe" : "",
  ].filter(Boolean);

  for (const candidate of candidates) {
    if (commandExists(candidate)) {
      return candidate;
    }
  }
  if (process.platform === "win32") {
    return "";
  }
  throw new Error("bash is required for deploy shell syntax checks on non-Windows systems.");
}

function runOptionalBashSyntaxChecks() {
  const bash = findBashForSyntaxChecks();
  if (!bash) {
    console.log("Skipping bash syntax checks: bash/Git Bash not found.");
    return;
  }
  run(bash, ["-n", "scripts/deploy-bash.sh"]);
  run(bash, ["-n", "scripts/deploy-python.sh"]);
}

function main() {
  logHeader();
  const jsOnly = process.argv.includes("--js-only");
  const rollupE2eOnly = process.argv.includes("--rollup-e2e");
  if (rollupE2eOnly) {
    const python = findPython();
    run(python, ["scripts/test/rollup-e2e.py", "--docker"]);
    console.log("\nRollup E2E check passed.");
    return;
  }
  if (jsOnly) {
    runNodeSyntaxChecks();
    validateDashboardJson();
    auditOriginalQueries();
    run(process.execPath, ["scripts/test/dashboard-semantic-check.mjs"]);
    runCrossPlatformAudit();
    runPowerShellDeployerCompatCheck();
    runLocalizationIdempotencyCheck();
    console.log("\nLocal JS checks passed.");
    return;
  }

  const python = findPython();
  run(python, ["-m", "unittest", "discover", "tests"]);
  run(python, ["-m", "py_compile", ...pythonScripts]);
  runNodeSyntaxChecks();
  validateDashboardJson();
  auditOriginalQueries();
  run(process.execPath, ["scripts/test/dashboard-semantic-check.mjs"]);
  runCrossPlatformAudit();
  runPowerShellDeployerCompatCheck();
  runLocalizationIdempotencyCheck();
  runOptionalBashSyntaxChecks();
  console.log("\nLocal checks passed.");
}

try {
  main();
} catch (error) {
  console.error(`\nLocal checks failed: ${error.message || error}`);
  process.exit(1);
}
