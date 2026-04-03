#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Benchmark EVCC raw-data import paths against a fresh local VictoriaMetrics instance.

This script is intentionally destructive for the configured VictoriaMetrics storage path.
It stops the VictoriaMetrics service, deletes all files below the storage path, starts
the service again, and then runs import benchmarks against the empty instance.

Required:
  --influx-base URL              InfluxDB v1 query endpoint base URL
  --start RFC3339                Inclusive benchmark start timestamp
  --end RFC3339                  Exclusive benchmark end timestamp
  --allow-destructive-reset      Required safety flag

Optional:
  --db NAME                      Influx database name (default: evcc)
  --vm-base URL                  VictoriaMetrics base URL (default: http://127.0.0.1:8428)
  --vm-service NAME              systemd service name (default: victoriametrics)
  --vm-storage-path PATH         storage path to wipe before each write run
                                 (default: /var/lib/victoria-metrics)
  --python-bin PATH              Python interpreter (default: python3)
  --python-importer PATH         reimport script path
                                 (default: ./reimport_influx_to_vm.py)
  --vmctl-bin PATH               vmctl binary (default: vmctl)
  --measurement NAME             Restrict all runs to a single measurement
  --influx-user USER             Optional InfluxDB user for vmctl
  --influx-password PASS         Optional InfluxDB password for vmctl
  --output-dir PATH              Output directory
  --workdir PATH                 Base directory for generated result folders
                                 (default: /tmp/evcc-vm-import-benchmark)
  --skip-python-dry-run          Skip the Python dry-run benchmark
  --skip-python-import           Skip the Python write benchmark
  --skip-vmctl                   Skip the vmctl write benchmark
  --vmctl-start RFC3339          Override vmctl start range
  --vmctl-end RFC3339            Override vmctl end range

Example:
  ./benchmark-influx-imports.sh \
    --influx-base http://192.168.1.183:8086 \
    --start 2024-01-01T00:00:00Z \
    --end 2026-03-30T00:00:00Z \
    --influx-user endurance \
    --influx-password 'secret' \
    --allow-destructive-reset
EOF
}

log() {
  printf '[%s] %s\n' "$(date -Is)" "$*" >&2
}

die() {
  log "ERROR: $*"
  exit 1
}

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "Required command not found: $1"
}

run_root() {
  if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
    "$@"
  else
    sudo "$@"
  fi
}

INFLUX_BASE=""
INFLUX_DB="evcc"
VM_BASE="http://127.0.0.1:8428"
VM_SERVICE="victoriametrics"
VM_STORAGE_PATH="/var/lib/victoria-metrics"
PYTHON_BIN="python3"
PYTHON_IMPORTER="./reimport_influx_to_vm.py"
VMCTL_BIN="vmctl"
MEASUREMENT=""
INFLUX_USER=""
INFLUX_PASSWORD=""
WORKDIR="/tmp/evcc-vm-import-benchmark"
OUTPUT_DIR=""
START=""
END=""
VMCTL_START=""
VMCTL_END=""
ALLOW_DESTRUCTIVE_RESET=0
RUN_PYTHON_DRY=1
RUN_PYTHON_IMPORT=1
RUN_VMCTL=1

while [[ $# -gt 0 ]]; do
  case "$1" in
    --influx-base) INFLUX_BASE="${2:-}"; shift 2 ;;
    --db) INFLUX_DB="${2:-}"; shift 2 ;;
    --vm-base) VM_BASE="${2:-}"; shift 2 ;;
    --vm-service) VM_SERVICE="${2:-}"; shift 2 ;;
    --vm-storage-path) VM_STORAGE_PATH="${2:-}"; shift 2 ;;
    --python-bin) PYTHON_BIN="${2:-}"; shift 2 ;;
    --python-importer) PYTHON_IMPORTER="${2:-}"; shift 2 ;;
    --vmctl-bin) VMCTL_BIN="${2:-}"; shift 2 ;;
    --measurement) MEASUREMENT="${2:-}"; shift 2 ;;
    --influx-user) INFLUX_USER="${2:-}"; shift 2 ;;
    --influx-password) INFLUX_PASSWORD="${2:-}"; shift 2 ;;
    --workdir) WORKDIR="${2:-}"; shift 2 ;;
    --output-dir) OUTPUT_DIR="${2:-}"; shift 2 ;;
    --start) START="${2:-}"; shift 2 ;;
    --end) END="${2:-}"; shift 2 ;;
    --vmctl-start) VMCTL_START="${2:-}"; shift 2 ;;
    --vmctl-end) VMCTL_END="${2:-}"; shift 2 ;;
    --allow-destructive-reset) ALLOW_DESTRUCTIVE_RESET=1; shift ;;
    --skip-python-dry-run) RUN_PYTHON_DRY=0; shift ;;
    --skip-python-import) RUN_PYTHON_IMPORT=0; shift ;;
    --skip-vmctl) RUN_VMCTL=0; shift ;;
    -h|--help) usage; exit 0 ;;
    *) die "Unknown argument: $1" ;;
  esac
done

[[ -n "$INFLUX_BASE" ]] || die "--influx-base is required"
[[ -n "$START" ]] || die "--start is required"
[[ -n "$END" ]] || die "--end is required"
[[ "$ALLOW_DESTRUCTIVE_RESET" -eq 1 ]] || die "--allow-destructive-reset is required"
[[ "$VM_STORAGE_PATH" != "/" ]] || die "Refusing to operate on / as storage path"
[[ -n "$VM_STORAGE_PATH" ]] || die "Storage path must not be empty"

VMCTL_START="${VMCTL_START:-$START}"
VMCTL_END="${VMCTL_END:-$END}"

need_cmd "$PYTHON_BIN"
need_cmd curl
need_cmd find
need_cmd systemctl
need_cmd /usr/bin/time
[[ "$RUN_VMCTL" -eq 0 ]] || need_cmd "$VMCTL_BIN"
[[ -f "$PYTHON_IMPORTER" ]] || die "Python importer not found: $PYTHON_IMPORTER"

timestamp="$(date +%Y%m%d-%H%M%S)"
OUTPUT_DIR="${OUTPUT_DIR:-$WORKDIR/$timestamp}"
mkdir -p "$OUTPUT_DIR"

SOURCE_BASELINE_JSON="$OUTPUT_DIR/source-baseline.json"
RUN_SUMMARY_JSON="$OUTPUT_DIR/run-summary.json"
RUN_SUMMARY_MD="$OUTPUT_DIR/run-summary.md"

wait_for_vm() {
  local url="$1/health"
  for _ in $(seq 1 60); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  return 1
}

reset_vm_storage() {
  log "Resetting VictoriaMetrics storage at $VM_STORAGE_PATH"
  run_root systemctl stop "$VM_SERVICE"
  run_root mkdir -p "$VM_STORAGE_PATH"
  run_root find "$VM_STORAGE_PATH" -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +
  run_root systemctl start "$VM_SERVICE"
  wait_for_vm "$VM_BASE" || die "VictoriaMetrics did not become healthy again at $VM_BASE"
}

build_python_args() {
  local -n out_ref=$1
  out_ref=(
    "$PYTHON_BIN" "$PYTHON_IMPORTER"
    --influx-base "$INFLUX_BASE"
    --vm-base "$VM_BASE"
    --db "$INFLUX_DB"
    --start "$START"
    --end "$END"
  )
  if [[ -n "$MEASUREMENT" ]]; then
    out_ref+=(--measurement "$MEASUREMENT")
  fi
}

build_vmctl_args() {
  local -n out_ref=$1
  out_ref=(
    "$VMCTL_BIN" influx
    --influx-addr="$INFLUX_BASE"
    --influx-database="$INFLUX_DB"
    --influx-filter-time-start="$VMCTL_START"
    --influx-filter-time-end="$VMCTL_END"
    --vm-addr="$VM_BASE"
  )
  if [[ -n "$INFLUX_USER" ]]; then
    out_ref+=(--influx-user="$INFLUX_USER")
  fi
  if [[ -n "$INFLUX_PASSWORD" ]]; then
    out_ref+=(--influx-password="$INFLUX_PASSWORD")
  fi
}

analyze_source_baseline() {
  log "Building source baseline from InfluxDB"
  "$PYTHON_BIN" - "$PYTHON_IMPORTER" "$INFLUX_BASE" "$INFLUX_DB" "$START" "$END" "$MEASUREMENT" > "$SOURCE_BASELINE_JSON" <<'PY'
import hashlib
import importlib.util
import json
import sys

script_path, influx_base, db, start, end, measurement = sys.argv[1:7]
measurement = measurement or None

spec = importlib.util.spec_from_file_location("reimport_influx_to_vm", script_path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

def make_key(labels):
    return json.dumps(sorted(labels.items()), separators=(",",":"), ensure_ascii=True)

def update_signature(entry, timestamps, values):
    for ts, value in zip(timestamps, values):
        if entry["point_count"] == 0:
            entry["first_timestamp"] = ts
            entry["first_value"] = value
        entry["last_timestamp"] = ts
        entry["last_value"] = value
        entry["point_count"] += 1
        entry["sum_value"] += float(value)
        entry["hasher"].update(str(ts).encode("utf-8"))
        entry["hasher"].update(b"|")
        entry["hasher"].update(repr(float(value)).encode("utf-8"))
        entry["hasher"].update(b"\n")

names = [measurement] if measurement else module.measurements(influx_base, db)
per_metric = {}
per_measurement = {}
per_series = {}
numeric_measurements = 0

for name in names:
    ftypes = module.field_map(influx_base, db, name)
    if not any(ft in module.NUMERIC_TYPES for ft in ftypes.values()):
        continue
    numeric_measurements += 1
    query = f'SELECT * FROM "{name}" WHERE time >= \'{start}\' AND time < \'{end}\''
    url = (
        f"{influx_base}/query?db={module.urllib.parse.quote(db)}"
        f"&epoch=ns&chunked=true&chunk_size=5000&q={module.urllib.parse.quote(query)}"
    )
    measurement_series = set()
    measurement_points = 0
    measurement_metrics = set()
    for obj in module.influx_stream(url):
        rows = module.series_rows_from_chunk(obj, ftypes, name, db)
        for row in rows:
            labels = dict(row["metric"])
            metric_name = labels["__name__"]
            key = make_key(labels)
            points = len(row["values"])
            metric_entry = per_metric.setdefault(metric_name, {"series": 0, "points": 0, "measurement": name})
            if key not in per_series:
                per_series[key] = {
                    "labels": labels,
                    "metric": metric_name,
                    "measurement": name,
                    "point_count": 0,
                    "sum_value": 0.0,
                    "first_timestamp": None,
                    "last_timestamp": None,
                    "first_value": None,
                    "last_value": None,
                    "hasher": hashlib.blake2b(digest_size=16),
                }
                metric_entry["series"] += 1
            update_signature(per_series[key], row["timestamps"], row["values"])
            metric_entry["points"] += points
            measurement_series.add(key)
            measurement_points += points
            measurement_metrics.add(metric_name)
    per_measurement[name] = {
        "metrics": sorted(measurement_metrics),
        "series": len(measurement_series),
        "points": measurement_points,
    }

normalized_series = {}
for key, entry in per_series.items():
    normalized_series[key] = {
        "labels": entry["labels"],
        "metric": entry["metric"],
        "measurement": entry["measurement"],
        "point_count": entry["point_count"],
        "sum_value": round(entry["sum_value"], 12),
        "first_timestamp": entry["first_timestamp"],
        "last_timestamp": entry["last_timestamp"],
        "first_value": entry["first_value"],
        "last_value": entry["last_value"],
        "content_hash": entry["hasher"].hexdigest(),
    }

summary = {
    "measurement_count": numeric_measurements,
    "metric_count": len(per_metric),
    "series": len(normalized_series),
    "points": sum(v["points"] for v in per_metric.values()),
    "per_measurement": per_measurement,
    "per_metric": {key: value for key, value in sorted(per_metric.items())},
    "per_series": normalized_series,
}

print(json.dumps(summary, indent=2, sort_keys=True))
PY
}

collect_target_stats() {
  local output_json="$1"
  local range_start="$2"
  local range_end="$3"
  log "Collecting target stats from VictoriaMetrics -> $output_json"
  "$PYTHON_BIN" - "$VM_BASE" "$SOURCE_BASELINE_JSON" "$output_json" "$range_start" "$range_end" "$INFLUX_DB" <<'PY'
import hashlib
import json
import sys
import urllib.parse
import urllib.request

vm_base, source_json, output_json, range_start, range_end, db = sys.argv[1:7]

with open(source_json, encoding="utf-8") as handle:
    source = json.load(handle)

def make_key(labels):
    return json.dumps(sorted(labels.items()), separators=(",",":"), ensure_ascii=True)

def export_series(match_expr):
    url = (
        f"{vm_base}/api/v1/export?match[]={urllib.parse.quote(match_expr, safe='')}"
        f"&start={urllib.parse.quote(range_start, safe='')}"
        f"&end={urllib.parse.quote(range_end, safe='')}"
    )
    with urllib.request.urlopen(url, timeout=600) as response:
        for raw_line in response:
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            yield json.loads(line)

per_metric = {}
per_series = {}
metric_names = sorted(source["per_metric"].keys())

for metric_name in metric_names:
    match_expr = f'{metric_name}{{db="{db}"}}'
    metric_series = 0
    metric_points = 0
    for row in export_series(match_expr):
        labels = dict(row.get("metric", {}))
        key = make_key(labels)
        timestamps = row.get("timestamps", [])
        values = row.get("values", [])
        hasher = hashlib.blake2b(digest_size=16)
        point_count = 0
        sum_value = 0.0
        first_timestamp = None
        last_timestamp = None
        first_value = None
        last_value = None
        for ts, value in zip(timestamps, values):
            numeric = float(value)
            if point_count == 0:
                first_timestamp = ts
                first_value = numeric
            last_timestamp = ts
            last_value = numeric
            point_count += 1
            sum_value += numeric
            hasher.update(str(ts).encode("utf-8"))
            hasher.update(b"|")
            hasher.update(repr(numeric).encode("utf-8"))
            hasher.update(b"\n")
        per_series[key] = {
            "labels": labels,
            "metric": metric_name,
            "point_count": point_count,
            "sum_value": round(sum_value, 12),
            "first_timestamp": first_timestamp,
            "last_timestamp": last_timestamp,
            "first_value": first_value,
            "last_value": last_value,
            "content_hash": hasher.hexdigest(),
        }
        metric_series += 1
        metric_points += point_count
    if metric_series > 0:
        per_metric[metric_name] = {
            "series": metric_series,
            "points": metric_points,
        }

out = {
    "metric_count": len(per_metric),
    "series": len(per_series),
    "points": sum(item["points"] for item in per_metric.values()),
    "per_metric": per_metric,
    "per_series": per_series,
}

with open(output_json, "w", encoding="utf-8") as handle:
    json.dump(out, handle, indent=2, sort_keys=True)
PY
}

build_compare_report() {
  local label="$1"
  local target_json="$2"
  local report_json="$3"
  "$PYTHON_BIN" - "$SOURCE_BASELINE_JSON" "$target_json" "$label" > "$report_json" <<'PY'
import json
import sys

source_json, target_json, label = sys.argv[1:4]

with open(source_json, encoding="utf-8") as handle:
    source = json.load(handle)
with open(target_json, encoding="utf-8") as handle:
    target = json.load(handle)

source_series = source["per_series"]
target_series = target["per_series"]

missing_series = []
extra_series = []
content_mismatches = []
metric_count_mismatches = []

for key, source_entry in source_series.items():
    target_entry = target_series.get(key)
    if target_entry is None:
        missing_series.append({
            "metric": source_entry["metric"],
            "measurement": source_entry["measurement"],
            "labels": source_entry["labels"],
            "source_point_count": source_entry["point_count"],
        })
        continue
    if any([
        source_entry["point_count"] != target_entry["point_count"],
        source_entry["first_timestamp"] != target_entry["first_timestamp"],
        source_entry["last_timestamp"] != target_entry["last_timestamp"],
        source_entry["content_hash"] != target_entry["content_hash"],
    ]):
        content_mismatches.append({
            "metric": source_entry["metric"],
            "measurement": source_entry["measurement"],
            "labels": source_entry["labels"],
            "source_point_count": source_entry["point_count"],
            "target_point_count": target_entry["point_count"],
            "source_first_timestamp": source_entry["first_timestamp"],
            "target_first_timestamp": target_entry["first_timestamp"],
            "source_last_timestamp": source_entry["last_timestamp"],
            "target_last_timestamp": target_entry["last_timestamp"],
            "source_hash": source_entry["content_hash"],
            "target_hash": target_entry["content_hash"],
        })

for key, target_entry in target_series.items():
    if key not in source_series:
        extra_series.append({
            "metric": target_entry["metric"],
            "labels": target_entry["labels"],
            "target_point_count": target_entry["point_count"],
        })

all_metrics = sorted(set(source["per_metric"].keys()) | set(target["per_metric"].keys()))
for metric_name in all_metrics:
    source_metric = source["per_metric"].get(metric_name, {"series": 0, "points": 0})
    target_metric = target["per_metric"].get(metric_name, {"series": 0, "points": 0})
    if source_metric["series"] != target_metric["series"] or source_metric["points"] != target_metric["points"]:
        metric_count_mismatches.append({
            "metric": metric_name,
            "source_series": source_metric["series"],
            "target_series": target_metric["series"],
            "source_points": source_metric["points"],
            "target_points": target_metric["points"],
        })

severity = "OK"
if missing_series or extra_series:
    severity = "CRITICAL"
elif content_mismatches:
    severity = "CRITICAL"
elif metric_count_mismatches:
    severity = "WARNING"

result = {
    "label": label,
    "severity": severity,
    "source_metric_count": source["metric_count"],
    "target_metric_count": target["metric_count"],
    "source_series": source["series"],
    "target_series": target["series"],
    "source_points": source["points"],
    "target_points": target["points"],
    "missing_series_count": len(missing_series),
    "extra_series_count": len(extra_series),
    "content_mismatch_count": len(content_mismatches),
    "metric_count_mismatch_count": len(metric_count_mismatches),
    "missing_series": sorted(missing_series, key=lambda item: (item["metric"], json.dumps(item["labels"], sort_keys=True)))[:25],
    "extra_series": sorted(extra_series, key=lambda item: (item["metric"], json.dumps(item["labels"], sort_keys=True)))[:25],
    "content_mismatches": sorted(content_mismatches, key=lambda item: (item["metric"], json.dumps(item["labels"], sort_keys=True)))[:25],
    "metric_count_mismatches": metric_count_mismatches[:50],
}

print(json.dumps(result, indent=2, sort_keys=True))
PY
}

run_python_case() {
  local label="$1"
  local dry_run="$2"
  local out_dir="$OUTPUT_DIR/$label"
  local out_json="$out_dir/summary.json"
  local stderr_log="$out_dir/stderr.log"
  local stdout_log="$out_dir/stdout.log"
  local time_log="$out_dir/time.log"
  mkdir -p "$out_dir"

  local args=()
  build_python_args args
  if [[ "$dry_run" -eq 1 ]]; then
    args+=(--dry-run)
  fi

  log "Running $label"
  /usr/bin/time -p -o "$time_log" "${args[@]}" >"$stdout_log" 2>"$stderr_log"

  "$PYTHON_BIN" - "$stdout_log" "$time_log" "$SOURCE_BASELINE_JSON" "$label" > "$out_json" <<'PY'
import json
import pathlib
import sys

stdout_log, time_log, source_json, label = sys.argv[1:5]

with open(source_json, encoding="utf-8") as handle:
    source = json.load(handle)

summary = None
for line in reversed(pathlib.Path(stdout_log).read_text(encoding="utf-8", errors="replace").splitlines()):
    line = line.strip()
    if not line:
        continue
    try:
        candidate = json.loads(line)
    except json.JSONDecodeError:
        continue
    if isinstance(candidate, dict) and "measurements" in candidate and "series" in candidate and "points" in candidate:
        summary = candidate
        break

if summary is None:
    raise SystemExit(f"Could not parse Python importer summary from {stdout_log}")

elapsed = None
for line in pathlib.Path(time_log).read_text(encoding="utf-8", errors="replace").splitlines():
    if line.startswith("real "):
        elapsed = float(line.split()[1])
        break

result = {
    "label": label,
    "tool": "reimport_influx_to_vm.py",
    "measurements": summary["measurements"],
    "series": summary["series"],
    "points": summary["points"],
    "imported": summary["imported"],
    "elapsed_seconds": elapsed,
    "throughput_points_per_second": None if not elapsed else round(source["points"] / elapsed, 2),
    "source_points": source["points"],
    "dry_run": label.endswith("dry-run"),
}

print(json.dumps(result, indent=2, sort_keys=True))
PY
}

run_vmctl_case() {
  local label="$1"
  local out_dir="$OUTPUT_DIR/$label"
  local stdout_log="$out_dir/stdout.log"
  local stderr_log="$out_dir/stderr.log"
  local time_log="$out_dir/time.log"
  local out_json="$out_dir/summary.json"
  mkdir -p "$out_dir"

  local args=()
  build_vmctl_args args

  log "Running $label"
  /usr/bin/time -p -o "$time_log" bash -lc 'yes | "$@"' _ "${args[@]}" >"$stdout_log" 2>"$stderr_log"

  "$PYTHON_BIN" - "$stdout_log" "$stderr_log" "$time_log" "$SOURCE_BASELINE_JSON" "$label" > "$out_json" <<'PY'
import json
import pathlib
import re
import sys

stdout_log, stderr_log, time_log, source_json, label = sys.argv[1:6]
with open(source_json, encoding="utf-8") as handle:
    source = json.load(handle)

stdout_text = pathlib.Path(stdout_log).read_text(encoding="utf-8", errors="replace")
stderr_text = pathlib.Path(stderr_log).read_text(encoding="utf-8", errors="replace")
combined = stdout_text + "\n" + stderr_text

elapsed = None
for line in pathlib.Path(time_log).read_text(encoding="utf-8", errors="replace").splitlines():
    if line.startswith("real "):
        elapsed = float(line.split()[1])
        break

def extract(patterns):
    for pattern in patterns:
        match = re.search(pattern, combined, re.IGNORECASE | re.MULTILINE)
        if match:
            try:
                return int(match.group(1).replace(",", "").replace(".", ""))
            except ValueError:
                continue
    return None

found_series = extract([
    r'([0-9][0-9.,]*)\s+(?:time\s+)?series\s+(?:were\s+)?found',
    r'found\s*[:=]\s*([0-9][0-9.,]*)\s+series',
])
processed_series = extract([
    r'([0-9][0-9.,]*)\s+(?:time\s+)?series\s+(?:were\s+)?processed',
    r'processed\s*[:=]\s*([0-9][0-9.,]*)\s+series',
])
imported_samples = extract([
    r'([0-9][0-9.,]*)\s+samples\s+(?:were\s+)?imported',
    r'imported\s*[:=]\s*([0-9][0-9.,]*)\s+samples',
])

result = {
    "label": label,
    "tool": "vmctl influx",
    "elapsed_seconds": elapsed,
    "throughput_points_per_second": None if not elapsed else round(source["points"] / elapsed, 2),
    "source_points": source["points"],
    "found_series": found_series,
    "processed_series": processed_series,
    "imported_samples": imported_samples,
}

print(json.dumps(result, indent=2, sort_keys=True))
PY
}

render_summary() {
  "$PYTHON_BIN" - "$OUTPUT_DIR" "$RUN_SUMMARY_JSON" "$RUN_SUMMARY_MD" "$SOURCE_BASELINE_JSON" <<'PY'
import json
import pathlib
import sys

output_dir, summary_json_path, summary_md_path, source_json = sys.argv[1:5]
root = pathlib.Path(output_dir)
with open(source_json, encoding="utf-8") as handle:
    source = json.load(handle)

runs = []
for run_dir in sorted(path for path in root.iterdir() if path.is_dir()):
    summary_file = run_dir / "summary.json"
    compare_file = run_dir / "compare.json"
    if not summary_file.exists():
        continue
    with open(summary_file, encoding="utf-8") as handle:
        summary = json.load(handle)
    if compare_file.exists():
        with open(compare_file, encoding="utf-8") as handle:
            summary["compare"] = json.load(handle)
    runs.append(summary)

result = {
    "source_baseline": {
        "measurements": source["measurement_count"],
        "metrics": source["metric_count"],
        "series": source["series"],
        "points": source["points"],
    },
    "runs": runs,
}

with open(summary_json_path, "w", encoding="utf-8") as handle:
    json.dump(result, handle, indent=2, sort_keys=True)

lines = []
lines.append("# Import benchmark summary")
lines.append("")
lines.append("## Source baseline")
lines.append("")
lines.append(f"- measurements: `{source['measurement_count']}`")
lines.append(f"- metrics: `{source['metric_count']}`")
lines.append(f"- series: `{source['series']}`")
lines.append(f"- points: `{source['points']}`")
lines.append("")
lines.append("## Runs")
lines.append("")
lines.append("| Run | Tool | Elapsed | Throughput | Imported | Difference check |")
lines.append("|---|---|---:|---:|---:|---|")

for item in runs:
    elapsed = item.get("elapsed_seconds")
    throughput = item.get("throughput_points_per_second")
    imported = item.get("imported")
    if imported is None:
        imported = item.get("imported_samples")
    compare = item.get("compare", {})
    severity = compare.get("severity", "n/a")
    lines.append(
        f"| {item['label']} | {item['tool']} | "
        f"{'n/a' if elapsed is None else f'{elapsed:.2f}s'} | "
        f"{'n/a' if throughput is None else f'{throughput:,.0f} pts/s'} | "
        f"{'n/a' if imported is None else imported} | "
        f"{severity} |"
    )

    if compare:
        lines.append("")
        lines.append(f"### {item['label']} differences")
        lines.append("")
        lines.append(f"- severity: `{compare['severity']}`")
        lines.append(f"- missing series: `{compare.get('missing_series_count', 0)}`")
        lines.append(f"- extra series: `{compare.get('extra_series_count', 0)}`")
        lines.append(f"- content mismatches: `{compare.get('content_mismatch_count', 0)}`")
        lines.append(f"- metric count mismatches: `{compare.get('metric_count_mismatch_count', 0)}`")
        if compare.get("missing_series"):
            lines.append("- missing series examples:")
            for entry in compare["missing_series"][:10]:
                lines.append(f"  - `{entry['metric']}` labels `{json.dumps(entry['labels'], ensure_ascii=True, sort_keys=True)}`")
        if compare.get("extra_series"):
            lines.append("- extra series examples:")
            for entry in compare["extra_series"][:10]:
                lines.append(f"  - `{entry['metric']}` labels `{json.dumps(entry['labels'], ensure_ascii=True, sort_keys=True)}`")
        if compare.get("content_mismatches"):
            lines.append("- content mismatch examples:")
            for entry in compare["content_mismatches"][:10]:
                lines.append(
                    f"  - `{entry['metric']}` labels `{json.dumps(entry['labels'], ensure_ascii=True, sort_keys=True)}` source points `{entry['source_point_count']}`, target points `{entry['target_point_count']}`"
                )
        lines.append("- severity logic:")
        lines.append("  - `CRITICAL`: missing series, extra series, or content mismatches")
        lines.append("  - `WARNING`: metric-level count mismatch only")
        lines.append("  - `OK`: no detected differences")

lines.append("")
lines.append("## Notes")
lines.append("")
lines.append("- The comparison checks series presence plus a content signature per series.")
lines.append("- The content signature includes point count, first and last timestamp, and a hash over all exported points.")
lines.append("- Use the per-run logs in the same output directory for detailed importer output.")

pathlib.Path(summary_md_path).write_text("\n".join(lines) + "\n", encoding="utf-8")
PY
}

analyze_source_baseline

if [[ "$RUN_PYTHON_DRY" -eq 1 ]]; then
  run_python_case "python-dry-run" 1
fi

if [[ "$RUN_PYTHON_IMPORT" -eq 1 ]]; then
  reset_vm_storage
  run_python_case "python-import" 0
  collect_target_stats "$OUTPUT_DIR/python-import/target-stats.json" "$START" "$END"
  build_compare_report "python-import" "$OUTPUT_DIR/python-import/target-stats.json" "$OUTPUT_DIR/python-import/compare.json"
fi

if [[ "$RUN_VMCTL" -eq 1 ]]; then
  reset_vm_storage
  run_vmctl_case "vmctl-import"
  collect_target_stats "$OUTPUT_DIR/vmctl-import/target-stats.json" "$VMCTL_START" "$VMCTL_END"
  build_compare_report "vmctl-import" "$OUTPUT_DIR/vmctl-import/target-stats.json" "$OUTPUT_DIR/vmctl-import/compare.json"
fi

render_summary

log "Benchmark finished."
log "Summary JSON: $RUN_SUMMARY_JSON"
log "Summary Markdown: $RUN_SUMMARY_MD"
