#!/usr/bin/env python3
"""Import Victron VRM daily battery energy-flow stats into VictoriaMetrics."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple
from zoneinfo import ZoneInfo

SCRIPT_NAME = "import-vrm-energy-flows.py"
SCRIPT_VERSION = "2026.07.28.1"
SCRIPT_LAST_MODIFIED = "2026-07-28"
ROOT = Path(__file__).resolve().parents[2]
ENV_LOCAL = ROOT / ".env.local"
DEFAULT_VM_BASE_URL = "http://127.0.0.1:8428"
DEFAULT_TIMEZONE = "Europe/Berlin"
DEFAULT_SOURCE_LABEL = "vrm"
DEFAULT_LOOKBACK_DAYS = 7
DEFAULT_FETCH_CHUNK_DAYS = 31
VRM_KWH_KEYS = ("Bc", "Bg", "Gb", "Pb")
VRM_KEY_TO_FIELD = {
    "Bc": "battery_to_consumers_kwh",
    "Bg": "battery_to_grid_kwh",
    "Gb": "grid_to_battery_kwh",
    "Pb": "pv_to_battery_kwh",
}
DAILY_METRICS = {
    "evcc_vrm_pv_to_battery_daily_wh": "pv_to_battery_kwh",
    "evcc_vrm_grid_to_battery_daily_wh": "grid_to_battery_kwh",
    "evcc_vrm_battery_to_consumers_daily_wh": "battery_to_consumers_kwh",
    "evcc_vrm_battery_to_grid_daily_wh": "battery_to_grid_kwh",
    "evcc_vrm_battery_charge_daily_wh": "battery_charge_kwh",
    "evcc_vrm_battery_discharge_daily_wh": "battery_discharge_kwh",
}


def local_timestamp() -> str:
    return dt.datetime.now().astimezone().replace(microsecond=0).isoformat()


def load_env_local(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ.setdefault(key.strip(), value)


def parse_day(value: str) -> dt.date:
    try:
        return dt.date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Invalid date {value!r}; expected YYYY-MM-DD") from exc


def date_range(start_day: dt.date, end_day: dt.date) -> Iterable[dt.date]:
    for offset in range((end_day - start_day).days + 1):
        yield start_day + dt.timedelta(days=offset)


def local_midnight_epoch_seconds(day: dt.date, timezone_name: str) -> int:
    timezone = ZoneInfo(timezone_name)
    return int(dt.datetime.combine(day, dt.time.min, tzinfo=timezone).timestamp())


def local_noon_timestamp_ms(day: dt.date, timezone_name: str) -> int:
    timezone = ZoneInfo(timezone_name)
    return int(dt.datetime.combine(day, dt.time(hour=12), tzinfo=timezone).timestamp() * 1000)


def fetch_vrm_stats(site_id: str, token: str, start_day: dt.date, end_day: dt.date, timezone_name: str) -> Mapping[str, object]:
    start_epoch = local_midnight_epoch_seconds(start_day, timezone_name)
    end_epoch = local_midnight_epoch_seconds(end_day + dt.timedelta(days=1), timezone_name) - 1
    params = urllib.parse.urlencode({"type": "kwh", "interval": "days", "start": str(start_epoch), "end": str(end_epoch)})
    url = f"https://vrmapi.victronenergy.com/v2/installations/{site_id}/stats?{params}"
    request = urllib.request.Request(url, headers={"x-authorization": f"Token {token}"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def chunk_date_ranges(start_day: dt.date, end_day: dt.date, chunk_days: int) -> Iterable[tuple[dt.date, dt.date]]:
    if chunk_days < 1:
        raise ValueError("chunk_days must be >= 1")
    current = start_day
    while current <= end_day:
        chunk_end = min(end_day, current + dt.timedelta(days=chunk_days - 1))
        yield current, chunk_end
        current = chunk_end + dt.timedelta(days=1)


def fetch_vrm_rows_chunked(
    site_id: str,
    token: str,
    start_day: dt.date,
    end_day: dt.date,
    timezone_name: str,
    chunk_days: int,
) -> List[Dict[str, object]]:
    rows_by_day: Dict[str, Dict[str, object]] = {}
    for chunk_start, chunk_end in chunk_date_ranges(start_day, end_day, chunk_days):
        # Include the previous day as a baseline. VRM may return cumulative
        # counters for these flows; without the baseline the first day of each
        # chunk cannot be converted into a daily delta correctly.
        fetch_start_day = chunk_start - dt.timedelta(days=1)
        payload = fetch_vrm_stats(site_id, token, fetch_start_day, chunk_end, timezone_name)
        records = payload.get("records")
        if not payload.get("success") or not isinstance(records, dict):
            raise SystemExit(
                "VRM API did not return daily kWh records for "
                f"{fetch_start_day}..{chunk_end}: {json.dumps(payload, ensure_ascii=True)[:1000]}"
            )
        for row in filter_rows(normalize_api_records(records, fetch_start_day, chunk_end, timezone_name), chunk_start, chunk_end):
            rows_by_day[str(row["day"])] = row
    return [rows_by_day[day.isoformat()] for day in date_range(start_day, end_day) if day.isoformat() in rows_by_day]


def as_float(value: object) -> float:
    if value is None or value == "":
        return 0.0
    return float(value)


def day_from_vrm_timestamp(value: object, timezone_name: str) -> Optional[str]:
    try:
        timestamp = as_float(value)
    except (TypeError, ValueError):
        return None
    if timestamp <= 0:
        return None
    if timestamp > 10_000_000_000:
        timestamp /= 1000.0
    # VRM returns Unix timestamps for kWh buckets. Reject implausible values so
    # offline fixtures without timestamps can still fall back to index mapping.
    if timestamp < 946_684_800 or timestamp > 4_102_444_800:
        return None
    timezone = ZoneInfo(timezone_name)
    return dt.datetime.fromtimestamp(timestamp, tz=timezone).date().isoformat()


def parse_vrm_samples(values: object, days: Sequence[dt.date], timezone_name: str) -> List[Tuple[str, float]]:
    if not isinstance(values, list):
        return []
    samples: List[Tuple[str, float]] = []
    for index, entry in enumerate(values):
        day_key: Optional[str] = None
        value = 0.0
        if isinstance(entry, list) and len(entry) > 1:
            day_key = day_from_vrm_timestamp(entry[0], timezone_name)
            value = as_float(entry[1])
        elif isinstance(entry, (int, float, str)):
            value = as_float(entry)
        if day_key is None and index < len(days):
            day_key = days[index].isoformat()
        if day_key is not None:
            samples.append((day_key, value))
    return samples


def looks_like_cumulative_vrm_counter(samples: Sequence[Tuple[str, float]]) -> bool:
    positive_values = [value for _, value in samples if value > 0]
    if len(positive_values) < 4:
        return False
    max_value = max(positive_values)
    if max_value < 250.0:
        return False
    ordered_values = [value for _, value in sorted(samples, key=lambda item: item[0]) if value > 0]
    if len(ordered_values) < 4:
        return False
    non_decreasing = sum(1 for previous, current in zip(ordered_values, ordered_values[1:]) if current >= previous)
    mostly_non_decreasing = non_decreasing >= max(1, len(ordered_values) - 2)
    raw_sum_is_implausible = sum(ordered_values) > max_value * 2
    return mostly_non_decreasing and raw_sum_is_implausible


def normalize_vrm_samples(samples: Sequence[Tuple[str, float]], allowed_days: set[str]) -> Dict[str, float]:
    values_by_day: Dict[str, float] = {}
    if not samples:
        return values_by_day
    ordered = sorted(samples, key=lambda item: item[0])
    if looks_like_cumulative_vrm_counter(ordered):
        previous_value: Optional[float] = None
        for day_key, value in ordered:
            if previous_value is None:
                delta = 0.0
            elif value >= previous_value:
                delta = value - previous_value
            else:
                delta = value
            if day_key in allowed_days:
                values_by_day[day_key] = values_by_day.get(day_key, 0.0) + max(delta, 0.0)
            previous_value = value
        return values_by_day
    for day_key, value in ordered:
        if day_key in allowed_days:
            values_by_day[day_key] = values_by_day.get(day_key, 0.0) + value
    return values_by_day


def normalize_api_records(
    records: Mapping[str, object],
    start_day: dt.date,
    end_day: dt.date,
    timezone_name: str = DEFAULT_TIMEZONE,
) -> List[Dict[str, object]]:
    days = list(date_range(start_day, end_day))
    allowed_days = {day.isoformat() for day in days}
    values_by_key_day: Dict[str, Dict[str, float]] = {}
    observed_days: set[str] = set()

    for key in VRM_KWH_KEYS:
        samples = parse_vrm_samples(records.get(key, []), days, timezone_name)
        observed_days.update(day_key for day_key, _ in samples if day_key in allowed_days)
        values_by_key_day[key] = normalize_vrm_samples(samples, allowed_days)

    rows: List[Dict[str, object]] = []
    for day in days:
        day_key = day.isoformat()
        if day_key not in observed_days:
            continue
        row: Dict[str, object] = {"day": day_key}
        for key in VRM_KWH_KEYS:
            row[VRM_KEY_TO_FIELD[key]] = values_by_key_day.get(key, {}).get(day_key, 0.0)
        enrich_row(row)
        rows.append(row)
    return rows


def enrich_row(row: Dict[str, object]) -> None:
    row["pv_to_battery_kwh"] = as_float(row.get("pv_to_battery_kwh"))
    row["grid_to_battery_kwh"] = as_float(row.get("grid_to_battery_kwh"))
    row["battery_to_consumers_kwh"] = as_float(row.get("battery_to_consumers_kwh"))
    row["battery_to_grid_kwh"] = as_float(row.get("battery_to_grid_kwh"))
    row["battery_charge_kwh"] = row["pv_to_battery_kwh"] + row["grid_to_battery_kwh"]
    row["battery_discharge_kwh"] = row["battery_to_consumers_kwh"] + row["battery_to_grid_kwh"]


def load_json_rows(path: Path) -> List[Dict[str, object]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        raw_rows = payload
    elif isinstance(payload, dict) and isinstance(payload.get("rows"), list):
        raw_rows = payload["rows"]
    elif isinstance(payload, dict) and isinstance(payload.get("records"), dict):
        raise SystemExit("JSON contains raw VRM records; use live VRM import or cache format with rows for offline import.")
    else:
        raise SystemExit(f"Unsupported JSON input format: {path}")
    rows: List[Dict[str, object]] = []
    for item in raw_rows:
        row = dict(item)
        if not row.get("day"):
            raise SystemExit(f"JSON row without day in {path}: {item}")
        enrich_row(row)
        rows.append(row)
    return rows


def load_csv_rows(path: Path) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for item in reader:
            row = dict(item)
            if not row.get("day"):
                raise SystemExit(f"CSV row without day in {path}: {item}")
            enrich_row(row)
            rows.append(row)
    return rows


def filter_rows(rows: Sequence[Dict[str, object]], start_day: dt.date, end_day: dt.date) -> List[Dict[str, object]]:
    result: List[Dict[str, object]] = []
    for row in rows:
        day = parse_day(str(row["day"]))
        if start_day <= day <= end_day:
            result.append(row)
    return sorted(result, key=lambda item: str(item["day"]))


def make_metric_line(metric_name: str, value_wh: float, row: Mapping[str, object], site_id: str, source_label: str, timezone_name: str) -> str:
    day = parse_day(str(row["day"]))
    labels = {
        "__name__": metric_name,
        "source": source_label,
        "site": str(site_id),
        "local_year": f"{day.year:04d}",
        "local_month": f"{day.month:02d}",
        "local_day": f"{day.day:02d}",
        "local_date": day.isoformat(),
    }
    return json.dumps({"metric": labels, "values": [round(value_wh, 6)], "timestamps": [local_noon_timestamp_ms(day, timezone_name)]}, separators=(",", ":"), ensure_ascii=True)


def build_import_lines(rows: Sequence[Dict[str, object]], site_id: str, source_label: str, timezone_name: str) -> List[str]:
    lines: List[str] = []
    for row in rows:
        for metric_name, field_name in DAILY_METRICS.items():
            value_wh = as_float(row.get(field_name)) * 1000.0
            lines.append(make_metric_line(metric_name, value_wh, row, site_id, source_label, timezone_name))
    return lines


def post_bytes(url: str, payload: bytes, content_type: str) -> str:
    request = urllib.request.Request(url, data=payload, headers={"Content-Type": content_type}, method="POST")
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read().decode("utf-8", errors="replace")


def chunks(items: Sequence[str], size: int) -> Iterable[Sequence[str]]:
    for index in range(0, len(items), size):
        yield items[index : index + size]


def delete_existing(vm_base_url: str, metrics: Sequence[str], site_id: str, source_label: str, start_day: dt.date, end_day: dt.date) -> None:
    all_dates = [day.isoformat() for day in date_range(start_day, end_day)]
    endpoint = vm_base_url.rstrip("/") + "/api/v1/admin/tsdb/delete_series"
    for metric_name in metrics:
        for date_chunk in chunks(all_dates, 100):
            dates = "|".join(date_chunk)
            selector = f'{{__name__="{metric_name}",site="{site_id}",source="{source_label}",local_date=~"{dates}"}}'
            data = urllib.parse.urlencode([("match[]", selector)]).encode("utf-8")
            post_bytes(endpoint, data, "application/x-www-form-urlencoded")


def write_import(vm_base_url: str, lines: Sequence[str]) -> None:
    if not lines:
        return
    endpoint = vm_base_url.rstrip("/") + "/api/v1/import"
    payload = ("\n".join(lines) + "\n").encode("utf-8")
    post_bytes(endpoint, payload, "application/x-ndjson")


def summarize(rows: Sequence[Mapping[str, object]]) -> Dict[str, object]:
    def total(field: str) -> float:
        return round(sum(as_float(row.get(field)) for row in rows), 6)
    return {
        "days": len(rows),
        "first_day": rows[0]["day"] if rows else None,
        "last_day": rows[-1]["day"] if rows else None,
        "pv_to_battery_kwh": total("pv_to_battery_kwh"),
        "grid_to_battery_kwh": total("grid_to_battery_kwh"),
        "battery_to_consumers_kwh": total("battery_to_consumers_kwh"),
        "battery_to_grid_kwh": total("battery_to_grid_kwh"),
        "battery_charge_kwh": total("battery_charge_kwh"),
        "battery_discharge_kwh": total("battery_discharge_kwh"),
    }


def write_source_snapshot(
    path: Path,
    rows: Sequence[Mapping[str, object]],
    site_id: str,
    source_label: str,
    start_day: dt.date,
    end_day: dt.date,
) -> None:
    payload = {
        "script": {"name": SCRIPT_NAME, "version": SCRIPT_VERSION, "last_modified": SCRIPT_LAST_MODIFIED},
        "generated_at": local_timestamp(),
        "site_id": site_id,
        "source": source_label,
        "requested_start_day": start_day.isoformat(),
        "requested_end_day": end_day.isoformat(),
        "summary": summarize(rows),
        "rows": list(rows),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + chr(10), encoding="utf-8")
    temporary.replace(path)


def default_days(lookback_days: int) -> tuple[dt.date, dt.date]:
    end_day = dt.datetime.now().astimezone().date() - dt.timedelta(days=1)
    start_day = end_day - dt.timedelta(days=max(lookback_days, 1) - 1)
    return start_day, end_day


def main(argv: Optional[Sequence[str]] = None) -> int:
    load_env_local(ENV_LOCAL)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site-id", default=os.environ.get("VRM_SITE_ID", ""), help="Victron VRM installation/site ID")
    parser.add_argument("--token", default=os.environ.get("VRM_API_TOKEN", ""), help="Victron VRM API token")
    parser.add_argument("--vm-base-url", default=os.environ.get("VM_BASE_URL", DEFAULT_VM_BASE_URL), help="VictoriaMetrics base URL")
    parser.add_argument("--start-day", type=parse_day, help="Local first day to import, YYYY-MM-DD")
    parser.add_argument("--end-day", type=parse_day, help="Local last day to import, YYYY-MM-DD")
    parser.add_argument("--lookback-days", type=int, default=int(os.environ.get("VRM_LOOKBACK_DAYS", DEFAULT_LOOKBACK_DAYS)), help="Days to import when start/end are omitted")
    parser.add_argument("--fetch-chunk-days", type=int, default=int(os.environ.get("VRM_FETCH_CHUNK_DAYS", DEFAULT_FETCH_CHUNK_DAYS)), help="VRM API request chunk size in days for live imports")
    parser.add_argument("--timezone", default=os.environ.get("TIMEZONE", DEFAULT_TIMEZONE), help="Local timezone for day boundaries")
    parser.add_argument("--source-label", default=os.environ.get("VRM_SOURCE_LABEL", DEFAULT_SOURCE_LABEL), help="source label written to VictoriaMetrics")
    parser.add_argument("--input-json", help="Import rows from an existing fetch_vrm_kwh_cache.py JSON file")
    parser.add_argument("--input-csv", help="Import rows from an existing fetch_vrm_kwh_cache.py CSV file")
    parser.add_argument("--output-json", help="Write the normalized source rows from this run as a validation snapshot")
    parser.add_argument("--write", action="store_true", help="Write to VictoriaMetrics. Without this, only a summary is printed.")
    parser.add_argument("--replace-range", action="store_true", help="Delete the helper metrics for the selected site/source/date range before writing")
    args = parser.parse_args(argv)

    print(f"{SCRIPT_NAME} v{SCRIPT_VERSION} (last modified {SCRIPT_LAST_MODIFIED}, run {local_timestamp()})")
    if not args.site_id:
        raise SystemExit("Missing VRM site ID. Set VRM_SITE_ID or pass --site-id.")
    if args.start_day is None or args.end_day is None:
        default_start, default_end = default_days(args.lookback_days)
        start_day = args.start_day or default_start
        end_day = args.end_day or default_end
    else:
        start_day = args.start_day
        end_day = args.end_day
    if end_day < start_day:
        raise SystemExit("--end-day must be on or after --start-day")

    if args.input_json and args.input_csv:
        raise SystemExit("Use only one of --input-json or --input-csv.")
    if args.input_json:
        rows = filter_rows(load_json_rows(Path(args.input_json)), start_day, end_day)
    elif args.input_csv:
        rows = filter_rows(load_csv_rows(Path(args.input_csv)), start_day, end_day)
    else:
        if not args.token:
            raise SystemExit("Missing VRM API token. Set VRM_API_TOKEN or pass --token, or use --input-json/--input-csv.")
        rows = fetch_vrm_rows_chunked(
            str(args.site_id),
            str(args.token),
            start_day,
            end_day,
            args.timezone,
            args.fetch_chunk_days,
        )

    summary = summarize(rows)
    print(json.dumps({"site_id": str(args.site_id), "source": args.source_label, "summary": summary}, indent=2, ensure_ascii=True))
    if args.output_json:
        output_path = Path(args.output_json)
        write_source_snapshot(output_path, rows, str(args.site_id), args.source_label, start_day, end_day)
        print(f"Wrote validation source snapshot: {output_path}")
    if not args.write:
        print("Dry run only. Add --write to import into VictoriaMetrics.")
        return 0

    if args.replace_range:
        delete_existing(args.vm_base_url, list(DAILY_METRICS.keys()), str(args.site_id), args.source_label, start_day, end_day)
        print(f"Deleted existing helper metrics for {start_day}..{end_day}.")
    lines = build_import_lines(rows, str(args.site_id), args.source_label, args.timezone)
    write_import(args.vm_base_url, lines)
    print(f"Imported {len(lines)} samples into {args.vm_base_url}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
