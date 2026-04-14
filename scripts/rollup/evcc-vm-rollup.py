#!/usr/bin/env python3
"""Safe planning, benchmarking and test backfill helpers for EVCC rollups."""

from __future__ import annotations

import argparse
import configparser
import json
import math
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, time as dt_time, timedelta, timezone
from zoneinfo import ZoneInfo


SCRIPT_NAME = "evcc-vm-rollup.py"
SCRIPT_VERSION = "2026.04.14.1"
SCRIPT_LAST_MODIFIED = "2026-04-14"


def current_local_timestamp() -> datetime:
    return datetime.now().astimezone()


def format_local_timestamp(value: datetime) -> str:
    return value.astimezone().replace(microsecond=0).isoformat()


def script_metadata(generated_at: str | None = None) -> dict[str, str]:
    return {
        "name": SCRIPT_NAME,
        "version": SCRIPT_VERSION,
        "last_modified": SCRIPT_LAST_MODIFIED,
        "generated_at": generated_at or format_local_timestamp(current_local_timestamp()),
    }


def print_report_header(title: str, underline: str, generated_at: str | None = None) -> None:
    metadata = script_metadata(generated_at)
    print(title)
    print(underline)
    print(f"Script:       {metadata['name']}")
    print(f"Version:      {metadata['version']}")
    print(f"Last modified:{metadata['last_modified']:>12}")
    print(f"Run at:       {metadata['generated_at']}")


@dataclass(frozen=True)
class Settings:
    base_url: str
    host_label: str
    timezone: str
    metric_prefix: str
    raw_sample_step: str
    energy_rollup_step: str
    price_bucket_minutes: int
    max_fetch_points_per_series: int
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
    local_year: str
    local_month: str
    local_day: str
    local_date: str


@dataclass(frozen=True)
class MonthScope:
    local_year: str
    local_month: str
    start_iso: str
    end_iso: str
    matcher: str


@dataclass(frozen=True)
class ImportResponse:
    status_code: int
    body: str


@dataclass(frozen=True)
class ChunkWindow:
    name: str
    start_iso: str
    end_iso: str
    start_ts: int
    end_ts: int


ACTIVE_PROFILE: dict[str, float | int] | None = None


def current_memory_usage_mb() -> float | None:
    try:
        import ctypes
        from ctypes import wintypes

        class PROCESS_MEMORY_COUNTERS_EX(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
                ("PrivateUsage", ctypes.c_size_t),
            ]

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        psapi.GetProcessMemoryInfo.argtypes = (
            wintypes.HANDLE,
            ctypes.c_void_p,
            wintypes.DWORD,
        )
        psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
        counters = PROCESS_MEMORY_COUNTERS_EX()
        counters.cb = ctypes.sizeof(counters)
        if psapi.GetProcessMemoryInfo(
            kernel32.GetCurrentProcess(),
            ctypes.byref(counters),
            counters.cb,
        ):
            return counters.WorkingSetSize / (1024 * 1024)
    except Exception:
        pass

    try:
        import resource

        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        if rss > 10_000_000:
            return rss / (1024 * 1024)
        return rss / 1024
    except Exception:
        return None



def update_peak_memory() -> None:
    global ACTIVE_PROFILE
    if ACTIVE_PROFILE is None:
        return
    current = current_memory_usage_mb()
    if current is None:
        return
    ACTIVE_PROFILE["memory_last_mb"] = current
    ACTIVE_PROFILE["memory_peak_mb"] = max(float(ACTIVE_PROFILE.get("memory_peak_mb", 0.0)), current)



def bump_profile_value(name: str, value: float = 1.0) -> None:
    global ACTIVE_PROFILE
    if ACTIVE_PROFILE is None:
        return
    ACTIVE_PROFILE[name] = ACTIVE_PROFILE.get(name, 0) + value


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
        choices=["detect", "plan", "benchmark", "backfill", "delete"],
        help="Action to perform.",
    )
    parser.add_argument(
        "--start-day",
        help="Local day in YYYY-MM-DD format for backfill.",
    )
    parser.add_argument(
        "--end-day",
        help="Local day in YYYY-MM-DD format for backfill.",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Actually write generated rollups or execute delete operations in VictoriaMetrics.",
    )
    parser.add_argument(
        "--replace-range",
        action="store_true",
        help=(
            "For backfill, delete the affected monthly evcc_* rollup scopes before writing them again. "
            "Dry-run mode only reports the planned deletes."
        ),
    )
    parser.add_argument(
        "--allow-incomplete-current-day",
        action="store_true",
        help=(
            "Dangerous override: allow --write to include the current local day. "
            "Future days are still rejected."
        ),
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=200,
        help="Number of time series per import batch during backfill.",
    )
    parser.add_argument(
        "--progress",
        action="store_true",
        help="Print chunk progress to stderr while backfill is running.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON for detect/plan/benchmark/backfill output.",
    )
    return parser.parse_args()


def load_settings(path: str) -> Settings:
    parser = configparser.ConfigParser()
    try:
        with open(path, "r", encoding="utf-8") as handle:
            parser.read_file(handle)
    except FileNotFoundError as exc:
        raise SystemExit(
            "Configuration file not found: "
            f"{path}\n"
            "Create the rollup config first or pass the correct path with --config."
        ) from exc


    max_fetch_points_per_series = parser.getint("victoriametrics", "max_fetch_points_per_series", fallback=28000)
    if max_fetch_points_per_series < 1000:
        raise SystemExit("max_fetch_points_per_series must be at least 1000")

    benchmark_defaults = {
        "start": (datetime.now(timezone.utc) - timedelta(days=30)).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "end": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "step": "1d",
    }
    if parser.has_section("benchmark"):
        benchmark_start = parser.get("benchmark", "start", fallback=benchmark_defaults["start"])
        benchmark_end = parser.get("benchmark", "end", fallback=benchmark_defaults["end"])
        benchmark_step = parser.get("benchmark", "step", fallback=benchmark_defaults["step"])
    else:
        benchmark_start = benchmark_defaults["start"]
        benchmark_end = benchmark_defaults["end"]
        benchmark_step = benchmark_defaults["step"]

    return Settings(
        base_url=parser.get("victoriametrics", "base_url").rstrip("/"),
        host_label=parser.get("victoriametrics", "host_label", fallback=""),
        timezone=parser.get("victoriametrics", "timezone"),
        metric_prefix=parser.get("victoriametrics", "metric_prefix"),
        raw_sample_step=parser.get("victoriametrics", "raw_sample_step", fallback="30s"),
        energy_rollup_step=parser.get("victoriametrics", "energy_rollup_step", fallback="60s"),
        price_bucket_minutes=parser.getint("victoriametrics", "price_bucket_minutes", fallback=15),
        max_fetch_points_per_series=max_fetch_points_per_series,
        benchmark_start=benchmark_start,
        benchmark_end=benchmark_end,
        benchmark_step=benchmark_step,
    )


def http_get_json(settings: Settings, path: str, params: dict[str, str | list[str]] | None = None) -> dict:
    url = settings.base_url + path
    if params:
        url = url + "?" + urllib.parse.urlencode(params, doseq=True)
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    started_at = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} for {url}: {body}") from exc
    finally:
        bump_profile_value("http_get_json_s", time.perf_counter() - started_at)
        bump_profile_value("http_get_json_calls")


def http_get_text(settings: Settings, path: str, params: dict[str, str | list[str]] | None = None) -> str:
    url = settings.base_url + path
    if params:
        url = url + "?" + urllib.parse.urlencode(params, doseq=True)
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    started_at = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} for {url}: {body}") from exc
    finally:
        bump_profile_value("http_get_text_s", time.perf_counter() - started_at)
        bump_profile_value("http_get_text_calls")


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
    started_at = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return ImportResponse(
                status_code=response.getcode(),
                body=response.read().decode("utf-8", errors="replace"),
            )
    finally:
        bump_profile_value("http_post_bytes_s", time.perf_counter() - started_at)
        bump_profile_value("http_post_bytes_calls")
        bump_profile_value("http_post_bytes_payload_mb", len(payload) / (1024 * 1024))


def http_post_form(settings: Settings, path: str, fields: list[tuple[str, str]]) -> ImportResponse:
    payload = urllib.parse.urlencode(fields).encode("utf-8")
    request = urllib.request.Request(
        settings.base_url + path,
        data=payload,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    started_at = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return ImportResponse(
                status_code=response.getcode(),
                body=response.read().decode("utf-8", errors="replace"),
            )
    finally:
        bump_profile_value("http_post_form_s", time.perf_counter() - started_at)
        bump_profile_value("http_post_form_calls")


def join_matchers(*parts: str) -> str:
    values: list[str] = []
    for part in parts:
        if not part:
            continue
        values.extend([item for item in part.split(",") if item])
    return ",".join(values)


def selector(metric_name: str, *parts: str) -> str:
    matcher = join_matchers(*parts)
    return f"{metric_name}{{{matcher}}}" if matcher else metric_name


def base_matchers(settings: Settings) -> str:
    _ = settings
    return ""


def record_name(settings: Settings, suffix: str) -> str:
    return f"{settings.metric_prefix}_{suffix}"


def series_match(settings: Settings, metric_name: str) -> str:
    return selector(metric_name, base_matchers(settings))


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
    root_no_id = join_matchers(root, 'id=""')
    return [
        RollupMetric(
            key="pv_daily_energy",
            record=record_name(settings, "pv_energy_daily_wh"),
            expr="python: legacy-style daily PV energy from positive mean buckets",
            description="PV daily energy from positive raw power buckets using the legacy mean-per-step integration semantics.",
            phase="phase-1",
            implemented=True,
            group_labels=(),
        ),
        RollupMetric(
            key="home_daily_energy",
            record=record_name(settings, "home_energy_daily_wh"),
            expr="python: legacy-style daily home energy from positive mean buckets",
            description="Home daily energy from positive raw power buckets using the legacy mean-per-step integration semantics.",
            phase="phase-1",
            implemented=True,
            group_labels=(),
        ),
        RollupMetric(
            key="loadpoint_daily_energy",
            record=record_name(settings, "loadpoint_energy_daily_wh"),
            expr=f"integrate((avg by (loadpoint) ({selector('chargePower_value', root, 'loadpoint!=""')}))[1d]) / 3600",
            description="Per-loadpoint daily charging energy.",
            phase="phase-1",
            implemented=True,
            group_labels=("loadpoint",),
        ),
        RollupMetric(
            key="vehicle_daily_energy",
            record=record_name(settings, "vehicle_energy_daily_wh"),
            expr=f"integrate((avg by (vehicle) ({selector('chargePower_value', root, 'vehicle!=""')}))[1d]) / 3600",
            description="Per-vehicle daily charging energy.",
            phase="phase-1",
            implemented=True,
            group_labels=("vehicle",),
        ),
        RollupMetric(
            key="vehicle_daily_distance",
            record=record_name(settings, "vehicle_distance_daily_km"),
            expr=(
                f"max(max_over_time(({selector('vehicleOdometer_value', root)} > 0)[1d])) by (vehicle) "
                f"- max(max_over_time(({selector('vehicleOdometer_value', root)} > 0)[1d] offset 1d)) by (vehicle)"
            ),
            description="Per-vehicle daily driven distance from odometer spread.",
            phase="phase-1",
            implemented=True,
            group_labels=("vehicle",),
        ),
        RollupMetric(
            key="vehicle_charge_cost_daily",
            record=record_name(settings, "vehicle_charge_cost_daily_eur"),
            expr="python: 15m raw per-vehicle charging cost from loadpoint tariffs",
            description="Per-vehicle daily charging cost from 15-minute charge energy weighted by matching loadpoint tariffs.",
            phase="phase-2",
            implemented=True,
            group_labels=("vehicle",),
        ),
        RollupMetric(
            key="potential_vehicle_charge_cost_daily",
            record=record_name(settings, "potential_vehicle_charge_cost_daily_eur"),
            expr="python: 15m raw per-vehicle charging cost from grid tariffs",
            description="Per-vehicle daily charging cost at grid tariffs as the no-PV comparison baseline.",
            phase="phase-2",
            implemented=True,
            group_labels=("vehicle",),
        ),
        RollupMetric(
            key="potential_home_cost_daily",
            record=record_name(settings, "potential_home_cost_daily_eur"),
            expr="python: 15m raw daily home cost at grid tariffs",
            description="Daily home energy valued at grid tariffs as the no-PV baseline.",
            phase="phase-2",
            implemented=True,
            group_labels=(),
        ),
        RollupMetric(
            key="potential_loadpoint_cost_daily",
            record=record_name(settings, "potential_loadpoint_cost_daily_eur"),
            expr="python: 15m raw daily loadpoint charging cost at grid tariffs",
            description="Daily charging energy valued at grid tariffs as the no-PV baseline.",
            phase="phase-2",
            implemented=True,
            group_labels=(),
        ),
        RollupMetric(
            key="battery_discharge_value_daily",
            record=record_name(settings, "battery_discharge_value_daily_eur"),
            expr="python: 15m raw daily battery discharge value at grid tariffs",
            description="Daily value of discharged battery energy at grid tariffs.",
            phase="phase-2",
            implemented=True,
            group_labels=(),
        ),
        RollupMetric(
            key="battery_charge_feedin_cost_daily",
            record=record_name(settings, "battery_charge_feedin_cost_daily_eur"),
            expr="python: 15m raw daily battery charge opportunity cost at feed-in tariffs",
            description="Daily opportunity cost of charging the battery instead of exporting at feed-in tariffs.",
            phase="phase-2",
            implemented=True,
            group_labels=(),
        ),
        RollupMetric(
            key="ext_daily_energy",
            record=record_name(settings, "ext_energy_daily_wh"),
            expr=f"integrate((avg by (title) ({selector('extPower_value', root, 'title!=""')}))[1d]) / 3600",
            description="Per-ext-title daily energy.",
            phase="phase-1",
            implemented=True,
            group_labels=("title",),
        ),
        RollupMetric(
            key="aux_daily_energy",
            record=record_name(settings, "aux_energy_daily_wh"),
            expr=f"integrate((avg by (title) ({selector('auxPower_value', root, 'title!=""')}))[1d]) / 3600",
            description="Per-aux-title daily energy.",
            phase="phase-1",
            implemented=True,
            group_labels=("title",),
        ),
        RollupMetric(
            key="loadpoint_daily_energy_from_pv",
            record=record_name(settings, "loadpoint_energy_from_pv_daily_wh"),
            expr="python: per-loadpoint daily charging energy attributed to PV supply",
            description="Per-loadpoint daily charging energy attributed to PV supply on 60-second buckets.",
            phase="phase-3",
            implemented=True,
            group_labels=("loadpoint",),
        ),
        RollupMetric(
            key="loadpoint_daily_energy_from_battery",
            record=record_name(settings, "loadpoint_energy_from_battery_daily_wh"),
            expr="python: per-loadpoint daily charging energy attributed to battery discharge",
            description="Per-loadpoint daily charging energy attributed to battery discharge on 60-second buckets.",
            phase="phase-3",
            implemented=True,
            group_labels=("loadpoint",),
        ),
        RollupMetric(
            key="loadpoint_daily_energy_from_grid",
            record=record_name(settings, "loadpoint_energy_from_grid_daily_wh"),
            expr="python: per-loadpoint daily charging energy attributed to grid supply",
            description="Per-loadpoint daily charging energy attributed to grid supply on 60-second buckets.",
            phase="phase-3",
            implemented=True,
            group_labels=("loadpoint",),
        ),
        RollupMetric(
            key="ext_daily_energy_from_pv",
            record=record_name(settings, "ext_energy_from_pv_daily_wh"),
            expr="python: per-ext-title daily energy attributed to PV supply",
            description="Per-ext-title daily energy attributed to PV supply on 60-second buckets.",
            phase="phase-3",
            implemented=True,
            group_labels=("title",),
        ),
        RollupMetric(
            key="ext_daily_energy_from_battery",
            record=record_name(settings, "ext_energy_from_battery_daily_wh"),
            expr="python: per-ext-title daily energy attributed to battery discharge",
            description="Per-ext-title daily energy attributed to battery discharge on 60-second buckets.",
            phase="phase-3",
            implemented=True,
            group_labels=("title",),
        ),
        RollupMetric(
            key="ext_daily_energy_from_grid",
            record=record_name(settings, "ext_energy_from_grid_daily_wh"),
            expr="python: per-ext-title daily energy attributed to grid supply",
            description="Per-ext-title daily energy attributed to grid supply on 60-second buckets.",
            phase="phase-3",
            implemented=True,
            group_labels=("title",),
        ),
        RollupMetric(
            key="aux_daily_energy_from_pv",
            record=record_name(settings, "aux_energy_from_pv_daily_wh"),
            expr="python: per-aux-title daily energy attributed to PV supply",
            description="Per-aux-title daily energy attributed to PV supply on 60-second buckets.",
            phase="phase-3",
            implemented=True,
            group_labels=("title",),
        ),
        RollupMetric(
            key="aux_daily_energy_from_battery",
            record=record_name(settings, "aux_energy_from_battery_daily_wh"),
            expr="python: per-aux-title daily energy attributed to battery discharge",
            description="Per-aux-title daily energy attributed to battery discharge on 60-second buckets.",
            phase="phase-3",
            implemented=True,
            group_labels=("title",),
        ),
        RollupMetric(
            key="aux_daily_energy_from_grid",
            record=record_name(settings, "aux_energy_from_grid_daily_wh"),
            expr="python: per-aux-title daily energy attributed to grid supply",
            description="Per-aux-title daily energy attributed to grid supply on 60-second buckets.",
            phase="phase-3",
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
            expr="python: daily grid import energy from gridEnergy counter spread",
            description="Daily grid import energy from the local-day spread of the gridEnergy meter counter.",
            phase="phase-2",
            implemented=True,
            group_labels=(),
        ),
        RollupMetric(
            key="grid_export_daily_energy",
            record=record_name(settings, "grid_export_daily_wh"),
            expr="python: sign-aware daily grid export energy",
            description="Daily grid export energy on the active sampled/clamp comparison path.",
            phase="phase-2",
            implemented=True,
            group_labels=(),
        ),
        RollupMetric(
            key="battery_charge_daily_energy",
            record=record_name(settings, "battery_charge_daily_wh"),
            expr="python: sign-aware daily battery charge energy",
            description="Daily battery charge energy from the negative branch of battery power.",
            phase="phase-2",
            implemented=True,
            group_labels=(),
        ),
        RollupMetric(
            key="battery_discharge_daily_energy",
            record=record_name(settings, "battery_discharge_daily_wh"),
            expr="python: sign-aware daily battery discharge energy",
            description="Daily battery discharge energy from the positive branch of battery power.",
            phase="phase-2",
            implemented=True,
            group_labels=(),
        ),
        RollupMetric(
            key="grid_import_cost_daily",
            record=record_name(settings, "grid_import_cost_daily_eur"),
            expr="python: gridEnergy counter import energy weighted by 15m effective grid tariff",
            description="Daily grid import cost from the gridEnergy counter-spread import energy weighted by the 15-minute effective tariff.",
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
            key="grid_export_credit_daily",
            record=record_name(settings, "grid_export_credit_daily_eur"),
            expr="python: 15m raw daily export credit from feed-in tariff",
            description="Daily feed-in credit from 15-minute export energy weighted by matching feed-in tariff.",
            phase="phase-2",
            implemented=True,
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
        day_text = current.isoformat()
        windows.append(
            DayWindow(
                day=day_text,
                start_iso=to_iso_z(start_utc),
                end_iso=to_iso_z(end_utc),
                sample_timestamp_ms=int(start_utc.timestamp() * 1000),
                local_year=day_text[0:4],
                local_month=day_text[5:7],
                local_day=day_text[8:10],
                local_date=day_text,
            )
        )
        current += timedelta(days=1)
    return windows


def last_day_of_month(value: date) -> date:
    if value.month == 12:
        return date(value.year, 12, 31)
    return date(value.year, value.month + 1, 1) - timedelta(days=1)


def current_local_day(settings: Settings) -> date:
    return datetime.now(ZoneInfo(settings.timezone)).date()


def validate_backfill_write_window(
    settings: Settings,
    args: argparse.Namespace,
    end_day: date,
    today: date | None = None,
) -> dict[str, str | bool]:
    local_today = today or current_local_day(settings)
    latest_completed_day = local_today - timedelta(days=1)
    includes_incomplete_day = end_day >= local_today

    safety = {
        "local_today": local_today.isoformat(),
        "latest_completed_day": latest_completed_day.isoformat(),
        "includes_incomplete_day": includes_incomplete_day,
        "allow_incomplete_current_day": bool(getattr(args, "allow_incomplete_current_day", False)),
    }

    if not args.write:
        return safety

    if end_day > local_today:
        raise SystemExit(
            "NO-GO: --write must not include future local days. "
            f"Timezone is {settings.timezone}; today is {local_today.isoformat()}. "
            f"Use --end-day {latest_completed_day.isoformat()} for the latest safe completed day."
        )

    if end_day == local_today and not getattr(args, "allow_incomplete_current_day", False):
        raise SystemExit(
            "NO-GO: --write would include the current incomplete local day. "
            f"Timezone is {settings.timezone}; today is {local_today.isoformat()}. "
            f"Use --end-day {latest_completed_day.isoformat()} for production rollups, "
            "or pass --allow-incomplete-current-day only for an intentional diagnostic write."
        )

    return safety


def validate_month_replace_range(
    settings: Settings,
    start_day: date,
    end_day: date,
    today: date | None = None,
) -> None:
    local_today = today or current_local_day(settings)
    latest_completed_day = local_today - timedelta(days=1)

    if start_day.day != 1:
        raise SystemExit(
            "NO-GO: monthly rollup replacement deletes whole local_month scopes, "
            f"so --start-day must be the first day of a month. Got {start_day.isoformat()}."
        )

    allowed_end_day = last_day_of_month(end_day)
    if end_day != allowed_end_day and end_day != latest_completed_day:
        raise SystemExit(
            "NO-GO: monthly rollup replacement deletes whole local_month scopes. "
            f"Use --end-day {allowed_end_day.isoformat()} for a completed historical month, "
            f"or --end-day {latest_completed_day.isoformat()} for the current in-progress month."
        )


def promql_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def rollup_month_matcher(settings: Settings, local_year: str, local_month: str) -> str:
    name_regex = re.escape(f"{settings.metric_prefix}_") + ".*"
    return (
        "{"
        f'__name__=~"{promql_string(name_regex)}",'
        f'local_year="{promql_string(local_year)}",'
        f'local_month="{promql_string(local_month)}"'
        "}"
    )


def build_month_scopes(settings: Settings, windows: list[DayWindow]) -> list[MonthScope]:
    month_windows: dict[tuple[str, str], list[DayWindow]] = {}
    for window in windows:
        month_windows.setdefault((window.local_year, window.local_month), []).append(window)

    scopes: list[MonthScope] = []
    for (local_year, local_month), items in sorted(month_windows.items()):
        ordered = sorted(items, key=lambda item: item.start_iso)
        scopes.append(
            MonthScope(
                local_year=local_year,
                local_month=local_month,
                start_iso=ordered[0].start_iso,
                end_iso=ordered[-1].end_iso,
                matcher=rollup_month_matcher(settings, local_year, local_month),
            )
        )
    return scopes


def count_matching_series(settings: Settings, matcher: str, start_iso: str, end_iso: str) -> int:
    response = http_get_json(
        settings,
        "/api/v1/series",
        {
            "match[]": [matcher],
            "start": start_iso,
            "end": end_iso,
        },
    )
    return len(response.get("data", []))


def delete_rollup_scopes(settings: Settings, scopes: list[MonthScope], write: bool) -> list[dict[str, str | int]]:
    results: list[dict[str, str | int]] = []
    for scope in scopes:
        before = count_matching_series(settings, scope.matcher, scope.start_iso, scope.end_iso)
        after = before
        status = "dry-run"
        if write:
            http_post_form(settings, "/api/v1/admin/tsdb/delete_series", [("match[]", scope.matcher)])
            after = count_matching_series(settings, scope.matcher, scope.start_iso, scope.end_iso)
            status = "deleted"
        results.append(
            {
                "local_year": scope.local_year,
                "local_month": scope.local_month,
                "matcher": scope.matcher,
                "start": scope.start_iso,
                "end": scope.end_iso,
                "series_before": before,
                "series_after": after,
                "status": status,
            }
        )
    return results


def build_window_chunks(windows: list[DayWindow]) -> list[tuple[str, list[DayWindow]]]:
    chunks: list[tuple[str, list[DayWindow]]] = []
    current_label = ""
    current_windows: list[DayWindow] = []

    for window in windows:
        label = window.day[:7]
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


def print_list_section(title: str, values: list[str], empty_text: str = "none detected") -> None:
    print(f"\n{title}")
    print("-" * len(title))
    if not values:
        print(empty_text)
        return
    for value in values:
        print(f"- {value}")


def print_detect(settings: Settings, as_json: bool = False) -> int:
    detection = detect_dimensions(settings)
    if as_json:
        output = dict(detection)
        output["script"] = script_metadata()
        print(json.dumps(output, indent=2, ensure_ascii=True))
        return 0

    print_report_header("EVCC rollup dimension detection", "============================")
    print(f"Namespace:  {settings.metric_prefix}")
    print(f"Timezone:   {settings.timezone}")
    print(f"VM base:    {settings.base_url}")
    print(f"Range:      {settings.benchmark_start} -> {settings.benchmark_end}")
    print_list_section("Loadpoints", detection["loadpoints"])
    print_list_section("Vehicles", detection["vehicles"])
    print_list_section("EXT titles", detection["ext_titles"])
    print_list_section("AUX titles", detection["aux_titles"])
    return 0


def print_plan(settings: Settings, as_json: bool = False) -> int:
    detection = detect_dimensions(settings)
    catalog = [item for item in build_catalog(settings) if item.implemented]
    if as_json:
        output = {
            "script": script_metadata(),
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
                    "phase": item.phase,
                }
                for item in catalog
            ],
        }
        print(json.dumps(output, indent=2, ensure_ascii=True))
        return 0

    print_report_header("EVCC rollup plan", "================")
    print(f"Namespace:   {settings.metric_prefix}")
    print(f"Timezone:    {settings.timezone}")
    print(f"VM base:     {settings.base_url}")
    print(f"Raw step:    {settings.raw_sample_step}")
    print(f"Energy step: {settings.energy_rollup_step}")
    print(f"Price bucket minutes: {settings.price_bucket_minutes}")
    print(f"Implemented rollups: {len(catalog)}")

    print_list_section("Loadpoints", detection["loadpoints"])
    print_list_section("Vehicles", detection["vehicles"])
    print_list_section("EXT titles", detection["ext_titles"])
    print_list_section("AUX titles", detection["aux_titles"])

    phase_groups: dict[str, list[RollupMetric]] = {}
    for item in catalog:
        phase_groups.setdefault(item.phase, []).append(item)

    phase_titles = {
        "phase-1": "Phase 1: core energy and distance rollups",
        "phase-2": "Phase 2: battery, grid, and pricing rollups",
        "phase-3": "Phase 3: source attribution rollups",
    }
    for phase in ("phase-1", "phase-2", "phase-3"):
        items = phase_groups.get(phase, [])
        title = phase_titles[phase]
        print(f"\n{title}")
        print("-" * len(title))
        if not items:
            print("none")
            continue
        for item in items:
            scope = ", ".join(item.group_labels) if item.group_labels else "global"
            print(f"- {item.record} [{scope}]")
            print(f"  {item.description}")

    print("\nPlan notes")
    print("----------")
    print("- This plan only lists implemented rollups.")
    print("- detect/plan do not write data.")
    print("- backfill --write creates the daily evcc_* metrics.")
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


def run_benchmark(settings: Settings, as_json: bool = False) -> int:
    catalog = [item for item in build_catalog(settings) if item.implemented]
    results = [benchmark_query(settings, item) for item in catalog]
    payload = {
        "script": script_metadata(),
        "range": {
            "start": settings.benchmark_start,
            "end": settings.benchmark_end,
            "step": settings.benchmark_step,
        },
        "results": results,
    }
    if as_json:
        print(json.dumps(payload, indent=2, ensure_ascii=True))
        return 0

    promql_results = [item for item in results if item["elapsed_ms"] is not None]
    python_results = [item for item in results if item["elapsed_ms"] is None]
    successful_promql = [item for item in promql_results if item["status"] == "success"]
    failed_promql = [item for item in promql_results if item["status"] != "success"]
    slowest = sorted(successful_promql, key=lambda item: float(item["elapsed_ms"]), reverse=True)[:5]

    print_report_header("EVCC rollup benchmark", "====================")
    print(f"Range: {settings.benchmark_start} -> {settings.benchmark_end}")
    print(f"Step:  {settings.benchmark_step}")

    print("\nSummary")
    print("-------")
    print(f"- Implemented rollups: {len(results)}")
    print(f"- Direct PromQL checks: {len(promql_results)}")
    print(f"- Python-only rollups: {len(python_results)}")
    print(f"- Successful PromQL checks: {len(successful_promql)}")
    print(f"- Failed PromQL checks: {len(failed_promql)}")

    print("\nInterpretation")
    print("--------------")
    print("- PromQL checks validate that the required raw source metrics can be queried from VictoriaMetrics.")
    print("- Python-only rollups are computed during backfill; they do not have a single PromQL query to benchmark here.")
    print("- If PromQL checks are fast and successful, the setup is usually ready for a dry-run backfill.")

    if slowest:
        print("\nSlowest direct checks")
        print("--------------------")
        for item in slowest:
            print(f"- {item['record']}: {item['elapsed_ms']} ms, series={item['series']}")

    if failed_promql:
        print("\nFailed direct checks")
        print("--------------------")
        for item in failed_promql:
            series_text = "n/a" if item["series"] is None else str(item["series"])
            print(f"- {item['record']}: status={item['status']}, series={series_text}")

    print("\nPython-only rollups")
    print("-------------------")
    for item in python_results:
        print(f"- {item['record']}")

    print("\nResult")
    print("------")
    if failed_promql:
        print("NOT OK: one or more direct source checks failed. Review the failed checks before running backfill.")
    else:
        print("OK: direct source checks passed. The setup is ready for a dry-run backfill.")
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
            "query": f"{selector('batterySoc_value', base_matchers(settings))}",
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


def fetch_series_range(
    settings: Settings,
    query: str,
    start_iso: str,
    end_iso: str,
    step: str,
) -> list[dict]:
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
    out: list[dict] = []
    for result_item in response.get("data", {}).get("result", []):
        samples: list[tuple[int, float]] = []
        for row in result_item.get("values", []):
            if not isinstance(row, list) or len(row) != 2:
                continue
            try:
                timestamp = int(row[0])
                value = float(row[1])
            except (TypeError, ValueError):
                continue
            if math.isfinite(value):
                samples.append((timestamp, value))
        if samples:
            out.append({"metric": result_item.get("metric", {}), "samples": samples})
    return out


def fetch_single_series_range(
    settings: Settings,
    query: str,
    start_iso: str,
    end_iso: str,
    step: str,
) -> list[tuple[int, float]]:
    series = fetch_series_range(settings, query, start_iso, end_iso, step)
    if not series:
        return []
    return series[0]["samples"]


def iso_to_timestamp(iso_value: str) -> int:
    return int(datetime.fromisoformat(iso_value.replace("Z", "+00:00")).timestamp())


def build_chunk_window(chunk_name: str, windows: list[DayWindow]) -> ChunkWindow:
    start_iso = windows[0].start_iso
    end_iso = windows[-1].end_iso
    return ChunkWindow(
        name=chunk_name,
        start_iso=start_iso,
        end_iso=end_iso,
        start_ts=iso_to_timestamp(start_iso),
        end_ts=iso_to_timestamp(end_iso),
    )


def build_fetch_blocks(
    chunk_name: str,
    windows: list[DayWindow],
    step_seconds: int,
    max_points_per_series: int = 28000,
) -> tuple[list[ChunkWindow], dict[str, ChunkWindow]]:
    max_block_seconds = step_seconds * max_points_per_series
    blocks: list[ChunkWindow] = []
    block_by_day: dict[str, ChunkWindow] = {}
    current_windows: list[DayWindow] = []
    current_seconds = 0
    block_index = 1

    for window in windows:
        window_seconds = iso_to_timestamp(window.end_iso) - iso_to_timestamp(window.start_iso)
        if current_windows and current_seconds + window_seconds > max_block_seconds:
            block = build_chunk_window(f"{chunk_name}-b{block_index}", current_windows)
            blocks.append(block)
            for item in current_windows:
                block_by_day[item.day] = block
            block_index += 1
            current_windows = []
            current_seconds = 0
        current_windows.append(window)
        current_seconds += window_seconds

    if current_windows:
        block = build_chunk_window(f"{chunk_name}-b{block_index}", current_windows)
        blocks.append(block)
        for item in current_windows:
            block_by_day[item.day] = block

    return blocks, block_by_day


def slice_samples(
    samples: list[tuple[int, float]],
    start_ts: int,
    end_ts: int,
    include_last_before: bool = False,
    max_lookback_seconds: int | None = None,
) -> list[tuple[int, float]]:
    sliced = [(timestamp, value) for timestamp, value in samples if start_ts <= timestamp < end_ts]
    if include_last_before:
        previous = None
        for timestamp, value in samples:
            if timestamp >= start_ts:
                break
            previous = (timestamp, value)
        if previous is not None and (
            max_lookback_seconds is None or previous[0] >= (start_ts - max_lookback_seconds)
        ):
            sliced.insert(0, previous)
    return sliced



def slice_matrix_samples(
    matrix: list[dict],
    start_ts: int,
    end_ts: int,
    include_last_before: bool = False,
) -> list[dict]:
    out: list[dict] = []
    for result_item in matrix:
        samples = slice_samples(result_item["samples"], start_ts, end_ts, include_last_before=include_last_before)
        if samples:
            out.append({"metric": result_item.get("metric", {}), "samples": samples})
    return out


def fetch_metric_export_samples(
    settings: Settings,
    matcher: str,
    start_iso: str,
    end_iso: str,
) -> list[tuple[int, float]]:
    start_ts = int(datetime.fromisoformat(start_iso.replace("Z", "+00:00")).timestamp())
    end_ts = int(datetime.fromisoformat(end_iso.replace("Z", "+00:00")).timestamp())
    text = http_get_text(
        settings,
        "/api/v1/export",
        {
            "match[]": [matcher],
            "start": start_iso,
            "end": end_iso,
        },
    )
    samples: list[tuple[int, float]] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        timestamps = item.get("timestamps", [])
        values = item.get("values", [])
        for timestamp_ms, value in zip(timestamps, values):
            try:
                timestamp = int(timestamp_ms) // 1000
                numeric = float(value)
            except (TypeError, ValueError):
                continue
            if not math.isfinite(numeric):
                continue
            if start_ts <= timestamp < end_ts:
                samples.append((timestamp, numeric))
    samples.sort()
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


def summarize_polarity_bucket_energy_samples(
    samples: list[tuple[int, float]],
    bucket_seconds: int,
    positive_label: str,
    negative_label: str,
    peak_power_limit: float,
) -> dict[str, float]:
    positive_sums: dict[int, float] = {}
    positive_counts: dict[int, int] = {}
    negative_sums: dict[int, float] = {}
    negative_counts: dict[int, int] = {}

    for timestamp, value in samples:
        bucket_start = (timestamp // bucket_seconds) * bucket_seconds
        if 0 <= value < peak_power_limit:
            positive_sums[bucket_start] = positive_sums.get(bucket_start, 0.0) + value
            positive_counts[bucket_start] = positive_counts.get(bucket_start, 0) + 1
        if value <= 0 and value < peak_power_limit:
            negative_sums[bucket_start] = negative_sums.get(bucket_start, 0.0) + value
            negative_counts[bucket_start] = negative_counts.get(bucket_start, 0) + 1

    positive_wh = sum(
        (positive_sums[bucket] / positive_counts[bucket]) * bucket_seconds / 3600
        for bucket in positive_sums
    )
    negative_wh = sum(
        (-negative_sums[bucket] / negative_counts[bucket]) * bucket_seconds / 3600
        for bucket in negative_sums
    )
    return {
        positive_label: positive_wh,
        negative_label: negative_wh,
    }


def summarize_grid_energy_samples(
    grid_samples: list[tuple[int, float]],
    bucket_seconds: int,
    peak_power_limit: float = 40000.0,
) -> dict[str, float]:
    return summarize_polarity_bucket_energy_samples(
        samples=grid_samples,
        bucket_seconds=bucket_seconds,
        positive_label="grid_import_daily_energy",
        negative_label="grid_export_daily_energy",
        peak_power_limit=peak_power_limit,
    )


def summarize_counter_spread_samples(
    counter_samples: list[tuple[int, float]],
    unit_multiplier: float = 1000.0,
) -> float | None:
    values = [
        value
        for _, value in counter_samples
        if math.isfinite(value) and value >= 0
    ]
    if len(values) < 2:
        return None
    spread = max(values) - min(values)
    if spread < 0:
        return None
    return spread * unit_multiplier


def summarize_battery_energy_samples(
    battery_samples: list[tuple[int, float]],
    bucket_seconds: int,
    peak_power_limit: float = 40000.0,
) -> dict[str, float]:
    return summarize_polarity_bucket_energy_samples(
        samples=[(timestamp, -value) for timestamp, value in battery_samples],
        bucket_seconds=bucket_seconds,
        positive_label="battery_charge_daily_energy",
        negative_label="battery_discharge_daily_energy",
        peak_power_limit=peak_power_limit,
    )


def summarize_bucket_grid_energy(
    bucket_import_samples: list[tuple[int, float]],
    bucket_export_samples: list[tuple[int, float]],
) -> dict[str, float]:
    import_wh = sum(max(value, 0.0) for _, value in bucket_import_samples) * 1000
    export_wh = sum(max(value, 0.0) for _, value in bucket_export_samples) * 1000
    return {
        "grid_import_daily_energy": import_wh,
        "grid_export_daily_energy": export_wh,
    }


def summarize_positive_bucket_energy_samples(
    samples: list[tuple[int, float]],
    bucket_seconds: int,
    peak_power_limit: float = 40000.0,
) -> float:
    buckets: dict[int, list[float]] = {}
    for timestamp, value in samples:
        if not math.isfinite(value) or value <= 0 or value >= peak_power_limit:
            continue
        bucket_start = (timestamp // bucket_seconds) * bucket_seconds
        buckets.setdefault(bucket_start, []).append(value)
    total_wh = 0.0
    for values in buckets.values():
        total_wh += (sum(values) / len(values)) * bucket_seconds / 3600.0
    return total_wh


def reduce_bucket_values(values: list[float], reducer: str) -> float:
    if reducer == "max":
        return max(values)
    if reducer == "mean":
        return sum(values) / len(values)
    raise ValueError(f"Unsupported bucket reducer: {reducer}")


def summarize_legacy_bucket_energy_samples(
    samples: list[tuple[int, float]],
    start_ts: int,
    end_ts: int,
    bucket_seconds: int,
    reducer: str,
    peak_power_limit: float = 40000.0,
) -> float:
    bucket_map: dict[int, list[float]] = {}
    for timestamp, value in samples:
        if timestamp < start_ts or timestamp >= end_ts:
            continue
        if not math.isfinite(value) or value < 0 or value >= peak_power_limit:
            continue
        bucket_start = start_ts + (((timestamp - start_ts) // bucket_seconds) * bucket_seconds)
        bucket_map.setdefault(bucket_start, []).append(value)
    total_wh = 0.0
    for bucket_start in range(start_ts, end_ts, bucket_seconds):
        values = bucket_map.get(bucket_start)
        if not values:
            continue
        total_wh += reduce_bucket_values(values, reducer) * bucket_seconds / 3600.0
    return total_wh


def legacy_bucket_reducer_for_item(item: RollupMetric) -> str | None:
    if item.key in {"pv_daily_energy", "home_daily_energy"}:
        return "mean"
    return None


def summarize_legacy_positive_energy_rollups_from_matrix(
    settings: Settings,
    item: RollupMetric,
    window: DayWindow,
    matrix: list[dict],
) -> list[tuple[dict[str, str], float]]:
    reducer = legacy_bucket_reducer_for_item(item)
    if reducer is None:
        raise ValueError(f"Unsupported legacy positive energy key: {item.key}")
    bucket_seconds = parse_step_seconds(settings.energy_rollup_step)
    start_ts = iso_to_timestamp(window.start_iso)
    end_ts = iso_to_timestamp(window.end_iso)
    out: list[tuple[dict[str, str], float]] = []
    for result_item in matrix:
        samples = slice_samples(result_item["samples"], start_ts, end_ts)
        if not samples:
            continue
        value = summarize_legacy_bucket_energy_samples(
            samples,
            start_ts,
            end_ts,
            bucket_seconds,
            reducer,
        )
        labels = normalize_rollup_labels(settings, item, result_item.get("metric", {}), window)
        out.append((labels, value))
    return out

def positive_energy_query(settings: Settings, item: RollupMetric) -> str:
    root = base_matchers(settings)
    if item.key == "pv_daily_energy":
        return (
            f'sum(avg by (id) ({selector("pvPower_value", root, "id!=\"\"")})) '
            f'or avg({selector("pvPower_value", root, "id=\"\"")})'
        )
    if item.key == "home_daily_energy":
        return f'avg({selector("homePower_value", root)})'
    if item.key == "loadpoint_daily_energy":
        return f'avg by (loadpoint) ({selector("chargePower_value", root, "loadpoint!=\"\"")})'
    if item.key == "vehicle_daily_energy":
        return f'avg by (vehicle) ({selector("chargePower_value", root, "vehicle!=\"\"")})'
    if item.key == "ext_daily_energy":
        return f'avg by (title) ({selector("extPower_value", root, "title!=\"\"")})'
    if item.key == "aux_daily_energy":
        return f'avg by (title) ({selector("auxPower_value", root, "title!=\"\"")})'
    raise ValueError(f"Unsupported positive energy key: {item.key}")


def fetch_chunk_positive_energy_matrix(
    settings: Settings,
    item: RollupMetric,
    chunk: ChunkWindow,
) -> list[dict]:
    result = fetch_series_range(
        settings,
        positive_energy_query(settings, item),
        chunk.start_iso,
        chunk.end_iso,
        settings.raw_sample_step,
    )
    update_peak_memory()
    return result



def summarize_positive_energy_rollups_from_matrix(
    settings: Settings,
    item: RollupMetric,
    window: DayWindow,
    matrix: list[dict],
) -> list[tuple[dict[str, str], float]]:
    bucket_seconds = parse_step_seconds(settings.energy_rollup_step)
    start_ts = iso_to_timestamp(window.start_iso)
    end_ts = iso_to_timestamp(window.end_iso)
    out: list[tuple[dict[str, str], float]] = []
    for result_item in matrix:
        samples = slice_samples(result_item["samples"], start_ts, end_ts)
        if not samples:
            continue
        value = summarize_positive_bucket_energy_samples(samples, bucket_seconds)
        labels = normalize_rollup_labels(settings, item, result_item.get("metric", {}), window)
        out.append((labels, value))
    return out



def build_positive_bucket_average_map(
    samples: list[tuple[int, float]],
    start_ts: int,
    end_ts: int,
    bucket_seconds: int,
) -> dict[int, float]:
    bucket_map: dict[int, list[float]] = {}
    for timestamp, value in samples:
        if timestamp < start_ts or timestamp >= end_ts:
            continue
        if not math.isfinite(value) or value <= 0:
            continue
        bucket_start = start_ts + (((timestamp - start_ts) // bucket_seconds) * bucket_seconds)
        bucket_map.setdefault(bucket_start, []).append(value)
    return {
        bucket_start: sum(values) / len(values)
        for bucket_start, values in bucket_map.items()
        if values
    }


def build_consumer_bucket_average_maps(
    matrix: list[dict],
    start_ts: int,
    end_ts: int,
    bucket_seconds: int,
    label_name: str,
) -> dict[str, dict[int, float]]:
    out: dict[str, dict[int, float]] = {}
    for result_item in matrix:
        label_value = str(result_item.get("metric", {}).get(label_name, "")).strip()
        if not label_value:
            continue
        bucket_map = build_positive_bucket_average_map(result_item.get("samples", []), start_ts, end_ts, bucket_seconds)
        if bucket_map:
            out[label_value] = bucket_map
    return out


def attribute_consumer_bucket_maps(
    consumer_maps: dict[str, dict[int, float]],
    pv_bucket_map: dict[int, float],
    battery_bucket_map: dict[int, float],
    bucket_seconds: int,
) -> dict[str, dict[str, float]]:
    totals = {
        consumer: {"pv": 0.0, "battery": 0.0, "grid": 0.0}
        for consumer in consumer_maps
    }
    all_bucket_starts = sorted(
        {
            bucket_start
            for bucket_map in consumer_maps.values()
            for bucket_start in bucket_map
        }
    )
    hours_per_bucket = bucket_seconds / 3600.0
    for bucket_start in all_bucket_starts:
        active_powers = {
            consumer: power
            for consumer, bucket_map in consumer_maps.items()
            for power in [bucket_map.get(bucket_start, 0.0)]
            if math.isfinite(power) and power > 0.0
        }
        total_power = sum(active_powers.values())
        if total_power <= 0.0:
            continue
        pv_supply = min(max(pv_bucket_map.get(bucket_start, 0.0), 0.0), total_power)
        remaining_after_pv = max(total_power - pv_supply, 0.0)
        battery_supply = min(max(battery_bucket_map.get(bucket_start, 0.0), 0.0), remaining_after_pv)
        grid_supply = max(total_power - pv_supply - battery_supply, 0.0)
        for consumer, power in active_powers.items():
            share = power / total_power
            totals[consumer]["pv"] += pv_supply * share * hours_per_bucket
            totals[consumer]["battery"] += battery_supply * share * hours_per_bucket
            totals[consumer]["grid"] += grid_supply * share * hours_per_bucket
    return totals


def summarize_consumer_source_attribution_rollups(
    settings: Settings,
    window: DayWindow,
    context: dict[str, object],
) -> dict[str, list[tuple[dict[str, str], float]]]:
    bucket_seconds = parse_step_seconds(settings.energy_rollup_step)
    start_ts = iso_to_timestamp(window.start_iso)
    end_ts = iso_to_timestamp(window.end_iso)
    pv_bucket_map = build_positive_bucket_average_map(
        slice_samples(context["pv_samples"], start_ts, end_ts),
        start_ts,
        end_ts,
        bucket_seconds,
    )
    battery_bucket_map = build_positive_bucket_average_map(
        slice_samples(context["battery_samples"], start_ts, end_ts),
        start_ts,
        end_ts,
        bucket_seconds,
    )
    loadpoint_maps = build_consumer_bucket_average_maps(
        context["charge_loadpoint_matrix"],
        start_ts,
        end_ts,
        bucket_seconds,
        "loadpoint",
    )
    ext_maps = build_consumer_bucket_average_maps(
        context["ext_title_matrix"],
        start_ts,
        end_ts,
        bucket_seconds,
        "title",
    )
    aux_maps = build_consumer_bucket_average_maps(
        context["aux_title_matrix"],
        start_ts,
        end_ts,
        bucket_seconds,
        "title",
    )
    metric_name_by_key = {
        "loadpoint_daily_energy_from_pv": "loadpoint_energy_from_pv_daily_wh",
        "loadpoint_daily_energy_from_battery": "loadpoint_energy_from_battery_daily_wh",
        "loadpoint_daily_energy_from_grid": "loadpoint_energy_from_grid_daily_wh",
        "ext_daily_energy_from_pv": "ext_energy_from_pv_daily_wh",
        "ext_daily_energy_from_battery": "ext_energy_from_battery_daily_wh",
        "ext_daily_energy_from_grid": "ext_energy_from_grid_daily_wh",
        "aux_daily_energy_from_pv": "aux_energy_from_pv_daily_wh",
        "aux_daily_energy_from_battery": "aux_energy_from_battery_daily_wh",
        "aux_daily_energy_from_grid": "aux_energy_from_grid_daily_wh",
    }
    out = {metric_key: [] for metric_key in metric_name_by_key}
    for consumer, totals in attribute_consumer_bucket_maps(loadpoint_maps, pv_bucket_map, battery_bucket_map, bucket_seconds).items():
        for source_name, metric_key in (("pv", "loadpoint_daily_energy_from_pv"), ("battery", "loadpoint_daily_energy_from_battery"), ("grid", "loadpoint_daily_energy_from_grid")):
            labels = base_daily_labels(settings, record_name(settings, metric_name_by_key[metric_key]), window)
            labels["loadpoint"] = consumer
            out[metric_key].append((labels, totals[source_name]))
    for consumer, totals in attribute_consumer_bucket_maps(ext_maps, pv_bucket_map, battery_bucket_map, bucket_seconds).items():
        for source_name, metric_key in (("pv", "ext_daily_energy_from_pv"), ("battery", "ext_daily_energy_from_battery"), ("grid", "ext_daily_energy_from_grid")):
            labels = base_daily_labels(settings, record_name(settings, metric_name_by_key[metric_key]), window)
            labels["title"] = consumer
            out[metric_key].append((labels, totals[source_name]))
    for consumer, totals in attribute_consumer_bucket_maps(aux_maps, pv_bucket_map, battery_bucket_map, bucket_seconds).items():
        for source_name, metric_key in (("pv", "aux_daily_energy_from_pv"), ("battery", "aux_daily_energy_from_battery"), ("grid", "aux_daily_energy_from_grid")):
            labels = base_daily_labels(settings, record_name(settings, metric_name_by_key[metric_key]), window)
            labels["title"] = consumer
            out[metric_key].append((labels, totals[source_name]))
    return out


def fetch_chunk_consumer_attribution_context(settings: Settings, chunk: ChunkWindow) -> dict[str, object]:
    root = base_matchers(settings)
    context = {
        "pv_samples": fetch_single_series_range(
            settings,
            f"avg({selector('pvPower_value', root, 'id=""')})",
            chunk.start_iso,
            chunk.end_iso,
            settings.raw_sample_step,
        ),
        "battery_samples": fetch_single_series_range(
            settings,
            f"avg_over_time(avg({selector('batteryPower_value', root, 'id=""')})[{settings.raw_sample_step}])",
            chunk.start_iso,
            chunk.end_iso,
            settings.raw_sample_step,
        ),
        "charge_loadpoint_matrix": fetch_series_range(
            settings,
            f"avg by (loadpoint) ({selector('chargePower_value', root, 'loadpoint!=""')})",
            chunk.start_iso,
            chunk.end_iso,
            settings.raw_sample_step,
        ),
        "ext_title_matrix": fetch_series_range(
            settings,
            f"avg by (title) ({selector('extPower_value', root, 'title!=""')})",
            chunk.start_iso,
            chunk.end_iso,
            settings.raw_sample_step,
        ),
        "aux_title_matrix": fetch_series_range(
            settings,
            f"avg by (title) ({selector('auxPower_value', root, 'title!=""')})",
            chunk.start_iso,
            chunk.end_iso,
            settings.raw_sample_step,
        ),
    }
    update_peak_memory()
    return context


def summarize_bucket_battery_energy(
    bucket_charge_samples: list[tuple[int, float]],
    bucket_discharge_samples: list[tuple[int, float]],
) -> dict[str, float]:
    charge_wh = sum(max(value, 0.0) for _, value in bucket_charge_samples) * 1000
    discharge_wh = sum(max(value, 0.0) for _, value in bucket_discharge_samples) * 1000
    return {
        "battery_charge_daily_energy": charge_wh,
        "battery_discharge_daily_energy": discharge_wh,
    }


def quarter_hour_price_rollups(
    grid_samples: list[tuple[int, float]],
    tariff_samples: list[tuple[int, float]],
    feed_in_tariff_samples: list[tuple[int, float]],
    bucket_starts: list[int],
    raw_step_seconds: int,
    bucket_minutes: int,
    import_kwh_override: float | None = None,
) -> dict[str, float | None]:
    bucket_seconds = bucket_minutes * 60
    bucket_prices: list[float] = []
    day_tariff_values: list[float] = []
    total_import_kwh = 0.0
    total_import_cost_eur = 0.0
    total_export_credit_eur = 0.0
    last_price: float | None = None
    last_feed_in_price: float | None = None

    grid_index = 0
    tariff_index = 0
    feed_in_index = 0
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

        while feed_in_index < len(feed_in_tariff_samples) and feed_in_tariff_samples[feed_in_index][0] < bucket_start:
            last_feed_in_price = feed_in_tariff_samples[feed_in_index][1]
            feed_in_index += 1

        bucket_feed_in_price = last_feed_in_price
        scan_index = feed_in_index
        while scan_index < len(feed_in_tariff_samples):
            timestamp, value = feed_in_tariff_samples[scan_index]
            if timestamp >= bucket_end:
                break
            if timestamp >= bucket_start:
                bucket_feed_in_price = value
            scan_index += 1
        feed_in_index = scan_index

        if bucket_price is not None:
            last_price = bucket_price
            bucket_prices.append(bucket_price)
        if bucket_feed_in_price is not None:
            last_feed_in_price = bucket_feed_in_price

        while grid_index < len(grid_samples) and grid_samples[grid_index][0] < bucket_start:
            grid_index += 1
        scan_index = grid_index
        bucket_import_kwh = 0.0
        bucket_export_kwh = 0.0
        while scan_index < len(grid_samples):
            timestamp, value = grid_samples[scan_index]
            if timestamp >= bucket_end:
                break
            if timestamp >= bucket_start and value > 0:
                bucket_import_kwh += value * raw_step_seconds / 3600000
            elif timestamp >= bucket_start and value < 0:
                bucket_export_kwh += (-value) * raw_step_seconds / 3600000
            scan_index += 1
        grid_index = scan_index

        if bucket_price is not None and bucket_import_kwh > 0:
            total_import_kwh += bucket_import_kwh
            total_import_cost_eur += bucket_import_kwh * bucket_price
        if bucket_feed_in_price is not None and bucket_export_kwh > 0:
            total_export_credit_eur += bucket_export_kwh * bucket_feed_in_price

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
    grid_import_cost_eur = total_import_cost_eur
    if import_kwh_override is not None and effective_price is not None:
        grid_import_cost_eur = import_kwh_override * effective_price / 100

    return {
        "grid_import_cost_daily": grid_import_cost_eur,
        "grid_import_price_avg_daily": arithmetic_avg,
        "grid_import_price_effective_daily": effective_price,
        "grid_import_price_min_daily": minimum_price,
        "grid_import_price_max_daily": maximum_price,
        "grid_export_credit_daily": total_export_credit_eur,
    }


def fetch_grid_energy_rollups(
    settings: Settings,
    window: DayWindow,
    context: dict[str, object] | None = None,
) -> dict[str, float]:
    start_ts = iso_to_timestamp(window.start_iso)
    end_ts = iso_to_timestamp(window.end_iso)
    if context is None:
        grid_samples = fetch_single_series_range(
            settings,
            f'avg_over_time(avg({selector("gridPower_value", base_matchers(settings))})[{settings.raw_sample_step}])',
            window.start_iso,
            window.end_iso,
            settings.raw_sample_step,
        )
        grid_energy_samples = fetch_single_series_range(
            settings,
            f'avg({selector("gridEnergy_value", base_matchers(settings))})',
            window.start_iso,
            window.end_iso,
            settings.raw_sample_step,
        )
    else:
        grid_samples = slice_samples(context["grid_samples"], start_ts, end_ts)
        grid_energy_samples = slice_samples(context["grid_energy_samples"], start_ts, end_ts)
    rollups = summarize_grid_energy_samples(grid_samples, parse_step_seconds(settings.energy_rollup_step))
    counter_import_wh = summarize_counter_spread_samples(grid_energy_samples)
    if counter_import_wh is not None:
        rollups["grid_import_daily_energy"] = counter_import_wh
    return rollups


def fetch_battery_energy_rollups(
    settings: Settings,
    window: DayWindow,
    context: dict[str, object] | None = None,
) -> dict[str, float]:
    start_ts = iso_to_timestamp(window.start_iso)
    end_ts = iso_to_timestamp(window.end_iso)
    if context is None:
        battery_samples = fetch_single_series_range(
            settings,
            f'avg_over_time(avg({selector("batteryPower_value", base_matchers(settings), "id=\"\"")})[{settings.raw_sample_step}])',
            window.start_iso,
            window.end_iso,
            settings.raw_sample_step,
        )
    else:
        battery_samples = slice_samples(context["battery_samples"], start_ts, end_ts)
    return summarize_battery_energy_samples(battery_samples, parse_step_seconds(settings.energy_rollup_step))


def fetch_chunk_price_context(settings: Settings, chunk: ChunkWindow) -> dict[str, object]:
    raw_step_seconds = parse_step_seconds(settings.raw_sample_step)
    extended_start_iso = to_iso_z(datetime.fromisoformat(chunk.start_iso.replace("Z", "+00:00")) - timedelta(minutes=settings.price_bucket_minutes))
    root = base_matchers(settings)
    context = {
        "raw_step_seconds": raw_step_seconds,
        "grid_samples": fetch_single_series_range(
            settings,
            f"avg_over_time(avg({selector('gridPower_value', root)})[{settings.raw_sample_step}])",
            chunk.start_iso,
            chunk.end_iso,
            settings.raw_sample_step,
        ),
        "grid_energy_samples": fetch_single_series_range(
            settings,
            f"avg({selector('gridEnergy_value', root)})",
            chunk.start_iso,
            chunk.end_iso,
            settings.raw_sample_step,
        ),
        "battery_samples": fetch_single_series_range(
            settings,
            f"avg_over_time(avg({selector('batteryPower_value', root, 'id=""')})[{settings.raw_sample_step}])",
            chunk.start_iso,
            chunk.end_iso,
            settings.raw_sample_step,
        ),
        "home_samples": fetch_single_series_range(
            settings,
            f"avg_over_time(avg({selector('homePower_value', root)})[{settings.raw_sample_step}])",
            chunk.start_iso,
            chunk.end_iso,
            settings.raw_sample_step,
        ),
        "charge_total_samples": fetch_single_series_range(
            settings,
            f"avg_over_time((sum(avg by (loadpoint) ({selector('chargePower_value', root, 'loadpoint!=""')})))[{settings.raw_sample_step}])",
            chunk.start_iso,
            chunk.end_iso,
            settings.raw_sample_step,
        ),
        "charge_vehicle_matrix": fetch_series_range(
            settings,
            f"avg by (vehicle) ({selector('chargePower_value', root, 'vehicle!=""')})",
            chunk.start_iso,
            chunk.end_iso,
            settings.raw_sample_step,
        ),
        "grid_tariff_samples": fetch_single_series_range(
            settings,
            f"avg({selector('tariffGrid_value', root)})",
            extended_start_iso,
            chunk.end_iso,
            settings.raw_sample_step,
        ),
        "feed_in_tariff_samples": fetch_single_series_range(
            settings,
            f"avg({selector('tariffFeedIn_value', root)})",
            extended_start_iso,
            chunk.end_iso,
            settings.raw_sample_step,
        ),
        "loadpoint_tariff_samples": fetch_single_series_range(
            settings,
            f"avg({selector('tariffPriceLoadpoints_value', root)})",
            extended_start_iso,
            chunk.end_iso,
            settings.raw_sample_step,
        ),
    }
    update_peak_memory()
    return context


def bucket_price_rollups(
    bucket_import_samples: list[tuple[int, float]],
    bucket_export_samples: list[tuple[int, float]],
    tariff_samples: list[tuple[int, float]],
    feed_in_tariff_samples: list[tuple[int, float]],
    bucket_starts: list[int],
    bucket_minutes: int,
) -> dict[str, float | None]:
    bucket_seconds = bucket_minutes * 60
    bucket_prices: list[float] = []
    day_tariff_values: list[float] = []
    total_import_kwh = 0.0
    total_import_cost_eur = 0.0
    total_export_credit_eur = 0.0
    last_price: float | None = None
    last_feed_in_price: float | None = None

    bucket_import_map = {timestamp: value for timestamp, value in bucket_import_samples}
    bucket_export_map = {timestamp: value for timestamp, value in bucket_export_samples}
    day_start = bucket_starts[0] if bucket_starts else 0
    day_end = (bucket_starts[-1] + bucket_seconds) if bucket_starts else 0

    for timestamp, value in tariff_samples:
        if day_start <= timestamp < day_end:
            day_tariff_values.append(value)

    tariff_index = 0
    feed_in_index = 0
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

        while feed_in_index < len(feed_in_tariff_samples) and feed_in_tariff_samples[feed_in_index][0] < bucket_start:
            last_feed_in_price = feed_in_tariff_samples[feed_in_index][1]
            feed_in_index += 1

        bucket_feed_in_price = last_feed_in_price
        scan_index = feed_in_index
        while scan_index < len(feed_in_tariff_samples):
            timestamp, value = feed_in_tariff_samples[scan_index]
            if timestamp >= bucket_end:
                break
            if timestamp >= bucket_start:
                bucket_feed_in_price = value
            scan_index += 1
        feed_in_index = scan_index

        if bucket_price is not None:
            last_price = bucket_price
            bucket_prices.append(bucket_price)
        if bucket_feed_in_price is not None:
            last_feed_in_price = bucket_feed_in_price

        bucket_import_kwh = max(bucket_import_map.get(bucket_end, 0.0), 0.0)
        bucket_export_kwh = max(bucket_export_map.get(bucket_end, 0.0), 0.0)
        if bucket_price is not None and bucket_import_kwh > 0:
            total_import_kwh += bucket_import_kwh
            total_import_cost_eur += bucket_import_kwh * bucket_price
        if bucket_feed_in_price is not None and bucket_export_kwh > 0:
            total_export_credit_eur += bucket_export_kwh * bucket_feed_in_price

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
        "grid_export_credit_daily": total_export_credit_eur,
    }


def fetch_grid_price_rollups(
    settings: Settings,
    window: DayWindow,
    context: dict[str, object] | None = None,
) -> dict[str, float | None]:
    raw_step_seconds = parse_step_seconds(settings.raw_sample_step)
    bucket_starts = bucket_start_timestamps(window, settings.price_bucket_minutes)
    start_ts = iso_to_timestamp(window.start_iso)
    end_ts = iso_to_timestamp(window.end_iso)
    if context is None:
        start_dt = datetime.fromisoformat(window.start_iso.replace("Z", "+00:00"))
        extended_start_iso = to_iso_z(start_dt - timedelta(minutes=settings.price_bucket_minutes))
        tariff_samples = fetch_single_series_range(
            settings,
            f'avg({selector("tariffGrid_value", base_matchers(settings))})',
            extended_start_iso,
            window.end_iso,
            settings.raw_sample_step,
        )
        feed_in_tariff_samples = fetch_single_series_range(
            settings,
            f'avg({selector("tariffFeedIn_value", base_matchers(settings))})',
            extended_start_iso,
            window.end_iso,
            settings.raw_sample_step,
        )
        grid_samples = fetch_single_series_range(
            settings,
            f'avg_over_time(avg({selector("gridPower_value", base_matchers(settings))})[{settings.raw_sample_step}])',
            window.start_iso,
            window.end_iso,
            settings.raw_sample_step,
        )
        grid_energy_samples = fetch_single_series_range(
            settings,
            f'avg({selector("gridEnergy_value", base_matchers(settings))})',
            window.start_iso,
            window.end_iso,
            settings.raw_sample_step,
        )
    else:
        tariff_samples = slice_samples(context["grid_tariff_samples"], start_ts, end_ts, include_last_before=True, max_lookback_seconds=settings.price_bucket_minutes * 60)
        feed_in_tariff_samples = slice_samples(context["feed_in_tariff_samples"], start_ts, end_ts, include_last_before=True, max_lookback_seconds=settings.price_bucket_minutes * 60)
        grid_samples = slice_samples(context["grid_samples"], start_ts, end_ts)
        grid_energy_samples = slice_samples(context["grid_energy_samples"], start_ts, end_ts)
    counter_import_wh = summarize_counter_spread_samples(grid_energy_samples)
    counter_import_kwh = (counter_import_wh / 1000.0) if counter_import_wh is not None else None
    return quarter_hour_price_rollups(
        grid_samples=grid_samples,
        tariff_samples=tariff_samples,
        feed_in_tariff_samples=feed_in_tariff_samples,
        bucket_starts=bucket_starts,
        raw_step_seconds=raw_step_seconds,
        bucket_minutes=settings.price_bucket_minutes,
        import_kwh_override=counter_import_kwh,
    )


def fetch_vehicle_price_rollups(
    settings: Settings,
    item: RollupMetric,
    window: DayWindow,
    context: dict[str, object] | None = None,
) -> list[tuple[dict[str, str], float]]:
    raw_step_seconds = parse_step_seconds(settings.raw_sample_step)
    bucket_starts = bucket_start_timestamps(window, settings.price_bucket_minutes)
    start_ts = iso_to_timestamp(window.start_iso)
    end_ts = iso_to_timestamp(window.end_iso)
    if context is None:
        start_dt = datetime.fromisoformat(window.start_iso.replace("Z", "+00:00"))
        extended_start_iso = to_iso_z(start_dt - timedelta(minutes=settings.price_bucket_minutes))
        grid_tariff_samples = fetch_single_series_range(
            settings,
            f'avg({selector("tariffGrid_value", base_matchers(settings))})',
            extended_start_iso,
            window.end_iso,
            settings.raw_sample_step,
        )
        charge_tariff_samples = fetch_single_series_range(
            settings,
            f'avg({selector("tariffPriceLoadpoints_value", base_matchers(settings))})',
            extended_start_iso,
            window.end_iso,
            settings.raw_sample_step,
        )
        charge_matrix = fetch_series_range(
            settings,
            f'avg by (vehicle) ({selector("chargePower_value", base_matchers(settings), "vehicle!=\"\"")})',
            window.start_iso,
            window.end_iso,
            settings.raw_sample_step,
        )
    else:
        grid_tariff_samples = slice_samples(context["grid_tariff_samples"], start_ts, end_ts, include_last_before=True, max_lookback_seconds=settings.price_bucket_minutes * 60)
        charge_tariff_samples = slice_samples(context["loadpoint_tariff_samples"], start_ts, end_ts, include_last_before=True, max_lookback_seconds=settings.price_bucket_minutes * 60)
        charge_matrix = slice_matrix_samples(context["charge_vehicle_matrix"], start_ts, end_ts)
    if item.key == "vehicle_charge_cost_daily":
        tariff_samples = charge_tariff_samples
    elif item.key == "potential_vehicle_charge_cost_daily":
        tariff_samples = grid_tariff_samples
    else:
        raise ValueError(f"Unsupported vehicle price rollup key: {item.key}")

    out: list[tuple[dict[str, str], float]] = []
    for result_item in charge_matrix:
        vehicle = str(result_item.get("metric", {}).get("vehicle", "")).strip()
        if not vehicle:
            continue
        rollups = quarter_hour_price_rollups(
            grid_samples=result_item["samples"],
            tariff_samples=tariff_samples,
            feed_in_tariff_samples=[],
            bucket_starts=bucket_starts,
            raw_step_seconds=raw_step_seconds,
            bucket_minutes=settings.price_bucket_minutes,
        )
        value = rollups.get("grid_import_cost_daily")
        if value is None or not math.isfinite(value):
            continue
        labels = base_daily_labels(settings, item.record, window)
        labels["vehicle"] = vehicle
        out.append((labels, value))
    return out


def fetch_aggregate_price_rollups(
    settings: Settings,
    item: RollupMetric,
    window: DayWindow,
    context: dict[str, object] | None = None,
) -> dict[str, float | None]:
    raw_step_seconds = parse_step_seconds(settings.raw_sample_step)
    bucket_starts = bucket_start_timestamps(window, settings.price_bucket_minutes)
    start_ts = iso_to_timestamp(window.start_iso)
    end_ts = iso_to_timestamp(window.end_iso)
    if context is None:
        start_dt = datetime.fromisoformat(window.start_iso.replace("Z", "+00:00"))
        extended_start_iso = to_iso_z(start_dt - timedelta(minutes=settings.price_bucket_minutes))
        grid_tariff_samples = fetch_single_series_range(
            settings,
            f'avg({selector("tariffGrid_value", base_matchers(settings))})',
            extended_start_iso,
            window.end_iso,
            settings.raw_sample_step,
        )
        feed_in_tariff_samples = fetch_single_series_range(
            settings,
            f'avg({selector("tariffFeedIn_value", base_matchers(settings))})',
            extended_start_iso,
            window.end_iso,
            settings.raw_sample_step,
        )
        home_samples = fetch_single_series_range(
            settings,
            f'avg_over_time(avg({selector("homePower_value", base_matchers(settings))})[{settings.raw_sample_step}])',
            window.start_iso,
            window.end_iso,
            settings.raw_sample_step,
        )
        charge_total_samples = fetch_single_series_range(
            settings,
            f'avg_over_time((sum(avg by (loadpoint) ({selector("chargePower_value", base_matchers(settings), "loadpoint!=\"\"")})))[{settings.raw_sample_step}])',
            window.start_iso,
            window.end_iso,
            settings.raw_sample_step,
        )
        battery_samples = fetch_single_series_range(
            settings,
            f'avg_over_time(avg({selector("batteryPower_value", base_matchers(settings), "id=\"\"")})[{settings.raw_sample_step}])',
            window.start_iso,
            window.end_iso,
            settings.raw_sample_step,
        )
    else:
        grid_tariff_samples = slice_samples(context["grid_tariff_samples"], start_ts, end_ts, include_last_before=True, max_lookback_seconds=settings.price_bucket_minutes * 60)
        feed_in_tariff_samples = slice_samples(context["feed_in_tariff_samples"], start_ts, end_ts, include_last_before=True, max_lookback_seconds=settings.price_bucket_minutes * 60)
        home_samples = slice_samples(context["home_samples"], start_ts, end_ts)
        charge_total_samples = slice_samples(context["charge_total_samples"], start_ts, end_ts)
        battery_samples = slice_samples(context["battery_samples"], start_ts, end_ts)
    if item.key == "potential_home_cost_daily":
        rollups = quarter_hour_price_rollups(
            grid_samples=home_samples,
            tariff_samples=grid_tariff_samples,
            feed_in_tariff_samples=[],
            bucket_starts=bucket_starts,
            raw_step_seconds=raw_step_seconds,
            bucket_minutes=settings.price_bucket_minutes,
        )
        return {item.key: rollups.get("grid_import_cost_daily")}
    if item.key == "potential_loadpoint_cost_daily":
        rollups = quarter_hour_price_rollups(
            grid_samples=charge_total_samples,
            tariff_samples=grid_tariff_samples,
            feed_in_tariff_samples=[],
            bucket_starts=bucket_starts,
            raw_step_seconds=raw_step_seconds,
            bucket_minutes=settings.price_bucket_minutes,
        )
        return {item.key: rollups.get("grid_import_cost_daily")}
    if item.key == "battery_discharge_value_daily":
        discharge_samples = [(ts, max(value, 0.0)) for ts, value in battery_samples]
        rollups = quarter_hour_price_rollups(
            grid_samples=discharge_samples,
            tariff_samples=grid_tariff_samples,
            feed_in_tariff_samples=[],
            bucket_starts=bucket_starts,
            raw_step_seconds=raw_step_seconds,
            bucket_minutes=settings.price_bucket_minutes,
        )
        return {item.key: rollups.get("grid_import_cost_daily")}
    if item.key == "battery_charge_feedin_cost_daily":
        charge_samples = [(ts, max(-value, 0.0)) for ts, value in battery_samples]
        total_cost = 0.0
        bucket_seconds = settings.price_bucket_minutes * 60
        last_price = None
        idx = 0
        for bucket_start in bucket_starts:
            bucket_end = bucket_start + bucket_seconds
            while idx < len(feed_in_tariff_samples) and feed_in_tariff_samples[idx][0] < bucket_start:
                last_price = feed_in_tariff_samples[idx][1]
                idx += 1
            bucket_price = last_price
            scan = idx
            while scan < len(feed_in_tariff_samples):
                ts, val = feed_in_tariff_samples[scan]
                if ts >= bucket_end:
                    break
                if ts >= bucket_start:
                    bucket_price = val
                scan += 1
            idx = scan
            if bucket_price is None:
                continue
            bucket_kwh = 0.0
            for ts, value in charge_samples:
                if bucket_start <= ts < bucket_end:
                    bucket_kwh += value * raw_step_seconds / 3600000.0
            total_cost += bucket_kwh * bucket_price
        return {item.key: total_cost}
    raise ValueError(f"Unsupported aggregate price rollup key: {item.key}")


def window_local_labels(window: DayWindow) -> dict[str, str]:
    return {
        "local_year": window.local_year,
        "local_month": window.local_month,
    }


def base_daily_labels(settings: Settings, record: str, window: DayWindow) -> dict[str, str]:
    _ = settings
    labels: dict[str, str] = {
        "__name__": record,
    }
    labels.update(window_local_labels(window))
    return labels


def normalize_rollup_labels(settings: Settings, item: RollupMetric, metric: dict, window: DayWindow) -> dict[str, str]:
    labels = base_daily_labels(settings, item.record, window)
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


def add_duration(profile: dict[str, float], key: str, started_at: float) -> None:
    profile[key] = profile.get(key, 0.0) + (time.perf_counter() - started_at)


def mean_of_top(values: list[float], limit: int) -> float | None:
    finite = [value for value in values if math.isfinite(value)]
    if not finite:
        return None
    top_values = sorted(finite, reverse=True)[:limit]
    if not top_values:
        return None
    return sum(top_values) / len(top_values)


def build_pv_health_rollups(
    settings: Settings,
    pv_daily_values_by_year: dict[str, dict[str, object]],
    pv_daily_values_by_year_month: dict[tuple[str, str], dict[str, object]],
) -> list[dict]:
    series_rows: list[dict] = []
    yearly_record = record_name(settings, "pv_top30_mean_yearly_wh")
    monthly_record = record_name(settings, "pv_top5_mean_monthly_wh")

    for local_year, payload in sorted(pv_daily_values_by_year.items()):
        value = mean_of_top(payload.get("values", []), 30)
        timestamp_ms = int(payload.get("timestamp_ms", 0) or 0)
        if value is None or timestamp_ms <= 0:
            continue
        series_rows.append(
            {
                "metric": {
                    "__name__": yearly_record,
                    "local_year": local_year,
                },
                "values": [value],
                "timestamps": [timestamp_ms],
            }
        )

    for (local_year, local_month), payload in sorted(pv_daily_values_by_year_month.items()):
        value = mean_of_top(payload.get("values", []), 5)
        timestamp_ms = int(payload.get("timestamp_ms", 0) or 0)
        if value is None or timestamp_ms <= 0:
            continue
        series_rows.append(
            {
                "metric": {
                    "__name__": monthly_record,
                    "local_year": local_year,
                    "local_month": local_month,
                },
                "values": [value],
                "timestamps": [timestamp_ms],
            }
        )

    return series_rows


def backfill(settings: Settings, args: argparse.Namespace) -> int:
    if not args.start_day or not args.end_day:
        raise SystemExit("backfill requires --start-day and --end-day.")
    if args.batch_size < 1:
        raise SystemExit("--batch-size must be at least 1.")

    total_started_at = time.perf_counter()
    global ACTIVE_PROFILE
    ACTIVE_PROFILE = {
        "build_windows_s": 0.0,
        "memory_peak_mb": 0.0,
        "memory_last_mb": 0.0,
        "build_chunks_s": 0.0,
        "build_catalog_s": 0.0,
        "chunk_processing_s": 0.0,
        "window_processing_s": 0.0,
        "vehicle_distance_s": 0.0,
        "battery_soc_s": 0.0,
        "positive_energy_s": 0.0,
        "price_rollups_s": 0.0,
        "vehicle_price_s": 0.0,
        "aggregate_price_s": 0.0,
        "grid_energy_s": 0.0,
        "battery_energy_s": 0.0,
        "consumer_attribution_s": 0.0,
        "generic_rollup_s": 0.0,
        "import_s": 0.0,
        "health_rollup_s": 0.0,
    }
    update_peak_memory()
    started_at = time.perf_counter()
    start_day = parse_local_day(args.start_day, "--start-day")
    end_day = parse_local_day(args.end_day, "--end-day")
    write_safety = validate_backfill_write_window(settings, args, end_day)
    windows = build_day_windows(settings, start_day, end_day)
    replace_summary = []
    if getattr(args, "replace_range", False):
        validate_month_replace_range(settings, start_day, end_day)
        replace_summary = delete_rollup_scopes(settings, build_month_scopes(settings, windows), args.write)
    add_duration(ACTIVE_PROFILE, "build_windows_s", started_at)
    started_at = time.perf_counter()
    chunks = build_window_chunks(windows)
    add_duration(ACTIVE_PROFILE, "build_chunks_s", started_at)
    started_at = time.perf_counter()
    catalog = [item for item in build_catalog(settings) if item.implemented]
    add_duration(ACTIVE_PROFILE, "build_catalog_s", started_at)

    previous_vehicle_odometer: dict[str, float] = {}
    seen_series_keys: set[tuple[tuple[str, str], ...]] = set()
    import_results = []
    chunk_summaries = []
    skipped = 0
    skip_reasons: dict[str, int] = {}
    invalid_examples: list[dict[str, str]] = []
    emitted_samples = 0
    total_batches = 0
    processed_days = 0
    pv_daily_values_by_year: dict[str, dict[str, object]] = {}
    pv_daily_values_by_year_month: dict[tuple[str, str], dict[str, object]] = {}
    legacy_positive_energy_metric_keys = {
        "pv_daily_energy",
        "home_daily_energy",
    }
    direct_positive_energy_metric_keys = {
        "loadpoint_daily_energy",
        "vehicle_daily_energy",
        "ext_daily_energy",
        "aux_daily_energy",
    }
    price_metric_keys = {
        "grid_import_cost_daily",
        "grid_import_price_avg_daily",
        "grid_import_price_effective_daily",
        "grid_import_price_min_daily",
        "grid_import_price_max_daily",
        "grid_export_credit_daily",
    }
    vehicle_price_metric_keys = {
        "vehicle_charge_cost_daily",
        "potential_vehicle_charge_cost_daily",
    }
    aggregate_price_metric_keys = {
        "potential_home_cost_daily",
        "potential_loadpoint_cost_daily",
        "battery_discharge_value_daily",
        "battery_charge_feedin_cost_daily",
    }
    grid_energy_metric_keys = {
        "grid_import_daily_energy",
        "grid_export_daily_energy",
    }
    battery_energy_metric_keys = {
        "battery_charge_daily_energy",
        "battery_discharge_daily_energy",
    }
    attribution_metric_keys = {
        "loadpoint_daily_energy_from_pv",
        "loadpoint_daily_energy_from_battery",
        "loadpoint_daily_energy_from_grid",
        "ext_daily_energy_from_pv",
        "ext_daily_energy_from_battery",
        "ext_daily_energy_from_grid",
        "aux_daily_energy_from_pv",
        "aux_daily_energy_from_battery",
        "aux_daily_energy_from_grid",
    }

    for chunk_index, (chunk_name, chunk_windows) in enumerate(chunks, start=1):
        chunk_started_at = time.perf_counter()
        series_map: dict[tuple[tuple[str, str], ...], dict] = {}
        chunk_start_samples = emitted_samples
        chunk_start_skipped = skipped
        chunk_start_skip_reasons = dict(skip_reasons)
        fetch_blocks, fetch_block_by_day = build_fetch_blocks(
            chunk_name,
            chunk_windows,
            parse_step_seconds(settings.raw_sample_step),
            settings.max_fetch_points_per_series,
        )
        shared_price_contexts: dict[str, dict[str, object]] = {}
        attribution_contexts: dict[str, dict[str, object]] = {}
        positive_energy_contexts: dict[tuple[str, str], list[dict]] = {}

        update_peak_memory()
        if args.progress:
            print(
                f"[chunk {chunk_index}/{len(chunks)}] start {chunk_name} days={len(chunk_windows)}",
                file=sys.stderr,
                flush=True,
            )

        for window in chunk_windows:
            window_started_at = time.perf_counter()
            processed_days += 1
            fetch_block = fetch_block_by_day[window.day]
            price_rollups: dict[str, float | None] | None = None
            grid_energy_rollups: dict[str, float] | None = None
            battery_energy_rollups: dict[str, float] | None = None
            attribution_rollups: dict[str, list[tuple[dict[str, str], float]]] | None = None
            shared_price_context = shared_price_contexts.get(fetch_block.name)
            for item in catalog:
                if item.key == "vehicle_daily_distance":
                    started_at = time.perf_counter()
                    for result_item in fetch_vehicle_odometer_vector(settings, window):
                        value = sample_value(result_item)
                        if value is None:
                            skipped += 1
                            bump_skip_reason(skip_reasons, "no_data")
                            continue
                        vehicle = str(result_item.get("metric", {}).get("vehicle", "")).strip()
                        if not vehicle:
                            skipped += 1
                            bump_skip_reason(skip_reasons, "missing_label")
                            continue
                        previous_value = previous_vehicle_odometer.get(vehicle)
                        previous_vehicle_odometer[vehicle] = value
                        if previous_value is None:
                            continue
                        delta = value - previous_value
                        if not math.isfinite(delta) or delta < 0:
                            skipped += 1
                            bump_skip_reason(skip_reasons, "invalid_value")
                            record_invalid_example(invalid_examples, item.record, window.day, "negative_or_non_finite_delta", vehicle)
                            continue
                        labels = base_daily_labels(settings, item.record, window)
                        labels["vehicle"] = vehicle
                        append_series_sample(
                            series_map,
                            labels,
                            window.sample_timestamp_ms,
                            delta,
                        )
                        emitted_samples += 1
                    add_duration(ACTIVE_PROFILE, "vehicle_distance_s", started_at)
                    continue
                if item.key in {"battery_soc_daily_min", "battery_soc_daily_max"}:
                    started_at = time.perf_counter()
                    day_min, day_max = fetch_battery_soc_extrema(settings, window)
                    selected_value = day_min if item.key == "battery_soc_daily_min" else day_max
                    if selected_value is None:
                        skipped += 1
                        bump_skip_reason(skip_reasons, "no_data")
                        continue
                    append_series_sample(
                        series_map,
                        base_daily_labels(settings, item.record, window),
                        window.sample_timestamp_ms,
                        selected_value,
                    )
                    emitted_samples += 1
                    add_duration(ACTIVE_PROFILE, "battery_soc_s", started_at)
                    continue
                if item.key in legacy_positive_energy_metric_keys:
                    started_at = time.perf_counter()
                    matrix_cache_key = (fetch_block.name, item.key)
                    matrix = positive_energy_contexts.get(matrix_cache_key)
                    if matrix is None:
                        matrix = fetch_chunk_positive_energy_matrix(settings, item, fetch_block)
                        positive_energy_contexts[matrix_cache_key] = matrix
                    result_items = summarize_legacy_positive_energy_rollups_from_matrix(settings, item, window, matrix)
                    if not result_items:
                        skipped += 1
                        bump_skip_reason(skip_reasons, "no_data")
                        add_duration(ACTIVE_PROFILE, "positive_energy_s", started_at)
                        continue
                    for labels, value in result_items:
                        append_series_sample(
                            series_map,
                            labels,
                            window.sample_timestamp_ms,
                            value,
                        )
                        if item.key == "pv_daily_energy":
                            year_bucket = pv_daily_values_by_year.setdefault(
                                window.local_year,
                                {"values": [], "timestamp_ms": 0},
                            )
                            year_bucket["values"].append(value)
                            year_bucket["timestamp_ms"] = max(int(year_bucket["timestamp_ms"]), window.sample_timestamp_ms)
                            month_key = (window.local_year, window.local_month)
                            month_bucket = pv_daily_values_by_year_month.setdefault(
                                month_key,
                                {"values": [], "timestamp_ms": 0},
                            )
                            month_bucket["values"].append(value)
                            month_bucket["timestamp_ms"] = max(int(month_bucket["timestamp_ms"]), window.sample_timestamp_ms)
                        emitted_samples += 1
                    add_duration(ACTIVE_PROFILE, "positive_energy_s", started_at)
                    continue
                if item.key in direct_positive_energy_metric_keys:
                    started_at = time.perf_counter()
                    result_items = fetch_rollup_vector(settings, item, window)
                    if not result_items:
                        skipped += 1
                        bump_skip_reason(skip_reasons, "no_data")
                        add_duration(ACTIVE_PROFILE, "positive_energy_s", started_at)
                        continue
                    for result_item in result_items:
                        value = sample_value(result_item)
                        if value is None or not math.isfinite(value):
                            skipped += 1
                            bump_skip_reason(skip_reasons, "invalid_value" if value is not None else "no_data")
                            if value is not None:
                                record_invalid_example(invalid_examples, item.record, window.day, "non_finite_result")
                            continue
                        labels = normalize_rollup_labels(settings, item, result_item.get("metric", {}), window)
                        append_series_sample(
                            series_map,
                            labels,
                            window.sample_timestamp_ms,
                            value,
                        )
                        emitted_samples += 1
                    add_duration(ACTIVE_PROFILE, "positive_energy_s", started_at)
                    continue
                if item.key in price_metric_keys:
                    started_at = time.perf_counter()
                    if shared_price_context is None:
                        shared_price_context = fetch_chunk_price_context(settings, fetch_block)
                        shared_price_contexts[fetch_block.name] = shared_price_context
                    if price_rollups is None:
                        price_rollups = fetch_grid_price_rollups(settings, window, shared_price_context)
                    selected_value = price_rollups.get(item.key)
                    if selected_value is None or not math.isfinite(selected_value):
                        skipped += 1
                        bump_skip_reason(skip_reasons, "no_data" if selected_value is None else "invalid_value")
                        if selected_value is not None:
                            record_invalid_example(invalid_examples, item.record, window.day, "non_finite_result")
                        continue
                    append_series_sample(
                        series_map,
                        base_daily_labels(settings, item.record, window),
                        window.sample_timestamp_ms,
                        selected_value,
                    )
                    emitted_samples += 1
                    add_duration(ACTIVE_PROFILE, "price_rollups_s", started_at)
                    continue
                if item.key in vehicle_price_metric_keys:
                    started_at = time.perf_counter()
                    if shared_price_context is None:
                        shared_price_context = fetch_chunk_price_context(settings, fetch_block)
                        shared_price_contexts[fetch_block.name] = shared_price_context
                    for labels, value in fetch_vehicle_price_rollups(settings, item, window, shared_price_context):
                        if not math.isfinite(value):
                            skipped += 1
                            bump_skip_reason(skip_reasons, "invalid_value")
                            record_invalid_example(invalid_examples, item.record, window.day, "non_finite_result")
                            continue
                        append_series_sample(
                            series_map,
                            labels,
                            window.sample_timestamp_ms,
                            value,
                        )
                        emitted_samples += 1
                    add_duration(ACTIVE_PROFILE, "vehicle_price_s", started_at)
                    continue
                if item.key in aggregate_price_metric_keys:
                    started_at = time.perf_counter()
                    if shared_price_context is None:
                        shared_price_context = fetch_chunk_price_context(settings, fetch_block)
                        shared_price_contexts[fetch_block.name] = shared_price_context
                    aggregate_price_rollups = fetch_aggregate_price_rollups(settings, item, window, shared_price_context)
                    selected_value = aggregate_price_rollups.get(item.key)
                    if selected_value is None or not math.isfinite(selected_value):
                        skipped += 1
                        bump_skip_reason(skip_reasons, "no_data" if selected_value is None else "invalid_value")
                        if selected_value is not None:
                            record_invalid_example(invalid_examples, item.record, window.day, "non_finite_result")
                        continue
                    append_series_sample(
                        series_map,
                        base_daily_labels(settings, item.record, window),
                        window.sample_timestamp_ms,
                        selected_value,
                    )
                    emitted_samples += 1
                    add_duration(ACTIVE_PROFILE, "aggregate_price_s", started_at)
                    continue
                if item.key in grid_energy_metric_keys:
                    started_at = time.perf_counter()
                    if shared_price_context is None:
                        shared_price_context = fetch_chunk_price_context(settings, fetch_block)
                        shared_price_contexts[fetch_block.name] = shared_price_context
                    if grid_energy_rollups is None:
                        grid_energy_rollups = fetch_grid_energy_rollups(settings, window, shared_price_context)
                    selected_value = grid_energy_rollups.get(item.key)
                    if selected_value is None or not math.isfinite(selected_value):
                        skipped += 1
                        bump_skip_reason(skip_reasons, "no_data" if selected_value is None else "invalid_value")
                        if selected_value is not None:
                            record_invalid_example(invalid_examples, item.record, window.day, "non_finite_result")
                        continue
                    append_series_sample(
                        series_map,
                        base_daily_labels(settings, item.record, window),
                        window.sample_timestamp_ms,
                        selected_value,
                    )
                    emitted_samples += 1
                    add_duration(ACTIVE_PROFILE, "grid_energy_s", started_at)
                    continue
                if item.key in battery_energy_metric_keys:
                    started_at = time.perf_counter()
                    if shared_price_context is None:
                        shared_price_context = fetch_chunk_price_context(settings, fetch_block)
                        shared_price_contexts[fetch_block.name] = shared_price_context
                    if battery_energy_rollups is None:
                        battery_energy_rollups = fetch_battery_energy_rollups(settings, window, shared_price_context)
                    selected_value = battery_energy_rollups.get(item.key)
                    if selected_value is None or not math.isfinite(selected_value):
                        skipped += 1
                        bump_skip_reason(skip_reasons, "no_data" if selected_value is None else "invalid_value")
                        if selected_value is not None:
                            record_invalid_example(invalid_examples, item.record, window.day, "non_finite_result")
                        continue
                    append_series_sample(
                        series_map,
                        base_daily_labels(settings, item.record, window),
                        window.sample_timestamp_ms,
                        selected_value,
                    )
                    emitted_samples += 1
                    add_duration(ACTIVE_PROFILE, "battery_energy_s", started_at)
                    continue
                if item.key in attribution_metric_keys:
                    started_at = time.perf_counter()
                    attribution_context = attribution_contexts.get(fetch_block.name)
                    if attribution_context is None:
                        attribution_context = fetch_chunk_consumer_attribution_context(settings, fetch_block)
                        attribution_contexts[fetch_block.name] = attribution_context
                    if attribution_rollups is None:
                        attribution_rollups = summarize_consumer_source_attribution_rollups(settings, window, attribution_context)
                    for labels, value in attribution_rollups.get(item.key, []):
                        if not math.isfinite(value):
                            skipped += 1
                            bump_skip_reason(skip_reasons, "invalid_value")
                            record_invalid_example(invalid_examples, item.record, window.day, "non_finite_result")
                            continue
                        append_series_sample(
                            series_map,
                            labels,
                            window.sample_timestamp_ms,
                            value,
                        )
                        emitted_samples += 1
                    add_duration(ACTIVE_PROFILE, "consumer_attribution_s", started_at)
                    continue
                started_at = time.perf_counter()
                for result_item in fetch_rollup_vector(settings, item, window):
                    value = sample_value(result_item)
                    if value is None:
                        skipped += 1
                        bump_skip_reason(skip_reasons, "no_data")
                        continue
                    labels = normalize_rollup_labels(settings, item, result_item.get("metric", {}), window)
                    append_series_sample(series_map, labels, window.sample_timestamp_ms, value)
                    emitted_samples += 1
                add_duration(ACTIVE_PROFILE, "generic_rollup_s", started_at)
            update_peak_memory()
            add_duration(ACTIVE_PROFILE, "window_processing_s", window_started_at)

        seen_series_keys.update(series_map.keys())
        series_rows = list(series_map.values())
        batches = chunked(series_rows, args.batch_size)
        total_batches += len(batches)

        if args.write and batches:
            import_started_at = time.perf_counter()
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
            add_duration(ACTIVE_PROFILE, "import_s", import_started_at)

        chunk_summary = {
            "chunk": chunk_name,
            "days": len(chunk_windows),
            "samples": emitted_samples - chunk_start_samples,
            "series": len(series_rows),
            "skipped": skipped - chunk_start_skipped,
            "skip_reasons": diff_skip_reasons(skip_reasons, chunk_start_skip_reasons),
            "batches": len(batches),
            "duration_s": round(time.perf_counter() - chunk_started_at, 6),
        }
        chunk_summaries.append(chunk_summary)
        update_peak_memory()
        add_duration(ACTIVE_PROFILE, "chunk_processing_s", chunk_started_at)

        update_peak_memory()
        if args.progress:
            skip_reason_text = ""
            if chunk_summary["skipped"] > 0 and chunk_summary.get("skip_reasons"):
                top_reason = max(chunk_summary["skip_reasons"].items(), key=lambda pair: pair[1])
                skip_reason_text = f" top-skip={top_reason[0]}:{top_reason[1]}"
            print(
                f"[chunk {chunk_index}/{len(chunks)}] done {chunk_name} days={processed_days}/{len(windows)} samples={chunk_summary['samples']} series={chunk_summary['series']} skipped={chunk_summary['skipped']} batches={chunk_summary['batches']}{skip_reason_text}",
                file=sys.stderr,
                flush=True,
            )

    health_started_at = time.perf_counter()
    health_series_rows = build_pv_health_rollups(
        settings,
        pv_daily_values_by_year,
        pv_daily_values_by_year_month,
    )
    add_duration(ACTIVE_PROFILE, "health_rollup_s", health_started_at)
    if args.write and health_series_rows:
        for batch_index, batch in enumerate(chunked(health_series_rows, args.batch_size), start=1):
            response = http_post_bytes(settings, "/api/v1/import", serialize_import_jsonl(batch))
            import_results.append(
                {
                    "chunk": "health",
                    "batch": batch_index,
                    "status_code": response.status_code,
                    "body": response.body.strip(),
                    "series": len(batch),
                }
            )
        total_batches += len(chunked(health_series_rows, args.batch_size))
    seen_series_keys.update(tuple(sorted(row["metric"].items())) for row in health_series_rows)
    update_peak_memory()
    ACTIVE_PROFILE["total_s"] = time.perf_counter() - total_started_at

    summary = {
        "script": script_metadata(),
        "mode": "write" if args.write else "dry-run",
        "timezone": settings.timezone,
        "raw_sample_step": settings.raw_sample_step,
        "energy_rollup_step": settings.energy_rollup_step,
        "price_bucket_minutes": settings.price_bucket_minutes,
        "max_fetch_points_per_series": settings.max_fetch_points_per_series,
        "range": {
            "start_day": start_day.isoformat(),
            "end_day": end_day.isoformat(),
            "days": len(windows),
        },
        "write_safety": write_safety,
        "replace_range": bool(getattr(args, "replace_range", False)),
        "replace_delete_results": replace_summary,
        "metrics": [item.record for item in catalog] + [
            record_name(settings, "pv_top30_mean_yearly_wh"),
            record_name(settings, "pv_top5_mean_monthly_wh"),
        ],
        "samples": emitted_samples,
        "series": len(seen_series_keys),
        "skipped": skipped,
        "skip_reasons": dict(sorted(skip_reasons.items())),
        "invalid_examples": invalid_examples,
        "chunks": chunk_summaries,
        "batches": total_batches,
        "batch_size": args.batch_size,
        "import_results": import_results,
        "profile": {key: round(float(value), 6) for key, value in ACTIVE_PROFILE.items()},
    }
    if args.json:
        print(json.dumps(summary, indent=2, ensure_ascii=True))
    else:
        print_backfill_summary(summary, args)
    return 0


def delete_rollups(settings: Settings, args: argparse.Namespace) -> int:
    if not args.start_day or not args.end_day:
        raise SystemExit("delete requires --start-day and --end-day.")
    if getattr(args, "replace_range", False):
        raise SystemExit("delete does not use --replace-range. Use delete --write to execute deletion.")

    start_day = parse_local_day(args.start_day, "--start-day")
    end_day = parse_local_day(args.end_day, "--end-day")
    if end_day < start_day:
        raise SystemExit("--end-day must not be earlier than --start-day.")
    validate_month_replace_range(settings, start_day, end_day)
    windows = build_day_windows(settings, start_day, end_day)
    scopes = build_month_scopes(settings, windows)
    delete_results = delete_rollup_scopes(settings, scopes, args.write)
    summary = {
        "script": script_metadata(),
        "mode": "write" if args.write else "dry-run",
        "timezone": settings.timezone,
        "range": {
            "start_day": start_day.isoformat(),
            "end_day": end_day.isoformat(),
            "days": len(windows),
        },
        "delete_results": delete_results,
    }
    if args.json:
        print(json.dumps(summary, indent=2, ensure_ascii=True))
    else:
        print_delete_summary(summary, args)
    return 0


def print_delete_summary(summary: dict, args: argparse.Namespace) -> None:
    print_report_header(
        f"EVCC rollup delete {'write' if args.write else 'dry-run'}",
        "========================",
        str(summary.get("script", {}).get("generated_at", "")) or None,
    )
    print(f"Range:    {summary['range']['start_day']} -> {summary['range']['end_day']}")
    print(f"Days:     {summary['range']['days']}")
    print(f"Timezone: {summary['timezone']}")
    print("\nMonthly rollup scopes")
    print("---------------------")
    for item in summary.get("delete_results", []):
        print(
            f"- {item['local_year']}-{item['local_month']}: {item['status']}, "
            f"series_before={item['series_before']}, series_after={item['series_after']}"
        )
        print(f"  matcher: {item['matcher']}")

    print("\nResult")
    print("------")
    if args.write:
        print("OK: matching monthly rollup scopes were deleted.")
    else:
        print("GO: dry-run completed. Rerun with --write to delete these monthly rollup scopes.")


def bump_skip_reason(skip_reasons: dict[str, int], reason: str) -> None:
    skip_reasons[reason] = skip_reasons.get(reason, 0) + 1


def record_invalid_example(
    invalid_examples: list[dict[str, str]],
    metric: str,
    day: str,
    reason: str,
    detail: str = "",
    limit: int = 5,
) -> None:
    if len(invalid_examples) >= limit:
        return
    entry = {"metric": metric, "day": day, "reason": reason}
    if detail:
        entry["detail"] = detail
    invalid_examples.append(entry)


def diff_skip_reasons(current: dict[str, int], snapshot: dict[str, int]) -> dict[str, int]:
    keys = set(current) | set(snapshot)
    return {key: current.get(key, 0) - snapshot.get(key, 0) for key in sorted(keys) if current.get(key, 0) - snapshot.get(key, 0) > 0}


def top_skip_reason_text(skip_reasons: dict[str, int]) -> str:
    if not skip_reasons:
        return ""
    top_reason = max(skip_reasons.items(), key=lambda pair: pair[1])
    return f"{top_reason[0]}:{top_reason[1]}"


def print_backfill_summary(summary: dict, args: argparse.Namespace) -> None:
    profile = summary.get("profile", {})
    total_s = float(profile.get("total_s", 0.0) or 0.0)
    peak_memory = profile.get("memory_peak_mb")
    chunks = summary.get("chunks", [])
    slowest_chunks = sorted(chunks, key=lambda item: float(item.get("duration_s", 0.0)), reverse=True)[:5]
    skipped_chunks = [item for item in chunks if int(item.get("skipped", 0)) > 0]
    most_skipped_chunks = sorted(skipped_chunks, key=lambda item: int(item.get("skipped", 0)), reverse=True)[:5]

    print_report_header(
        f"EVCC rollup {'write' if args.write else 'dry-run'}",
        "===========================",
        str(summary.get("script", {}).get("generated_at", "")) or None,
    )
    print(f"Range:        {summary['range']['start_day']} -> {summary['range']['end_day']}")
    print(f"Days:         {summary['range']['days']}")
    print(f"Timezone:     {summary['timezone']}")
    write_safety = summary.get("write_safety", {})
    if write_safety:
        print(f"Latest safe:  {write_safety.get('latest_completed_day')} (completed local day)")
    print(f"Raw step:     {summary['raw_sample_step']}")
    print(f"Energy step:  {summary['energy_rollup_step']}")
    print(f"Batch size:   {summary['batch_size']}")
    if summary.get("replace_range"):
        print("Replace mode: enabled")

    print("\nSummary")
    print("-------")
    print(f"- Rollup metrics: {len(summary['metrics'])}")
    print(f"- Output series: {summary['series']}")
    print(f"- Output samples: {summary['samples']}")
    print(f"- Skipped items: {summary['skipped']}")
    print(f"- Month chunks: {len(chunks)}")
    skip_reasons = summary.get("skip_reasons", {})
    print(f"- Import batches: {summary['batches']}")
    print(f"- Total runtime: {round(total_s, 2)} s")
    if peak_memory is not None:
        print(f"- Peak RAM: {round(float(peak_memory), 2)} MB")

    replace_results = summary.get("replace_delete_results", [])
    if replace_results:
        print("\nReplace deletes")
        print("---------------")
        for item in replace_results:
            print(
                f"- {item['local_year']}-{item['local_month']}: {item['status']}, "
                f"series_before={item['series_before']}, series_after={item['series_after']}"
            )

    if skip_reasons:
        print("\nSkip reasons")
        print("------------")
        labels = {
            "no_data": "No usable source data for that rollup/day",
            "invalid_value": "Computed or fetched value was invalid",
            "missing_label": "Required business label was missing",
        }
        for key, count in skip_reasons.items():
            print(f"- {labels.get(key, key)}: {count}")

    if slowest_chunks:
        print("\nSlowest chunks")
        print("-------------")
        for item in slowest_chunks:
            skip_reason_text = ""
            if item.get("skip_reasons"):
                top_reason = max(item["skip_reasons"].items(), key=lambda pair: pair[1])
                skip_reason_text = f", top-skip={top_reason[0]}:{top_reason[1]}"
            print(
                f"- {item['chunk']}: {item['duration_s']} s, samples={item['samples']}, "
                f"series={item['series']}, skipped={item['skipped']}{skip_reason_text}"
            )

    print("\nInterpretation")
    print("--------------")
    print("- 'Skipped items' are grouped below so you can see whether they mostly come from missing source data, invalid values, or missing labels.")
    if args.write:
        print("- Write mode calculated the rollups and imported the resulting evcc_* metrics into VictoriaMetrics.")
        if summary.get("replace_range"):
            print("- Replace mode deleted the affected monthly rollup scopes before importing fresh samples.")
    else:
        print("- Dry-run mode calculates the rollups but does not write any evcc_* metrics.")
        if summary.get("replace_range"):
            print("- Replace mode is dry-run only here: planned deletes were counted but not executed.")
        print("- If this dry-run looks plausible, the next step is the same command with --write.")

    print("\nResult")
    print("------")
    if summary['samples'] <= 0 or summary['series'] <= 0:
        print("NO-GO: the dry-run produced no rollup output. Review detect/plan and the raw data first.")
        return

    if peak_memory is not None and float(peak_memory) >= 3072.0:
        if args.write:
            print("OK WITH CAUTION: write completed, but peak memory was high. Check system headroom before repeating the run.")
        else:
            print("GO WITH CAUTION: dry-run succeeded, but peak memory was high. Consider a smaller range or batch size before --write.")
        return

    if args.write:
        print("OK: write completed successfully.")
    else:
        print("GO: dry-run completed successfully. The setup is ready for the real write run.")


def main() -> int:
    args = parse_args()
    settings = load_settings(args.config)

    if args.command == "detect":
        return print_detect(settings, as_json=args.json)
    if args.command == "plan":
        return print_plan(settings, as_json=args.json)
    if args.command == "benchmark":
        return run_benchmark(settings, as_json=args.json)
    if args.command == "backfill":
        return backfill(settings, args)
    if args.command == "delete":
        return delete_rollups(settings, args)

    raise AssertionError(f"Unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())





