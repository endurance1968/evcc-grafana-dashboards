#!/usr/bin/env bash
set -euo pipefail

CONFIG_PATH="./vm-dashboard-install.env"
CLI_URL=""
CLI_TOKEN=""
CLI_PURGE=""

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
    --help|-h)
      cat <<'EOF'
Usage: ./deploy-bash.sh [--config <path>] [--url <url>] [--token <token>] [--purge true|false]
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

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required command: $1" >&2
    exit 1
  }
}

require_cmd curl
require_cmd jq

GRAFANA_URL="http://localhost:3000"
GRAFANA_API_TOKEN=""
GRAFANA_DS_VM_EVCC_UID="vm-evcc"
GRAFANA_FOLDER_UID="evcc"
GRAFANA_FOLDER_TITLE="EVCC"
DASHBOARD_SOURCE_MODE="github"
GITHUB_REPO="endurance1968/evcc-grafana-dashboards"
GITHUB_REF="main"
DASHBOARD_LANGUAGE="en"
DASHBOARD_VARIANT="gen"
DASHBOARD_LOCAL_DIR=""
PURGE="false"
DASHBOARD_FILTER_PEAK_POWER_LIMIT=""
DASHBOARD_ENERGY_SAMPLE_INTERVAL=""
DASHBOARD_TARIFF_PRICE_INTERVAL=""
DASHBOARD_FILTER_ENERGY_SAMPLE_INTERVAL=""
DASHBOARD_FILTER_TARIFF_PRICE_INTERVAL=""
DASHBOARD_FILTER_LOADPOINT_BLOCKLIST=""
DASHBOARD_FILTER_EXT_BLOCKLIST=""
DASHBOARD_FILTER_AUX_BLOCKLIST=""
DASHBOARD_EVCC_URL=""
DASHBOARD_PORTAL_TITLE=""
DASHBOARD_PORTAL_URL=""

if [[ -f "$CONFIG_PATH" ]]; then
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
if [[ -n "$CLI_PURGE" ]]; then
  PURGE="$CLI_PURGE"
fi
if [[ -n "${DEPLOY_PURGE:-}" && -z "${PURGE:-}" ]]; then
  PURGE="$DEPLOY_PURGE"
fi

if [[ -z "$GRAFANA_API_TOKEN" ]]; then
  echo "Missing GRAFANA_API_TOKEN. Set it in the config file, environment, or --token." >&2
  exit 1
fi
if [[ "$DASHBOARD_SOURCE_MODE" == "local" && -z "$DASHBOARD_LOCAL_DIR" ]]; then
  echo "DASHBOARD_LOCAL_DIR is required when DASHBOARD_SOURCE_MODE=local." >&2
  exit 1
fi

api() {
  local method="$1"
  local path="$2"
  local body_file="${3:-}"
  local out_file="$4"
  local status
  local url="${GRAFANA_URL%/}${path}"
  if [[ -n "$body_file" ]]; then
    status=$(curl -sS -o "$out_file" -w "%{http_code}" -X "$method" \
      -H "Authorization: Bearer $GRAFANA_API_TOKEN" \
      -H "Accept: application/json" \
      -H "Content-Type: application/json" \
      --data-binary "@$body_file" \
      "$url")
  else
    status=$(curl -sS -o "$out_file" -w "%{http_code}" -X "$method" \
      -H "Authorization: Bearer $GRAFANA_API_TOKEN" \
      -H "Accept: application/json" \
      "$url")
  fi
  printf '%s' "$status"
}

urlencode() {
  jq -rn --arg v "$1" '$v|@uri'
}

fetch_source() {
  local filename="$1"
  local out_file="$2"
  if [[ "$DASHBOARD_SOURCE_MODE" == "local" ]]; then
    cp "$DASHBOARD_LOCAL_DIR/$filename" "$out_file"
    return
  fi
  local subdir
  if [[ "$DASHBOARD_VARIANT" == "orig" ]]; then
    subdir="dashboards/original/$DASHBOARD_LANGUAGE"
  else
    subdir="dashboards/translation/$DASHBOARD_LANGUAGE"
  fi
  curl -fsSL "https://raw.githubusercontent.com/$GITHUB_REPO/$GITHUB_REF/$subdir/$(urlencode "$filename")" -o "$out_file"
}

apply_dashboard_override() {
  local file="$1"
  local variable_name="$2"
  local value="$3"
  [[ -n "$value" ]] || return 0
  local tmp_file="${file}.tmp"
  jq --arg name "$variable_name" --arg value "$value" '
    if .templating and .templating.list then
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

print_dashboard_overrides() {
  local printed=0
  for entry in \
    "peakPowerLimit:$DASHBOARD_FILTER_PEAK_POWER_LIMIT" \
    "energySampleInterval:${DASHBOARD_ENERGY_SAMPLE_INTERVAL:-$DASHBOARD_FILTER_ENERGY_SAMPLE_INTERVAL}" \
    "tariffPriceInterval:${DASHBOARD_TARIFF_PRICE_INTERVAL:-$DASHBOARD_FILTER_TARIFF_PRICE_INTERVAL}" \
    "loadpointBlocklist:$DASHBOARD_FILTER_LOADPOINT_BLOCKLIST" \
    "extBlocklist:$DASHBOARD_FILTER_EXT_BLOCKLIST" \
    "auxBlocklist:$DASHBOARD_FILTER_AUX_BLOCKLIST" \
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

replace_ds_filter='def walk(f): . as $in | if type == "object" then reduce keys[] as $key ({}; .[$key] = ($in[$key] | walk(f))) | f elif type == "array" then map(walk(f)) | f else f end; walk(if type == "string" and . == "${DS_VM-EVCC}" then $ds else . end)'

DASHBOARD_FILES=(
  "VM_ EVCC_ All-time.json"
  "VM_ EVCC_ Jahr.json"
  "VM_ EVCC_ Monat.json"
  "VM_ EVCC_ Today - Details.json"
  "VM_ EVCC_ Today.json"
  "VM_ EVCC_ Today - Mobile.json"
)

TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT
LIB_DIR="$TMP_DIR/library"
mkdir -p "$LIB_DIR"

for file_name in "${DASHBOARD_FILES[@]}"; do
  raw_file="$TMP_DIR/$file_name"
  inputs_file="$TMP_DIR/$file_name.inputs.json"
  fetch_source "$file_name" "$raw_file"
  apply_dashboard_override "$raw_file" "peakPowerLimit" "$DASHBOARD_FILTER_PEAK_POWER_LIMIT"
  apply_dashboard_override "$raw_file" "energySampleInterval" "${DASHBOARD_ENERGY_SAMPLE_INTERVAL:-$DASHBOARD_FILTER_ENERGY_SAMPLE_INTERVAL}"
  apply_dashboard_override "$raw_file" "tariffPriceInterval" "${DASHBOARD_TARIFF_PRICE_INTERVAL:-$DASHBOARD_FILTER_TARIFF_PRICE_INTERVAL}"
  apply_dashboard_override "$raw_file" "loadpointBlocklist" "$DASHBOARD_FILTER_LOADPOINT_BLOCKLIST"
  apply_dashboard_override "$raw_file" "extBlocklist" "$DASHBOARD_FILTER_EXT_BLOCKLIST"
  apply_dashboard_override "$raw_file" "auxBlocklist" "$DASHBOARD_FILTER_AUX_BLOCKLIST"
  apply_dashboard_override "$raw_file" "evccUrl" "$DASHBOARD_EVCC_URL"
  apply_dashboard_override "$raw_file" "inverterPortalTitle" "$DASHBOARD_PORTAL_TITLE"
  apply_dashboard_override "$raw_file" "inverterPortalUrl" "$DASHBOARD_PORTAL_URL"

  jq --arg ds "$GRAFANA_DS_VM_EVCC_UID" '
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
  echo "Grafana check failed: $(cat "$health_out")" >&2
  exit 1
fi

echo "Grafana check: OK"
echo "URL: $GRAFANA_URL"
echo "Folder: $GRAFANA_FOLDER_TITLE ($GRAFANA_FOLDER_UID)"
echo "Datasource UID: $GRAFANA_DS_VM_EVCC_UID"
if [[ "$DASHBOARD_SOURCE_MODE" == "local" ]]; then
  echo "Source: local / $DASHBOARD_LOCAL_DIR"
else
  echo "Source: github / $GITHUB_REPO / $GITHUB_REF"
fi
echo "Language: $DASHBOARD_LANGUAGE"
echo "Variant: $DASHBOARD_VARIANT"
echo "Purge: $PURGE"
print_dashboard_overrides
echo
echo "Will import dashboards:"
for file_name in "${DASHBOARD_FILES[@]}"; do
  raw_file="$TMP_DIR/$file_name"
  echo "- $(jq -r '.title' "$raw_file") [$(jq -r '.uid // ""' "$raw_file")]"
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

if [[ "${PURGE,,}" != "true" && ${#existing_library[@]} -gt 0 ]]; then
  echo
  echo "Existing library panels already present and will be left in place because purge=false:"
  for item in "${existing_library[@]}"; do
    echo "- $item"
  done
  echo "Dashboard import will rely on the embedded __elements definitions."
fi

if [[ "${PURGE,,}" == "true" ]]; then
  echo
  echo "Will delete existing dashboards before import:"
  found=0
  for file_name in "${DASHBOARD_FILES[@]}"; do
    raw_file="$TMP_DIR/$file_name"
    uid=$(jq -r '.uid // empty' "$raw_file")
    [[ -n "$uid" ]] || continue
    purge_out="$TMP_DIR/check-dashboard.json"
    status=$(api GET "/api/dashboards/uid/$(urlencode "$uid")" "" "$purge_out")
    if [[ "$status" == "200" ]]; then
      echo "- $(jq -r '.dashboard.title' "$purge_out") [$uid]"
      found=1
    elif [[ "$status" != "404" ]]; then
      echo "Failed to inspect dashboard $uid: $(cat "$purge_out")" >&2
      exit 1
    fi
  done
  [[ "$found" -eq 1 ]] || echo "- none"

  echo
  echo "Will delete existing library panels before import:"
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
  [[ "$found" -eq 1 ]] || echo "- none"
fi

echo
printf 'Proceed with dashboard deployment? [y/N] '
read -r answer
case "${answer:-}" in
  y|Y|yes|YES|Yes) ;;
  *)
    echo "Aborted. No changes applied."
    exit 0
    ;;
esac

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

if [[ "${PURGE,,}" != "true" && ${#existing_library[@]} -gt 0 ]]; then
  echo
  echo "Existing library panels already present and will be left in place because purge=false:"
  for item in "${existing_library[@]}"; do
    echo "- $item"
  done
  echo "Dashboard import will rely on the embedded __elements definitions."
fi

if [[ "${PURGE,,}" == "true" ]]; then
  for file_name in "${DASHBOARD_FILES[@]}"; do
    raw_file="$TMP_DIR/$file_name"
    uid=$(jq -r '.uid // empty' "$raw_file")
    if [[ -n "$uid" ]]; then
      purge_out="$TMP_DIR/purge-dashboard.json"
      status=$(api DELETE "/api/dashboards/uid/$(urlencode "$uid")" "" "$purge_out")
      if [[ "$status" == "404" ]]; then
        echo "Skipping dashboard delete (not found): $(jq -r '.title // ""' "$raw_file") [$uid]"
      elif [[ "$status" -lt 200 || "$status" -ge 300 ]]; then
        echo "Failed to purge dashboard $uid: $(cat "$purge_out")" >&2
        exit 1
      else
        echo "Deleted dashboard: $(jq -r '.title // ""' "$raw_file") [$uid]"
      fi
    fi
  done
  for lib_file in "$LIB_DIR"/*.json; do
    [[ -e "$lib_file" ]] || continue
    uid=$(jq -r '.uid' "$lib_file")
    purge_out="$TMP_DIR/purge-library.json"
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
fi

for file_name in "${DASHBOARD_FILES[@]}"; do
  raw_file="$TMP_DIR/$file_name"
  inputs_file="$TMP_DIR/$file_name.inputs.json"
  body_file="$TMP_DIR/$file_name.import.json"
  jq -n \
    --slurpfile dashboard "$raw_file" \
    --slurpfile inputs "$inputs_file" \
    --arg folderUid "$GRAFANA_FOLDER_UID" \
    '{dashboard:$dashboard[0],folderUid:$folderUid,overwrite:true,message:"EVCC VM dashboard install",inputs:$inputs[0]}' > "$body_file"
  out_file="$TMP_DIR/$file_name.import.out.json"
  status=$(api POST "/api/dashboards/import" "$body_file" "$out_file")
  if [[ "$status" -lt 200 || "$status" -ge 300 ]]; then
    echo "Failed to import dashboard $file_name: $(cat "$out_file")" >&2
    exit 1
  fi
  title=$(jq -r '.dashboard.title // empty' "$body_file")
  echo "Imported dashboard: $title"
done

echo
echo "Install finished."
echo "Folder: $GRAFANA_FOLDER_TITLE ($GRAFANA_FOLDER_UID)"
if [[ "$DASHBOARD_SOURCE_MODE" == "local" ]]; then
  echo "Source: local / $DASHBOARD_LOCAL_DIR"
else
  echo "Source: github / $GITHUB_REPO / $GITHUB_REF"
fi



