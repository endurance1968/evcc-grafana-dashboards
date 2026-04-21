/**
 * Script: powershell-deployer-compat.mjs
 * Purpose: Validate deploy.ps1 JSON handling and local manifest resolution under Windows PowerShell 5.1 so copied deployers behave like the repo version.
 * Version: 2026.04.20.4
 * Last modified: 2026-04-20
 */
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { readDeployManifest, resolveDashboardSet } from "../helper/deploy-manifest.mjs";

const repoRoot = process.cwd();
const scriptName = "powershell-deployer-compat.mjs";
const version = "2026.04.20.4";
const lastModified = "2026-04-20";
const deployerPath = path.join(repoRoot, "scripts", "deploy.ps1");
const manifest = readDeployManifest(repoRoot);
const { files: defaultDashboardFiles } = resolveDashboardSet(manifest);
const dashboardPath = path.join(
  repoRoot,
  "dashboards",
  "original",
  "en",
  defaultDashboardFiles.find((file) => file.includes("All-time")) || defaultDashboardFiles[0],
);
const localDashboardDir = path.join(repoRoot, "dashboards", "original", "en");
const manifestPath = path.join(repoRoot, "dashboards", "deploy-manifest.json");

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
  const startPattern = new RegExp(`function\\s+${name}\\b`, "m");
  const startMatch = startPattern.exec(text);
  if (!startMatch) {
    throw new Error(`Unable to locate function ${name} in scripts/deploy.ps1`);
  }

  const braceStart = text.indexOf("{", startMatch.index);
  if (braceStart < 0) {
    throw new Error(`Unable to locate opening brace for function ${name}`);
  }

  let depth = 0;
  let inSingle = false;
  let inDouble = false;
  let inComment = false;
  let prev = "";
  for (let i = braceStart; i < text.length; i += 1) {
    const char = text[i];
    const next = text[i + 1] || "";

    if (inComment) {
      if (char === "\n") {
        inComment = false;
      }
      prev = char;
      continue;
    }

    if (!inSingle && !inDouble && char === "#") {
      inComment = true;
      prev = char;
      continue;
    }

    if (!inDouble && char === "'" && prev !== "`") {
      inSingle = !inSingle;
      prev = char;
      continue;
    }

    if (!inSingle && char === '"' && prev !== "`") {
      inDouble = !inDouble;
      prev = char;
      continue;
    }

    if (!inSingle && !inDouble) {
      if (char === "{") {
        depth += 1;
      } else if (char === "}") {
        depth -= 1;
        if (depth === 0) {
          return text.slice(startMatch.index, i + 1);
        }
      }
    }

    prev = char;
  }

  throw new Error(`Unable to locate closing brace for function ${name}`);
}

function buildHarness(functionSources) {
  return [
    "$ErrorActionPreference = 'Stop'",
    "",
    ...functionSources,
    "",
    `$repoRoot = '${repoRoot.replace(/'/g, "''")}'`,
    `$dashboardPath = '${dashboardPath.replace(/'/g, "''")}'`,
    `$manifestPath = '${manifestPath.replace(/'/g, "''")}'`,
    `$localDashboardDir = '${localDashboardDir.replace(/'/g, "''")}'`,
    "$settings = @{ GRAFANA_DS_VM_EVCC_UID = 'vm-evcc'; DASHBOARD_SOURCE_MODE = 'local'; DASHBOARD_LOCAL_DIR = $localDashboardDir }",
    "$script:ResolvedLocalRepoRoot = $null",
    "$raw = Parse-JsonDocument (Get-Content -Raw -LiteralPath $dashboardPath)",
    "$rewritten = Replace-DatasourcePlaceholders $raw",
    "$resolvedRepoRoot = Resolve-LocalRepoRoot",
    "$manifestText = Get-RepoFileContent 'dashboards/deploy-manifest.json'",
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
    "if ($resolvedRepoRoot -ne $repoRoot) { throw \"Resolve-LocalRepoRoot returned $resolvedRepoRoot, expected $repoRoot\" }",
    "if (-not $manifestText.Contains('defaultSet')) { throw 'Manifest text did not contain defaultSet' }",
    "if ($manifestText -ne (Get-Content -Raw -LiteralPath $manifestPath)) { throw 'Get-RepoFileContent returned unexpected manifest content' }",
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
    extractFunctionSource(deployerText, "Resolve-LocalRepoRoot"),
    extractFunctionSource(deployerText, "Get-RepoFileContent"),
  ];

  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "evcc-ps-compat-"));
  const harnessPath = path.join(tempDir, "powershell-deployer-compat.ps1");
  fs.writeFileSync(harnessPath, buildHarness(functionSources), "utf8");

  try {
    const result = run(powershell, ["-NoProfile", "-ExecutionPolicy", "Bypass", "-File", harnessPath], { cwd: tempDir });
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

