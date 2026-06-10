#!/usr/bin/env bash
# Script: evcc-vm-investment-weekly.sh
# Purpose: Cron-safe weekly PV investment/generation-cost rollup for production VictoriaMetrics.
# Version: 2026.06.10.1
# Last modified: 2026-06-10
set -euo pipefail

SCRIPT_VERSION="2026.06.10.1"
SCRIPT_LAST_MODIFIED="2026-06-10"
CONFIG_FILE="${EVCC_VM_INVESTMENT_CONFIG:-/etc/evcc-vm-investment-costs.conf}"

if [[ -f "$CONFIG_FILE" ]]; then
  # shellcheck source=/etc/evcc-vm-investment-costs.conf
  source "$CONFIG_FILE"
fi

: "${PYTHON_BIN:=/usr/bin/python3}"
: "${HELPER_SCRIPT:=/opt/evcc-vm-migration/import-investment-costs.py}"
: "${VM_BASE_URL:=http://127.0.0.1:8428}"
: "${INVESTMENT_FILE:=/etc/evcc-investments.xlsx}"
: "${TIMEZONE:=Europe/Berlin}"
: "${START_DAY:=}"
: "${END_DAY:=$(date -d 'today' +%F)}"
: "${ENERGY_SOURCE:=pv-power}"
: "${PV_ENERGY_METRIC:=evcc_pv_energy_by_title_daily_wh}"
: "${COMBINED_ENERGY_CONFLICT:=prefer-evcc}"
: "${PEAK_POWER_LIMIT:=30000}"
: "${SAMPLE_INTERVAL:=30s}"
: "${MIN_LCOE_COVERAGE_RATIO:=0.0}"
: "${PARTIAL_WARNING_THRESHOLD:=0.95}"
: "${BATCH_SIZE:=200}"
: "${SKIP_TITLES_WITHOUT_ENERGY:=true}"
: "${WRITE_PV_ENERGY_ROLLUP:=false}"
: "${WRITE:=true}"
: "${REPLACE:=true}"
: "${LOCK_FILE:=/var/lock/evcc-vm-investment-costs.lock}"

is_true() {
  case "${1,,}" in
    1|true|yes|y|on) return 0 ;;
    *) return 1 ;;
  esac
}

log() {
  printf '%s %s\n' "$(date --iso-8601=seconds)" "$*"
}

if [[ ! -f "$HELPER_SCRIPT" ]]; then
  log "ERROR: helper script not found: $HELPER_SCRIPT"
  exit 2
fi
if [[ ! -f "$INVESTMENT_FILE" ]]; then
  log "ERROR: investment file not found: $INVESTMENT_FILE"
  exit 2
fi

mkdir -p "$(dirname "$LOCK_FILE")"
exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  log "Another investment rollup is already running; exiting."
  exit 0
fi

cmd=(
  "$PYTHON_BIN" "$HELPER_SCRIPT"
  --vm-base-url "$VM_BASE_URL"
  --investment-file "$INVESTMENT_FILE"
  --timezone "$TIMEZONE"
  --end "$END_DAY"
  --energy-source "$ENERGY_SOURCE"
  --pv-energy-metric "$PV_ENERGY_METRIC"
  --combined-energy-conflict "$COMBINED_ENERGY_CONFLICT"
  --peak-power-limit "$PEAK_POWER_LIMIT"
  --sample-interval "$SAMPLE_INTERVAL"
  --min-lcoe-coverage-ratio "$MIN_LCOE_COVERAGE_RATIO"
  --partial-warning-threshold "$PARTIAL_WARNING_THRESHOLD"
  --batch-size "$BATCH_SIZE"
)

if [[ -n "$START_DAY" ]]; then
  cmd+=(--start "$START_DAY")
fi
if is_true "$SKIP_TITLES_WITHOUT_ENERGY"; then
  cmd+=(--skip-titles-without-energy)
fi
if is_true "$WRITE_PV_ENERGY_ROLLUP"; then
  cmd+=(--write-pv-energy-rollup)
fi
if is_true "$REPLACE"; then
  cmd+=(--replace)
fi
if is_true "$WRITE"; then
  cmd+=(--write)
fi

log "evcc-vm-investment-weekly.sh v${SCRIPT_VERSION} (last modified ${SCRIPT_LAST_MODIFIED})"
log "Config: ${CONFIG_FILE}"
log "VM: ${VM_BASE_URL}"
log "Investment file: ${INVESTMENT_FILE}"
log "Range: ${START_DAY:-auto} .. ${END_DAY} (exclusive), timezone=${TIMEZONE}"
log "Energy source: ${ENERGY_SOURCE}"
log "Write: ${WRITE}, replace generated metrics: ${REPLACE}"

"${cmd[@]}"
log "Investment rollup finished."