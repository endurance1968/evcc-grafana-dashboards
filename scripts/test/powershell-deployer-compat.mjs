/**
 * Script: powershell-deployer-compat.mjs
 * Purpose: Validate deploy.ps1 JSON handling under Windows PowerShell 5.1 so single-item arrays survive the deployer roundtrip.
 * Version: 2026.04.18.1
 * Last modified: 2026-04-18
 */
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";

const repoRoot = process.cwd();
const scriptName = "powershell-deployer-compat.mjs";
const version = "2026.04.18.1";
const lastModified = "2026-04-18";
const deployerPath = path.join(repoRoot, "scripts", "deploy.ps1");
const dashboardPath = path.join(repoRoot, "dashboards", "original", "en", "VM_ EVCC_ All-time.json");

function run(command, args, options = {}) {
  const result = spawnSync(command, args, {
    encoding: "utf8",
    stdio: "pipe",
    ...options,
  });
  if (result.error) {
    throw result.error;
  }
  return result;
}

function ensureWindowsPowerShell() {
  if (process.platform !== "win32") {
    console.log("Skipping Windows PowerShell deployer compatibility check: non-Windows host.");
    return "";
  }
  const result = run("powershell.exe", ["-NoProfile", "-Command", "$PSVersionTable.PSVersion.ToString()"]);
  if (result.status !== 0) {
    throw new Error(`powershell.exe is required on Windows for the deployer compatibility check. ${result.stderr || result.stdout}`.trim());
  }
  const versionText = (result.stdout || "").trim();
  console.log(`Windows PowerShell detected: ${versionText}`);
  return "powershell.exe";
}

function extractFunctionSource(text, name) {
  const pattern = new RegExp(`function\\s+${name}\\b[\\s\\S]*?^}`, "m");
  const match = text.match(pattern);
  if (!match) {
    throw new Error(`Unable to locate function ${name} in scripts/deploy.ps1`);
  }
  return match[0];
}

function buildHarness(functionSources) {
  return [
    "$ErrorActionPreference = 'Stop'",
    "",
    ...functionSources,
    "",
    "$settings = @{ GRAFANA_DS_VM_EVCC_UID = 'vm-evcc' }",
    `$deployerPath = '${deployerPath.replace(/'/g, "''")}'`,
    `$dashboardPath = '${dashboardPath.replace(/'/g, "''")}'`,
    "[scriptblock]::Create((Get-Content -Raw -LiteralPath $deployerPath)) | Out-Null",
    "$raw = Parse-JsonDocument (Get-Content -Raw -LiteralPath $dashboardPath)",
    "$rewritten = Replace-DatasourcePlaceholders $raw",
    "",
    "function Assert-Array([object]$Value, [string]$Name, [int]$ExpectedCount = -1) {",
    "  if ($null -eq $Value) { throw \"$Name is null\" }",
    "  if (-not ($Value -is [System.Array])) { throw \"$Name is $($Value.GetType().FullName), expected array\" }",
    "  if ($ExpectedCount -ge 0 -and @($Value).Count -ne $ExpectedCount) { throw \"$Name count $(@($Value).Count), expected $ExpectedCount\" }",
    "}",
    "",
    "$avg = @($rewritten.panels | Where-Object { $_.title -eq 'Average yearly specific yield' })[0]",
    "if ($null -eq $avg) { throw 'Average yearly specific yield panel not found' }",
    "Assert-Array $avg.targets 'avg.targets' 1",
    "Assert-Array $avg.fieldConfig.defaults.mappings 'avg.fieldConfig.defaults.mappings' 0",
    "Assert-Array $avg.fieldConfig.defaults.thresholds.steps 'avg.fieldConfig.defaults.thresholds.steps' 1",
    "Assert-Array $avg.fieldConfig.overrides 'avg.fieldConfig.overrides' 0",
    "Assert-Array $avg.options.reduceOptions.calcs 'avg.options.reduceOptions.calcs' 1",
    "if ($avg.targets[0].datasource.uid -ne 'vm-evcc') { throw \"avg.targets[0].datasource.uid is $($avg.targets[0].datasource.uid), expected vm-evcc\" }",
    "",
    "$metric = @($rewritten.panels | Where-Object { $_.title -eq 'Metric gauges' })[0]",
    "if ($null -eq $metric) { throw 'Metric gauges panel not found' }",
    "Assert-Array $metric.targets 'metric.targets' 7",
    "Assert-Array $metric.fieldConfig.defaults.links 'metric.fieldConfig.defaults.links' 0",
    "Assert-Array $metric.fieldConfig.defaults.mappings 'metric.fieldConfig.defaults.mappings' 0",
    "Assert-Array $metric.fieldConfig.defaults.thresholds.steps 'metric.fieldConfig.defaults.thresholds.steps' 1",
    "Assert-Array $metric.options.reduceOptions.calcs 'metric.options.reduceOptions.calcs' 1",
    "if ($metric.targets[0].datasource.uid -ne 'vm-evcc') { throw \"metric.targets[0].datasource.uid is $($metric.targets[0].datasource.uid), expected vm-evcc\" }",
    "",
    "Write-Output 'Windows PowerShell deployer compatibility check passed.'",
    "",
  ].join("\r\n");
}

function main() {
  console.log(`${scriptName} v${version} (last modified ${lastModified})`);
  const powershell = ensureWindowsPowerShell();
  if (!powershell) {
    return;
  }

  const deployerText = fs.readFileSync(deployerPath, "utf8");
  const functionSources = [
    extractFunctionSource(deployerText, "Convert-JsonNode"),
    extractFunctionSource(deployerText, "Parse-JsonDocument"),
    extractFunctionSource(deployerText, "Replace-DatasourcePlaceholders"),
  ];

  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "evcc-ps-compat-"));
  const harnessPath = path.join(tempDir, "powershell-deployer-compat.ps1");
  fs.writeFileSync(harnessPath, buildHarness(functionSources), "utf8");

  try {
    const result = run(powershell, ["-NoProfile", "-ExecutionPolicy", "Bypass", "-File", harnessPath]);
    if (result.status !== 0) {
      throw new Error((result.stderr || result.stdout || `exit ${result.status}`).trim());
    }
    process.stdout.write(result.stdout || "");
  } finally {
    fs.rmSync(tempDir, { recursive: true, force: true });
  }
}

try {
  main();
} catch (error) {
  console.error(`\n${scriptName} failed: ${error.message || error}`);
  process.exit(1);
}
