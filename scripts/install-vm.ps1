param(
  [string]$Config = (Join-Path $PSScriptRoot "vm-dashboard-install.env"),
  [Alias("url")][string]$url,
  [Alias("token")][string]$token,
  [string]$DatasourceUid,
  [string]$Language,
  [string]$Variant,
  [string]$SourceMode,
  [string]$GitHubRepo,
  [string]$GitHubRef,
  [string]$LocalDir,
  [string]$FolderUid,
  [string]$FolderTitle,
  [string]$Purge = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Load-DotEnv([string]$Path) {
  $map = @{}
  if (-not (Test-Path -LiteralPath $Path)) {
    return $map
  }
  foreach ($line in (Get-Content -LiteralPath $Path)) {
    $trimmed = $line.Trim()
    if (-not $trimmed -or $trimmed.StartsWith("#")) { continue }
    $idx = $trimmed.IndexOf("=")
    if ($idx -lt 1) { continue }
    $key = $trimmed.Substring(0, $idx).Trim()
    $value = $trimmed.Substring($idx + 1).Trim()
    if (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'"))) {
      $value = $value.Substring(1, $value.Length - 2)
    }
    $map[$key] = $value
  }
  return $map
}

function Merge-Setting([hashtable]$Settings, [string]$Key, [object]$Value) {
  if ($null -eq $Value) { return }
  if ($Value -is [string] -and [string]::IsNullOrWhiteSpace($Value)) { return }
  $Settings[$Key] = $Value
}

function Invoke-GrafanaApi([string]$Method, [string]$Path, $Body = $null, [switch]$Allow404) {
  $uri = ($settings.GRAFANA_URL.TrimEnd("/")) + $Path
  $headers = @{
    Authorization = "Bearer $($settings.GRAFANA_API_TOKEN)"
    Accept = "application/json"
  }
  try {
    if ($null -ne $Body) {
      return Invoke-RestMethod -Method $Method -Uri $uri -Headers $headers -ContentType "application/json" -Body ($Body | ConvertTo-Json -Depth 100)
    }
    return Invoke-RestMethod -Method $Method -Uri $uri -Headers $headers
  } catch {
    $response = $_.Exception.Response
    if ($Allow404 -and $null -ne $response -and $response.StatusCode.value__ -eq 404) {
      return $null
    }
    throw
  }
}

function Escape-PathSegment([string]$Value) {
  return [Uri]::EscapeDataString($Value)
}

function Get-SourceFileContent([string]$FileName) {
  if ($settings.DASHBOARD_SOURCE_MODE -eq "local") {
    $full = Join-Path $settings.DASHBOARD_LOCAL_DIR $FileName
    return Get-Content -Raw -LiteralPath $full
  }
  $subDir = if ($settings.DASHBOARD_VARIANT -eq "orig") {
    "dashboards/original/$($settings.DASHBOARD_LANGUAGE)"
  } else {
    "dashboards/translation/$($settings.DASHBOARD_LANGUAGE)"
  }
  $parts = @(
    "https://raw.githubusercontent.com",
    $settings.GITHUB_REPO,
    $settings.GITHUB_REF,
    ($subDir -replace "\\", "/").Trim("/"),
    (Escape-PathSegment $FileName)
  )
  $url = ($parts -join "/")
  return (Invoke-WebRequest -Method Get -Uri $url).Content
}

function Replace-DatasourcePlaceholders($Node) {
  if ($null -eq $Node) { return $Node }
  if ($Node -is [string]) {
    if ($Node -eq '${DS_VM-EVCC}') { return $settings.GRAFANA_DS_VM_EVCC_UID }
    return $Node
  }
  if ($Node -is [System.Collections.IEnumerable] -and -not ($Node -is [hashtable]) -and -not ($Node -is [pscustomobject])) {
    $list = @()
    foreach ($item in $Node) { $list += ,(Replace-DatasourcePlaceholders $item) }
    return $list
  }
  if ($Node -is [hashtable] -or $Node -is [pscustomobject]) {
    $out = @{}
    foreach ($prop in $Node.PSObject.Properties) {
      $out[$prop.Name] = Replace-DatasourcePlaceholders $prop.Value
    }
    return [pscustomobject]$out
  }
  return $Node
}

function Build-Inputs($Raw) {
  $inputs = @()
  foreach ($input in @($Raw.__inputs)) {
    if ($null -eq $input -or -not $input.name -or -not $input.type) { continue }
    if ($input.type -eq "datasource") {
      $value = if ($input.name -eq "DS_VM-EVCC") { $settings.GRAFANA_DS_VM_EVCC_UID } elseif ($input.pluginId -eq "__expr__") { "__expr__" } else { "" }
      if (-not $value) { throw "Missing datasource mapping for input $($input.name)" }
      $inputs += @{
        name = $input.name
        type = $input.type
        pluginId = $input.pluginId
        value = $value
      }
    } else {
      $inputs += @{
        name = $input.name
        type = $input.type
        value = $input.value
      }
    }
  }
  return $inputs
}

function Ensure-Folder() {
  $existing = Invoke-GrafanaApi GET "/api/folders/$($settings.GRAFANA_FOLDER_UID)" -Allow404
  if ($null -eq $existing) {
    Invoke-GrafanaApi POST "/api/folders" @{
      uid = $settings.GRAFANA_FOLDER_UID
      title = $settings.GRAFANA_FOLDER_TITLE
    } | Out-Null
  }
}

function Remove-IfExists([string]$Path) {
  Invoke-GrafanaApi DELETE $Path -Allow404 | Out-Null
}

$settings = @{
  GRAFANA_URL = "http://localhost:3000"
  GRAFANA_API_TOKEN = ""
  GRAFANA_DS_VM_EVCC_UID = "vm-evcc"
  GRAFANA_FOLDER_UID = "evcc"
  GRAFANA_FOLDER_TITLE = "EVCC"
  DASHBOARD_SOURCE_MODE = "github"
  GITHUB_REPO = "endurance1968/evcc-grafana-dashboards"
  GITHUB_REF = "main"
  DASHBOARD_LANGUAGE = "en"
  DASHBOARD_VARIANT = "orig"
  DASHBOARD_LOCAL_DIR = ""
  DEPLOY_PURGE = "true"
}

$fileSettings = Load-DotEnv $Config
foreach ($entry in $fileSettings.GetEnumerator()) {
  $settings[$entry.Key] = $entry.Value
}
foreach ($key in @("GRAFANA_URL","GRAFANA_API_TOKEN","GRAFANA_DS_VM_EVCC_UID","GRAFANA_FOLDER_UID","GRAFANA_FOLDER_TITLE","DASHBOARD_SOURCE_MODE","GITHUB_REPO","GITHUB_REF","DASHBOARD_LANGUAGE","DASHBOARD_VARIANT","DASHBOARD_LOCAL_DIR","DEPLOY_PURGE")) {
  $envValue = [Environment]::GetEnvironmentVariable($key)
  if ($envValue) { $settings[$key] = $envValue }
}

Merge-Setting $settings "GRAFANA_URL" $url
Merge-Setting $settings "GRAFANA_API_TOKEN" $token
Merge-Setting $settings "GRAFANA_DS_VM_EVCC_UID" $DatasourceUid
Merge-Setting $settings "DASHBOARD_LANGUAGE" $Language
Merge-Setting $settings "DASHBOARD_VARIANT" $Variant
Merge-Setting $settings "DASHBOARD_SOURCE_MODE" $SourceMode
Merge-Setting $settings "GITHUB_REPO" $GitHubRepo
Merge-Setting $settings "GITHUB_REF" $GitHubRef
Merge-Setting $settings "DASHBOARD_LOCAL_DIR" $LocalDir
Merge-Setting $settings "GRAFANA_FOLDER_UID" $FolderUid
Merge-Setting $settings "GRAFANA_FOLDER_TITLE" $FolderTitle
if (-not [string]::IsNullOrWhiteSpace($Purge)) { $settings["DEPLOY_PURGE"] = $(if ($Purge -match "^(1|true|yes|on)$") { "true" } else { "false" }) }

if (-not $settings.GRAFANA_API_TOKEN) {
  throw "Missing GRAFANA_API_TOKEN. Set it in the config file, environment, or -token."
}
if ($settings.DASHBOARD_SOURCE_MODE -eq "local" -and -not $settings.DASHBOARD_LOCAL_DIR) {
  throw "DASHBOARD_LOCAL_DIR is required when DASHBOARD_SOURCE_MODE=local."
}

$dashboardFiles = @(
  "VM_ EVCC_ All-time.json",
  "VM_ EVCC_ Jahr.json",
  "VM_ EVCC_ Monat.json",
  "VM_ EVCC_ Today - Details.json",
  "VM_ EVCC_ Today - Mobile.json",
  "VM_ EVCC_ Today.json"
)

$dashboards = @()
$libraryElements = @{}

foreach ($fileName in $dashboardFiles) {
  $content = Get-SourceFileContent $fileName
  $raw = $content | ConvertFrom-Json -Depth 100
  $dashboards += @{
    fileName = $fileName
    raw = $raw
    inputs = (Build-Inputs $raw)
  }
  foreach ($prop in $raw.__elements.PSObject.Properties) {
    $libraryElements[$prop.Name] = $prop.Value
  }
}

Ensure-Folder

if ($settings.DEPLOY_PURGE -eq "true") {
  foreach ($dashboard in $dashboards) {
    if ($dashboard.raw.uid) {
      Remove-IfExists "/api/dashboards/uid/$([Uri]::EscapeDataString($dashboard.raw.uid))"
    }
  }
  foreach ($element in $libraryElements.Values) {
    if ($element.uid) {
      Remove-IfExists "/api/library-elements/$([Uri]::EscapeDataString($element.uid))"
    }
  }
}

foreach ($element in $libraryElements.Values) {
  $body = @{
    uid = $element.uid
    name = $element.name
    kind = $(if ($element.kind) { $element.kind } else { 1 })
    folderUid = $settings.GRAFANA_FOLDER_UID
    model = (Replace-DatasourcePlaceholders $element.model)
  }
  Invoke-GrafanaApi POST "/api/library-elements" $body | Out-Null
  Write-Host "Imported library panel: $($element.name)"
}

foreach ($dashboard in $dashboards) {
  $body = @{
    dashboard = $dashboard.raw
    folderUid = $settings.GRAFANA_FOLDER_UID
    overwrite = $true
    message = "EVCC VM dashboard install"
    inputs = $dashboard.inputs
  }
  Invoke-GrafanaApi POST "/api/dashboards/import" $body | Out-Null
  Write-Host "Imported dashboard: $($dashboard.raw.title)"
}

Write-Host ""
Write-Host "Install finished." -ForegroundColor Green
Write-Host "Folder: $($settings.GRAFANA_FOLDER_TITLE) ($($settings.GRAFANA_FOLDER_UID))"
if ($settings.DASHBOARD_SOURCE_MODE -eq "local") {
  Write-Host "Source: local / $($settings.DASHBOARD_LOCAL_DIR)"
} else {
  Write-Host "Source: github / $($settings.GITHUB_REPO) / $($settings.GITHUB_REF)"
}



