#!/usr/bin/env python3
"""
Script: import-sma-energy-balance.py
Purpose: Import SMA energy-balance daily exports as EVCC-compatible daily VictoriaMetrics rollups.
Version: 2026.06.07.1
Last modified: 2026-06-07
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

SCRIPT_VERSION = "2026.06.07.1"
SCRIPT_LAST_MODIFIED = "2026-06-07"
SOURCE_LABEL = "sma_energy_balance"

TARGET_METRICS = {
    "home_wh": "evcc_home_energy_daily_wh",
    "pv_wh": "evcc_pv_energy_daily_wh",
    "grid_import_wh": "evcc_grid_import_daily_wh",
    "grid_export_wh": "evcc_grid_export_daily_wh",
    "battery_charge_wh": "evcc_battery_charge_daily_wh",
    "battery_discharge_wh": "evcc_battery_discharge_daily_wh",
    "direct_consumption_wh": "evcc_pv_direct_consumption_daily_wh",
}

FIELD_ALIASES = {
    "home_wh": ["gesamtverbrauch"],
    "direct_consumption_wh": ["direktverbrauch"],
    "battery_discharge_wh": ["batterieentladung"],
    "grid_import_wh": ["netzbezug"],
    "pv_wh": ["pv_erzeugung", "pverzeugung"],
    "grid_export_wh": ["netzeinspeisung"],
    "battery_charge_wh": ["batterieladung"],
}


@dataclass(frozen=True)
class EnergyBalanceRow:
    day: dt.date
    home_wh: float | None = None
    direct_consumption_wh: float | None = None
    battery_discharge_wh: float | None = None
    grid_import_wh: float | None = None
    pv_wh: float | None = None
    grid_export_wh: float | None = None
    battery_charge_wh: float | None = None


def log(message: str) -> None:
    print(message, flush=True)


def normalize_header(value: str) -> str:
    text = str(value or "").strip().lower()
    replacements = {
        "ä": "ae",
        "ö": "oe",
        "ü": "ue",
        "ß": "ss",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    text = re.sub(r"\[[^\]]+\]", "", text)
    text = re.sub(r"/.*$", "", text)
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_")


def cleanup_cell(value: Any) -> str:
    text = str(value or "").strip()
    if text.startswith('="') and text.endswith('"'):
        text = text[2:-1]
    return text.strip().strip('"').strip()


def parse_day(value: Any, year: int, month: int, field: str) -> dt.date:
    text = cleanup_cell(value)
    match = re.match(r"^(\d{1,2})\.(\d{1,2})\.(\d{2,4})$", text)
    if not match:
        raise ValueError(f"invalid SMA energy-balance day in {field}: {value!r}")
    day = int(match.group(1))
    parsed_month = int(match.group(2))
    parsed_year = int(match.group(3))
    if parsed_year < 100:
        parsed_year += 2000
    if parsed_year != year or parsed_month != month:
        raise ValueError(f"day {value!r} does not match filename {year:04d}-{month:02d}")
    return dt.date(year, month, day)


def parse_float(value: Any, field: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        if math.isfinite(float(value)):
            return float(value)
        return None
    text = cleanup_cell(value)
    if not text:
        return None
    text = text.replace("\u00a0", " ").replace(" ", "")
    text = text.replace("kWh", "").replace("MWh", "").replace("Wh", "")
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    else:
        text = text.replace(",", ".")
    try:
        parsed = float(text)
    except ValueError as exc:
        raise ValueError(f"invalid {field}: {value!r}") from exc
    return parsed if math.isfinite(parsed) else None


def detect_delimiter(path: Path) -> str:
    sample = path.read_text(encoding="utf-8-sig", errors="replace")[:8192]
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t").delimiter
    except csv.Error:
        return ";" if sample.count(";") > sample.count(",") else ","


def parse_month_from_filename(path: Path) -> tuple[int, int]:
    match = re.match(r"^Energiebilanz_(\d{4})_(\d{2})\.csv$", path.name, re.IGNORECASE)
    if not match:
        raise ValueError(f"not an SMA monthly energy-balance file: {path.name}")
    return int(match.group(1)), int(match.group(2))


def find_header_indices(headers: list[str]) -> dict[str, int]:
    normalized = [normalize_header(header) for header in headers]
    indices: dict[str, int] = {}
    for field, aliases in FIELD_ALIASES.items():
        for alias in aliases:
            if alias in normalized:
                indices[field] = normalized.index(alias)
                break
    required = ["home_wh", "grid_import_wh", "pv_wh", "grid_export_wh"]
    missing = [field for field in required if field not in indices]
    if missing:
        raise ValueError(f"missing required SMA energy-balance columns: {', '.join(missing)}")
    return indices


def parse_monthly_file(path: Path) -> list[EnergyBalanceRow]:
    year, month = parse_month_from_filename(path)
    delimiter = detect_delimiter(path)
    rows: list[EnergyBalanceRow] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle, delimiter=delimiter)
        try:
            headers = next(reader)
        except StopIteration:
            return []
        indices = find_header_indices(headers)
        for row_number, row in enumerate(reader, start=2):
            if not row or not cleanup_cell(row[0]):
                continue
            day = parse_day(row[0], year, month, f"{path.name} row {row_number}")
            values: dict[str, float | None] = {}
            for field, index in indices.items():
                raw_value = row[index] if index < len(row) else None
                value_kwh = parse_float(raw_value, f"{path.name} row {row_number} {field}")
                values[field] = value_kwh * 1000.0 if value_kwh is not None else None
            rows.append(EnergyBalanceRow(day=day, **values))
    return rows


def read_energy_balance_dir(input_dir: Path) -> list[EnergyBalanceRow]:
    files = sorted(input_dir.glob("Energiebilanz_[0-9][0-9][0-9][0-9]_[0-9][0-9].csv"))
    if not files:
        raise SystemExit(f"No SMA monthly energy-balance files found in {input_dir}")
    rows: list[EnergyBalanceRow] = []
    for path in files:
        rows.extend(parse_monthly_file(path))
    return rows


def parse_date(value: str, field: str) -> dt.date:
    try:
        return dt.date.fromisoformat(value[:10])
    except Exception as exc:
        raise SystemExit(f"invalid {field}: {value!r}; expected YYYY-MM-DD") from exc


def timestamp_for_day(day: dt.date, tz: ZoneInfo) -> int:
    local = dt.datetime.combine(day, dt.time.min, tzinfo=tz)
    return int(local.timestamp() * 1000)


def escape_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def line(metric: str, labels: dict[str, str], samples: list[tuple[int, float]]) -> str:
    label_text = "".join(f',"{key}":"{escape_label(value)}"' for key, value in sorted(labels.items()))
    return json.dumps({
        "metric": {"__name__": metric, **labels},
        "timestamps": [ts for ts, _ in samples],
        "values": [value for _, value in samples],
    }, separators=(",", ":"), ensure_ascii=False)


def append_sample(series: dict[tuple[str, tuple[tuple[str, str], ...]], list[tuple[int, float]]], metric: str, labels: dict[str, str], ts: int, value: float) -> None:
    if value <= 0:
        return
    key = (metric, tuple(sorted(labels.items())))
    series.setdefault(key, []).append((ts, float(value)))


def build_series(rows: list[EnergyBalanceRow], tz: ZoneInfo, start_day: dt.date | None, end_day: dt.date | None, source_label: str) -> tuple[dict[tuple[str, tuple[tuple[str, str], ...]], list[tuple[int, float]]], dict[str, Any]]:
    grouped: dict[dt.date, dict[str, float]] = {}
    for row in rows:
        if start_day and row.day < start_day:
            continue
        if end_day and row.day >= end_day:
            continue
        day_values = grouped.setdefault(row.day, {})
        for field in TARGET_METRICS:
            value = getattr(row, field)
            if value is None:
                continue
            if value < 0:
                raise SystemExit(f"Negative SMA energy-balance value is not supported: {row.day} {field}={value}")
            day_values[field] = day_values.get(field, 0.0) + value

    series: dict[tuple[str, tuple[tuple[str, str], ...]], list[tuple[int, float]]] = {}
    totals = {field: 0.0 for field in TARGET_METRICS}
    first_day: dt.date | None = None
    last_day: dt.date | None = None
    for day, values in sorted(grouped.items()):
        labels = {
            "source": source_label,
            "local_year": f"{day.year:04d}",
            "local_month": f"{day.month:02d}",
        }
        ts = timestamp_for_day(day, tz)
        for field, metric in TARGET_METRICS.items():
            value = values.get(field)
            if value is None:
                continue
            append_sample(series, metric, labels, ts, value)
            totals[field] += value
        first_day = day if first_day is None else min(first_day, day)
        last_day = day if last_day is None else max(last_day, day)

    summary = {
        "source": source_label,
        "series": len(series),
        "samples": sum(len(samples) for samples in series.values()),
        "days": len(grouped),
        "first_day": first_day.isoformat() if first_day else None,
        "last_day": last_day.isoformat() if last_day else None,
        "totals_kwh": {field: round(value / 1000.0, 6) for field, value in totals.items() if value > 0},
    }
    return series, summary


def post_bytes(url: str, data: bytes, timeout: int = 120) -> None:
    request = urllib.request.Request(url, data=data, method="POST", headers={"Content-Type": "application/jsonl"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response.read()
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} for {url}: {body}") from exc


def delete_source_series(base_url: str, metric: str, source_label: str) -> None:
    selector = f'{metric}{{source="{escape_label(source_label)}"}}'
    params = urllib.parse.urlencode({"match[]": selector})
    url = f"{base_url.rstrip('/')}/api/v1/admin/tsdb/delete_series?{params}"
    request = urllib.request.Request(url, data=b"", method="POST")
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            response.read()
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} while deleting {selector}: {body}") from exc


def import_series(base_url: str, series: dict[tuple[str, tuple[tuple[str, str], ...]], list[tuple[int, float]]], batch_size: int) -> int:
    batch: list[str] = []
    batches = 0
    for metric, label_items in sorted(series):
        samples = series[(metric, label_items)]
        batch.append(line(metric, dict(label_items), sorted(samples)))
        if len(batch) >= batch_size:
            post_bytes(f"{base_url.rstrip('/')}/api/v1/import", ("\n".join(batch) + "\n").encode("utf-8"))
            batches += 1
            batch = []
    if batch:
        post_bytes(f"{base_url.rstrip('/')}/api/v1/import", ("\n".join(batch) + "\n").encode("utf-8"))
        batches += 1
    return batches


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import SMA energy-balance daily exports as EVCC-compatible daily rollups")
    parser.add_argument("--vm-base-url", default="http://127.0.0.1:8428")
    parser.add_argument("--input-dir", required=True, help="Directory containing Energiebilanz_YYYY_MM.csv files")
    parser.add_argument("--timezone", default="Europe/Berlin")
    parser.add_argument("--start", help="first local day, YYYY-MM-DD")
    parser.add_argument("--end", help="exclusive local end day, YYYY-MM-DD")
    parser.add_argument("--source-label", default=SOURCE_LABEL, help="source label for generated EVCC-compatible metrics")
    parser.add_argument("--replace", action="store_true", help="delete existing generated source series before writing")
    parser.add_argument("--write", action="store_true", help="write imported metrics to VictoriaMetrics")
    parser.add_argument("--batch-size", type=int, default=200)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    started = time.perf_counter()
    log(f"import-sma-energy-balance.py v{SCRIPT_VERSION} (last modified {SCRIPT_LAST_MODIFIED})")
    input_dir = Path(args.input_dir)
    if not input_dir.exists():
        raise SystemExit(f"SMA energy-balance input directory not found: {input_dir}")
    tz = ZoneInfo(args.timezone)
    start_day = parse_date(args.start, "--start") if args.start else None
    end_day = parse_date(args.end, "--end") if args.end else None
    if start_day and end_day and end_day <= start_day:
        raise SystemExit("--end must be after --start")
    rows = read_energy_balance_dir(input_dir)
    if not rows:
        raise SystemExit(f"No SMA energy-balance rows found in {input_dir}")
    series, summary = build_series(rows, tz, start_day, end_day, args.source_label)
    log(json.dumps(summary, indent=2, ensure_ascii=False))
    if args.write:
        if args.replace:
            for metric in sorted(set(TARGET_METRICS.values())):
                log(f"Delete existing generated source series: {metric}{{source=\"{args.source_label}\"}}")
                delete_source_series(args.vm_base_url, metric, args.source_label)
        batches = import_series(args.vm_base_url, series, args.batch_size)
        log(f"Imported batches: {batches}")
    else:
        log("Dry run only. Re-run with --write to import metrics.")
    log(f"Finished in {time.perf_counter() - started:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
