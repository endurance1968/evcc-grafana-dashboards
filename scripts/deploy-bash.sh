#!/usr/bin/env bash
# Deploy dashboards to Grafana with the bash installer flow.
# Reads vm-dashboard-install.env, resolves the dashboard file list and uploads dashboards.
set -euo pipefail
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT_VERSION="2026.06.02.1"
SCRIPT_BUILD_DATE="2026-05-31"
SCRIPT_LAST_MODIFIED="2026-06-02"
SCRIPT_NAME="${0##*/}"

CONFIG_PATH="./vm-dashboard-install.env"
CLI_URL=""
CLI_TOKEN=""
CLI_PURGE=""
CLI_PURGE_ONLY=""
CLI_THEME=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --config)
      CONFIG_PATH="$2"
      shift 2
      ;;
    --url)
      CLI_URL="$2"
      shift 2
      ;;
    --token)
      CLI_TOKEN="$2"
      shift 2
      ;;
    --purge)
      CLI_PURGE="$2"
      shift 2
      ;;
    --purge-only)
      CLI_PURGE_ONLY="$2"
      shift 2
      ;;
    --theme)
      CLI_THEME="$2"
      shift 2
      ;;
    --help|-h)
      cat <<'EOF'
Usage: ./deploy-bash.sh [--config <path>] [--url <url>] [--token <token>] [--theme dark|light|bright|default] [--purge true|false] [--purge-only true|false]
Requires: bash, curl, jq
EOF
      exit 0
      ;;
    *)
      if [[ "$CONFIG_PATH" == "./vm-dashboard-install.env" && -f "$1" ]]; then
        CONFIG_PATH="$1"
        shift
      else
        echo "Unknown argument: $1" >&2
        exit 1
      fi
      ;;
  esac
done

printf '%s v%s (build %s, last modified %s, run %s)\n' "$SCRIPT_NAME" "$SCRIPT_VERSION" "$SCRIPT_BUILD_DATE" "$SCRIPT_LAST_MODIFIED" "$(date '+%Y-%m-%dT%H:%M:%S%z')"

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required command: $1" >&2
    exit 1
  }
}

require_cmd curl
require_cmd jq

GRAFANA_URL="http://localhost:3000"
GRAFANA_AUTH_MODE="auto"
GRAFANA_API_TOKEN=""
GRAFANA_SERVICE_ACCOUNT_TOKEN=""
GRAFANA_USER=""
GRAFANA_PASSWORD=""
GRAFANA_DS_VM_EVCC_UID="vm-evcc"
GRAFANA_FOLDER_UID="evcc"
GRAFANA_FOLDER_TITLE="EVCC"
GRAFANA_THEME=""
DASHBOARD_SOURCE_MODE="github"
GITHUB_REPO="endurance1968/evcc-grafana-dashboards"
GITHUB_REF="main"
DASHBOARD_RAW_BASE_URL=""
DASHBOARD_LANGUAGE="de"
DASHBOARD_VARIANT="gen"
DASHBOARD_LOCAL_DIR=""
PURGE="false"
PURGE_ONLY="false"
DASHBOARD_FILTER_PEAK_POWER_LIMIT=""
DASHBOARD_ENERGY_SAMPLE_INTERVAL=""
DASHBOARD_TARIFF_PRICE_INTERVAL=""
DASHBOARD_FILTER_ENERGY_SAMPLE_INTERVAL=""
DASHBOARD_FILTER_TARIFF_PRICE_INTERVAL=""
DASHBOARD_INSTALLED_WATT_PEAK=""
DASHBOARD_VEHICLE_CONSUMPTION_L_PER_100KM=""
DASHBOARD_FUEL_COST_PER_L=""
DASHBOARD_STORAGE_CAPACITY_WH=""
DASHBOARD_ICE_CONSUMPTION_L_PER_100KM=""
DASHBOARD_FUEL_PRICE_PER_L=""
DASHBOARD_PV_PURCHASE_PRICE=""
DASHBOARD_BATTERY_PURCHASE_PRICE=""
DASHBOARD_RUNNING_COSTS_YEARLY=""
DASHBOARD_BATTERY_CAPACITY_WH=""
DASHBOARD_HEAT_PUMP_LOADPOINT_REGEX=""
DASHBOARD_FILTER_LOADPOINT_BLOCKLIST=""
DASHBOARD_FILTER_EXT_BLOCKLIST=""
DASHBOARD_FILTER_AUX_BLOCKLIST=""
DASHBOARD_FILTER_VEHICLE_BLOCKLIST=""
DASHBOARD_EVCC_URL=""
DASHBOARD_PORTAL_TITLE=""
DASHBOARD_PORTAL_URL=""

if [[ -f "$CONFIG_PATH" ]]; then
  duplicate_keys=$(awk -F= '
    /^[[:space:]]*($|#)/ { next }
    /^[[:space:]]*[A-Za-z_][A-Za-z0-9_]*[[:space:]]*=/ {
      key=$1
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", key)
      count[key]++
      if (count[key] == 2) duplicates[++n]=key
    }
    END { for (i=1; i<=n; i++) print duplicates[i] }
  ' "$CONFIG_PATH")
  if [[ -n "$duplicate_keys" ]]; then
    echo "Duplicate keys in $CONFIG_PATH:" >&2
    printf '%s\n' "$duplicate_keys" | sed 's/^/- /' >&2
    echo "Define each key only once; comment out old alternatives." >&2
    exit 1
  fi
  set -a
  # shellcheck disable=SC1090
  . "$CONFIG_PATH"
  set +a
fi

if [[ -n "$CLI_URL" ]]; then
  GRAFANA_URL="$CLI_URL"
fi
if [[ -n "$CLI_TOKEN" ]]; then
  GRAFANA_API_TOKEN="$CLI_TOKEN"
fi
if [[ -z "$GRAFANA_API_TOKEN" && -n "${GRAFANA_SERVICE_ACCOUNT_TOKEN:-}" ]]; then
  GRAFANA_API_TOKEN="$GRAFANA_SERVICE_ACCOUNT_TOKEN"
fi
if [[ -n "$CLI_PURGE" ]]; then
  PURGE="$CLI_PURGE"
fi
if [[ -n "$CLI_PURGE_ONLY" ]]; then
  PURGE_ONLY="$CLI_PURGE_ONLY"
fi
if [[ -n "$CLI_THEME" ]]; then
  GRAFANA_THEME="$CLI_THEME"
fi
if [[ -n "${DEPLOY_PURGE:-}" && -z "${PURGE:-}" ]]; then
  PURGE="$DEPLOY_PURGE"
fi
if [[ -n "${DEPLOY_PURGE_ONLY:-}" && "${PURGE_ONLY,,}" == "false" ]]; then
  PURGE_ONLY="$DEPLOY_PURGE_ONLY"
fi
truthy() {
  case "${1,,}" in 1|true|yes|on) return 0 ;; *) return 1 ;; esac
}
if truthy "$PURGE_ONLY"; then
  PURGE_EFFECTIVE="true"
else
  PURGE_EFFECTIVE="$PURGE"
fi


DASHBOARD_SOURCE_MODE="${DASHBOARD_SOURCE_MODE,,}"
FIXED_DASHBOARD_FILES=(
  "VM_EVCC_All-time.json"
  "VM_EVCC_Year.json"
  "VM_EVCC_Month.json"
  "VM_EVCC_Today-Details.json"
  "VM_EVCC_Today.json"
  "VM_EVCC_Today-Gauges.json"
  "VM_EVCC_Today-Mobile.json"
)
case "$DASHBOARD_SOURCE_MODE" in
  github)
    [[ -n "$GITHUB_REPO" ]] || { echo "GITHUB_REPO is required when DASHBOARD_SOURCE_MODE=github." >&2; exit 1; }
    [[ -n "$GITHUB_REF" ]] || { echo "GITHUB_REF is required when DASHBOARD_SOURCE_MODE=github." >&2; exit 1; }
    ;;
  rawurl)
    [[ -n "${DASHBOARD_RAW_BASE_URL:-}" ]] || { echo "DASHBOARD_RAW_BASE_URL is required when DASHBOARD_SOURCE_MODE=rawurl." >&2; exit 1; }
    ;;
  localdir)
    [[ -n "$DASHBOARD_LOCAL_DIR" ]] || { echo "DASHBOARD_LOCAL_DIR is required when DASHBOARD_SOURCE_MODE=localdir." >&2; exit 1; }
    [[ -d "$DASHBOARD_LOCAL_DIR" ]] || { echo "DASHBOARD_LOCAL_DIR does not exist or is not a directory: $DASHBOARD_LOCAL_DIR" >&2; exit 1; }
    ;;
  *)
    echo "Unsupported DASHBOARD_SOURCE_MODE. Use github, rawurl, or localdir." >&2
    exit 1
    ;;
esac


auth_mode() {
  local mode="${GRAFANA_AUTH_MODE,,}"
  if [[ -z "$mode" || "$mode" == "auto" ]]; then
    if [[ -n "$GRAFANA_API_TOKEN" ]]; then
      printf 'token'
    elif [[ -n "$GRAFANA_USER" && -n "$GRAFANA_PASSWORD" ]]; then
      printf 'basic'
    else
      printf 'token'
    fi
    return
  fi
  case "$mode" in
    token|bearer|service-account|service_account) printf 'token' ;;
    basic|userpass|user-password) printf 'basic' ;;
    *)
      echo "Unsupported GRAFANA_AUTH_MODE '$GRAFANA_AUTH_MODE'. Use auto, token, or basic." >&2
      exit 1
      ;;
  esac
}

grafana_version() {
  local out_file="$TMP_DIR/health-version.json"
  if curl -fsS "${GRAFANA_URL%/}/api/health" -o "$out_file" >/dev/null 2>&1; then
    jq -r '.version // "unknown"' "$out_file" 2>/dev/null || printf 'unknown'
  else
    printf 'unknown'
  fi
}

api() {
  local method="$1"
  local path="$2"
  local body_file="${3:-}"
  local out_file="$4"
  local status
  local url="${GRAFANA_URL%/}${path}"
  local auth=()
  case "$(auth_mode)" in
    basic)
      if [[ -z "$GRAFANA_USER" || -z "$GRAFANA_PASSWORD" ]]; then
        echo "Missing GRAFANA_USER or GRAFANA_PASSWORD for GRAFANA_AUTH_MODE=basic." >&2
        exit 1
      fi
      auth=(-u "$GRAFANA_USER:$GRAFANA_PASSWORD")
      ;;
    token)
      if [[ -z "$GRAFANA_API_TOKEN" ]]; then
        echo "Missing GRAFANA_API_TOKEN. For Grafana 13 set a service-account token in GRAFANA_API_TOKEN, or use GRAFANA_AUTH_MODE=basic with GRAFANA_USER and GRAFANA_PASSWORD." >&2
        exit 1
      fi
      auth=(-H "Authorization: Bearer $GRAFANA_API_TOKEN")
      ;;
  esac
  if [[ -n "$body_file" ]]; then
    status=$(curl -sS -o "$out_file" -w "%{http_code}" -X "$method" \
      "${auth[@]}" \
      -H "Accept: application/json" \
      -H "Content-Type: application/json" \
      --data-binary "@$body_file" \
      "$url")
  else
    status=$(curl -sS -o "$out_file" -w "%{http_code}" -X "$method" \
      "${auth[@]}" \
      -H "Accept: application/json" \
      "$url")
  fi
  printf '%s' "$status"
}


normalize_grafana_theme() {
  local raw="${GRAFANA_THEME,,}"
  raw="${raw//[[:space:]]/}"
  case "$raw" in
    "") return 1 ;;
    dark|light) printf '%s' "$raw" ;;
    bright|bright-mode|brightmode) printf 'light' ;;
    default|grafana-default|system) printf '' ;;
    *) echo "Unsupported GRAFANA_THEME. Use dark, light, bright, or default." >&2; exit 1 ;;
  esac
}

grafana_theme_display() {
  if [[ -z "$1" ]]; then
    printf 'default'
  else
    printf '%s' "$1"
  fi
}

apply_grafana_theme() {
  local prefs_file="$TMP_DIR/org-preferences.json"
  local body_file="$TMP_DIR/org-preferences-body.json"
  local out_file="$TMP_DIR/org-preferences-update.json"
  local status
  status=$(api GET "/api/org/preferences" "" "$prefs_file")
  if [[ "$status" -lt 200 || "$status" -ge 300 ]]; then
    echo "Failed to query Grafana org preferences: $(cat "$prefs_file")" >&2
    exit 1
  fi
  jq --arg theme "$GRAFANA_THEME_NORMALIZED" '
    {theme:$theme}
    + (if has("homeDashboardId") and .homeDashboardId != null then {homeDashboardId:.homeDashboardId} else {} end)
    + (if has("homeDashboardUID") and .homeDashboardUID != null then {homeDashboardUID:.homeDashboardUID} else {} end)
    + (if has("timezone") and .timezone != null then {timezone:.timezone} else {} end)
    + (if has("weekStart") and .weekStart != null then {weekStart:.weekStart} else {} end)
  ' "$prefs_file" > "$body_file"
  status=$(api PUT "/api/org/preferences" "$body_file" "$out_file")
  if [[ "$status" -lt 200 || "$status" -ge 300 ]]; then
    echo "Failed to update Grafana org theme: $(cat "$out_file")" >&2
    exit 1
  fi
  echo "Grafana org theme set: $(grafana_theme_display "$GRAFANA_THEME_NORMALIZED")"
}
urlencode() {
  jq -rn --arg v "$1" '$v|@uri'
}

remote_source_url() {
  local relative_path="$1"
  if [[ "$DASHBOARD_SOURCE_MODE" == "rawurl" ]]; then
    printf '%s/%s' "${DASHBOARD_RAW_BASE_URL%/}" "$relative_path"
    return
  fi
  printf 'https://raw.githubusercontent.com/%s/%s/%s' "$GITHUB_REPO" "$GITHUB_REF" "$relative_path"
}

fetch_remote_content() {
  local relative_path="$1"
  local url
  url="$(remote_source_url "$relative_path")"
  if ! curl -fsSL "$url"; then
    echo "Failed to download $relative_path from $url" >&2
    return 1
  fi
}

repo_file_content() {
  local relative_path="$1"
  fetch_remote_content "$relative_path"
}

load_dashboard_files() {
  if [[ "$DASHBOARD_SOURCE_MODE" == "localdir" ]]; then
    DASHBOARD_FILES=("${FIXED_DASHBOARD_FILES[@]}")
    for file_name in "${DASHBOARD_FILES[@]}"; do
      if [[ ! -f "$DASHBOARD_LOCAL_DIR/$file_name" ]]; then
        echo "DASHBOARD_LOCAL_DIR is missing required dashboard file: $file_name" >&2
        exit 1
      fi
    done
    return
  fi
  local manifest_file="$TMP_DIR/deploy-manifest.json"
  local manifest_path="dashboards/deploy-manifest.json"
  repo_file_content "$manifest_path" > "$manifest_file"
  if ! jq -e '.files | type == "array" and length > 0' "$manifest_file" >/dev/null; then
    echo "$manifest_path from $(remote_source_url "$manifest_path") is missing a non-empty files array." >&2
    echo "Check DASHBOARD_SOURCE_MODE=$DASHBOARD_SOURCE_MODE and the selected source variables." >&2
    exit 1
  fi
  mapfile -t DASHBOARD_FILES < <(jq -r '.files[]' "$manifest_file")
}
effective_dashboard_language() {
  if [[ "$DASHBOARD_VARIANT" == "orig" ]]; then
    printf 'en'
  else
    printf '%s' "$DASHBOARD_LANGUAGE"
  fi
}

fetch_source() {
  local filename="$1"
  local out_file="$2"
  if [[ "$DASHBOARD_SOURCE_MODE" == "localdir" ]]; then
    cp "$DASHBOARD_LOCAL_DIR/$filename" "$out_file"
    return
  fi
  local subdir
  local language
  language="$(effective_dashboard_language)"
  if [[ "$DASHBOARD_VARIANT" == "orig" ]]; then
    subdir="dashboards/original/$language"
  else
    subdir="dashboards/translation/$language"
  fi
  local relative_path="$subdir/$filename"
  local url
  url="$(remote_source_url "$relative_path")"
  if ! curl -fsSL "$url" -o "$out_file"; then
    echo "Failed to download $relative_path from $url" >&2
    return 1
  fi
}

dashboard_is_v2() {
  jq -e '.kind == "Dashboard" and ((.apiVersion // "") | startswith("dashboard.grafana.app/v2"))' "$1" >/dev/null
}

dashboard_title() {
  jq -r 'if .kind == "Dashboard" and ((.apiVersion // "") | startswith("dashboard.grafana.app/v2")) then .spec.title else .title end // ""' "$1"
}

dashboard_uid() {
  jq -r 'if .kind == "Dashboard" and ((.apiVersion // "") | startswith("dashboard.grafana.app/v2")) then .metadata.name else .uid end // ""' "$1"
}

dashboard_api_path() {
  local file="$1"
  local uid
  uid=$(dashboard_uid "$file")
  if dashboard_is_v2 "$file"; then
    printf '/apis/dashboard.grafana.app/v2/namespaces/default/dashboards/%s' "$(urlencode "$uid")"
  else
    printf '/api/dashboards/uid/%s' "$(urlencode "$uid")"
  fi
}

ensure_v2_folder_annotation() {
  local file="$1"
  local tmp_file="${file}.tmp"
  jq --arg folder "$GRAFANA_FOLDER_UID" '
    def is_v2: .kind == "Dashboard" and ((.apiVersion // "") | startswith("dashboard.grafana.app/v2"));
    if is_v2 then
      .metadata = (.metadata // {})
      | .metadata.annotations = (.metadata.annotations // {})
      | .metadata.annotations["grafana.app/folder"] = $folder
    else . end
  ' "$file" > "$tmp_file"
  mv "$tmp_file" "$file"
}
apply_dashboard_override() {
  local file="$1"
  local variable_name="$2"
  local value="$3"
  [[ -n "$value" ]] || return 0
  local tmp_file="${file}.tmp"
  jq --arg name "$variable_name" --arg value "$value" '
    def is_v2: .kind == "Dashboard" and ((.apiVersion // "") | startswith("dashboard.grafana.app/v2"));
    if is_v2 then
      .spec.variables |= map(
        if .spec.name == $name then
          (if .kind != "QueryVariable" then .spec.query = $value else . end)
          | .spec.current = ((.spec.current // {}) + {text:$value, value:$value})
          | if ((.spec // {}) | has("options")) then .spec.options = [{selected:true, text:$value, value:$value}] else . end
        else . end
      )
    elif .templating and .templating.list then
      .templating.list |= map(
        if .name == $name then
          .query = $value
          | .current = ((.current // {}) + {text:$value, value:$value})
          | .options = [{selected:true, text:$value, value:$value}]
        else . end
      )
    else . end
  ' "$file" > "$tmp_file"
  mv "$tmp_file" "$file"
}

dashboard_build_marker() {
  local source
  if [[ "$DASHBOARD_SOURCE_MODE" == "localdir" ]]; then
    source="localdir:$DASHBOARD_LOCAL_DIR"
    printf 'deployed %s | %s' "$(date '+%Y-%m-%d %H:%M:%S %z')" "$source"
    return
  fi
  if [[ "$DASHBOARD_SOURCE_MODE" == "rawurl" ]]; then
    source="rawurl:${DASHBOARD_RAW_BASE_URL%/}"
  else
    source="github:$GITHUB_REPO@$GITHUB_REF"
  fi
  printf 'deployed %s | %s/%s | %s' "$(date '+%Y-%m-%d %H:%M:%S %z')" "$(effective_dashboard_language)" "$DASHBOARD_VARIANT" "$source"
}

apply_dashboard_build_description() {
  local file="$1"
  local marker="$2"
  local tmp_file="${file}.tmp"
  jq --arg description "$marker" '
    def is_v2: .kind == "Dashboard" and ((.apiVersion // "") | startswith("dashboard.grafana.app/v2"));
    if is_v2 then
      .spec.variables |= map(
        if .spec.name == "dashboardBuild" then
          .spec.description = $description
        else . end
      )
    elif .templating and .templating.list then
      .templating.list |= map(
        if .name == "dashboardBuild" then
          .description = $description
        else . end
      )
    else . end
  ' "$file" > "$tmp_file"
  mv "$tmp_file" "$file"
}

print_dashboard_overrides() {
  local printed=0
  for entry in \
    "peakPowerLimit:$DASHBOARD_FILTER_PEAK_POWER_LIMIT" \
    "energySampleInterval:${DASHBOARD_ENERGY_SAMPLE_INTERVAL:-$DASHBOARD_FILTER_ENERGY_SAMPLE_INTERVAL}" \
    "tariffPriceInterval:${DASHBOARD_TARIFF_PRICE_INTERVAL:-$DASHBOARD_FILTER_TARIFF_PRICE_INTERVAL}" \
    "installedWattPeak:$DASHBOARD_INSTALLED_WATT_PEAK" \
    "vehicleConsumption:${DASHBOARD_VEHICLE_CONSUMPTION_L_PER_100KM:-$DASHBOARD_ICE_CONSUMPTION_L_PER_100KM}" \
    "fuelCost:${DASHBOARD_FUEL_COST_PER_L:-$DASHBOARD_FUEL_PRICE_PER_L}" \
    "purchasePricePv:$DASHBOARD_PV_PURCHASE_PRICE" \
    "batteryPurchasePrice:$DASHBOARD_BATTERY_PURCHASE_PRICE" \
    "runningCosts:$DASHBOARD_RUNNING_COSTS_YEARLY" \
    "storageCapacity:${DASHBOARD_STORAGE_CAPACITY_WH:-$DASHBOARD_BATTERY_CAPACITY_WH}" \
    "heatPumpLoadpointRegex:$DASHBOARD_HEAT_PUMP_LOADPOINT_REGEX" \
    "loadpointBlocklist:$DASHBOARD_FILTER_LOADPOINT_BLOCKLIST" \
    "extBlocklist:$DASHBOARD_FILTER_EXT_BLOCKLIST" \
    "auxBlocklist:$DASHBOARD_FILTER_AUX_BLOCKLIST" \
    "vehicleBlocklist:$DASHBOARD_FILTER_VEHICLE_BLOCKLIST" \
    "evccUrl:$DASHBOARD_EVCC_URL" \
    "inverterPortalTitle:$DASHBOARD_PORTAL_TITLE" \
    "inverterPortalUrl:$DASHBOARD_PORTAL_URL"; do
    key=${entry%%:*}
    value=${entry#*:}
    if [[ -n "$value" ]]; then
      if [[ "$printed" -eq 0 ]]; then
        echo
        echo "Will apply dashboard overrides:"
        printed=1
      fi
      echo "- $key = $value"
    fi
  done
}

replace_ds_filter='def walk(f): . as $in | if type == "object" then reduce keys[] as $key ({}; .[$key] = ($in[$key] | walk(f))) | f elif type == "array" then map(walk(f)) | f else f end; walk(if type == "string" and . == "${DS_VM-EVCC}" then $ds elif type == "object" and .type == "victoriametrics-metrics-datasource" and has("uid") then .uid = $ds else . end)'

TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT
LIB_DIR="$TMP_DIR/library"
mkdir -p "$LIB_DIR"
load_dashboard_files
DASHBOARD_BUILD_MARKER="$(dashboard_build_marker)"
GRAFANA_THEME_CONFIGURED="false"
GRAFANA_THEME_NORMALIZED=""
if [[ -n "${GRAFANA_THEME//[[:space:]]/}" ]]; then
  GRAFANA_THEME_CONFIGURED="true"
  GRAFANA_THEME_NORMALIZED="$(normalize_grafana_theme)"
fi

for file_name in "${DASHBOARD_FILES[@]}"; do
  raw_file="$TMP_DIR/$file_name"
  inputs_file="$TMP_DIR/$file_name.inputs.json"
  fetch_source "$file_name" "$raw_file"
  apply_dashboard_build_description "$raw_file" "$DASHBOARD_BUILD_MARKER"
  apply_dashboard_override "$raw_file" "peakPowerLimit" "$DASHBOARD_FILTER_PEAK_POWER_LIMIT"
  apply_dashboard_override "$raw_file" "energySampleInterval" "${DASHBOARD_ENERGY_SAMPLE_INTERVAL:-$DASHBOARD_FILTER_ENERGY_SAMPLE_INTERVAL}"
  apply_dashboard_override "$raw_file" "tariffPriceInterval" "${DASHBOARD_TARIFF_PRICE_INTERVAL:-$DASHBOARD_FILTER_TARIFF_PRICE_INTERVAL}"
  apply_dashboard_override "$raw_file" "installedWattPeak" "$DASHBOARD_INSTALLED_WATT_PEAK"
  apply_dashboard_override "$raw_file" "vehicleConsumption" "${DASHBOARD_VEHICLE_CONSUMPTION_L_PER_100KM:-$DASHBOARD_ICE_CONSUMPTION_L_PER_100KM}"
  apply_dashboard_override "$raw_file" "fuelCost" "${DASHBOARD_FUEL_COST_PER_L:-$DASHBOARD_FUEL_PRICE_PER_L}"
  apply_dashboard_override "$raw_file" "purchasePricePv" "$DASHBOARD_PV_PURCHASE_PRICE"
  apply_dashboard_override "$raw_file" "batteryPurchasePrice" "$DASHBOARD_BATTERY_PURCHASE_PRICE"
  apply_dashboard_override "$raw_file" "runningCosts" "$DASHBOARD_RUNNING_COSTS_YEARLY"
  apply_dashboard_override "$raw_file" "storageCapacity" "${DASHBOARD_STORAGE_CAPACITY_WH:-$DASHBOARD_BATTERY_CAPACITY_WH}"
  apply_dashboard_override "$raw_file" "heatPumpLoadpointRegex" "$DASHBOARD_HEAT_PUMP_LOADPOINT_REGEX"
  apply_dashboard_override "$raw_file" "loadpointBlocklist" "$DASHBOARD_FILTER_LOADPOINT_BLOCKLIST"
  apply_dashboard_override "$raw_file" "extBlocklist" "$DASHBOARD_FILTER_EXT_BLOCKLIST"
  apply_dashboard_override "$raw_file" "auxBlocklist" "$DASHBOARD_FILTER_AUX_BLOCKLIST"
  apply_dashboard_override "$raw_file" "vehicleBlocklist" "$DASHBOARD_FILTER_VEHICLE_BLOCKLIST"
  apply_dashboard_override "$raw_file" "evccUrl" "$DASHBOARD_EVCC_URL"
  apply_dashboard_override "$raw_file" "inverterPortalTitle" "$DASHBOARD_PORTAL_TITLE"
  apply_dashboard_override "$raw_file" "inverterPortalUrl" "$DASHBOARD_PORTAL_URL"

  tmp_ds_file="$raw_file.ds"
  jq --arg ds "$GRAFANA_DS_VM_EVCC_UID" "$replace_ds_filter" "$raw_file" > "$tmp_ds_file"
  mv "$tmp_ds_file" "$raw_file"
  ensure_v2_folder_annotation "$raw_file"

  jq --arg ds "$GRAFANA_DS_VM_EVCC_UID" '
    def is_v2: .kind == "Dashboard" and ((.apiVersion // "") | startswith("dashboard.grafana.app/v2"));
    if is_v2 then [] else
      [.__inputs[]? | select(.name and .type) |
        if .type == "datasource" then
          if .name == "DS_VM-EVCC" then
            {name: .name, type: .type, pluginId: .pluginId, value: $ds}
          elif .pluginId == "__expr__" then
            {name: .name, type: .type, pluginId: .pluginId, value: "__expr__"}
          else
            error("Missing datasource mapping for \(.name)")
          end
        else
          {name: .name, type: .type, value: (.value // "")}
        end]
    end
  ' "$raw_file" > "$inputs_file"

  jq -c --arg ds "$GRAFANA_DS_VM_EVCC_UID" "(.__elements // {}) | to_entries[]? | {uid: .value.uid, name: .value.name, kind: (.value.kind // 1), model: (.value.model | $replace_ds_filter)}" "$raw_file" |
  while IFS= read -r entry; do
    uid=$(printf '%s' "$entry" | jq -r '.uid')
    printf '%s' "$entry" > "$LIB_DIR/$uid.json"
  done
done

health_out="$TMP_DIR/health.json"
health_status=$(api GET "/api/search?limit=1" "" "$health_out")
if [[ "$health_status" -lt 200 || "$health_status" -ge 300 ]]; then
  if [[ "$health_status" == "401" ]]; then
    echo "Grafana authentication failed for GET /api/search?limit=1 (401): $(cat "$health_out")" >&2
    echo "Grafana 13 still supports the legacy /api routes, but API keys are deprecated. Create a Grafana service-account token and set GRAFANA_API_TOKEN, or set GRAFANA_AUTH_MODE=basic with GRAFANA_USER and GRAFANA_PASSWORD." >&2
    exit 1
  fi
  echo "Grafana check failed: $(cat "$health_out")" >&2
  exit 1
fi

echo "Grafana check: OK"
echo "URL: $GRAFANA_URL"
echo "Grafana version: $(grafana_version)"
echo "Auth mode: $(auth_mode)"
echo "Folder: $GRAFANA_FOLDER_TITLE ($GRAFANA_FOLDER_UID)"
echo "Datasource UID: $GRAFANA_DS_VM_EVCC_UID"
if [[ "$GRAFANA_THEME_CONFIGURED" == "true" ]]; then
  if truthy "$PURGE_ONLY"; then
    echo "Grafana theme: $(grafana_theme_display "$GRAFANA_THEME_NORMALIZED") (not applied in purge-only mode)"
  else
    echo "Grafana theme: $(grafana_theme_display "$GRAFANA_THEME_NORMALIZED") (will update org preference)"
  fi
fi
if [[ "$DASHBOARD_SOURCE_MODE" == "localdir" ]]; then
  echo "Source: localdir / $DASHBOARD_LOCAL_DIR"
else
  if [[ "$DASHBOARD_SOURCE_MODE" == "rawurl" ]]; then
    echo "Source: rawurl / ${DASHBOARD_RAW_BASE_URL%/}"
  else
    echo "Source: github / $GITHUB_REPO / $GITHUB_REF"
  fi
  echo "Language: $DASHBOARD_LANGUAGE"
  echo "Variant: $DASHBOARD_VARIANT"
  if [[ "$DASHBOARD_VARIANT" == "orig" && "$DASHBOARD_LANGUAGE" != "en" ]]; then
    echo "Effective source language: en (orig dashboards stay English)"
  fi
fi
echo "Build marker: $DASHBOARD_BUILD_MARKER"
echo "Purge: $PURGE"
echo "Purge only: $PURGE_ONLY"
print_dashboard_overrides
echo
if truthy "$PURGE_ONLY"; then
  echo "Will inspect dashboards for purge-only deletion:"
else
  echo "Will import dashboards:"
fi
for file_name in "${DASHBOARD_FILES[@]}"; do
  raw_file="$TMP_DIR/$file_name"
  echo "- $(dashboard_title "$raw_file") [$(dashboard_uid "$raw_file")]"
done
echo
echo "Dashboards embed these library panels:"
for lib_file in "$LIB_DIR"/*.json; do
  [[ -e "$lib_file" ]] || continue
  echo "- $(jq -r '.name' "$lib_file") [$(jq -r '.uid' "$lib_file")]"
done

existing_library=()
for lib_file in "$LIB_DIR"/*.json; do
  [[ -e "$lib_file" ]] || continue
  uid=$(jq -r '.uid' "$lib_file")
  purge_out="$TMP_DIR/check-library-existing.json"
  status=$(api GET "/api/library-elements/$(urlencode "$uid")" "" "$purge_out")
  if [[ "$status" == "200" ]]; then
    existing_library+=("$(jq -r '.result.name' "$purge_out") [$uid]")
  elif [[ "$status" != "404" ]]; then
    echo "Failed to inspect library panel $uid: $(cat "$purge_out")" >&2
    exit 1
  fi
done

if ! truthy "$PURGE_EFFECTIVE" && [[ ${#existing_library[@]} -gt 0 ]]; then
  echo
  echo "Existing library panels already present and will be updated because purge=false:"
  for item in "${existing_library[@]}"; do
    echo "- $item"
  done
  echo "Dashboard import will use the updated embedded __elements definitions."
fi

if truthy "$PURGE_EFFECTIVE"; then
  echo
  if truthy "$PURGE_ONLY"; then
    echo "Will delete existing dashboards without import:"
  else
    echo "Will delete existing dashboards before import:"
  fi
  found=0
  for file_name in "${DASHBOARD_FILES[@]}"; do
    raw_file="$TMP_DIR/$file_name"
    uid=$(dashboard_uid "$raw_file")
    [[ -n "$uid" ]] || continue
    purge_out="$TMP_DIR/check-dashboard.json"
    status=$(api GET "$(dashboard_api_path "$raw_file")" "" "$purge_out")
    if [[ "$status" == "200" ]]; then
      echo "- $(dashboard_title "$raw_file") [$uid]"
      found=1
    elif [[ "$status" != "404" ]]; then
      echo "Failed to inspect dashboard $uid: $(cat "$purge_out")" >&2
      exit 1
    fi
  done
  [[ "$found" -eq 1 ]] || echo "- none"

  echo
  if truthy "$PURGE_ONLY"; then
    echo "Will delete referenced library panels after dashboard deletion:"
  else
    echo "Will ensure referenced library panels before import:"
  fi
  found=0
  for lib_file in "$LIB_DIR"/*.json; do
    [[ -e "$lib_file" ]] || continue
    uid=$(jq -r '.uid' "$lib_file")
    purge_out="$TMP_DIR/check-library.json"
    status=$(api GET "/api/library-elements/$(urlencode "$uid")" "" "$purge_out")
    if [[ "$status" == "200" ]]; then
      echo "- $(jq -r '.result.name' "$purge_out") [$uid]"
      found=1
    elif [[ "$status" != "404" ]]; then
      echo "Failed to inspect library panel $uid: $(cat "$purge_out")" >&2
      exit 1
    fi
  done
  if truthy "$PURGE_ONLY"; then
    [[ "$found" -eq 1 ]] || echo "- none"
  else
    [[ "$found" -eq 1 ]] || echo "- none found yet; missing panels will be created"
  fi
fi

echo
if truthy "$PURGE_ONLY"; then
  printf 'Proceed with purge-only deletion? [y/N] '
else
  printf 'Proceed with dashboard deployment? [y/N] '
fi
read -r answer
case "${answer:-}" in
  y|Y|yes|YES|Yes) ;;
  *)
    echo "Aborted. No changes applied."
    exit 0
    ;;
esac

if [[ "$GRAFANA_THEME_CONFIGURED" == "true" ]] && ! truthy "$PURGE_ONLY"; then
  apply_grafana_theme
fi

if truthy "$PURGE_EFFECTIVE"; then
  for file_name in "${DASHBOARD_FILES[@]}"; do
    raw_file="$TMP_DIR/$file_name"
    uid=$(dashboard_uid "$raw_file")
    if [[ -n "$uid" ]]; then
      purge_out="$TMP_DIR/purge-dashboard.json"
      status=$(api DELETE "$(dashboard_api_path "$raw_file")" "" "$purge_out")
      if [[ "$status" == "404" ]]; then
        echo "Skipping dashboard delete (not found): $(dashboard_title "$raw_file") [$uid]"
      elif [[ "$status" -lt 200 || "$status" -ge 300 ]]; then
        echo "Failed to purge dashboard $uid: $(cat "$purge_out")" >&2
        exit 1
      else
        echo "Deleted dashboard: $(dashboard_title "$raw_file") [$uid]"
      fi
    fi
  done
  if truthy "$PURGE_ONLY"; then
    for lib_file in "$LIB_DIR"/*.json; do
      [[ -e "$lib_file" ]] || continue
      uid=$(jq -r '.uid' "$lib_file")
      purge_out="$TMP_DIR/purge-library-$uid.json"
      status=$(api DELETE "/api/library-elements/$(urlencode "$uid")" "" "$purge_out")
      if [[ "$status" == "404" ]]; then
        echo "Skipping library panel delete (not found): $(jq -r '.name' "$lib_file") [$uid]"
      elif [[ "$status" -lt 200 || "$status" -ge 300 ]]; then
        echo "Failed to purge library panel $uid: $(cat "$purge_out")" >&2
        exit 1
      else
        echo "Deleted library panel: $(jq -r '.name' "$lib_file") [$uid]"
      fi
    done
    echo
    echo "Purge-only finished. No dashboards imported."
    exit 0
  fi
fi

folder_resp="$TMP_DIR/folder.json"
folder_status=$(api GET "/api/folders/$(urlencode "$GRAFANA_FOLDER_UID")" "" "$folder_resp")
if [[ "$folder_status" == "404" ]]; then
  folder_body="$TMP_DIR/folder-body.json"
  jq -n --arg uid "$GRAFANA_FOLDER_UID" --arg title "$GRAFANA_FOLDER_TITLE" '{uid:$uid,title:$title}' > "$folder_body"
  create_out="$TMP_DIR/folder-create.json"
  create_status=$(api POST "/api/folders" "$folder_body" "$create_out")
  if [[ "$create_status" -lt 200 || "$create_status" -ge 300 ]]; then
    echo "Failed to create folder: $(cat "$create_out")" >&2
    exit 1
  fi
elif [[ "$folder_status" -lt 200 || "$folder_status" -ge 300 ]]; then
  echo "Failed to query folder: $(cat "$folder_resp")" >&2
  exit 1
fi

existing_library=()
for lib_file in "$LIB_DIR"/*.json; do
  [[ -e "$lib_file" ]] || continue
  uid=$(jq -r '.uid' "$lib_file")
  purge_out="$TMP_DIR/check-library-existing.json"
  status=$(api GET "/api/library-elements/$(urlencode "$uid")" "" "$purge_out")
  if [[ "$status" == "200" ]]; then
    existing_library+=("$(jq -r '.result.name' "$purge_out") [$uid]")
  elif [[ "$status" != "404" ]]; then
    echo "Failed to inspect library panel $uid: $(cat "$purge_out")" >&2
    exit 1
  fi
done

if ! truthy "$PURGE_EFFECTIVE" && [[ ${#existing_library[@]} -gt 0 ]]; then
  echo
  echo "Existing library panels already present and will be updated because purge=false:"
  for item in "${existing_library[@]}"; do
    echo "- $item"
  done
  echo "Dashboard import will use the updated embedded __elements definitions."
fi


for lib_file in "$LIB_DIR"/*.json; do
  [[ -e "$lib_file" ]] || continue
  uid=$(jq -r '.uid' "$lib_file")
  existing_out="$TMP_DIR/update-library-existing-$uid.json"
  status=$(api GET "/api/library-elements/$(urlencode "$uid")" "" "$existing_out")
  if [[ "$status" == "200" ]]; then
    body_file="$TMP_DIR/update-library-$uid.json"
    jq -n --slurpfile entry "$lib_file" --slurpfile existing "$existing_out" '
      {
        name: $entry[0].name,
        kind: ($entry[0].kind // $existing[0].result.kind // 1),
        model: $entry[0].model,
        version: $existing[0].result.version
      }
      + (if (($existing[0].result.folderUid // "") != "") then {folderUid: $existing[0].result.folderUid} else {} end)
    ' > "$body_file"
    update_out="$TMP_DIR/update-library-$uid.out.json"
    update_status=$(api PATCH "/api/library-elements/$(urlencode "$uid")" "$body_file" "$update_out")
    if [[ "$update_status" -lt 200 || "$update_status" -ge 300 ]]; then
      echo "Failed to update library panel $uid: $(cat "$update_out")" >&2
      exit 1
    fi
    echo "Updated library panel: $(jq -r '.name' "$lib_file") [$uid]"
  elif [[ "$status" != "404" ]]; then
    echo "Failed to inspect library panel $uid: $(cat "$existing_out")" >&2
    exit 1
  fi
done

for lib_file in "$LIB_DIR"/*.json; do
  [[ -e "$lib_file" ]] || continue
  uid=$(jq -r '.uid' "$lib_file")
  existing_out="$TMP_DIR/create-library-existing-$uid.json"
  status=$(api GET "/api/library-elements/$(urlencode "$uid")" "" "$existing_out")
  if [[ "$status" == "404" ]]; then
    body_file="$TMP_DIR/create-library-$uid.json"
    jq -n --slurpfile entry "$lib_file" --arg folderUid "$GRAFANA_FOLDER_UID" '
      {
        uid: $entry[0].uid,
        name: $entry[0].name,
        kind: ($entry[0].kind // 1),
        folderUid: $folderUid,
        model: $entry[0].model
      }
    ' > "$body_file"
    create_out="$TMP_DIR/create-library-$uid.out.json"
    create_status=$(api POST "/api/library-elements" "$body_file" "$create_out")
    if [[ "$create_status" -lt 200 || "$create_status" -ge 300 ]]; then
      echo "Failed to create library panel $uid: $(cat "$create_out")" >&2
      exit 1
    fi
    echo "Created library panel: $(jq -r '.name' "$lib_file") [$uid]"
  elif [[ "$status" != "200" ]]; then
    echo "Failed to inspect library panel $uid: $(cat "$existing_out")" >&2
    exit 1
  fi
done

for file_name in "${DASHBOARD_FILES[@]}"; do
  raw_file="$TMP_DIR/$file_name"
  inputs_file="$TMP_DIR/$file_name.inputs.json"
  title=$(dashboard_title "$raw_file")
  uid=$(dashboard_uid "$raw_file")
  echo "Importing dashboard: $title [$uid]"
  out_file="$TMP_DIR/$file_name.import.out.json"
  if dashboard_is_v2 "$raw_file"; then
    existing_out="$TMP_DIR/$file_name.v2.existing.json"
    status=$(api GET "$(dashboard_api_path "$raw_file")" "" "$existing_out")
    if [[ "$status" == "200" ]]; then
      body_file="$TMP_DIR/$file_name.v2.put.json"
      resource_version=$(jq -r '.metadata.resourceVersion // empty' "$existing_out")
      jq --arg resourceVersion "$resource_version" '.metadata.resourceVersion = $resourceVersion' "$raw_file" > "$body_file"
      status=$(api PUT "$(dashboard_api_path "$raw_file")" "$body_file" "$out_file")
    elif [[ "$status" == "404" ]]; then
      status=$(api POST "/apis/dashboard.grafana.app/v2/namespaces/default/dashboards" "$raw_file" "$out_file")
    else
      echo "Failed to inspect dashboard $uid: $(cat "$existing_out")" >&2
      exit 1
    fi
  else
    body_file="$TMP_DIR/$file_name.import.json"
    jq -n \
      --slurpfile dashboard "$raw_file" \
      --slurpfile inputs "$inputs_file" \
      --arg folderUid "$GRAFANA_FOLDER_UID" \
      '{dashboard:$dashboard[0],folderUid:$folderUid,overwrite:true,message:"EVCC VM dashboard install",inputs:$inputs[0]}' > "$body_file"
    status=$(api POST "/api/dashboards/import" "$body_file" "$out_file")
  fi
  if [[ "$status" -lt 200 || "$status" -ge 300 ]]; then
    echo "Failed to import dashboard $file_name: $(cat "$out_file")" >&2
    exit 1
  fi
  echo "Imported dashboard: $title"
done

echo
echo "Install finished."
echo "Folder: $GRAFANA_FOLDER_TITLE ($GRAFANA_FOLDER_UID)"
if [[ "$DASHBOARD_SOURCE_MODE" == "localdir" ]]; then
  echo "Source: localdir / $DASHBOARD_LOCAL_DIR"
else
  if [[ "$DASHBOARD_SOURCE_MODE" == "rawurl" ]]; then
    echo "Source: rawurl / ${DASHBOARD_RAW_BASE_URL%/}"
  else
    echo "Source: github / $GITHUB_REPO / $GITHUB_REF"
  fi
fi
