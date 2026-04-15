#!/usr/bin/env python3
"""Validate cached Tibber, Influx, VictoriaMetrics, and VRM comparison data.

This script is the reproducible offline validation entry point for external
energy comparison snapshots. It intentionally reads local cache files from
data/energy-comparison instead of calling Tibber or VRM APIs by default.

Use compare_tibber_vm.py and fetch_vrm_kwh_cache.py to refresh the source
snapshots. This validator then applies the documented exclusions and reports
whether the cached dashboard/rollup comparisons are still inside the expected
tolerances.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import os
import sys
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple
from zoneinfo import ZoneInfo

SCRIPT_NAME = "validate_energy_comparison.py"
SCRIPT_VERSION = "2026.04.15.1"
SCRIPT_LAST_MODIFIED = "2026-04-15"
UTC = dt.timezone.utc
ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TIBBER_DIR = ROOT / "data" / "energy-comparison" / "tibber"
DEFAULT_VRM_DIR = ROOT / "data" / "energy-comparison" / "vrm"
DEFAULT_EXCLUDED_MONTHS = ("2025-04", "2025-10")
EXCLUDED_MONTH_RATIONALE = {
    "2025-04": "documented Tibber/EVCC transition anomaly; exclude from dashboard accuracy validation",
    "2025-10": "documented Tibber billing/import anomaly; exclude from dashboard accuracy validation",
}


@dataclass(frozen=True)
class MonthlyCostRow:
    period: str
    reference_kwh: Optional[float]
    candidate_kwh: Optional[float]
    delta_kwh: Optional[float]
    reference_eur: Optional[float]
    candidate_eur: Optional[float]
    delta_eur: Optional[float]


@dataclass(frozen=True)
class VrmMonthlyRow:
    period: str
    vrm_pv_kwh: Optional[float]
    vm_pv_kwh: Optional[float]
    delta_pv_kwh: Optional[float]
    vrm_grid_kwh: Optional[float]
    vm_grid_kwh: Optional[float]
    delta_grid_kwh: Optional[float]


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: str
    details: str


def local_timestamp() -> str:
    return dt.datetime.now().astimezone().replace(microsecond=0).isoformat()


def load_env_file(path: str) -> None:
    env_path = Path(path)
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        os.environ.setdefault(key.strip(), value)


def parse_number(value: object) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        result = float(value)
    else:
        text = str(value).strip()
        if not text or text == "-":
            return None
        if "," in text:
            text = text.replace(".", "").replace(",", ".")
        result = float(text)
    if math.isnan(result) or math.isinf(result):
        return None
    return result


def rounded(value: Optional[float], digits: int = 6) -> Optional[float]:
    if value is None:
        return None
    return round(value, digits)


def month_from_day(day: str) -> str:
    return day[:7]


def sum_optional(values: Iterable[Optional[float]]) -> Optional[float]:
    found = False
    total = 0.0
    for value in values:
        if value is None:
            continue
        found = True
        total += value
    return total if found else None


def delta(candidate: Optional[float], reference: Optional[float]) -> Optional[float]:
    if candidate is None or reference is None:
        return None
    return candidate - reference


def pct_delta(delta_value: Optional[float], reference: Optional[float]) -> Optional[float]:
    if delta_value is None or reference is None or reference == 0:
        return None
    return delta_value / reference * 100.0


def fmt(value: Optional[float], digits: int = 2) -> str:
    if value is None:
        return "-"
    return f"{value:.{digits}f}"


def default_tibber_vm_json() -> Optional[Path]:
    paths = sorted(DEFAULT_TIBBER_DIR.glob("tibber-vm-cost-*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
    return paths[0] if paths else None


def default_tibber_influx_csv() -> Optional[Path]:
    paths = sorted(DEFAULT_TIBBER_DIR.glob("tibber-influx-cost-monthly*.csv"), key=lambda item: item.stat().st_mtime, reverse=True)
    return paths[0] if paths else None


def default_vrm_json() -> Optional[Path]:
    paths = sorted(DEFAULT_VRM_DIR.glob("vrm-kwh-days-site-*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
    return paths[0] if paths else None


def path_or_none(value: str, default_path: Optional[Path]) -> Optional[Path]:
    if value:
        return Path(value)
    return default_path


def load_tibber_vm_months(path: Path, excluded_months: Sequence[str]) -> List[MonthlyCostRow]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    months = payload.get("monthly")
    if not isinstance(months, list):
        months = aggregate_tibber_vm_daily(payload.get("daily") or [])
    rows: List[MonthlyCostRow] = []
    for item in months:
        period = str(item.get("period") or item.get("day", "")[:7])
        if not period or period in excluded_months:
            continue
        reference_kwh = parse_number(item.get("tibber_kwh"))
        candidate_kwh = parse_number(item.get("vm_kwh"))
        reference_eur = parse_number(item.get("tibber_eur"))
        candidate_eur = parse_number(item.get("vm_eur"))
        rows.append(
            MonthlyCostRow(
                period=period,
                reference_kwh=reference_kwh,
                candidate_kwh=candidate_kwh,
                delta_kwh=delta(candidate_kwh, reference_kwh),
                reference_eur=reference_eur,
                candidate_eur=candidate_eur,
                delta_eur=delta(candidate_eur, reference_eur),
            )
        )
    return sorted(rows, key=lambda row: row.period)


def aggregate_tibber_vm_daily(daily: Sequence[Mapping[str, object]]) -> List[Mapping[str, object]]:
    buckets: Dict[str, List[Mapping[str, object]]] = {}
    for item in daily:
        day = str(item.get("day") or "")
        if day:
            buckets.setdefault(month_from_day(day), []).append(item)
    months: List[Mapping[str, object]] = []
    for period, items in sorted(buckets.items()):
        months.append(
            {
                "period": period,
                "tibber_kwh": sum_optional(parse_number(item.get("tibber_kwh")) for item in items),
                "vm_kwh": sum_optional(parse_number(item.get("vm_kwh")) for item in items),
                "tibber_eur": sum_optional(parse_number(item.get("tibber_eur")) for item in items),
                "vm_eur": sum_optional(parse_number(item.get("vm_eur")) for item in items),
            }
        )
    return months


def load_tibber_influx_months(path: Path, excluded_months: Sequence[str]) -> List[MonthlyCostRow]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows: List[MonthlyCostRow] = []
        for item in reader:
            period = str(item.get("month") or "")
            if not period or period.startswith("TOTAL") or period in excluded_months:
                continue
            reference_kwh = parse_number(item.get("tibber_kwh"))
            candidate_kwh = parse_number(item.get("influx_kwh"))
            reference_eur = parse_number(item.get("tibber_eur"))
            candidate_eur = parse_number(item.get("influx_eur"))
            rows.append(
                MonthlyCostRow(
                    period=period,
                    reference_kwh=reference_kwh,
                    candidate_kwh=candidate_kwh,
                    delta_kwh=delta(candidate_kwh, reference_kwh),
                    reference_eur=reference_eur,
                    candidate_eur=candidate_eur,
                    delta_eur=delta(candidate_eur, reference_eur),
                )
            )
    return sorted(rows, key=lambda row: row.period)


def totals_for_cost_rows(rows: Sequence[MonthlyCostRow]) -> MonthlyCostRow:
    reference_kwh = sum_optional(row.reference_kwh for row in rows)
    candidate_kwh = sum_optional(row.candidate_kwh for row in rows)
    reference_eur = sum_optional(row.reference_eur for row in rows)
    candidate_eur = sum_optional(row.candidate_eur for row in rows)
    return MonthlyCostRow(
        period="TOTAL",
        reference_kwh=reference_kwh,
        candidate_kwh=candidate_kwh,
        delta_kwh=delta(candidate_kwh, reference_kwh),
        reference_eur=reference_eur,
        candidate_eur=candidate_eur,
        delta_eur=delta(candidate_eur, reference_eur),
    )


def evaluate_cost_rows(
    name: str,
    rows: Sequence[MonthlyCostRow],
    monthly_kwh_pct_tolerance: float,
    monthly_eur_pct_tolerance: float,
    total_kwh_pct_tolerance: float,
    total_eur_pct_tolerance: float,
) -> CheckResult:
    if not rows:
        return CheckResult(name=name, status="SKIP", details="no rows")
    missing = sum(1 for row in rows if row.reference_kwh is None or row.candidate_kwh is None)
    max_month_kwh_pct = max_abs_pct((row.delta_kwh, row.reference_kwh) for row in rows)
    max_month_eur_pct = max_abs_pct((row.delta_eur, row.reference_eur) for row in rows)
    total = totals_for_cost_rows(rows)
    total_kwh_pct = abs(pct_delta(total.delta_kwh, total.reference_kwh) or 0.0)
    total_eur_pct = abs(pct_delta(total.delta_eur, total.reference_eur) or 0.0)
    problems = missing
    if max_month_kwh_pct is not None and max_month_kwh_pct > monthly_kwh_pct_tolerance:
        problems += 1
    if max_month_eur_pct is not None and max_month_eur_pct > monthly_eur_pct_tolerance:
        problems += 1
    if total_kwh_pct > total_kwh_pct_tolerance:
        problems += 1
    if total_eur_pct > total_eur_pct_tolerance:
        problems += 1
    status = "OK" if problems == 0 else "CHECK"
    return CheckResult(
        name=name,
        status=status,
        details=(
            f"rows={len(rows)}, missing={missing}, "
            f"max_month_kwh_delta={fmt(max_month_kwh_pct)}%, max_month_eur_delta={fmt(max_month_eur_pct)}%, "
            f"total_kwh_delta={fmt(total_kwh_pct)}%, total_eur_delta={fmt(total_eur_pct)}%"
        ),
    )


def max_abs_pct(pairs: Iterable[Tuple[Optional[float], Optional[float]]]) -> Optional[float]:
    values = [abs(pct_delta(value, reference) or 0.0) for value, reference in pairs if value is not None and reference not in (None, 0)]
    return max(values) if values else None


def load_vrm_rows(path: Path, excluded_months: Sequence[str]) -> List[Mapping[str, object]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("rows")
    if not isinstance(rows, list):
        raise RuntimeError(f"{path} does not contain a VRM rows array")
    return [row for row in rows if str(row.get("day", ""))[:7] not in excluded_months]


def aggregate_vrm_months(rows: Sequence[Mapping[str, object]]) -> Dict[str, Dict[str, float]]:
    buckets: Dict[str, Dict[str, float]] = {}
    for row in rows:
        day = str(row.get("day") or "")
        if not day:
            continue
        period = month_from_day(day)
        bucket = buckets.setdefault(period, {"pv": 0.0, "grid": 0.0})
        bucket["pv"] += parse_number(row.get("pv_total_kwh")) or 0.0
        bucket["grid"] += parse_number(row.get("grid_import_total_kwh")) or 0.0
    return buckets


def vm_export_url(base_url: str, matcher: str, start: dt.datetime, end: dt.datetime) -> str:
    params = [("match[]", matcher), ("start", iso_z(start)), ("end", iso_z(end))]
    return f"{base_url.rstrip('/')}/api/v1/export?{urllib.parse.urlencode(params)}"


def iso_z(value: dt.datetime) -> str:
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def fetch_vm_daily_metric(base_url: str, metric: str, start_day: dt.date, end_day: dt.date, timezone: ZoneInfo, scale: float) -> Dict[str, float]:
    start = dt.datetime.combine(start_day, dt.time.min, tzinfo=timezone) - dt.timedelta(days=1)
    end = dt.datetime.combine(end_day, dt.time.min, tzinfo=timezone) + dt.timedelta(days=2)
    request = urllib.request.Request(vm_export_url(base_url, metric, start, end), method="GET")
    with urllib.request.urlopen(request, timeout=120) as response:
        text = response.read().decode("utf-8")
    out: Dict[str, float] = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        for raw_ts, raw_value in zip(item.get("timestamps") or [], item.get("values") or []):
            local_day = dt.datetime.fromtimestamp(int(raw_ts) / 1000, tz=UTC).astimezone(timezone).date()
            if start_day <= local_day <= end_day:
                value = parse_number(raw_value)
                if value is not None:
                    out[local_day.isoformat()] = value / scale
    return out


def build_vrm_vm_months(vrm_rows: Sequence[Mapping[str, object]], base_url: str, timezone_name: str) -> List[VrmMonthlyRow]:
    days = sorted(str(row.get("day")) for row in vrm_rows if row.get("day"))
    if not days:
        return []
    timezone = ZoneInfo(timezone_name)
    start_day = dt.date.fromisoformat(days[0])
    end_day = dt.date.fromisoformat(days[-1])
    vm_pv_daily = fetch_vm_daily_metric(base_url, "evcc_pv_energy_daily_wh", start_day, end_day, timezone, 1000.0)
    vm_grid_daily = fetch_vm_daily_metric(base_url, "evcc_grid_import_daily_wh", start_day, end_day, timezone, 1000.0)
    vrm_months = aggregate_vrm_months(vrm_rows)
    vm_months: Dict[str, Dict[str, float]] = {}
    for day, value in vm_pv_daily.items():
        vm_months.setdefault(month_from_day(day), {"pv": 0.0, "grid": 0.0})["pv"] += value
    for day, value in vm_grid_daily.items():
        vm_months.setdefault(month_from_day(day), {"pv": 0.0, "grid": 0.0})["grid"] += value

    rows: List[VrmMonthlyRow] = []
    for period in sorted(set(vrm_months) | set(vm_months)):
        vrm_pv = vrm_months.get(period, {}).get("pv")
        vm_pv = vm_months.get(period, {}).get("pv")
        vrm_grid = vrm_months.get(period, {}).get("grid")
        vm_grid = vm_months.get(period, {}).get("grid")
        rows.append(
            VrmMonthlyRow(
                period=period,
                vrm_pv_kwh=vrm_pv,
                vm_pv_kwh=vm_pv,
                delta_pv_kwh=delta(vm_pv, vrm_pv),
                vrm_grid_kwh=vrm_grid,
                vm_grid_kwh=vm_grid,
                delta_grid_kwh=delta(vm_grid, vrm_grid),
            )
        )
    return rows


def totals_for_vrm_rows(rows: Sequence[VrmMonthlyRow]) -> VrmMonthlyRow:
    vrm_pv = sum_optional(row.vrm_pv_kwh for row in rows)
    vm_pv = sum_optional(row.vm_pv_kwh for row in rows)
    vrm_grid = sum_optional(row.vrm_grid_kwh for row in rows)
    vm_grid = sum_optional(row.vm_grid_kwh for row in rows)
    return VrmMonthlyRow(
        period="TOTAL",
        vrm_pv_kwh=vrm_pv,
        vm_pv_kwh=vm_pv,
        delta_pv_kwh=delta(vm_pv, vrm_pv),
        vrm_grid_kwh=vrm_grid,
        vm_grid_kwh=vm_grid,
        delta_grid_kwh=delta(vm_grid, vrm_grid),
    )


def evaluate_vrm_rows(rows: Sequence[VrmMonthlyRow], monthly_pct_tolerance: float, total_pct_tolerance: float) -> CheckResult:
    if not rows:
        return CheckResult(name="VRM vs VM", status="SKIP", details="no live VM comparison rows")
    max_month_pv_pct = max_abs_pct((row.delta_pv_kwh, row.vrm_pv_kwh) for row in rows)
    max_month_grid_pct = max_abs_pct((row.delta_grid_kwh, row.vrm_grid_kwh) for row in rows)
    total = totals_for_vrm_rows(rows)
    total_pv_pct = abs(pct_delta(total.delta_pv_kwh, total.vrm_pv_kwh) or 0.0)
    total_grid_pct = abs(pct_delta(total.delta_grid_kwh, total.vrm_grid_kwh) or 0.0)
    missing = sum(
        1
        for row in rows
        if row.vrm_pv_kwh is None or row.vm_pv_kwh is None or row.vrm_grid_kwh is None or row.vm_grid_kwh is None
    )
    problems = missing
    if max_month_pv_pct is not None and max_month_pv_pct > monthly_pct_tolerance:
        problems += 1
    if max_month_grid_pct is not None and max_month_grid_pct > monthly_pct_tolerance:
        problems += 1
    if total_pv_pct > total_pct_tolerance:
        problems += 1
    if total_grid_pct > total_pct_tolerance:
        problems += 1
    return CheckResult(
        name="VRM vs VM",
        status="OK" if problems == 0 else "CHECK",
        details=(
            f"rows={len(rows)}, missing={missing}, "
            f"max_month_pv_delta={fmt(max_month_pv_pct)}%, max_month_grid_delta={fmt(max_month_grid_pct)}%, "
            f"total_pv_delta={fmt(total_pv_pct)}%, total_grid_delta={fmt(total_grid_pct)}%"
        ),
    )


def required_status(name: str, status: str, details: str, cache_key: str, required_caches: Sequence[str]) -> CheckResult:
    if status == "SKIP" and cache_key in required_caches:
        return CheckResult(name=name, status="CHECK", details=f"{details}; required by --require-cache {cache_key}")
    return CheckResult(name=name, status=status, details=details)


def print_exclusion_rationale(excluded_months: Sequence[str]) -> None:
    if not excluded_months:
        return
    print("Excluded month rationale")
    print("------------------------")
    for month in excluded_months:
        print(f"- {month}: {EXCLUDED_MONTH_RATIONALE.get(month, 'manually excluded by --exclude-month')}")
    print()


def print_cost_table(title: str, rows: Sequence[MonthlyCostRow], candidate_label: str) -> None:
    if not rows:
        print(f"{title}: SKIP - no rows")
        print()
        return
    table_rows = list(rows) + [totals_for_cost_rows(rows)]
    print(title)
    print("-" * len(title))
    print(f"{'Month':<10} {'Tibber kWh':>11} {candidate_label + ' kWh':>11} {'Delta kWh':>11} {'Delta %':>8} {'Tibber EUR':>11} {candidate_label + ' EUR':>11} {'Delta EUR':>11} {'Delta %':>8}")
    for row in table_rows:
        kwh_pct = pct_delta(row.delta_kwh, row.reference_kwh)
        eur_pct = pct_delta(row.delta_eur, row.reference_eur)
        print(
            f"{row.period:<10} {fmt(row.reference_kwh):>11} {fmt(row.candidate_kwh):>11} {fmt(row.delta_kwh):>11} {fmt(kwh_pct):>8} "
            f"{fmt(row.reference_eur):>11} {fmt(row.candidate_eur):>11} {fmt(row.delta_eur):>11} {fmt(eur_pct):>8}"
        )
    print()


def print_vrm_summary(vrm_rows: Sequence[Mapping[str, object]]) -> None:
    if not vrm_rows:
        print("VRM cache summary: SKIP - no rows")
        print()
        return
    print("VRM cache summary")
    print("-----------------")
    print(f"- Days:            {len(vrm_rows)}")
    print(f"- PV total kWh:    {fmt(sum(parse_number(row.get('pv_total_kwh')) or 0.0 for row in vrm_rows), 3)}")
    print(f"- Grid import kWh: {fmt(sum(parse_number(row.get('grid_import_total_kwh')) or 0.0 for row in vrm_rows), 3)}")
    print()


def print_vrm_table(rows: Sequence[VrmMonthlyRow]) -> None:
    if not rows:
        print("VRM vs VM rollups: SKIP - pass --vm-base-url to compare live VM rollups")
        print()
        return
    table_rows = list(rows) + [totals_for_vrm_rows(rows)]
    print("VRM vs VM rollups")
    print("-----------------")
    print(f"{'Month':<10} {'VRM PV':>11} {'VM PV':>11} {'Delta PV':>11} {'Delta %':>8} {'VRM Grid':>11} {'VM Grid':>11} {'Delta Grid':>11} {'Delta %':>8}")
    for row in table_rows:
        pv_pct = pct_delta(row.delta_pv_kwh, row.vrm_pv_kwh)
        grid_pct = pct_delta(row.delta_grid_kwh, row.vrm_grid_kwh)
        print(
            f"{row.period:<10} {fmt(row.vrm_pv_kwh):>11} {fmt(row.vm_pv_kwh):>11} {fmt(row.delta_pv_kwh):>11} {fmt(pv_pct):>8} "
            f"{fmt(row.vrm_grid_kwh):>11} {fmt(row.vm_grid_kwh):>11} {fmt(row.delta_grid_kwh):>11} {fmt(grid_pct):>8}"
        )
    print()


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate cached Tibber, Influx, VM, and VRM comparison data.")
    parser.add_argument("--env-file", default=".env.local", help="Optional env file. Used only for VM_BASE_URL fallback.")
    parser.add_argument("--tibber-vm-json", default="", help="compare_tibber_vm.py JSON output. Defaults to newest local Tibber/VM cache.")
    parser.add_argument("--tibber-influx-csv", default="", help="Tibber vs Influx monthly CSV. Defaults to newest local Influx comparison cache.")
    parser.add_argument("--vrm-json", default="", help="VRM kWh cache JSON. Defaults to newest local VRM cache.")
    parser.add_argument("--vm-base-url", default="", help="Optional live VictoriaMetrics base URL for VRM-vs-VM rollup comparison.")
    parser.add_argument("--timezone", default="Europe/Berlin", help="Local timezone for live VM day mapping.")
    parser.add_argument("--exclude-month", action="append", default=list(DEFAULT_EXCLUDED_MONTHS), help="Month to exclude, YYYY-MM. Can be repeated.")
    parser.add_argument("--monthly-kwh-pct-tolerance", type=float, default=2.0, help="Allowed max monthly energy delta percent.")
    parser.add_argument("--monthly-eur-pct-tolerance", type=float, default=12.0, help="Allowed max monthly cost delta percent.")
    parser.add_argument("--total-kwh-pct-tolerance", type=float, default=1.0, help="Allowed total energy delta percent.")
    parser.add_argument("--total-eur-pct-tolerance", type=float, default=5.0, help="Allowed total cost delta percent.")
    parser.add_argument("--vrm-monthly-pct-tolerance", type=float, default=3.0, help="Allowed max monthly VRM-vs-VM energy delta percent.")
    parser.add_argument("--vrm-total-pct-tolerance", type=float, default=2.0, help="Allowed total VRM-vs-VM energy delta percent.")
    parser.add_argument(
        "--require-cache",
        action="append",
        choices=("tibber-vm", "tibber-influx", "vrm", "vrm-vm"),
        default=[],
        help="Turn a missing cache/comparison into CHECK. Repeat for multiple required inputs.",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text tables.")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    load_env_file(args.env_file)
    excluded_months = tuple(sorted(set(args.exclude_month or [])))
    tibber_vm_path = path_or_none(args.tibber_vm_json, default_tibber_vm_json())
    tibber_influx_path = path_or_none(args.tibber_influx_csv, default_tibber_influx_csv())
    vrm_path = path_or_none(args.vrm_json, default_vrm_json())
    vm_base_url = args.vm_base_url or os.environ.get("VM_BASE_URL", "")
    required_caches = tuple(sorted(set(args.require_cache or [])))

    checks: List[CheckResult] = []
    tibber_vm_rows: List[MonthlyCostRow] = []
    tibber_influx_rows: List[MonthlyCostRow] = []
    vrm_rows: List[Mapping[str, object]] = []
    vrm_vm_rows: List[VrmMonthlyRow] = []

    if tibber_vm_path and tibber_vm_path.exists():
        tibber_vm_rows = load_tibber_vm_months(tibber_vm_path, excluded_months)
        checks.append(
            evaluate_cost_rows(
                "Tibber vs VM",
                tibber_vm_rows,
                args.monthly_kwh_pct_tolerance,
                args.monthly_eur_pct_tolerance,
                args.total_kwh_pct_tolerance,
                args.total_eur_pct_tolerance,
            )
        )
    else:
        checks.append(required_status("Tibber vs VM", "SKIP", "no local Tibber/VM JSON cache found", "tibber-vm", required_caches))

    if tibber_influx_path and tibber_influx_path.exists():
        tibber_influx_rows = load_tibber_influx_months(tibber_influx_path, excluded_months)
        checks.append(
            evaluate_cost_rows(
                "Tibber vs Influx",
                tibber_influx_rows,
                args.monthly_kwh_pct_tolerance,
                args.monthly_eur_pct_tolerance,
                args.total_kwh_pct_tolerance,
                args.total_eur_pct_tolerance,
            )
        )
    else:
        checks.append(
            required_status("Tibber vs Influx", "SKIP", "no local Tibber/Influx CSV cache found", "tibber-influx", required_caches)
        )

    if vrm_path and vrm_path.exists():
        vrm_rows = load_vrm_rows(vrm_path, excluded_months)
        checks.append(required_status("VRM cache", "OK" if vrm_rows else "SKIP", f"rows={len(vrm_rows)}", "vrm", required_caches))
        if vm_base_url:
            vrm_vm_rows = build_vrm_vm_months(vrm_rows, vm_base_url, args.timezone)
            checks.append(evaluate_vrm_rows(vrm_vm_rows, args.vrm_monthly_pct_tolerance, args.vrm_total_pct_tolerance))
        elif "vrm-vm" in required_caches:
            checks.append(CheckResult("VRM vs VM", "CHECK", "--require-cache vrm-vm needs --vm-base-url or VM_BASE_URL"))
    else:
        checks.append(required_status("VRM cache", "SKIP", "no local VRM JSON cache found", "vrm", required_caches))
        if "vrm-vm" in required_caches:
            checks.append(CheckResult("VRM vs VM", "CHECK", "--require-cache vrm-vm needs a VRM cache and --vm-base-url/VM_BASE_URL"))

    if args.json:
        print(
            json.dumps(
                {
                    "script": {"name": SCRIPT_NAME, "version": SCRIPT_VERSION, "last_modified": SCRIPT_LAST_MODIFIED},
                    "generated_at": local_timestamp(),
                    "excluded_months": list(excluded_months),
                    "excluded_month_rationale": {month: EXCLUDED_MONTH_RATIONALE.get(month, "") for month in excluded_months},
                    "required_caches": list(required_caches),
                    "inputs": {
                        "tibber_vm_json": str(tibber_vm_path) if tibber_vm_path else None,
                        "tibber_influx_csv": str(tibber_influx_path) if tibber_influx_path else None,
                        "vrm_json": str(vrm_path) if vrm_path else None,
                        "vm_base_url": vm_base_url or None,
                    },
                    "checks": [check.__dict__ for check in checks],
                    "tibber_vm_monthly": [row.__dict__ for row in tibber_vm_rows],
                    "tibber_influx_monthly": [row.__dict__ for row in tibber_influx_rows],
                    "vrm_vm_monthly": [row.__dict__ for row in vrm_vm_rows],
                },
                ensure_ascii=True,
                indent=2,
            )
        )
    else:
        print("EVCC external energy validation")
        print("================================")
        print(f"Script:        {SCRIPT_NAME}")
        print(f"Version:       {SCRIPT_VERSION}")
        print(f"Last modified: {SCRIPT_LAST_MODIFIED}")
        print(f"Run at:        {local_timestamp()}")
        print(f"Excluded:      {', '.join(excluded_months) if excluded_months else '-'}")
        print(f"Required:      {', '.join(required_caches) if required_caches else '-'}")
        print()
        print_exclusion_rationale(excluded_months)
        print_cost_table("Tibber vs VM rollup costs", tibber_vm_rows, "VM")
        print_cost_table("Tibber vs Influx dashboard costs", tibber_influx_rows, "Influx")
        print_vrm_summary(vrm_rows)
        print_vrm_table(vrm_vm_rows)
        print("Checks")
        print("------")
        for check in checks:
            print(f"{check.status:<5} {check.name:<18} {check.details}")
        print()

    blocking = [check for check in checks if check.status == "CHECK"]
    return 1 if blocking else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
