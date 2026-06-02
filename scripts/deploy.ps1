<#
.SYNOPSIS
Deploy dashboards to Grafana from GitHub, a raw URL base, or a local dashboard directory.

.DESCRIPTION
Loads the install environment, resolves the requested dashboard source and
pushes the fixed dashboard file list into the target Grafana folder.
#>
param(
  [string]$config = (Join-Path $PSScriptRoot "vm-dashboard-install.env"),
  [string]$url,
  [string]$token,
  [string]$purge = "",
  [string]$purgeonly = "",
  [string]$datasourceuid,
  [string]$language,
  [string]$variant,
  [string]$sourcemode,
  [string]$githubrepo,
  [string]$githubref,
  [string]$rawurl,
  [string]$localdir,
  [string]$folderuid,
  [string]$foldertitle,
  [string]$authmode,
  [string]$user,
  [string]$password,
  [string]$theme
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ScriptVersion = '2026.06.02.1'
$ScriptBuildDate = '2026-05-31'
$ScriptLastModified = '2026-06-02'
Write-Host "$((Split-Path -Leaf $PSCommandPath)) v$ScriptVersion (build $ScriptBuildDate, last modified $ScriptLastModified, run $((Get-Date).ToString('yyyy-MM-ddTHH:mm:sszzz')))"

function Load-DotEnv([string]$Path) {
  $map = @{}
  if (-not (Test-Path -LiteralPath $Path)) { return $map }
  foreach ($line in Get-Content -LiteralPath $Path) {
    $trimmed = $line.Trim()
    if (-not $trimmed -or $trimmed.StartsWith('#')) { continue }
    $idx = $trimmed.IndexOf('=')
    if ($idx -lt 1) { continue }
    $key = $trimmed.Substring(0, $idx).Trim()
    if ($map.ContainsKey($key)) {
      throw "Duplicate key in ${Path}: $key. Define each key only once; comment out old alternatives."
    }
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

function Resolve-GrafanaAuthMode {
  $mode = ([string]$settings.GRAFANA_AUTH_MODE).Trim().ToLowerInvariant()
  if ([string]::IsNullOrWhiteSpace($mode) -or $mode -eq 'auto') {
    if (-not [string]::IsNullOrWhiteSpace([string]$settings.GRAFANA_API_TOKEN)) { return 'token' }
    if (-not [string]::IsNullOrWhiteSpace([string]$settings.GRAFANA_USER) -and -not [string]::IsNullOrWhiteSpace([string]$settings.GRAFANA_PASSWORD)) { return 'basic' }
    return 'token'
  }
  if ($mode -in @('token','bearer','service-account','service_account')) { return 'token' }
  if ($mode -in @('basic','userpass','user-password')) { return 'basic' }
  throw "Unsupported GRAFANA_AUTH_MODE '$($settings.GRAFANA_AUTH_MODE)'. Use auto, token, or basic."
}

function Get-GrafanaHeaders {
  $headers = @{ Accept = 'application/json' }
  $mode = Resolve-GrafanaAuthMode
  if ($mode -eq 'basic') {
    if ([string]::IsNullOrWhiteSpace([string]$settings.GRAFANA_USER) -or [string]::IsNullOrWhiteSpace([string]$settings.GRAFANA_PASSWORD)) {
      throw 'Missing GRAFANA_USER or GRAFANA_PASSWORD for GRAFANA_AUTH_MODE=basic.'
    }
    $raw = "$($settings.GRAFANA_USER):$($settings.GRAFANA_PASSWORD)"
    $headers.Authorization = "Basic $([Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($raw)))"
    return $headers
  }
  if ([string]::IsNullOrWhiteSpace([string]$settings.GRAFANA_API_TOKEN)) {
    throw 'Missing GRAFANA_API_TOKEN. For Grafana 13 use a service-account token, or set GRAFANA_AUTH_MODE=basic with GRAFANA_USER and GRAFANA_PASSWORD.'
  }
  $headers.Authorization = "Bearer $($settings.GRAFANA_API_TOKEN)"
  return $headers
}

function Get-ErrorResponseText($ErrorRecord) {
  try {
    $response = $ErrorRecord.Exception.Response
    if ($null -eq $response) { return '' }
    $stream = $response.GetResponseStream()
    if ($null -eq $stream) { return '' }
    $reader = New-Object System.IO.StreamReader($stream)
    try { return $reader.ReadToEnd() } finally { $reader.Dispose() }
  } catch {
    return ''
  }
}

function Get-GrafanaVersion {
  $uri = ($settings.GRAFANA_URL.TrimEnd('/')) + '/api/health'
  try {
    $response = Invoke-WebRequest -UseBasicParsing -Method Get -Uri $uri
    if (-not $response.Content) { return 'unknown' }
    $health = $response.Content | ConvertFrom-Json
    if ($health.version) { return [string]$health.version }
  } catch {
    return 'unknown'
  }
  return 'unknown'
}

function Invoke-GrafanaApi([string]$Method, [string]$Path, $Body = $null, [switch]$Allow404) {
  $uri = ($settings.GRAFANA_URL.TrimEnd('/') ) + $Path
  $headers = Get-GrafanaHeaders
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
    if ($_.Exception.Response -and $_.Exception.Response.StatusCode.value__ -eq 401) {
      $responseText = Get-ErrorResponseText $_
      throw "Grafana authentication failed for $Method $Path (401). Response: $responseText`nGrafana 13 still supports the legacy /api routes, but API keys are deprecated. Create a Grafana service-account token and set GRAFANA_API_TOKEN, or set GRAFANA_AUTH_MODE=basic with GRAFANA_USER and GRAFANA_PASSWORD."
    }
    throw
  }
}


function Resolve-GrafanaTheme {
  $raw = ([string]$settings.GRAFANA_THEME).Trim().ToLowerInvariant()
  if ([string]::IsNullOrWhiteSpace($raw)) { return $null }
  if ($raw -in @('dark','light')) { return $raw }
  if ($raw -in @('bright','bright-mode','brightmode')) { return 'light' }
  if ($raw -in @('default','grafana-default','system')) { return '' }
  throw 'Unsupported GRAFANA_THEME. Use dark, light, bright, or default.'
}

function Get-GrafanaThemeDisplay([AllowEmptyString()][string]$ThemeValue) {
  if ($ThemeValue -eq '') { return 'default' }
  return $ThemeValue
}

function Set-GrafanaOrgTheme([AllowEmptyString()][string]$ThemeValue) {
  $preferences = Invoke-GrafanaApi GET '/api/org/preferences'
  $body = @{}
  foreach ($key in @('homeDashboardId','homeDashboardUID','timezone','weekStart')) {
    if ($null -ne $preferences -and $null -ne $preferences.PSObject.Properties[$key] -and $null -ne $preferences.$key) {
      $body[$key] = $preferences.$key
    }
  }
  $body['theme'] = $ThemeValue
  Invoke-GrafanaApi PUT '/api/org/preferences' $body | Out-Null
  Write-Host "Grafana org theme set: $(Get-GrafanaThemeDisplay -ThemeValue $ThemeValue)" -ForegroundColor Green
}
function Get-EffectiveDashboardLanguage() {
  if ($settings.DASHBOARD_VARIANT -eq 'orig') { return 'en' }
  return [string]$settings.DASHBOARD_LANGUAGE
}

function Get-SourceSubDir() {
  $language = Get-EffectiveDashboardLanguage
  if ($settings.DASHBOARD_VARIANT -eq 'orig') {
    return "dashboards/original/$language"
  }
  return "dashboards/translation/$language"
}

$FixedDashboardFiles = @(
  'VM_EVCC_All-time.json',
  'VM_EVCC_Year.json',
  'VM_EVCC_Month.json',
  'VM_EVCC_Today-Details.json',
  'VM_EVCC_Today.json',
  'VM_EVCC_Today-Gauges.json',
  'VM_EVCC_Today-Mobile.json'
)


function Get-RemoteSourceUrl([string]$RelativePath) {
  $segments = New-Object System.Collections.Generic.List[string]
  if ($settings.DASHBOARD_SOURCE_MODE -eq 'rawurl') {
    $segments.Add(([string]$settings.DASHBOARD_RAW_BASE_URL).TrimEnd('/'))
  } else {
    $segments.Add('https://raw.githubusercontent.com')
    $segments.Add([string]$settings.GITHUB_REPO)
    $segments.Add([string]$settings.GITHUB_REF)
  }
  foreach ($part in $RelativePath.Replace('\\','/').Split('/')) {
    if (-not [string]::IsNullOrWhiteSpace($part)) {
      $segments.Add([Uri]::EscapeDataString($part))
    }
  }
  return ($segments -join '/')
}

function Get-RepoFileContent([string]$RelativePath) {
  $sourceUrl = Get-RemoteSourceUrl $RelativePath
  try {
    $response = Invoke-WebRequest -UseBasicParsing -Method Get -Uri $sourceUrl
  } catch {
    throw "Failed to download $RelativePath from $sourceUrl. $($_.Exception.Message)"
  }
  if ($null -ne $response.RawContentStream) {
    try {
      $response.RawContentStream.Position = 0
      $reader = New-Object System.IO.StreamReader($response.RawContentStream, [System.Text.Encoding]::UTF8, $true)
      try { return $reader.ReadToEnd() } finally { $reader.Dispose() }
    } catch { }
  }
  return $response.Content
}

function Get-SourceFileContent([string]$FileName) {
  if ($settings.DASHBOARD_SOURCE_MODE -eq 'localdir') {
    return Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $settings.DASHBOARD_LOCAL_DIR $FileName)
  }
  return Get-RepoFileContent ((Get-SourceSubDir) + '/' + $FileName)
}

function Get-DashboardFilesFromManifest() {
  if ($settings.DASHBOARD_SOURCE_MODE -eq 'localdir') {
    foreach ($file in $FixedDashboardFiles) {
      $filePath = Join-Path $settings.DASHBOARD_LOCAL_DIR $file
      if (-not (Test-Path -LiteralPath $filePath -PathType Leaf)) {
        throw "DASHBOARD_LOCAL_DIR is missing required dashboard file: $file"
      }
    }
    return $FixedDashboardFiles
  }
  $manifestPath = 'dashboards/deploy-manifest.json'
  $manifest = Parse-JsonDocument (Get-RepoFileContent $manifestPath)
  if ($null -eq $manifest.PSObject.Properties['files'] -or $null -eq $manifest.files) {
    throw "$manifestPath from $(Get-RemoteSourceUrl $manifestPath) is missing a files array. Check DASHBOARD_SOURCE_MODE=$($settings.DASHBOARD_SOURCE_MODE) and the selected source variables."
  }
  $files = @($manifest.files | ForEach-Object { [string]$_ })
  if ($files.Count -eq 0) {
    throw "$manifestPath from $(Get-RemoteSourceUrl $manifestPath) has an empty files array. Check DASHBOARD_SOURCE_MODE=$($settings.DASHBOARD_SOURCE_MODE) and the selected source variables."
  }
  return $files
}

function Convert-JsonNode($Node) {
  if ($null -eq $Node) { return $null }
  if ($Node -is [string]) { return $Node }
  if ($Node -is [System.Collections.IDictionary]) {
    $out = [ordered]@{}
    foreach ($key in $Node.Keys) {
      $out[$key] = Convert-JsonNode $Node[$key]
    }
    return [pscustomobject]$out
  }
  if ($Node -is [System.Collections.IEnumerable] -and -not ($Node -is [hashtable]) -and -not ($Node -is [pscustomobject])) {
    $items = New-Object System.Collections.Generic.List[object]
    foreach ($item in $Node) {
      $items.Add((Convert-JsonNode $item))
    }
    return ,($items.ToArray())
  }
  return $Node
}

function Parse-JsonDocument([string]$Json) {
  $command = Get-Command ConvertFrom-Json -ErrorAction Stop
  if ($command.Parameters.ContainsKey('AsHashtable')) {
    return Convert-JsonNode ($Json | ConvertFrom-Json -AsHashtable)
  }

  Add-Type -AssemblyName System.Web.Extensions
  $serializer = New-Object System.Web.Script.Serialization.JavaScriptSerializer
  $serializer.MaxJsonLength = [int]::MaxValue
  $serializer.RecursionLimit = 512
  return Convert-JsonNode ($serializer.DeserializeObject($Json))
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
    return ,$list
  }
  if ($Node -is [hashtable] -or $Node -is [pscustomobject]) {
    $out = @{}
    foreach ($prop in $Node.PSObject.Properties) { $out[$prop.Name] = Replace-DatasourcePlaceholders $prop.Value }
    if ($out.ContainsKey('group') -and [string]$out['group'] -eq 'victoriametrics-metrics-datasource' -and $out.ContainsKey('datasource') -and ($out['datasource'] -is [hashtable] -or $out['datasource'] -is [pscustomobject])) {
      $datasource = @{}
      foreach ($prop in $out['datasource'].PSObject.Properties) { $datasource[$prop.Name] = $prop.Value }
      $datasource['name'] = $settings.GRAFANA_DS_VM_EVCC_UID
      if ($datasource.ContainsKey('uid')) {
        $datasource['uid'] = $settings.GRAFANA_DS_VM_EVCC_UID
      }
      $out['datasource'] = [pscustomobject]$datasource
    }
    if ($out.ContainsKey('type') -and [string]$out['type'] -eq 'victoriametrics-metrics-datasource' -and $out.ContainsKey('uid')) {
      $out['uid'] = $settings.GRAFANA_DS_VM_EVCC_UID
    }
    return [pscustomobject]$out
  }
  return $Node
}

function Is-V2Dashboard($Raw) {
  return ($null -ne $Raw -and $null -ne $Raw.PSObject.Properties['kind'] -and [string]$Raw.kind -eq 'Dashboard' -and $null -ne $Raw.PSObject.Properties['apiVersion'] -and [string]$Raw.apiVersion -like 'dashboard.grafana.app/v2*')
}

function Get-DashboardTitle([object]$Raw) {
  if (Is-V2Dashboard $Raw) { return [string]$Raw.spec.title }
  return [string]$Raw.title
}

function Get-DashboardUid([object]$Raw) {
  if (Is-V2Dashboard $Raw) { return [string]$Raw.metadata.name }
  return [string]$Raw.uid
}

function Get-DashboardPath([object]$Raw) {
  $uid = Get-DashboardUid $Raw
  if ([string]::IsNullOrWhiteSpace($uid)) { return '' }
  if (Is-V2Dashboard $Raw) {
    return "/apis/dashboard.grafana.app/v2/namespaces/default/dashboards/$([Uri]::EscapeDataString($uid))"
  }
  return "/api/dashboards/uid/$([Uri]::EscapeDataString($uid))"
}


function Ensure-V2DashboardMetadata($Raw) {
  if (-not (Is-V2Dashboard $Raw)) { return $Raw }
  if ($null -eq $Raw.PSObject.Properties['metadata'] -or $null -eq $Raw.metadata) {
    $Raw | Add-Member -NotePropertyName metadata -NotePropertyValue ([pscustomobject]@{}) -Force
  }
  if ($null -eq $Raw.metadata.PSObject.Properties['annotations'] -or $null -eq $Raw.metadata.annotations) {
    $Raw.metadata | Add-Member -NotePropertyName annotations -NotePropertyValue ([pscustomobject]@{}) -Force
  }
  return $Raw
}

function Ensure-V2FolderAnnotation($Raw) {
  if (-not (Is-V2Dashboard $Raw)) { return $Raw }
  $Raw = Ensure-V2DashboardMetadata $Raw
  $Raw.metadata.annotations.'grafana.app/folder' = $settings.GRAFANA_FOLDER_UID
  return $Raw
}

function Build-Inputs($Raw) {
  if (Is-V2Dashboard $Raw) { return @() }
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
  if ($settings.DASHBOARD_SOURCE_MODE -eq 'localdir') {
    $source = "localdir:$($settings.DASHBOARD_LOCAL_DIR)"
    return "deployed $timestamp | $source"
  }
  if ($settings.DASHBOARD_SOURCE_MODE -eq 'rawurl') {
    $source = "rawurl:$(([string]$settings.DASHBOARD_RAW_BASE_URL).TrimEnd('/'))"
  } else {
    $source = "github:$($settings.GITHUB_REPO)@$($settings.GITHUB_REF)"
  }
  return "deployed $timestamp | $(Get-EffectiveDashboardLanguage)/$($settings.DASHBOARD_VARIANT) | $source"
}

function Get-DashboardOverrides() {
  return @{
    peakPowerLimit = $settings.DASHBOARD_FILTER_PEAK_POWER_LIMIT
    energySampleInterval = $(if ($settings.DASHBOARD_ENERGY_SAMPLE_INTERVAL) { $settings.DASHBOARD_ENERGY_SAMPLE_INTERVAL } else { $settings.DASHBOARD_FILTER_ENERGY_SAMPLE_INTERVAL })
    tariffPriceInterval = $(if ($settings.DASHBOARD_TARIFF_PRICE_INTERVAL) { $settings.DASHBOARD_TARIFF_PRICE_INTERVAL } else { $settings.DASHBOARD_FILTER_TARIFF_PRICE_INTERVAL })
    installedWattPeak = $settings.DASHBOARD_INSTALLED_WATT_PEAK
    vehicleConsumption = $(if ($settings.DASHBOARD_VEHICLE_CONSUMPTION_L_PER_100KM) { $settings.DASHBOARD_VEHICLE_CONSUMPTION_L_PER_100KM } else { $settings.DASHBOARD_ICE_CONSUMPTION_L_PER_100KM })
    fuelCost = $(if ($settings.DASHBOARD_FUEL_COST_PER_L) { $settings.DASHBOARD_FUEL_COST_PER_L } else { $settings.DASHBOARD_FUEL_PRICE_PER_L })
    purchasePricePv = $settings.DASHBOARD_PV_PURCHASE_PRICE
    batteryPurchasePrice = $settings.DASHBOARD_BATTERY_PURCHASE_PRICE
    runningCosts = $settings.DASHBOARD_RUNNING_COSTS_YEARLY
    storageCapacity = $(if ($settings.DASHBOARD_STORAGE_CAPACITY_WH) { $settings.DASHBOARD_STORAGE_CAPACITY_WH } else { $settings.DASHBOARD_BATTERY_CAPACITY_WH })
    heatPumpLoadpointRegex = $settings.DASHBOARD_HEAT_PUMP_LOADPOINT_REGEX
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
  if (Is-V2Dashboard $Raw) {
    foreach ($variable in @($Raw.spec.variables)) {
      if ([string]$variable.spec.name -eq 'dashboardBuild') {
        $variable.spec.description = $BuildMarker
      }
    }
    return $Raw
  }
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
  if (Is-V2Dashboard $Raw) {
    foreach ($variable in @($Raw.spec.variables)) {
      $name = [string]$variable.spec.name
      if (-not $Overrides.ContainsKey($name)) { continue }
      $value = [string]$Overrides[$name]
      if ([string]::IsNullOrWhiteSpace($value)) { continue }
      if ($variable.kind -ne 'QueryVariable') {
        $variable.spec.query = $value
      }
      if ($null -eq $variable.spec.current) {
        $variable.spec | Add-Member -NotePropertyName current -NotePropertyValue ([pscustomobject]@{ text = $value; value = $value }) -Force
      } else {
        $variable.spec.current.text = $value
        $variable.spec.current.value = $value
      }
      if ($null -ne $variable.spec.PSObject.Properties['options']) {
        $variable.spec.options = @([pscustomobject]@{ selected = $true; text = $value; value = $value })
      }
    }
    return $Raw
  }
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

function Create-LibraryPanel($Element) {
  if ($null -eq $Element -or -not $Element.uid) { return }
  $body = @{
    uid = $Element.uid
    name = $Element.name
    kind = $(if ($Element.kind) { $Element.kind } else { 1 })
    folderUid = $settings.GRAFANA_FOLDER_UID
    model = (Replace-DatasourcePlaceholders $Element.model)
  }
  Invoke-GrafanaApi POST '/api/library-elements' $body | Out-Null
  Write-Host "Created library panel: $($body.name) [$($Element.uid)]" -ForegroundColor Green
}

function Import-ClassicDashboard($Dashboard) {
  $body = @{ dashboard = $Dashboard.raw; folderUid = $settings.GRAFANA_FOLDER_UID; overwrite = $true; message = 'EVCC VM dashboard install'; inputs = [object[]]@($Dashboard.inputs) }
  Invoke-GrafanaApi POST '/api/dashboards/import' $body | Out-Null
}

function Import-V2Dashboard($Dashboard) {
  $raw = Ensure-V2FolderAnnotation $Dashboard.raw
  $path = Get-DashboardPath $raw
  $existing = Invoke-GrafanaApi GET $path -Allow404
  if ($null -ne $existing -and $existing.metadata.resourceVersion) {
    $raw.metadata.resourceVersion = $existing.metadata.resourceVersion
    Invoke-GrafanaApi PUT $path $raw | Out-Null
    return
  }
  Invoke-GrafanaApi POST '/apis/dashboard.grafana.app/v2/namespaces/default/dashboards' $raw | Out-Null
}
function Confirm-Apply([string]$Prompt = 'Proceed with dashboard deployment? [y/N]') {
  $answer = Read-Host $Prompt
  return $answer -match '^(y|yes)$'
}
function Test-Truthy($Value) {
  return [string]$Value -match '^(?i:1|true|yes|on)$'
}

$settings = @{
  GRAFANA_URL = 'http://localhost:3000'
  GRAFANA_AUTH_MODE = 'auto'
  GRAFANA_API_TOKEN = ''
  GRAFANA_SERVICE_ACCOUNT_TOKEN = ''
  GRAFANA_USER = ''
  GRAFANA_PASSWORD = ''
  GRAFANA_DS_VM_EVCC_UID = 'vm-evcc'
  GRAFANA_FOLDER_UID = 'evcc'
  GRAFANA_FOLDER_TITLE = 'EVCC'
  GRAFANA_THEME = ''
  DASHBOARD_SOURCE_MODE = 'github'
  GITHUB_REPO = 'endurance1968/evcc-grafana-dashboards'
  GITHUB_REF = 'main'
  DASHBOARD_LANGUAGE = 'de'
  DASHBOARD_VARIANT = 'gen'
  DASHBOARD_RAW_BASE_URL = ''
  DASHBOARD_LOCAL_DIR = ''
  PURGE = 'false'
  PURGE_ONLY = 'false'
  DASHBOARD_FILTER_PEAK_POWER_LIMIT = ''
  DASHBOARD_ENERGY_SAMPLE_INTERVAL = ''
  DASHBOARD_TARIFF_PRICE_INTERVAL = ''
  DASHBOARD_FILTER_ENERGY_SAMPLE_INTERVAL = ''
  DASHBOARD_FILTER_TARIFF_PRICE_INTERVAL = ''
  DASHBOARD_INSTALLED_WATT_PEAK = ''
  DASHBOARD_VEHICLE_CONSUMPTION_L_PER_100KM = ''
  DASHBOARD_FUEL_COST_PER_L = ''
  DASHBOARD_STORAGE_CAPACITY_WH = ''
  DASHBOARD_ICE_CONSUMPTION_L_PER_100KM = ''
  DASHBOARD_FUEL_PRICE_PER_L = ''
  DASHBOARD_PV_PURCHASE_PRICE = ''
  DASHBOARD_BATTERY_PURCHASE_PRICE = ''
  DASHBOARD_RUNNING_COSTS_YEARLY = ''
  DASHBOARD_BATTERY_CAPACITY_WH = ''
  DASHBOARD_HEAT_PUMP_LOADPOINT_REGEX = ''
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
foreach ($key in @('GRAFANA_URL','GRAFANA_AUTH_MODE','GRAFANA_API_TOKEN','GRAFANA_SERVICE_ACCOUNT_TOKEN','GRAFANA_USER','GRAFANA_PASSWORD','GRAFANA_DS_VM_EVCC_UID','GRAFANA_FOLDER_UID','GRAFANA_FOLDER_TITLE','GRAFANA_THEME','DASHBOARD_SOURCE_MODE','GITHUB_REPO','GITHUB_REF','DASHBOARD_LANGUAGE','DASHBOARD_VARIANT','DASHBOARD_RAW_BASE_URL','DASHBOARD_LOCAL_DIR','PURGE','PURGE_ONLY','DEPLOY_PURGE','DEPLOY_PURGE_ONLY','DASHBOARD_FILTER_PEAK_POWER_LIMIT','DASHBOARD_ENERGY_SAMPLE_INTERVAL','DASHBOARD_TARIFF_PRICE_INTERVAL','DASHBOARD_FILTER_ENERGY_SAMPLE_INTERVAL','DASHBOARD_FILTER_TARIFF_PRICE_INTERVAL','DASHBOARD_INSTALLED_WATT_PEAK','DASHBOARD_VEHICLE_CONSUMPTION_L_PER_100KM','DASHBOARD_FUEL_COST_PER_L','DASHBOARD_STORAGE_CAPACITY_WH','DASHBOARD_ICE_CONSUMPTION_L_PER_100KM','DASHBOARD_FUEL_PRICE_PER_L','DASHBOARD_PV_PURCHASE_PRICE','DASHBOARD_BATTERY_PURCHASE_PRICE','DASHBOARD_RUNNING_COSTS_YEARLY','DASHBOARD_BATTERY_CAPACITY_WH','DASHBOARD_HEAT_PUMP_LOADPOINT_REGEX','DASHBOARD_FILTER_LOADPOINT_BLOCKLIST','DASHBOARD_FILTER_EXT_BLOCKLIST','DASHBOARD_FILTER_AUX_BLOCKLIST','DASHBOARD_FILTER_VEHICLE_BLOCKLIST','DASHBOARD_EVCC_URL','DASHBOARD_PORTAL_TITLE','DASHBOARD_PORTAL_URL')) {
  $envValue = [Environment]::GetEnvironmentVariable($key)
  if ($envValue) { $settings[$key] = $envValue }
}

Merge-Setting $settings 'GRAFANA_URL' $url
Merge-Setting $settings 'GRAFANA_AUTH_MODE' $authmode
Merge-Setting $settings 'GRAFANA_API_TOKEN' $token
Merge-Setting $settings 'GRAFANA_USER' $user
Merge-Setting $settings 'GRAFANA_PASSWORD' $password
Merge-Setting $settings 'GRAFANA_THEME' $theme
Merge-Setting $settings 'GRAFANA_DS_VM_EVCC_UID' $datasourceuid
Merge-Setting $settings 'DASHBOARD_LANGUAGE' $language
Merge-Setting $settings 'DASHBOARD_VARIANT' $variant
Merge-Setting $settings 'DASHBOARD_SOURCE_MODE' $sourcemode
Merge-Setting $settings 'GITHUB_REPO' $githubrepo
Merge-Setting $settings 'GITHUB_REF' $githubref
Merge-Setting $settings 'DASHBOARD_RAW_BASE_URL' $rawurl
Merge-Setting $settings 'DASHBOARD_LOCAL_DIR' $localdir
Merge-Setting $settings 'GRAFANA_FOLDER_UID' $folderuid
Merge-Setting $settings 'GRAFANA_FOLDER_TITLE' $foldertitle
if ($settings.ContainsKey('DEPLOY_PURGE') -and -not $settings.ContainsKey('PURGE')) { $settings['PURGE'] = $settings['DEPLOY_PURGE'] }
if ($settings.ContainsKey('DEPLOY_PURGE_ONLY') -and -not (Test-Truthy $settings.PURGE_ONLY)) { $settings['PURGE_ONLY'] = $settings['DEPLOY_PURGE_ONLY'] }
if (-not [string]::IsNullOrWhiteSpace($purge)) { $settings['PURGE'] = if ($purge -match '^(1|true|yes|on)$') { 'true' } else { 'false' } }
if (-not [string]::IsNullOrWhiteSpace($purgeonly)) { $settings['PURGE_ONLY'] = if ($purgeonly -match '^(1|true|yes|on)$') { 'true' } else { 'false' } }
if (-not $settings.GRAFANA_API_TOKEN -and $settings.GRAFANA_SERVICE_ACCOUNT_TOKEN) { $settings.GRAFANA_API_TOKEN = $settings.GRAFANA_SERVICE_ACCOUNT_TOKEN }
$settings.DASHBOARD_SOURCE_MODE = ([string]$settings.DASHBOARD_SOURCE_MODE).Trim().ToLowerInvariant()
switch ($settings.DASHBOARD_SOURCE_MODE) {
  'github' {
    if ([string]::IsNullOrWhiteSpace([string]$settings.GITHUB_REPO)) { throw 'GITHUB_REPO is required when DASHBOARD_SOURCE_MODE=github.' }
    if ([string]::IsNullOrWhiteSpace([string]$settings.GITHUB_REF)) { throw 'GITHUB_REF is required when DASHBOARD_SOURCE_MODE=github.' }
  }
  'rawurl' {
    if ([string]::IsNullOrWhiteSpace([string]$settings.DASHBOARD_RAW_BASE_URL)) { throw 'DASHBOARD_RAW_BASE_URL is required when DASHBOARD_SOURCE_MODE=rawurl.' }
  }
  'localdir' {
    if ([string]::IsNullOrWhiteSpace([string]$settings.DASHBOARD_LOCAL_DIR)) { throw 'DASHBOARD_LOCAL_DIR is required when DASHBOARD_SOURCE_MODE=localdir.' }
    if (-not (Test-Path -LiteralPath $settings.DASHBOARD_LOCAL_DIR -PathType Container)) { throw "DASHBOARD_LOCAL_DIR does not exist or is not a directory: $($settings.DASHBOARD_LOCAL_DIR)" }
  }
  default { throw 'Unsupported DASHBOARD_SOURCE_MODE. Use github, rawurl, or localdir.' }
}

$dashboardBuildMarker = Get-DashboardBuildMarker
$dashboardOverrides = Get-DashboardOverrides
$purgeOnlyEnabled = Test-Truthy $settings.PURGE_ONLY
$purgeEnabled = (Test-Truthy $settings.PURGE) -or $purgeOnlyEnabled
$grafanaThemeConfigured = -not [string]::IsNullOrWhiteSpace([string]$settings.GRAFANA_THEME)
$grafanaTheme = Resolve-GrafanaTheme

if ((Resolve-GrafanaAuthMode) -eq 'token' -and -not $settings.GRAFANA_API_TOKEN) { throw 'Missing GRAFANA_API_TOKEN. For Grafana 13 set a service-account token in GRAFANA_API_TOKEN, or use GRAFANA_AUTH_MODE=basic with GRAFANA_USER and GRAFANA_PASSWORD.' }

$dashboardFiles = @(Get-DashboardFilesFromManifest)

$dashboards = @()
$libraryElements = @{}
foreach ($fileName in $dashboardFiles) {
  $raw = Parse-JsonDocument (Get-SourceFileContent $fileName)
  $raw = Apply-DashboardFilterOverrides $raw $dashboardOverrides
  $raw = Set-DashboardBuildDescription $raw $dashboardBuildMarker
  $raw = Replace-DatasourcePlaceholders $raw
  $raw = Ensure-V2FolderAnnotation $raw
  $dashboards += @{ fileName = $fileName; raw = $raw; inputs = (Build-Inputs $raw) }
  if ($null -ne $raw.PSObject.Properties['__elements']) {
    foreach ($prop in $raw.__elements.PSObject.Properties) { $libraryElements[$prop.Name] = $prop.Value }
  }
}

$grafanaVersion = Get-GrafanaVersion
$null = Invoke-GrafanaApi GET '/api/search?limit=1'
Write-Host 'Grafana check: OK' -ForegroundColor Green
Write-Host "URL: $($settings.GRAFANA_URL)"
Write-Host "Grafana version: $grafanaVersion"
Write-Host "Auth mode: $(Resolve-GrafanaAuthMode)"
Write-Host "Folder: $($settings.GRAFANA_FOLDER_TITLE) ($($settings.GRAFANA_FOLDER_UID))"
Write-Host "Datasource UID: $($settings.GRAFANA_DS_VM_EVCC_UID)"
if ($grafanaThemeConfigured) {
  $action = if ($purgeOnlyEnabled) { 'not applied in purge-only mode' } else { 'will update org preference' }
  Write-Host "Grafana theme: $(Get-GrafanaThemeDisplay -ThemeValue $grafanaTheme) ($action)"
}
if ($settings.DASHBOARD_SOURCE_MODE -eq 'localdir') {
  Write-Host "Source: localdir / $($settings.DASHBOARD_LOCAL_DIR)"
} else {
  if ($settings.DASHBOARD_SOURCE_MODE -eq 'rawurl') {
    Write-Host "Source: rawurl / $(([string]$settings.DASHBOARD_RAW_BASE_URL).TrimEnd('/'))"
  } else {
    Write-Host "Source: github / $($settings.GITHUB_REPO) / $($settings.GITHUB_REF)"
  }
  Write-Host "Language: $($settings.DASHBOARD_LANGUAGE)"
  Write-Host "Variant: $($settings.DASHBOARD_VARIANT)"
  if ($settings.DASHBOARD_VARIANT -eq 'orig' -and $settings.DASHBOARD_LANGUAGE -ne 'en') {
    Write-Host 'Effective source language: en (orig dashboards stay English)'
  }
}
Write-Host "Build marker: $dashboardBuildMarker"
Write-Host "Purge: $($settings.PURGE)"
Write-Host "Purge only: $($settings.PURGE_ONLY)"
$activeDashboardOverrides = @($dashboardOverrides.GetEnumerator() | Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_.Value) })
if ($activeDashboardOverrides.Count -gt 0) {
  Write-Host ''
  Write-Host 'Will apply dashboard overrides:'
  foreach ($entry in $activeDashboardOverrides | Sort-Object Name) {
    Write-Host "- $($entry.Key) = $($entry.Value)"
  }
}
Write-Host ''
if ($purgeOnlyEnabled) { Write-Host 'Will inspect dashboards for purge-only deletion:' } else { Write-Host 'Will import dashboards:' }
foreach ($dashboard in $dashboards) { Write-Host "- $(Get-DashboardTitle $dashboard.raw) [$(Get-DashboardUid $dashboard.raw)]" }
Write-Host ''
Write-Host 'Dashboards embed these library panels:'
foreach ($element in $libraryElements.Values) { Write-Host "- $($element.name) [$($element.uid)]" }

$existingLibrary = @{}
foreach ($element in $libraryElements.Values) {
  if (-not $element.uid) { continue }
  $existing = Invoke-GrafanaApi GET "/api/library-elements/$([Uri]::EscapeDataString($element.uid))" -Allow404
  if ($null -ne $existing) { $existingLibrary[$element.uid] = $existing.result }
}
if (-not $purgeEnabled -and $existingLibrary.Count -gt 0) {
  Write-Host ''
  Write-Host 'Existing library panels already present and will be updated because purge=false:' -ForegroundColor Yellow
  foreach ($item in $existingLibrary.Values) { Write-Host "- $($item.name) [$($item.uid)]" }
  Write-Host 'Dashboard import will use the updated embedded __elements definitions.' -ForegroundColor Yellow
}

if ($purgeEnabled) {
  $existingDashboards = @()
  foreach ($dashboard in $dashboards) {
    $path = Get-DashboardPath $dashboard.raw
    if ([string]::IsNullOrWhiteSpace($path)) { continue }
    $existing = Invoke-GrafanaApi GET $path -Allow404
    if ($null -eq $existing) { continue }
    if (Is-V2Dashboard $dashboard.raw) {
      $existingDashboards += $existing
    } else {
      $existingDashboards += $existing.dashboard
    }
  }
  Write-Host ''
  if ($purgeOnlyEnabled) { Write-Host 'Will delete existing dashboards without import:' } else { Write-Host 'Will delete existing dashboards before import:' }
  if ($existingDashboards.Count -eq 0) { Write-Host '- none' } else { foreach ($item in $existingDashboards) { Write-Host "- $(Get-DashboardTitle $item) [$(Get-DashboardUid $item)]" } }
  Write-Host ''
  if ($purgeOnlyEnabled) { Write-Host 'Will delete referenced library panels after dashboard deletion:' } else { Write-Host 'Will ensure referenced library panels before import:' }
  if ($existingLibrary.Count -eq 0) { if ($purgeOnlyEnabled) { Write-Host '- none' } else { Write-Host '- none found yet; missing panels will be created' } } else { foreach ($item in $existingLibrary.Values) { Write-Host "- $($item.name) [$($item.uid)]" } }
}

Write-Host ''
$confirmPrompt = if ($purgeOnlyEnabled) { 'Proceed with purge-only deletion? [y/N]' } else { 'Proceed with dashboard deployment? [y/N]' }
if (-not (Confirm-Apply $confirmPrompt)) {
  Write-Host 'Aborted. No changes applied.' -ForegroundColor Yellow
  exit 0
}

if ($grafanaThemeConfigured -and -not $purgeOnlyEnabled) {
  Set-GrafanaOrgTheme -ThemeValue $grafanaTheme
}

if ($purgeEnabled) {
  foreach ($dashboard in $dashboards) {
    $uid = Get-DashboardUid $dashboard.raw
    if ($uid) {
      Remove-And-Report 'dashboard' (Get-DashboardTitle $dashboard.raw) $uid (Get-DashboardPath $dashboard.raw)
    }
  }
  if ($purgeOnlyEnabled) {
    foreach ($uid in ($libraryElements.Keys | Sort-Object)) {
      $element = $libraryElements[$uid]
      Remove-And-Report 'library panel' $element.name $uid "/api/library-elements/$([Uri]::EscapeDataString($uid))"
    }
    Write-Host ''
    Write-Host 'Purge-only finished. No dashboards imported.' -ForegroundColor Green
    exit 0
  }
}

Ensure-Folder
foreach ($uid in ($libraryElements.Keys | Sort-Object)) {
  if ($existingLibrary.ContainsKey($uid)) {
    Update-LibraryPanel $libraryElements[$uid] $existingLibrary[$uid]
    continue
  }
  Create-LibraryPanel $libraryElements[$uid]
}

foreach ($dashboard in $dashboards) {
  $title = Get-DashboardTitle $dashboard.raw
  $uid = Get-DashboardUid $dashboard.raw
  Write-Host "Importing dashboard: $title [$uid]"
  if (Is-V2Dashboard $dashboard.raw) {
    Import-V2Dashboard $dashboard
  } else {
    Import-ClassicDashboard $dashboard
  }
  Write-Host "Imported dashboard: $title"
}

Write-Host ''
Write-Host 'Install finished.' -ForegroundColor Green
Write-Host "Folder: $($settings.GRAFANA_FOLDER_TITLE) ($($settings.GRAFANA_FOLDER_UID))"
