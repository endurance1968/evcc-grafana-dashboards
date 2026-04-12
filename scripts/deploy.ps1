<#
.SYNOPSIS
Deploy dashboards to Grafana from a local checkout or GitHub source.

.DESCRIPTION
Loads the install environment, resolves the requested dashboard source and
pushes the selected dashboard set into the target Grafana folder.
#>
param(
  [string]$config = (Join-Path $PSScriptRoot "vm-dashboard-install.env"),
  [string]$url,
  [string]$token,
  [string]$purge = "",
  [string]$datasourceuid,
  [string]$language,
  [string]$variant,
  [string]$sourcemode,
  [string]$githubrepo,
  [string]$githubref,
  [string]$localdir,
  [string]$folderuid,
  [string]$foldertitle
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ScriptVersion = '2026.04.12.1'
$ScriptLastModified = '2026-04-12'
Write-Host "$((Split-Path -Leaf $PSCommandPath)) v$ScriptVersion (last modified $ScriptLastModified, run $((Get-Date).ToString('yyyy-MM-ddTHH:mm:sszzz')))"

function Load-DotEnv([string]$Path) {
  $map = @{}
  if (-not (Test-Path -LiteralPath $Path)) { return $map }
  foreach ($line in Get-Content -LiteralPath $Path) {
    $trimmed = $line.Trim()
    if (-not $trimmed -or $trimmed.StartsWith('#')) { continue }
    $idx = $trimmed.IndexOf('=')
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
  $uri = ($settings.GRAFANA_URL.TrimEnd('/') ) + $Path
  $headers = @{ Authorization = "Bearer $($settings.GRAFANA_API_TOKEN)"; Accept = 'application/json' }
  $jsonBody = $null
  $jsonBytes = $null
  if ($null -ne $Body) {
    $jsonBody = $Body | ConvertTo-Json -Depth 100
    $jsonBytes = [System.Text.Encoding]::UTF8.GetBytes($jsonBody)
  }
  try {
    if ($null -ne $jsonBody) {
      $response = Invoke-WebRequest -UseBasicParsing -Method $Method -Uri $uri -Headers $headers -ContentType 'application/json; charset=utf-8' -Body $jsonBytes
    } else {
      $response = Invoke-WebRequest -UseBasicParsing -Method $Method -Uri $uri -Headers $headers
    }
    if (-not $response.Content) { return $null }
    return $response.Content | ConvertFrom-Json
  } catch {
    if ($Allow404 -and $_.Exception.Response -and $_.Exception.Response.StatusCode.value__ -eq 404) {
      return $null
    }
    throw
  }
}

function Get-SourceFileContent([string]$FileName) {
  if ($settings.DASHBOARD_SOURCE_MODE -eq 'local') {
    return Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $settings.DASHBOARD_LOCAL_DIR $FileName)
  }
  $subDir = if ($settings.DASHBOARD_VARIANT -eq 'orig') { "dashboards/original/$($settings.DASHBOARD_LANGUAGE)" } else { "dashboards/translation/$($settings.DASHBOARD_LANGUAGE)" }
  $sourceUrl = @(
    'https://raw.githubusercontent.com',
    $settings.GITHUB_REPO,
    $settings.GITHUB_REF,
    $subDir.Replace('\\','/').Trim('/'),
    [Uri]::EscapeDataString($FileName)
  ) -join '/'
  $response = Invoke-WebRequest -UseBasicParsing -Method Get -Uri $sourceUrl
  if ($null -ne $response.RawContentStream) {
    try {
      $response.RawContentStream.Position = 0
      $reader = New-Object System.IO.StreamReader($response.RawContentStream, [System.Text.Encoding]::UTF8, $true)
      try { return $reader.ReadToEnd() } finally { $reader.Dispose() }
    } catch { }
  }
  return $response.Content
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
    foreach ($prop in $Node.PSObject.Properties) { $out[$prop.Name] = Replace-DatasourcePlaceholders $prop.Value }
    if ($out.ContainsKey('type') -and [string]$out['type'] -eq 'victoriametrics-metrics-datasource' -and $out.ContainsKey('uid')) {
      $out['uid'] = $settings.GRAFANA_DS_VM_EVCC_UID
    }
    return [pscustomobject]$out
  }
  return $Node
}

function Build-Inputs($Raw) {
  $inputs = @()
  $rawInputs = @()
  if ($null -ne $Raw.PSObject.Properties['__inputs']) { $rawInputs = @($Raw.__inputs) }
  foreach ($input in $rawInputs) {
    if ($null -eq $input -or -not $input.name -or -not $input.type) { continue }
    if ($input.type -eq 'datasource') {
      $value = if ($input.name -eq 'DS_VM-EVCC') { $settings.GRAFANA_DS_VM_EVCC_UID } elseif ($input.pluginId -eq '__expr__') { '__expr__' } else { '' }
      if (-not $value) { throw "Missing datasource mapping for input $($input.name)" }
      $inputs += @{ name = $input.name; type = $input.type; pluginId = $input.pluginId; value = $value }
    } else {
      $inputs += @{ name = $input.name; type = $input.type; value = $input.value }
    }
  }
  return $inputs
}

function Get-DashboardBuildMarker() {
  $timestamp = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss zzz")
  $source = if ($settings.DASHBOARD_SOURCE_MODE -eq 'local') {
    "local:$($settings.DASHBOARD_LOCAL_DIR)"
  } else {
    "github:$($settings.GITHUB_REPO)@$($settings.GITHUB_REF)"
  }
  return "deployed $timestamp | $($settings.DASHBOARD_LANGUAGE)/$($settings.DASHBOARD_VARIANT) | $source"
}

function Get-DashboardOverrides() {
  return @{
    peakPowerLimit = $settings.DASHBOARD_FILTER_PEAK_POWER_LIMIT
    energySampleInterval = $(if ($settings.DASHBOARD_ENERGY_SAMPLE_INTERVAL) { $settings.DASHBOARD_ENERGY_SAMPLE_INTERVAL } else { $settings.DASHBOARD_FILTER_ENERGY_SAMPLE_INTERVAL })
    tariffPriceInterval = $(if ($settings.DASHBOARD_TARIFF_PRICE_INTERVAL) { $settings.DASHBOARD_TARIFF_PRICE_INTERVAL } else { $settings.DASHBOARD_FILTER_TARIFF_PRICE_INTERVAL })
    installedWattPeak = $settings.DASHBOARD_INSTALLED_WATT_PEAK
    loadpointBlocklist = $settings.DASHBOARD_FILTER_LOADPOINT_BLOCKLIST
    extBlocklist = $settings.DASHBOARD_FILTER_EXT_BLOCKLIST
    auxBlocklist = $settings.DASHBOARD_FILTER_AUX_BLOCKLIST
    vehicleBlocklist = $settings.DASHBOARD_FILTER_VEHICLE_BLOCKLIST
    evccUrl = $settings.DASHBOARD_EVCC_URL
    inverterPortalTitle = $settings.DASHBOARD_PORTAL_TITLE
    inverterPortalUrl = $settings.DASHBOARD_PORTAL_URL
  }
}

function Set-DashboardBuildDescription($Raw, [string]$BuildMarker) {
  if ($null -eq $Raw -or [string]::IsNullOrWhiteSpace($BuildMarker)) { return $Raw }
  if ($null -eq $Raw.PSObject.Properties['templating'] -or $null -eq $Raw.templating) { return $Raw }
  if ($null -eq $Raw.templating.PSObject.Properties['list']) { return $Raw }
  foreach ($variable in @($Raw.templating.list)) {
    if ([string]$variable.name -eq 'dashboardBuild') {
      $variable.description = $BuildMarker
    }
  }
  return $Raw
}

function Apply-DashboardFilterOverrides($Raw, [hashtable]$Overrides) {
  if ($null -eq $Raw -or $null -eq $Overrides -or $Overrides.Count -eq 0) { return $Raw }
  if ($null -eq $Raw.PSObject.Properties['templating'] -or $null -eq $Raw.templating) { return $Raw }
  if ($null -eq $Raw.templating.PSObject.Properties['list']) { return $Raw }
  foreach ($variable in @($Raw.templating.list)) {
    $name = [string]$variable.name
    if (-not $Overrides.ContainsKey($name)) { continue }
    $value = [string]$Overrides[$name]
    if ([string]::IsNullOrWhiteSpace($value)) { continue }
    $variable.query = $value
    if ($null -eq $variable.current) {
      $variable | Add-Member -NotePropertyName current -NotePropertyValue ([pscustomobject]@{ text = $value; value = $value }) -Force
    } else {
      $variable.current.text = $value
      $variable.current.value = $value
    }
    if ($null -ne $variable.PSObject.Properties['options']) {
      $variable.options = @([pscustomobject]@{ selected = $true; text = $value; value = $value })
    }
  }
  return $Raw
}

function Ensure-Folder() {
  $folderUid = [Uri]::EscapeDataString($settings.GRAFANA_FOLDER_UID)
  $existing = Invoke-GrafanaApi GET "/api/folders/$folderUid" -Allow404
  if ($null -eq $existing) {
    Invoke-GrafanaApi POST '/api/folders' @{ uid = $settings.GRAFANA_FOLDER_UID; title = $settings.GRAFANA_FOLDER_TITLE } | Out-Null
  }
}

function Remove-IfExists([string]$Path) {
  Invoke-GrafanaApi DELETE $Path -Allow404 | Out-Null
}

function Remove-And-Report([string]$Kind, [string]$Name, [string]$Uid, [string]$Path) {
  $existing = Invoke-GrafanaApi GET $Path -Allow404
  if ($null -eq $existing) {
    Write-Host "Skipping ${Kind} delete (not found): $Name [$Uid]" -ForegroundColor DarkYellow
    return
  }
  Invoke-GrafanaApi DELETE $Path -Allow404 | Out-Null
  $afterDelete = Invoke-GrafanaApi GET $Path -Allow404
  if ($null -eq $afterDelete) {
    Write-Host "Deleted ${Kind}: $Name [$Uid]" -ForegroundColor Green
  } else {
    throw "Failed to delete ${Kind} $Name [$Uid]"
  }
}

function Update-LibraryPanel($Element, $Existing) {
  if ($null -eq $Element -or -not $Element.uid) { return }
  $body = @{
    name = $(if ($Element.name) { $Element.name } else { $Existing.name })
    kind = $(if ($Element.kind) { $Element.kind } elseif ($Existing.kind) { $Existing.kind } else { 1 })
    model = (Replace-DatasourcePlaceholders $Element.model)
    version = $Existing.version
  }
  if ($Existing.folderUid) { $body.folderUid = $Existing.folderUid }
  elseif ($Element.folderUid) { $body.folderUid = $Element.folderUid }
  Invoke-GrafanaApi PATCH "/api/library-elements/$([Uri]::EscapeDataString($Element.uid))" $body | Out-Null
  Write-Host "Updated library panel: $($body.name) [$($Element.uid)]" -ForegroundColor Green
}
function Confirm-Apply() {
  $answer = Read-Host 'Proceed with dashboard deployment? [y/N]'
  return $answer -match '^(y|yes)$'
}

$settings = @{
  GRAFANA_URL = 'http://localhost:3000'
  GRAFANA_API_TOKEN = ''
  GRAFANA_DS_VM_EVCC_UID = 'vm-evcc'
  GRAFANA_FOLDER_UID = 'evcc'
  GRAFANA_FOLDER_TITLE = 'EVCC'
  DASHBOARD_SOURCE_MODE = 'github'
  GITHUB_REPO = 'endurance1968/evcc-grafana-dashboards'
  GITHUB_REF = 'main'
  DASHBOARD_LANGUAGE = 'en'
  DASHBOARD_VARIANT = 'gen'
  DASHBOARD_LOCAL_DIR = ''
  PURGE = 'false'
  DASHBOARD_FILTER_PEAK_POWER_LIMIT = ''
  DASHBOARD_ENERGY_SAMPLE_INTERVAL = ''
  DASHBOARD_TARIFF_PRICE_INTERVAL = ''
  DASHBOARD_FILTER_ENERGY_SAMPLE_INTERVAL = ''
  DASHBOARD_FILTER_TARIFF_PRICE_INTERVAL = ''
  DASHBOARD_INSTALLED_WATT_PEAK = ''
  DASHBOARD_FILTER_LOADPOINT_BLOCKLIST = ''
  DASHBOARD_FILTER_EXT_BLOCKLIST = ''
  DASHBOARD_FILTER_AUX_BLOCKLIST = ''
  DASHBOARD_FILTER_VEHICLE_BLOCKLIST = ''
  DASHBOARD_EVCC_URL = ''
  DASHBOARD_PORTAL_TITLE = ''
  DASHBOARD_PORTAL_URL = ''
}

$fileSettings = Load-DotEnv $config
foreach ($entry in $fileSettings.GetEnumerator()) { $settings[$entry.Key] = $entry.Value }
foreach ($key in @('GRAFANA_URL','GRAFANA_API_TOKEN','GRAFANA_DS_VM_EVCC_UID','GRAFANA_FOLDER_UID','GRAFANA_FOLDER_TITLE','DASHBOARD_SOURCE_MODE','GITHUB_REPO','GITHUB_REF','DASHBOARD_LANGUAGE','DASHBOARD_VARIANT','DASHBOARD_LOCAL_DIR','PURGE','DEPLOY_PURGE','DASHBOARD_FILTER_PEAK_POWER_LIMIT','DASHBOARD_ENERGY_SAMPLE_INTERVAL','DASHBOARD_TARIFF_PRICE_INTERVAL','DASHBOARD_FILTER_ENERGY_SAMPLE_INTERVAL','DASHBOARD_FILTER_TARIFF_PRICE_INTERVAL','DASHBOARD_INSTALLED_WATT_PEAK','DASHBOARD_FILTER_LOADPOINT_BLOCKLIST','DASHBOARD_FILTER_EXT_BLOCKLIST','DASHBOARD_FILTER_AUX_BLOCKLIST','DASHBOARD_FILTER_VEHICLE_BLOCKLIST','DASHBOARD_EVCC_URL','DASHBOARD_PORTAL_TITLE','DASHBOARD_PORTAL_URL')) {
  $envValue = [Environment]::GetEnvironmentVariable($key)
  if ($envValue) { $settings[$key] = $envValue }
}

Merge-Setting $settings 'GRAFANA_URL' $url
Merge-Setting $settings 'GRAFANA_API_TOKEN' $token
Merge-Setting $settings 'GRAFANA_DS_VM_EVCC_UID' $datasourceuid
Merge-Setting $settings 'DASHBOARD_LANGUAGE' $language
Merge-Setting $settings 'DASHBOARD_VARIANT' $variant
Merge-Setting $settings 'DASHBOARD_SOURCE_MODE' $sourcemode
Merge-Setting $settings 'GITHUB_REPO' $githubrepo
Merge-Setting $settings 'GITHUB_REF' $githubref
Merge-Setting $settings 'DASHBOARD_LOCAL_DIR' $localdir
Merge-Setting $settings 'GRAFANA_FOLDER_UID' $folderuid
Merge-Setting $settings 'GRAFANA_FOLDER_TITLE' $foldertitle
if ($settings.ContainsKey('DEPLOY_PURGE') -and -not $settings.ContainsKey('PURGE')) { $settings['PURGE'] = $settings['DEPLOY_PURGE'] }
if (-not [string]::IsNullOrWhiteSpace($purge)) { $settings['PURGE'] = if ($purge -match '^(1|true|yes|on)$') { 'true' } else { 'false' } }
$dashboardBuildMarker = Get-DashboardBuildMarker
$dashboardOverrides = Get-DashboardOverrides

if (-not $settings.GRAFANA_API_TOKEN) { throw 'Missing GRAFANA_API_TOKEN. Set it in the config file, environment, or -token.' }
if ($settings.DASHBOARD_SOURCE_MODE -eq 'local' -and -not $settings.DASHBOARD_LOCAL_DIR) { throw 'DASHBOARD_LOCAL_DIR is required when DASHBOARD_SOURCE_MODE=local.' }

$dashboardFiles = @(
  'VM_ EVCC_ All-time.json',
  'VM_ EVCC_ Jahr.json',
  'VM_ EVCC_ Monat.json',
  'VM_ EVCC_ Today - Details.json',
  'VM_ EVCC_ Today.json',
  'VM_ EVCC_ Today - Mobile.json'
)

$dashboards = @()
$libraryElements = @{}
foreach ($fileName in $dashboardFiles) {
  $raw = (Get-SourceFileContent $fileName) | ConvertFrom-Json
  $raw = Apply-DashboardFilterOverrides $raw $dashboardOverrides
  $raw = Set-DashboardBuildDescription $raw $dashboardBuildMarker
  $raw = Replace-DatasourcePlaceholders $raw
  $dashboards += @{ fileName = $fileName; raw = $raw; inputs = (Build-Inputs $raw) }
  if ($null -ne $raw.PSObject.Properties['__elements']) {
    foreach ($prop in $raw.__elements.PSObject.Properties) { $libraryElements[$prop.Name] = $prop.Value }
  }
}

$null = Invoke-GrafanaApi GET '/api/search?limit=1'
Write-Host 'Grafana check: OK' -ForegroundColor Green
Write-Host "URL: $($settings.GRAFANA_URL)"
Write-Host "Folder: $($settings.GRAFANA_FOLDER_TITLE) ($($settings.GRAFANA_FOLDER_UID))"
Write-Host "Datasource UID: $($settings.GRAFANA_DS_VM_EVCC_UID)"
if ($settings.DASHBOARD_SOURCE_MODE -eq 'local') { Write-Host "Source: local / $($settings.DASHBOARD_LOCAL_DIR)" } else { Write-Host "Source: github / $($settings.GITHUB_REPO) / $($settings.GITHUB_REF)" }
Write-Host "Language: $($settings.DASHBOARD_LANGUAGE)"
Write-Host "Variant: $($settings.DASHBOARD_VARIANT)"
Write-Host "Build marker: $dashboardBuildMarker"
Write-Host "Purge: $($settings.PURGE)"
$activeDashboardOverrides = @($dashboardOverrides.GetEnumerator() | Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_.Value) })
if ($activeDashboardOverrides.Count -gt 0) {
  Write-Host ''
  Write-Host 'Will apply dashboard overrides:'
  foreach ($entry in $activeDashboardOverrides | Sort-Object Name) {
    Write-Host "- $($entry.Key) = $($entry.Value)"
  }
}
Write-Host ''
Write-Host 'Will import dashboards:'
foreach ($dashboard in $dashboards) { Write-Host "- $($dashboard.raw.title) [$($dashboard.raw.uid)]" }
Write-Host ''
Write-Host 'Dashboards embed these library panels:'
foreach ($element in $libraryElements.Values) { Write-Host "- $($element.name) [$($element.uid)]" }

$existingLibrary = @{}
foreach ($element in $libraryElements.Values) {
  if (-not $element.uid) { continue }
  $existing = Invoke-GrafanaApi GET "/api/library-elements/$([Uri]::EscapeDataString($element.uid))" -Allow404
  if ($null -ne $existing) { $existingLibrary[$element.uid] = $existing.result }
}
if ($settings.PURGE -ne 'true' -and $existingLibrary.Count -gt 0) {
  Write-Host ''
  Write-Host 'Existing library panels already present and will be updated because purge=false:' -ForegroundColor Yellow
  foreach ($item in $existingLibrary.Values) { Write-Host "- $($item.name) [$($item.uid)]" }
  Write-Host 'Dashboard import will use the updated embedded __elements definitions.' -ForegroundColor Yellow
}

if ($settings.PURGE -eq 'true') {
  $existingDashboards = @()
  foreach ($dashboard in $dashboards) {
    if (-not $dashboard.raw.uid) { continue }
    $existing = Invoke-GrafanaApi GET "/api/dashboards/uid/$([Uri]::EscapeDataString($dashboard.raw.uid))" -Allow404
    if ($null -ne $existing) { $existingDashboards += $existing.dashboard }
  }
  Write-Host ''
  Write-Host 'Will delete existing dashboards before import:'
  if ($existingDashboards.Count -eq 0) { Write-Host '- none' } else { foreach ($item in $existingDashboards) { Write-Host "- $($item.title) [$($item.uid)]" } }
  Write-Host ''
  Write-Host 'Will delete existing library panels before import:'
  if ($existingLibrary.Count -eq 0) { Write-Host '- none' } else { foreach ($item in $existingLibrary.Values) { Write-Host "- $($item.name) [$($item.uid)]" } }
}

Write-Host ''
if (-not (Confirm-Apply)) {
  Write-Host 'Aborted. No changes applied.' -ForegroundColor Yellow
  exit 0
}

Ensure-Folder
if ($settings.PURGE -eq 'true') {
  foreach ($dashboard in $dashboards) {
    if ($dashboard.raw.uid) {
      Remove-And-Report 'dashboard' $dashboard.raw.title $dashboard.raw.uid "/api/dashboards/uid/$([Uri]::EscapeDataString($dashboard.raw.uid))"
    }
  }
  foreach ($uid in $existingLibrary.Keys) {
    $item = $existingLibrary[$uid]
    Remove-And-Report 'library panel' $item.name $uid "/api/library-elements/$([Uri]::EscapeDataString($uid))"
  }
} else {
  foreach ($uid in $existingLibrary.Keys) {
    Update-LibraryPanel $libraryElements[$uid] $existingLibrary[$uid]
  }
}

foreach ($dashboard in $dashboards) {
  $body = @{ dashboard = $dashboard.raw; folderUid = $settings.GRAFANA_FOLDER_UID; overwrite = $true; message = 'EVCC VM dashboard install'; inputs = [object[]]@($dashboard.inputs) }
  $headers = @{ Authorization = "Bearer $($settings.GRAFANA_API_TOKEN)"; Accept = 'application/json' }
  $uri = ($settings.GRAFANA_URL.TrimEnd('/')) + '/api/dashboards/import'
  $jsonBody = $body | ConvertTo-Json -Depth 100
  $jsonBytes = [System.Text.Encoding]::UTF8.GetBytes($jsonBody)
  Write-Host "Importing dashboard: $($dashboard.raw.title) [$($dashboard.raw.uid)]"
  Invoke-WebRequest -UseBasicParsing -Method Post -Uri $uri -Headers $headers -ContentType 'application/json; charset=utf-8' -Body $jsonBytes | Out-Null
  Write-Host "Imported dashboard: $($dashboard.raw.title)"
}

Write-Host ''
Write-Host 'Install finished.' -ForegroundColor Green
Write-Host "Folder: $($settings.GRAFANA_FOLDER_TITLE) ($($settings.GRAFANA_FOLDER_UID))"


