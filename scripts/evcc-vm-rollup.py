#!/usr/bin/env python3
"""Safe planning, benchmarking and test backfill helpers for EVCC rollups."""

from __future__ import annotations

import argparse
import configparser
import json
import math
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, time as dt_time, timedelta, timezone
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class Settings:
    base_url: str
    db_label: str
    host_label: str
    timezone: str
    metric_prefix: str
    raw_sample_step: str
    price_bucket_minutes: int
    price_rollup_mode: str
    benchmark_start: str
    benchmark_end: str
    benchmark_step: str


@dataclass(frozen=True)
class RollupMetric:
    key: str
    record: str
    expr: str
    description: str
    phase: str
    implemented: bool
    group_labels: tuple[str, ...]


@dataclass(frozen=True)
class DayWindow:
    day: str
    start_iso: str
    end_iso: str
    sample_timestamp_ms: int


@dataclass(frozen=True)
class ImportResponse:
    status_code: int
    body: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plan, benchmark and backfill VictoriaMetrics rollups for EVCC safely."
    )
    parser.add_argument(
        "--config",
        required=True,
        help="Path to the INI configuration file.",
    )
    parser.add_argument(
        "command",
        choices=["detect", "plan", "render-vmalert-rules", "benchmark", "backfill-test"],
        help="Action to perform.",
    )
    parser.add_argument(
        "--start-day",
        help="Local day in YYYY-MM-DD format for backfill-test.",
    )
    parser.add_argument(
        "--end-day",
        help="Local day in YYYY-MM-DD format for backfill-test.",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Actually write the generated test rollups to VictoriaMetrics.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=200,
        help="Number of time series per import batch during backfill-test.",
    )
    parser.add_argument(
        "--chunk-by",
        choices=["all", "month"],
        default="month",
        help="Flush generated rollups per month or only once at the end.",
    )
    parser.add_argument(
        "--progress",
        action="store_true",
        help="Print chunk progress to stderr while backfill-test is running.",
    )
    return parser.parse_args()


def load_settings(path: str) -> Settings:
    parser = configparser.ConfigParser()
    with open(path, "r", encoding="utf-8") as handle:
        parser.read_file(handle)

    return Settings(
        base_url=parser.get("victoriametrics", "base_url").rstrip("/"),
        db_label=parser.get("victoriametrics", "db_label"),
        host_label=parser.get("victoriametrics", "host_label", fallback=""),
        timezone=parser.get("victoriametrics", "timezone"),
        metric_prefix=parser.get("victoriametrics", "metric_prefix"),
        raw_sample_step=parser.get("victoriametrics", "raw_sample_step", fallback="30s"),
        price_bucket_minutes=parser.getint("victoriametrics", "price_bucket_minutes", fallback=15),
        price_rollup_mode=parser.get("victoriametrics", "price_rollup_mode", fallback="sampled"),
        benchmark_start=parser.get("benchmark", "start"),
        benchmark_end=parser.get("benchmark", "end"),
        benchmark_step=parser.get("benchmark", "step"),
    )


def http_get_json(settings: Settings, path: str, params: dict[str, str | list[str]] | None = None) -> dict:
    url = settings.base_url + path
    if params:
        url = url + "?" + urllib.parse.urlencode(params, doseq=True)
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} for {url}: {body}") from exc


def http_post_bytes(
    settings: Settings,
    path: str,
    payload: bytes,
    content_type: str = "application/x-ndjson",
) -> ImportResponse:
    request = urllib.request.Request(
        settings.base_url + path,
        data=payload,
        method="POST",
        headers={"Content-Type": content_type},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return ImportResponse(
            status_code=response.getcode(),
            body=response.read().decode("utf-8", errors="replace"),
        )


def quote_label(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def base_matchers(settings: Settings) -> str:
    return f'db={quote_label(settings.db_label)}'


def record_name(settings: Settings, suffix: str) -> str:
    return f"{settings.metric_prefix}_{suffix}"


def series_match(settings: Settings, metric_name: str) -> str:
    return f'{metric_name}' + "{" + base_matchers(settings) + "}"


def collect_label_values(series: list[dict], label_name: str) -> list[str]:
    values = sorted(
        {
            metric.get(label_name, "")
            for metric in series
            if metric.get(label_name, "")
        }
    )
    return values


def detect_dimensions(settings: Settings) -> dict[str, list[str]]:
    time_window = {
        "start": settings.benchmark_start,
        "end": settings.benchmark_end,
    }
    charge_series = http_get_json(
        settings,
        "/api/v1/series",
        {
            "match[]": [series_match(settings, "chargePower_value")],
            **time_window,
        },
    ).get("data", [])
    ext_series = http_get_json(
        settings,
        "/api/v1/series",
        {
            "match[]": [series_match(settings, "extPower_value")],
            **time_window,
        },
    ).get("data", [])
    aux_series = http_get_json(
        settings,
        "/api/v1/series",
        {
            "match[]": [series_match(settings, "auxPower_value")],
            **time_window,
        },
    ).get("data", [])

    return {
        "loadpoints": collect_label_values(charge_series, "loadpoint"),
        "vehicles": collect_label_values(charge_series, "vehicle"),
        "ext_titles": collect_label_values(ext_series, "title"),
        "aux_titles": collect_label_values(aux_series, "title"),
    }


def build_catalog(settings: Settings) -> list[RollupMetric]:
    root = base_matchers(settings)
    root_no_id = root + ',id=""'
    return [
        RollupMetric(
            key="pv_daily_energy",
            record=record_name(settings, "pv_energy_daily_wh"),
            expr=f"sum(integrate(pvPower_value{{{root_no_id}}}[1d])) / 3600",
            description="PV daily energy from raw power values.",
            phase="phase-1",
            implemented=True,
            group_labels=(),
        ),
        RollupMetric(
            key="home_daily_energy",
            record=record_name(settings, "home_energy_daily_wh"),
            expr=f"sum(integrate(homePower_value{{{root}}}[1d])) / 3600",
            description="Home daily energy from raw power values.",
            phase="phase-1",
            implemented=True,
            group_labels=(),
        ),
        RollupMetric(
            key="loadpoint_daily_energy",
            record=record_name(settings, "loadpoint_energy_daily_wh"),
            expr=f"sum(integrate(chargePower_value{{{root}}}[1d])) by (loadpoint) / 3600",
            description="Per-loadpoint daily charging energy.",
            phase="phase-1",
            implemented=True,
            group_labels=("loadpoint",),
        ),
        RollupMetric(
            key="vehicle_daily_energy",
            record=record_name(settings, "vehicle_energy_daily_wh"),
            expr=f"sum(integrate(chargePower_value{{{root}}}[1d])) by (vehicle) / 3600",
            description="Per-vehicle daily charging energy.",
            phase="phase-1",
            implemented=True,
            group_labels=("vehicle",),
        ),
        RollupMetric(
            key="vehicle_daily_distance",
            record=record_name(settings, "vehicle_distance_daily_km"),
            expr=(
                f"max(max_over_time((vehicleOdometer_value{{{root}}} > 0)[1d])) by (vehicle) "
                f"- max(max_over_time((vehicleOdometer_value{{{root}}} > 0)[1d] offset 1d)) by (vehicle)"
            ),
            description="Per-vehicle daily driven distance from odometer spread.",
            phase="phase-1",
            implemented=True,
            group_labels=("vehicle",),
        ),
        RollupMetric(
            key="ext_daily_energy",
            record=record_name(settings, "ext_energy_daily_wh"),
            expr=f"sum(integrate(extPower_value{{{root}}}[1d])) by (title) / 3600",
            description="Per-ext-title daily energy.",
            phase="phase-1",
            implemented=True,
            group_labels=("title",),
        ),
        RollupMetric(
            key="aux_daily_energy",
            record=record_name(settings, "aux_energy_daily_wh"),
            expr=f"sum(integrate(auxPower_value{{{root}}}[1d])) by (title) / 3600",
            description="Per-aux-title daily energy.",
            phase="phase-1",
            implemented=True,
            group_labels=("title",),
        ),
        RollupMetric(
            key="battery_soc_daily_min",
            record=record_name(settings, "battery_soc_daily_min_pct"),
            expr=f"min(min_over_time(batterySoc_value{{{root_no_id}}}[1d]))",
            description="Minimum battery state of charge per day.",
            phase="phase-1",
            implemented=True,
            group_labels=(),
        ),
        RollupMetric(
            key="battery_soc_daily_max",
            record=record_name(settings, "battery_soc_daily_max_pct"),
            expr=f"max(max_over_time(batterySoc_value{{{root_no_id}}}[1d]))",
            description="Maximum battery state of charge per day.",
            phase="phase-1",
            implemented=True,
            group_labels=(),
        ),
        RollupMetric(
            key="grid_import_daily_energy",
            record=record_name(settings, "grid_import_daily_wh"),
            expr="deferred",
            description="Deferred: sign-aware grid import split needs a dedicated phase-2 design.",
            phase="phase-2",
            implemented=False,
            group_labels=(),
        ),
        RollupMetric(
            key="grid_export_daily_energy",
            record=record_name(settings, "grid_export_daily_wh"),
            expr="deferred",
            description="Deferred: sign-aware grid export split needs a dedicated phase-2 design.",
            phase="phase-2",
            implemented=False,
            group_labels=(),
        ),
        RollupMetric(
            key="battery_charge_daily_energy",
            record=record_name(settings, "battery_charge_daily_wh"),
            expr="deferred",
            description="Deferred: sign-aware battery charge split needs a dedicated phase-2 design.",
            phase="phase-2",
            implemented=False,
            group_labels=(),
        ),
        RollupMetric(
            key="battery_discharge_daily_energy",
            record=record_name(settings, "battery_discharge_daily_wh"),
            expr="deferred",
            description="Deferred: sign-aware battery discharge split needs a dedicated phase-2 design.",
            phase="phase-2",
            implemented=False,
            group_labels=(),
        ),
        RollupMetric(
            key="grid_import_cost_daily",
            record=record_name(settings, "grid_import_cost_daily_eur"),
            expr="python: 15m raw grid import cost calculation",
            description="Daily grid import cost from 15-minute raw import energy weighted by matching tariff.",
            phase="phase-2",
            implemented=True,
            group_labels=(),
        ),
        RollupMetric(
            key="grid_import_price_avg_daily",
            record=record_name(settings, "grid_import_price_avg_daily_ct_per_kwh"),
            expr="python: 15m raw arithmetic daily import price mean",
            description="Arithmetic daily mean of quarter-hour import tariffs.",
            phase="phase-2",
            implemented=True,
            group_labels=(),
        ),
        RollupMetric(
            key="grid_import_price_effective_daily",
            record=record_name(settings, "grid_import_price_effective_daily_ct_per_kwh"),
            expr="python: 15m raw effective import price weighted by quarter-hour grid import",
            description="Effective daily import price weighted by quarter-hour grid import energy.",
            phase="phase-2",
            implemented=True,
            group_labels=(),
        ),
        RollupMetric(
            key="grid_import_price_min_daily",
            record=record_name(settings, "grid_import_price_min_daily_ct_per_kwh"),
            expr="python: 15m raw daily minimum import tariff",
            description="Minimum quarter-hour import tariff of the day.",
            phase="phase-2",
            implemented=True,
            group_labels=(),
        ),
        RollupMetric(
            key="grid_import_price_max_daily",
            record=record_name(settings, "grid_import_price_max_daily_ct_per_kwh"),
            expr="python: 15m raw daily maximum import tariff",
            description="Maximum quarter-hour import tariff of the day.",
            phase="phase-2",
            implemented=True,
            group_labels=(),
        ),
        RollupMetric(
            key="pricing_rollups",
            record=record_name(settings, "energy_purchased_daily_eur"),
            expr="deferred",
            description="Deferred: tariff and finance rollups belong to phase 2.",
            phase="phase-2",
            implemented=False,
            group_labels=(),
        ),
    ]


def parse_local_day(text: str, arg_name: str) -> date:
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise SystemExit(f"Invalid {arg_name} '{text}'. Expected YYYY-MM-DD.") from exc


def to_iso_z(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_day_windows(settings: Settings, start_day: date, end_day: date) -> list[DayWindow]:
    if end_day < start_day:
        raise SystemExit("--end-day must not be earlier than --start-day.")

    tz = ZoneInfo(settings.timezone)
    windows: list[DayWindow] = []
    current = start_day
    while current <= end_day:
        start_local = datetime.combine(current, dt_time.min, tzinfo=tz)
        end_local = start_local + timedelta(days=1)
        start_utc = start_local.astimezone(timezone.utc)
        end_utc = end_local.astimezone(timezone.utc)
        windows.append(
            DayWindow(
                day=current.isoformat(),
                start_iso=to_iso_z(start_utc),
                end_iso=to_iso_z(end_utc),
                sample_timestamp_ms=int(start_utc.timestamp() * 1000),
            )
        )
        current += timedelta(days=1)
    return windows


def chunk_label(window: DayWindow, chunk_by: str) -> str:
    if chunk_by == "month":
        return window.day[:7]
    return "all"


def build_window_chunks(windows: list[DayWindow], chunk_by: str) -> list[tuple[str, list[DayWindow]]]:
    chunks: list[tuple[str, list[DayWindow]]] = []
    current_label = ""
    current_windows: list[DayWindow] = []

    for window in windows:
        label = chunk_label(window, chunk_by)
        if not current_windows:
            current_label = label
            current_windows = [window]
            continue
        if label != current_label:
            chunks.append((current_label, current_windows))
            current_label = label
            current_windows = [window]
            continue
        current_windows.append(window)

    if current_windows:
        chunks.append((current_label, current_windows))
    return chunks


def print_detect(settings: Settings) -> int:
    detection = detect_dimensions(settings)
    print(json.dumps(detection, indent=2, ensure_ascii=True))
    return 0


def print_plan(settings: Settings) -> int:
    detection = detect_dimensions(settings)
    catalog = build_catalog(settings)
    output = {
        "namespace": settings.metric_prefix,
        "timezone": settings.timezone,
        "detection": detection,
        "implemented": [
            {
                "key": item.key,
                "record": item.record,
                "description": item.description,
                "expr": item.expr,
                "group_labels": list(item.group_labels),
            }
            for item in catalog
            if item.implemented
        ],
        "deferred": [
            {
                "key": item.key,
                "record": item.record,
                "description": item.description,
            }
            for item in catalog
            if not item.implemented
        ],
    }
    print(json.dumps(output, indent=2, ensure_ascii=True))
    return 0


def render_vmalert_rules(settings: Settings) -> int:
    catalog = [
        item
        for item in build_catalog(settings)
        if item.implemented and not item.expr.startswith("python:")
    ]
    lines = [
        "groups:",
        "  - name: evcc_vm_rollups_daily_test",
        "    interval: 1d",
        "    rules:",
    ]
    for item in catalog:
        lines.extend(
            [
                f"      - record: {item.record}",
                f"        expr: {item.expr}",
                f"        labels:",
                f'          db: "{settings.db_label}"',
                f'          rollup_source: "raw"',
                f'          rollup_phase: "{item.phase}"',
            ]
        )
    sys.stdout.write("\n".join(lines) + "\n")
    return 0


def benchmark_query(settings: Settings, item: RollupMetric) -> dict:
    if item.expr.startswith("python:"):
        return {
            "key": item.key,
            "record": item.record,
            "elapsed_ms": None,
            "series": None,
            "status": "python-rollup",
        }
    params = {
        "query": item.expr,
        "start": settings.benchmark_start,
        "end": settings.benchmark_end,
        "step": settings.benchmark_step,
        "nocache": "1",
    }
    started = time.perf_counter()
    response = http_get_json(settings, "/api/v1/query_range", params)
    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    series = len(response.get("data", {}).get("result", []))
    return {
        "key": item.key,
        "record": item.record,
        "elapsed_ms": elapsed_ms,
        "series": series,
        "status": response.get("status", "unknown"),
    }


def run_benchmark(settings: Settings) -> int:
    catalog = [item for item in build_catalog(settings) if item.implemented]
    results = [benchmark_query(settings, item) for item in catalog]
    print(
        json.dumps(
            {
                "range": {
                    "start": settings.benchmark_start,
                    "end": settings.benchmark_end,
                    "step": settings.benchmark_step,
                },
                "results": results,
            },
            indent=2,
            ensure_ascii=True,
        )
    )
    return 0


def fetch_rollup_vector(settings: Settings, item: RollupMetric, window: DayWindow) -> list[dict]:
    response = http_get_json(
        settings,
        "/api/v1/query",
        {
            "query": item.expr,
            "time": window.end_iso,
            "nocache": "1",
        },
    )
    return response.get("data", {}).get("result", [])


def fetch_vehicle_odometer_vector(settings: Settings, window: DayWindow) -> list[dict]:
    response = http_get_json(
        settings,
        "/api/v1/query",
        {
            "query": f"max(max_over_time((vehicleOdometer_value{{{base_matchers(settings)}}} > 0)[1d])) by (vehicle)",
            "time": window.end_iso,
            "nocache": "1",
        },
    )
    return response.get("data", {}).get("result", [])


def matrix_values(result_item: dict) -> list[float]:
    values: list[float] = []
    for row in result_item.get("values", []):
        if not isinstance(row, list) or len(row) != 2:
            continue
        try:
            numeric = float(row[1])
        except (TypeError, ValueError):
            continue
        if math.isfinite(numeric):
            values.append(numeric)
    return values


def fetch_battery_soc_extrema(settings: Settings, window: DayWindow) -> tuple[float | None, float | None]:
    response = http_get_json(
        settings,
        "/api/v1/query_range",
        {
            "query": f"batterySoc_value{{{base_matchers(settings)}}}",
            "start": window.start_iso,
            "end": window.end_iso,
            "step": "10m",
            "nocache": "1",
        },
    )
    series = response.get("data", {}).get("result", [])
    all_values: list[float] = []
    for result_item in series:
        all_values.extend(matrix_values(result_item))
    positive_values = [value for value in all_values if value > 0]
    if not positive_values:
        return None, None
    return min(positive_values), max(positive_values)


def fetch_single_series_range(
    settings: Settings,
    query: str,
    start_iso: str,
    end_iso: str,
    step: str,
) -> list[tuple[int, float]]:
    response = http_get_json(
        settings,
        "/api/v1/query_range",
        {
            "query": query,
            "start": start_iso,
            "end": end_iso,
            "step": step,
            "nocache": "1",
        },
    )
    series = response.get("data", {}).get("result", [])
    if not series:
        return []
    samples: list[tuple[int, float]] = []
    for row in series[0].get("values", []):
        if not isinstance(row, list) or len(row) != 2:
            continue
        try:
            timestamp = int(row[0])
            value = float(row[1])
        except (TypeError, ValueError):
            continue
        if math.isfinite(value):
            samples.append((timestamp, value))
    return samples


def parse_step_seconds(step: str) -> int:
    if step.endswith("s"):
        return int(step[:-1])
    if step.endswith("m"):
        return int(step[:-1]) * 60
    if step.endswith("h"):
        return int(step[:-1]) * 3600
    raise ValueError(f"Unsupported step format: {step}")


def bucket_start_timestamps(window: DayWindow, bucket_minutes: int) -> list[int]:
    start_ts = int(datetime.fromisoformat(window.start_iso.replace("Z", "+00:00")).timestamp())
    end_ts = int(datetime.fromisoformat(window.end_iso.replace("Z", "+00:00")).timestamp())
    bucket_seconds = bucket_minutes * 60
    return list(range(start_ts, end_ts, bucket_seconds))


def bucket_end_timestamps(window: DayWindow, bucket_minutes: int) -> list[int]:
    bucket_seconds = bucket_minutes * 60
    return [timestamp + bucket_seconds for timestamp in bucket_start_timestamps(window, bucket_minutes)]


def quarter_hour_price_rollups(
    grid_samples: list[tuple[int, float]],
    tariff_samples: list[tuple[int, float]],
    bucket_starts: list[int],
    raw_step_seconds: int,
    bucket_minutes: int,
) -> dict[str, float | None]:
    bucket_seconds = bucket_minutes * 60
    bucket_prices: list[float] = []
    day_tariff_values: list[float] = []
    total_import_kwh = 0.0
    total_import_cost_eur = 0.0
    last_price: float | None = None

    grid_index = 0
    tariff_index = 0
    day_start = bucket_starts[0] if bucket_starts else 0
    day_end = (bucket_starts[-1] + bucket_seconds) if bucket_starts else 0

    for timestamp, value in tariff_samples:
        if day_start <= timestamp < day_end:
            day_tariff_values.append(value)

    for bucket_start in bucket_starts:
        bucket_end = bucket_start + bucket_seconds

        while tariff_index < len(tariff_samples) and tariff_samples[tariff_index][0] < bucket_start:
            last_price = tariff_samples[tariff_index][1]
            tariff_index += 1

        bucket_price = last_price
        scan_index = tariff_index
        while scan_index < len(tariff_samples):
            timestamp, value = tariff_samples[scan_index]
            if timestamp >= bucket_end:
                break
            if timestamp >= bucket_start:
                bucket_price = value
            scan_index += 1
        tariff_index = scan_index

        if bucket_price is not None:
            last_price = bucket_price
            bucket_prices.append(bucket_price)

        while grid_index < len(grid_samples) and grid_samples[grid_index][0] < bucket_start:
            grid_index += 1
        scan_index = grid_index
        bucket_import_kwh = 0.0
        while scan_index < len(grid_samples):
            timestamp, value = grid_samples[scan_index]
            if timestamp >= bucket_end:
                break
            if timestamp >= bucket_start and value > 0:
                bucket_import_kwh += value * raw_step_seconds / 3600000
            scan_index += 1
        grid_index = scan_index

        if bucket_price is not None and bucket_import_kwh > 0:
            total_import_kwh += bucket_import_kwh
            total_import_cost_eur += bucket_import_kwh * bucket_price

    if not day_tariff_values:
        day_tariff_values = bucket_prices

    arithmetic_avg = (sum(day_tariff_values) / len(day_tariff_values) * 100) if day_tariff_values else None
    minimum_price = (min(day_tariff_values) * 100) if day_tariff_values else None
    maximum_price = (max(day_tariff_values) * 100) if day_tariff_values else None
    effective_price = (
        total_import_cost_eur / total_import_kwh * 100
        if total_import_kwh > 0
        else None
    )

    return {
        "grid_import_cost_daily": total_import_cost_eur,
        "grid_import_price_avg_daily": arithmetic_avg,
        "grid_import_price_effective_daily": effective_price,
        "grid_import_price_min_daily": minimum_price,
        "grid_import_price_max_daily": maximum_price,
    }


def bucket_price_rollups(
    bucket_import_samples: list[tuple[int, float]],
    tariff_samples: list[tuple[int, float]],
    bucket_starts: list[int],
    bucket_minutes: int,
) -> dict[str, float | None]:
    bucket_seconds = bucket_minutes * 60
    bucket_prices: list[float] = []
    day_tariff_values: list[float] = []
    total_import_kwh = 0.0
    total_import_cost_eur = 0.0
    last_price: float | None = None

    bucket_import_map = {timestamp: value for timestamp, value in bucket_import_samples}
    day_start = bucket_starts[0] if bucket_starts else 0
    day_end = (bucket_starts[-1] + bucket_seconds) if bucket_starts else 0

    for timestamp, value in tariff_samples:
        if day_start <= timestamp < day_end:
            day_tariff_values.append(value)

    tariff_index = 0
    for bucket_start in bucket_starts:
        bucket_end = bucket_start + bucket_seconds

        while tariff_index < len(tariff_samples) and tariff_samples[tariff_index][0] < bucket_start:
            last_price = tariff_samples[tariff_index][1]
            tariff_index += 1

        bucket_price = last_price
        scan_index = tariff_index
        while scan_index < len(tariff_samples):
            timestamp, value = tariff_samples[scan_index]
            if timestamp >= bucket_end:
                break
            if timestamp >= bucket_start:
                bucket_price = value
            scan_index += 1
        tariff_index = scan_index

        if bucket_price is not None:
            last_price = bucket_price
            bucket_prices.append(bucket_price)

        bucket_import_kwh = max(bucket_import_map.get(bucket_end, 0.0), 0.0)
        if bucket_price is not None and bucket_import_kwh > 0:
            total_import_kwh += bucket_import_kwh
            total_import_cost_eur += bucket_import_kwh * bucket_price

    if not day_tariff_values:
        day_tariff_values = bucket_prices

    arithmetic_avg = (sum(day_tariff_values) / len(day_tariff_values) * 100) if day_tariff_values else None
    minimum_price = (min(day_tariff_values) * 100) if day_tariff_values else None
    maximum_price = (max(day_tariff_values) * 100) if day_tariff_values else None
    effective_price = (
        total_import_cost_eur / total_import_kwh * 100
        if total_import_kwh > 0
        else None
    )

    return {
        "grid_import_cost_daily": total_import_cost_eur,
        "grid_import_price_avg_daily": arithmetic_avg,
        "grid_import_price_effective_daily": effective_price,
        "grid_import_price_min_daily": minimum_price,
        "grid_import_price_max_daily": maximum_price,
    }


def fetch_grid_price_rollups(settings: Settings, window: DayWindow) -> dict[str, float | None]:
    raw_step_seconds = parse_step_seconds(settings.raw_sample_step)
    start_dt = datetime.fromisoformat(window.start_iso.replace("Z", "+00:00"))
    extended_start_iso = to_iso_z(start_dt - timedelta(minutes=settings.price_bucket_minutes))
    tariff_samples = fetch_single_series_range(
        settings,
        f'avg without(host) (tariffGrid_value{{{base_matchers(settings)}}})',
        extended_start_iso,
        window.end_iso,
        settings.raw_sample_step,
    )
    bucket_starts = bucket_start_timestamps(window, settings.price_bucket_minutes)

    if settings.price_rollup_mode == "clamp":
        bucket_step = f'{settings.price_bucket_minutes}m'
        bucket_end_set = set(bucket_end_timestamps(window, settings.price_bucket_minutes))
        first_bucket_end_iso = to_iso_z(start_dt + timedelta(minutes=settings.price_bucket_minutes))
        bucket_import_samples = fetch_single_series_range(
            settings,
            (
                f'sum without(host) '
                f'(integrate(clamp_min(gridPower_value{{{base_matchers(settings)}}}, 0)'
                f'[{settings.price_bucket_minutes}m])) / 3600000'
            ),
            first_bucket_end_iso,
            window.end_iso,
            bucket_step,
        )
        return bucket_price_rollups(
            bucket_import_samples=[
                (timestamp, value)
                for timestamp, value in bucket_import_samples
                if timestamp in bucket_end_set
            ],
            tariff_samples=tariff_samples,
            bucket_starts=bucket_starts,
            bucket_minutes=settings.price_bucket_minutes,
        )

    grid_samples = fetch_single_series_range(
        settings,
        f'avg_over_time(avg without(host) (gridPower_value{{{base_matchers(settings)}}})[{settings.raw_sample_step}])',
        window.start_iso,
        window.end_iso,
        settings.raw_sample_step,
    )
    return quarter_hour_price_rollups(
        grid_samples=grid_samples,
        tariff_samples=tariff_samples,
        bucket_starts=bucket_starts,
        raw_step_seconds=raw_step_seconds,
        bucket_minutes=settings.price_bucket_minutes,
    )


def normalize_rollup_labels(settings: Settings, item: RollupMetric, metric: dict) -> dict[str, str]:
    labels: dict[str, str] = {
        "__name__": item.record,
        "db": settings.db_label,
    }
    for label in item.group_labels:
        value = str(metric.get(label, "")).strip()
        if value:
            labels[label] = value
    return labels


def sample_value(result_item: dict) -> float | None:
    raw_value = result_item.get("value", [None, None])
    if not isinstance(raw_value, list) or len(raw_value) != 2:
        return None
    try:
        numeric = float(raw_value[1])
    except (TypeError, ValueError):
        return None
    if not math.isfinite(numeric):
        return None
    return numeric


def append_series_sample(
    series_map: dict[tuple[tuple[str, str], ...], dict],
    labels: dict[str, str],
    timestamp_ms: int,
    value: float,
) -> None:
    key = tuple(sorted(labels.items()))
    bucket = series_map.setdefault(
        key,
        {
            "metric": labels,
            "values": [],
            "timestamps": [],
        },
    )
    bucket["values"].append(value)
    bucket["timestamps"].append(timestamp_ms)


def chunked(items: list[dict], size: int) -> list[list[dict]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def serialize_import_jsonl(series_rows: list[dict]) -> bytes:
    lines = [json.dumps(row, separators=(",", ":"), ensure_ascii=True) for row in series_rows]
    return ("\n".join(lines) + ("\n" if lines else "")).encode("utf-8")


def backfill_test(settings: Settings, args: argparse.Namespace) -> int:
    if not args.start_day or not args.end_day:
        raise SystemExit("backfill-test requires --start-day and --end-day.")
    if args.batch_size < 1:
        raise SystemExit("--batch-size must be at least 1.")

    start_day = parse_local_day(args.start_day, "--start-day")
    end_day = parse_local_day(args.end_day, "--end-day")
    windows = build_day_windows(settings, start_day, end_day)
    chunks = build_window_chunks(windows, args.chunk_by)
    catalog = [item for item in build_catalog(settings) if item.implemented]

    previous_vehicle_odometer: dict[str, float] = {}
    seen_series_keys: set[tuple[tuple[str, str], ...]] = set()
    import_results = []
    chunk_summaries = []
    skipped = 0
    emitted_samples = 0
    total_batches = 0
    processed_days = 0
    price_metric_keys = {
        "grid_import_cost_daily",
        "grid_import_price_avg_daily",
        "grid_import_price_effective_daily",
        "grid_import_price_min_daily",
        "grid_import_price_max_daily",
    }

    for chunk_index, (chunk_name, chunk_windows) in enumerate(chunks, start=1):
        series_map: dict[tuple[tuple[str, str], ...], dict] = {}
        chunk_start_samples = emitted_samples
        chunk_start_skipped = skipped

        if args.progress:
            print(
                f"[chunk {chunk_index}/{len(chunks)}] start {chunk_name} days={len(chunk_windows)}",
                file=sys.stderr,
                flush=True,
            )

        for window in chunk_windows:
            processed_days += 1
            price_rollups: dict[str, float | None] | None = None
            for item in catalog:
                if item.key == "vehicle_daily_distance":
                    for result_item in fetch_vehicle_odometer_vector(settings, window):
                        value = sample_value(result_item)
                        if value is None:
                            skipped += 1
                            continue
                        vehicle = str(result_item.get("metric", {}).get("vehicle", "")).strip()
                        if not vehicle:
                            skipped += 1
                            continue
                        previous_value = previous_vehicle_odometer.get(vehicle)
                        previous_vehicle_odometer[vehicle] = value
                        if previous_value is None:
                            continue
                        delta = value - previous_value
                        if not math.isfinite(delta) or delta < 0:
                            skipped += 1
                            continue
                        append_series_sample(
                            series_map,
                            {
                                "__name__": item.record,
                                "db": settings.db_label,
                                "vehicle": vehicle,
                            },
                            window.sample_timestamp_ms,
                            delta,
                        )
                        emitted_samples += 1
                    continue
                if item.key in {"battery_soc_daily_min", "battery_soc_daily_max"}:
                    day_min, day_max = fetch_battery_soc_extrema(settings, window)
                    selected_value = day_min if item.key == "battery_soc_daily_min" else day_max
                    if selected_value is None:
                        skipped += 1
                        continue
                    append_series_sample(
                        series_map,
                        {
                            "__name__": item.record,
                            "db": settings.db_label,
                        },
                        window.sample_timestamp_ms,
                        selected_value,
                    )
                    emitted_samples += 1
                    continue
                if item.key in price_metric_keys:
                    if price_rollups is None:
                        price_rollups = fetch_grid_price_rollups(settings, window)
                    selected_value = price_rollups.get(item.key)
                    if selected_value is None or not math.isfinite(selected_value):
                        skipped += 1
                        continue
                    append_series_sample(
                        series_map,
                        {
                            "__name__": item.record,
                            "db": settings.db_label,
                        },
                        window.sample_timestamp_ms,
                        selected_value,
                    )
                    emitted_samples += 1
                    continue
                for result_item in fetch_rollup_vector(settings, item, window):
                    value = sample_value(result_item)
                    if value is None:
                        skipped += 1
                        continue
                    labels = normalize_rollup_labels(settings, item, result_item.get("metric", {}))
                    append_series_sample(series_map, labels, window.sample_timestamp_ms, value)
                    emitted_samples += 1

        seen_series_keys.update(series_map.keys())
        series_rows = list(series_map.values())
        batches = chunked(series_rows, args.batch_size)
        total_batches += len(batches)

        if args.write and batches:
            for batch_index, batch in enumerate(batches, start=1):
                response = http_post_bytes(settings, "/api/v1/import", serialize_import_jsonl(batch))
                import_results.append(
                    {
                        "chunk": chunk_name,
                        "batch": batch_index,
                        "status_code": response.status_code,
                        "body": response.body.strip(),
                        "series": len(batch),
                    }
                )

        chunk_summary = {
            "chunk": chunk_name,
            "days": len(chunk_windows),
            "samples": emitted_samples - chunk_start_samples,
            "series": len(series_rows),
            "skipped": skipped - chunk_start_skipped,
            "batches": len(batches),
        }
        chunk_summaries.append(chunk_summary)

        if args.progress:
            print(
                f"[chunk {chunk_index}/{len(chunks)}] done {chunk_name} days={processed_days}/{len(windows)} samples={chunk_summary['samples']} series={chunk_summary['series']} skipped={chunk_summary['skipped']} batches={chunk_summary['batches']}",
                file=sys.stderr,
                flush=True,
            )

    summary = {
        "mode": "write" if args.write else "dry-run",
        "timezone": settings.timezone,
        "raw_sample_step": settings.raw_sample_step,
        "price_bucket_minutes": settings.price_bucket_minutes,
        "price_rollup_mode": settings.price_rollup_mode,
        "range": {
            "start_day": start_day.isoformat(),
            "end_day": end_day.isoformat(),
            "days": len(windows),
        },
        "metrics": [item.record for item in catalog],
        "samples": emitted_samples,
        "series": len(seen_series_keys),
        "skipped": skipped,
        "chunk_by": args.chunk_by,
        "chunks": chunk_summaries,
        "batches": total_batches,
        "batch_size": args.batch_size,
        "import_results": import_results,
    }
    print(json.dumps(summary, indent=2, ensure_ascii=True))
    return 0


def main() -> int:
    args = parse_args()
    settings = load_settings(args.config)

    if args.command == "detect":
        return print_detect(settings)
    if args.command == "plan":
        return print_plan(settings)
    if args.command == "render-vmalert-rules":
        return render_vmalert_rules(settings)
    if args.command == "benchmark":
        return run_benchmark(settings)
    if args.command == "backfill-test":
        return backfill_test(settings, args)

    raise AssertionError(f"Unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())


