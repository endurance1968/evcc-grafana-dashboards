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
  $uri = ($settings.GRAFANA_URL.TrimEnd('/')) + $Path
  $headers = @{ Authorization = "Bearer $($settings.GRAFANA_API_TOKEN)"; Accept = 'application/json' }
  $jsonBody = $null
  if ($null -ne $Body) {
    $jsonBody = $Body | ConvertTo-Json -Depth 100
  }
  try {
    if ($null -ne $jsonBody) {
      $response = Invoke-WebRequest -UseBasicParsing -Method $Method -Uri $uri -Headers $headers -ContentType 'application/json' -Body $jsonBody
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
    return Get-Content -Raw -LiteralPath (Join-Path $settings.DASHBOARD_LOCAL_DIR $FileName)
  }
  $subDir = if ($settings.DASHBOARD_VARIANT -eq 'orig') { "dashboards/original/$($settings.DASHBOARD_LANGUAGE)" } else { "dashboards/translation/$($settings.DASHBOARD_LANGUAGE)" }
  $sourceUrl = @(
    'https://raw.githubusercontent.com',
    $settings.GITHUB_REPO,
    $settings.GITHUB_REF,
    ($subDir -replace '\\', '/').Trim('/'),
    [Uri]::EscapeDataString($FileName)
  ) -join '/'
  return (Invoke-WebRequest -UseBasicParsing -Method Get -Uri $sourceUrl).Content
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

function Prepare-DashboardForImport($DashboardRaw) {
  $prepared = ($DashboardRaw | ConvertTo-Json -Depth 100 | ConvertFrom-Json)
  if ($null -ne $prepared.PSObject.Properties['__elements']) {
    $prepared.PSObject.Properties.Remove('__elements')
  }
  return $prepared
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
}

$fileSettings = Load-DotEnv $config
foreach ($entry in $fileSettings.GetEnumerator()) { $settings[$entry.Key] = $entry.Value }
foreach ($key in @('GRAFANA_URL','GRAFANA_API_TOKEN','GRAFANA_DS_VM_EVCC_UID','GRAFANA_FOLDER_UID','GRAFANA_FOLDER_TITLE','DASHBOARD_SOURCE_MODE','GITHUB_REPO','GITHUB_REF','DASHBOARD_LANGUAGE','DASHBOARD_VARIANT','DASHBOARD_LOCAL_DIR','PURGE','DEPLOY_PURGE')) {
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

if (-not $settings.GRAFANA_API_TOKEN) { throw 'Missing GRAFANA_API_TOKEN. Set it in the config file, environment, or -token.' }
if ($settings.DASHBOARD_SOURCE_MODE -eq 'local' -and -not $settings.DASHBOARD_LOCAL_DIR) { throw 'DASHBOARD_LOCAL_DIR is required when DASHBOARD_SOURCE_MODE=local.' }

$dashboardFiles = @(
  'VM_ EVCC_ All-time.json',
  'VM_ EVCC_ Jahr.json',
  'VM_ EVCC_ Monat.json',
  'VM_ EVCC_ Today - Details.json',
  'VM_ EVCC_ Today - Mobile.json',
  'VM_ EVCC_ Today.json'
)

$dashboards = @()
$libraryElements = @{}
foreach ($fileName in $dashboardFiles) {
  $raw = (Get-SourceFileContent $fileName) | ConvertFrom-Json
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
Write-Host "Purge: $($settings.PURGE)"
Write-Host ''
Write-Host 'Will import dashboards:'
foreach ($dashboard in $dashboards) { Write-Host "- $($dashboard.raw.title) [$($dashboard.raw.uid)]" }
Write-Host ''
Write-Host 'Will import library panels:'
foreach ($element in $libraryElements.Values) { Write-Host "- $($element.name) [$($element.uid)]" }

$existingLibrary = @{}
foreach ($element in $libraryElements.Values) {
  if (-not $element.uid) { continue }
  $existing = Invoke-GrafanaApi GET "/api/library-elements/$([Uri]::EscapeDataString($element.uid))" -Allow404
  if ($null -ne $existing) { $existingLibrary[$element.uid] = $existing.result }
}
if ($settings.PURGE -ne 'true' -and $existingLibrary.Count -gt 0) {
  Write-Host ''
  Write-Host 'Existing library panels already present and will be kept because purge=false:' -ForegroundColor Yellow
  foreach ($item in $existingLibrary.Values) { Write-Host "- $($item.name) [$($item.uid)]" }
  Write-Host 'Only missing library panels will be imported. Existing ones are skipped.' -ForegroundColor Yellow
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
    if ($dashboard.raw.uid) { Remove-IfExists "/api/dashboards/uid/$([Uri]::EscapeDataString($dashboard.raw.uid))" }
  }
  foreach ($uid in $existingLibrary.Keys) { Remove-IfExists "/api/library-elements/$([Uri]::EscapeDataString($uid))" }
}

foreach ($element in $libraryElements.Values) {
  if ($settings.PURGE -ne 'true' -and $existingLibrary.ContainsKey($element.uid)) {
    Write-Host "Keeping existing library panel: $($element.name) [$($element.uid)]"
    continue
  }
  $body = @{ uid = $element.uid; name = $element.name; kind = $(if ($element.kind) { $element.kind } else { 1 }); folderUid = $settings.GRAFANA_FOLDER_UID; model = (Replace-DatasourcePlaceholders $element.model) }
  Invoke-GrafanaApi POST '/api/library-elements' $body | Out-Null
  Write-Host "Imported library panel: $($element.name)"
}

foreach ($dashboard in $dashboards) {
  $dashboardToImport = Prepare-DashboardForImport $dashboard.raw
  $body = @{ dashboard = $dashboardToImport; folderUid = $settings.GRAFANA_FOLDER_UID; overwrite = $true; message = 'EVCC VM dashboard install'; inputs = [object[]]@($dashboard.inputs) }
  $headers = @{ Authorization = "Bearer $($settings.GRAFANA_API_TOKEN)"; Accept = 'application/json' }
  $uri = ($settings.GRAFANA_URL.TrimEnd('/')) + '/api/dashboards/import'
  $jsonBody = $body | ConvertTo-Json -Depth 100
  Write-Host "Importing dashboard: $($dashboard.raw.title) [$($dashboard.raw.uid)]"
  Invoke-WebRequest -UseBasicParsing -Method Post -Uri $uri -Headers $headers -ContentType 'application/json' -Body $jsonBody | Out-Null
  Write-Host "Imported dashboard: $($dashboard.raw.title)"
}

Write-Host ''
Write-Host 'Install finished.' -ForegroundColor Green
Write-Host "Folder: $($settings.GRAFANA_FOLDER_TITLE) ($($settings.GRAFANA_FOLDER_UID))"

