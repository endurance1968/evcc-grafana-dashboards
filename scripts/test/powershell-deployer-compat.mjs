/**
 * Script: powershell-deployer-compat.mjs
 * Purpose: Validate deploy.ps1 JSON handling and localdir dashboard loading under Windows PowerShell 5.1 so copied deployers behave like the repo version.
 * Version: 2026.06.15.1
 * Last modified: 2026-06-15
 */
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { readDeployManifest, resolveDashboardFiles } from "../helper/deploy-manifest.mjs";

const repoRoot = process.cwd();
const scriptName = "powershell-deployer-compat.mjs";
const version = "2026.06.03.6";
const lastModified = "2026-06-03";
const deployerPath = path.join(repoRoot, "scripts", "deploy.ps1");
const manifest = readDeployManifest(repoRoot);
const defaultDashboardFiles = resolveDashboardFiles(manifest);
const dashboardPath = path.join(
  repoRoot,
  "dashboards",
  "original",
  "en",
  defaultDashboardFiles.find((file) => file === "VM_EVCC_Today.json") || defaultDashboardFiles[0],
);
const localDashboardDir = path.join(repoRoot, "dashboards", "original", "en");

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
    `$localDashboardDir = '${localDashboardDir.replace(/'/g, "''")}'`,
    "$settings = @{ GRAFANA_DS_VM_EVCC_UID = 'vm-evcc'; DASHBOARD_SOURCE_MODE = 'localdir'; DASHBOARD_LOCAL_DIR = $localDashboardDir }",
    "$FixedDashboardFiles = @('VM_EVCC_All-time.json','VM_EVCC_Year.json','VM_EVCC_Month.json','VM_EVCC_Today-Details.json','VM_EVCC_Today.json','VM_EVCC_Today-Mobile.json')",
    "$raw = Parse-JsonDocument (Get-Content -Raw -LiteralPath $dashboardPath)",
    "$rewritten = Replace-DatasourcePlaceholders $raw",
    "$dashboardFiles = @(Get-DashboardFilesFromManifest)",
    "$sourceText = Get-SourceFileContent 'VM_EVCC_Today.json'",
    "",
    "function Assert-Array([object]$Value, [string]$Name, [int]$ExpectedCount = -1) {",
    "  if ($null -eq $Value) { throw \"$Name is null\" }",
    "  if (-not ($Value -is [System.Array])) { throw \"$Name is $($Value.GetType().FullName), expected array\" }",
    "  if ($ExpectedCount -ge 0 -and @($Value).Count -ne $ExpectedCount) { throw \"$Name count $(@($Value).Count), expected $ExpectedCount\" }",
    "}",
    "function Convert-V2PanelToClassicShape([object]$Panel) {",
    "  $queries = @($Panel.spec.data.spec.queries | ForEach-Object {",
    "    [pscustomobject]@{",
    "      refId = $_.spec.refId",
    "      expr = $_.spec.query.spec.expr",
    "      datasource = [pscustomobject]@{ uid = $_.spec.query.datasource.name }",
    "    }",
    "  })",
    "  return [pscustomobject]@{",
    "    title = $Panel.spec.title",
    "    targets = $queries",
    "    fieldConfig = $Panel.spec.vizConfig.spec.fieldConfig",
    "    options = $Panel.spec.vizConfig.spec.options",
    "  }",
    "}",
    "function Find-PanelByTitle([object]$Node, [string]$Title) {",
    "  if ($null -eq $Node) { return $null }",
    "  if ($Node -is [System.Array]) {",
    "    foreach ($item in $Node) { $found = Find-PanelByTitle $item $Title; if ($null -ne $found) { return $found } }",
    "    return $null",
    "  }",
    "  if ($Node -is [pscustomobject]) {",
    "    if ($Node.PSObject.Properties['kind'] -and $Node.kind -eq 'Panel' -and $Node.spec.title -eq $Title) { return Convert-V2PanelToClassicShape $Node }",
    "    if ($Node.PSObject.Properties['title'] -and $Node.title -eq $Title -and $Node.PSObject.Properties['targets']) { return $Node }",
    "    foreach ($prop in $Node.PSObject.Properties) { $found = Find-PanelByTitle $prop.Value $Title; if ($null -ne $found) { return $found } }",
    "  }",
    "  return $null",
    "}",
    "",
    "$power = Find-PanelByTitle $rewritten 'Power'",
    "if ($null -eq $power) { throw 'Power panel not found' }",
    "Assert-Array $power.targets 'power.targets' 5",
    "Assert-Array $power.fieldConfig.defaults.mappings 'power.fieldConfig.defaults.mappings' 0",
    "Assert-Array $power.fieldConfig.defaults.thresholds.steps 'power.fieldConfig.defaults.thresholds.steps' 5",
    "Assert-Array $power.options.reduceOptions.calcs 'power.options.reduceOptions.calcs' 1",
    "if ($power.targets[0].datasource.uid -ne 'vm-evcc') { throw \"power.targets[0].datasource.uid is $($power.targets[0].datasource.uid), expected vm-evcc\" }",
    "",
    "$metric = Find-PanelByTitle $rewritten 'Metrics'",
    "if ($null -eq $metric) { throw 'Metrics panel not found' }",
    "Assert-Array $metric.targets 'metric.targets' 9",
    "Assert-Array $metric.fieldConfig.defaults.links 'metric.fieldConfig.defaults.links' 0",
    "Assert-Array $metric.fieldConfig.defaults.mappings 'metric.fieldConfig.defaults.mappings' 0",
    "Assert-Array $metric.fieldConfig.defaults.thresholds.steps 'metric.fieldConfig.defaults.thresholds.steps' 1",
    "Assert-Array $metric.options.reduceOptions.calcs 'metric.options.reduceOptions.calcs' 1",
    "if ($metric.targets[0].datasource.uid -ne 'vm-evcc') { throw \"metric.targets[0].datasource.uid is $($metric.targets[0].datasource.uid), expected vm-evcc\" }",
    "",
    "if ($dashboardFiles.Count -ne 6) { throw \"Get-DashboardFilesFromManifest returned $($dashboardFiles.Count), expected 6\" }",
    "if (-not $sourceText.Contains('\"title\"')) { throw 'Get-SourceFileContent returned unexpected dashboard content' }",
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
    extractFunctionSource(deployerText, "Get-SourceFileContent"),
    extractFunctionSource(deployerText, "Get-DashboardFilesFromManifest"),
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
