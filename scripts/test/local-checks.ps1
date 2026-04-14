<#
Script: local-checks.ps1
Purpose: Run the local deterministic validation checks for this repository.
Version: 2026.04.14.4
Last modified: 2026-04-14
#>
$ErrorActionPreference = "Stop"

$scriptVersion = "2026.04.14.4"
$scriptLastModified = "2026-04-14"
$repoRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path))
$pythonScripts = @(
    "scripts/helper/check_data.py",
    "scripts/helper/compare_import_coverage.py",
    "scripts/helper/compare_labelsets.py",
    "scripts/helper/compare_tibber_vm.py",
    "scripts/helper/fetch_vrm_kwh_cache.py",
    "scripts/helper/validate_energy_comparison.py",
    "scripts/helper/vm-rewrite-drop-label.py",
    "scripts/rollup/evcc-vm-rollup.py",
    "scripts/test/rollup-e2e.py"
)

function Invoke-CheckedCommand {
    param(
        [Parameter(Mandatory = $true)][string]$Command,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )

    Write-Host ""
    Write-Host ("$ " + $Command + " " + ($Arguments -join " "))
    & $Command @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code ${LASTEXITCODE}: $Command"
    }
}

function Test-Command {
    param([Parameter(Mandatory = $true)][string]$Command)

    try {
        & $Command --version *> $null
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    }
}

function Resolve-Python {
    $candidates = @(
        $env:PYTHON,
        (Join-Path $env:LOCALAPPDATA "Python/bin/python.exe"),
        (Join-Path $env:USERPROFILE "AppData/Local/Python/bin/python.exe"),
        "python3",
        "python"
    ) | Where-Object { $_ }

    foreach ($candidate in $candidates) {
        if (Test-Command $candidate) {
            return $candidate
        }
    }

    throw "No working Python interpreter found. Set PYTHON to the intended interpreter."
}

Push-Location $repoRoot
try {
    Write-Host "local-checks.ps1 v$scriptVersion (last modified $scriptLastModified)"
    $python = Resolve-Python

    Invoke-CheckedCommand $python @("-m", "unittest", "discover", "tests")
    Invoke-CheckedCommand $python (@("-m", "py_compile") + $pythonScripts)
    Invoke-CheckedCommand "node" @("scripts/test/local-checks.mjs", "--js-only")

    $gitBash = "C:\Program Files\Git\bin\bash.exe"
    if ((Test-Path -LiteralPath $gitBash) -and (Test-Command $gitBash)) {
        Invoke-CheckedCommand $gitBash @("-n", "scripts/deploy-bash.sh")
        Invoke-CheckedCommand $gitBash @("-n", "scripts/deploy-python.sh")
    } else {
        Write-Host "Skipping bash syntax checks: Git Bash not available in this process context."
    }

    Write-Host ""
    Write-Host "Local checks passed."
} finally {
    Pop-Location
}
