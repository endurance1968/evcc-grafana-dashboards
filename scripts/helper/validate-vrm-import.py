#!/usr/bin/env python3
"""Validate imported evcc_vrm_* daily metrics against a VRM cache."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Mapping, Sequence
from zoneinfo import ZoneInfo

SCRIPT_NAME = "validate-vrm-import.py"
SCRIPT_VERSION = "2026.07.28.1"
SCRIPT_LAST_MODIFIED = "2026-07-28"
ROOT = Path(__file__).resolve().parents[2]
DEFAULT_VRM_DIR = ROOT / "data" / "energy-comparison" / "vrm"
UTC = dt.timezone.utc
FIELD_METRICS = {
    "pv_to_battery_kwh": "evcc_vrm_pv_to_battery_daily_wh",
    "grid_to_battery_kwh": "evcc_vrm_grid_to_battery_daily_wh",
    "battery_to_consumers_kwh": "evcc_vrm_battery_to_consumers_daily_wh",
    "battery_to_grid_kwh": "evcc_vrm_battery_to_grid_daily_wh",
    "battery_charge_kwh": "evcc_vrm_battery_charge_daily_wh",
    "battery_discharge_kwh": "evcc_vrm_battery_discharge_daily_wh",
}


def newest_vrm_cache() -> Path | None:
    paths = sorted(
        [*DEFAULT_VRM_DIR.glob("vrm-import-source-site-*.json"), *DEFAULT_VRM_DIR.glob("vrm-kwh-days-site-*.json")],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return paths[0] if paths else None


def load_cache(path: Path) -> tuple[str, list[Mapping[str, object]]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("rows")
    if not isinstance(rows, list):
        raise ValueError(f"{path} does not contain a rows array")
    site_id = str(payload.get("site_id") or "").strip()
    if not site_id:
        raise ValueError(f"{path} does not contain site_id")
    return site_id, [row for row in rows if isinstance(row, dict) and row.get("day")]


def vm_export_url(base_url: str, matcher: str, start: str, end: str) -> str:
    query = urllib.parse.urlencode({"match[]": matcher, "start": start, "end": end})
    return f"{base_url.rstrip('/')}/api/v1/export?{query}"


def fetch_metric_days(
    base_url: str,
    metric: str,
    site_id: str,
    source: str,
    start_day: dt.date,
    end_day: dt.date,
    timezone_name: str,
) -> tuple[dict[str, float], list[str]]:
    timezone = ZoneInfo(timezone_name)
    start = dt.datetime.combine(start_day - dt.timedelta(days=1), dt.time.min, tzinfo=timezone).astimezone(UTC)
    end = dt.datetime.combine(end_day + dt.timedelta(days=2), dt.time.min, tzinfo=timezone).astimezone(UTC)
    matcher = f'{{__name__="{metric}",site="{site_id}",source="{source}"}}'
    request = urllib.request.Request(
        vm_export_url(base_url, matcher, start.isoformat().replace("+00:00", "Z"), end.isoformat().replace("+00:00", "Z")),
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        text = response.read().decode("utf-8")

    values: dict[str, float] = {}
    duplicates: list[str] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        metric_labels = item.get("metric") or {}
        label_day = str(metric_labels.get("local_date") or "")
        for raw_timestamp, raw_value in zip(item.get("timestamps") or [], item.get("values") or []):
            day = label_day
            if not day:
                day = dt.datetime.fromtimestamp(int(raw_timestamp) / 1000, tz=UTC).astimezone(timezone).date().isoformat()
            if not (start_day.isoformat() <= day <= end_day.isoformat()):
                continue
            if day in values:
                duplicates.append(day)
            values[day] = float(raw_value)
    return values, sorted(set(duplicates))


def expected_wh(row: Mapping[str, object], field: str) -> float:
    if field == "battery_charge_kwh":
        return (float(row.get("pv_to_battery_kwh") or 0.0) + float(row.get("grid_to_battery_kwh") or 0.0)) * 1000.0
    if field == "battery_discharge_kwh":
        return (float(row.get("battery_to_consumers_kwh") or 0.0) + float(row.get("battery_to_grid_kwh") or 0.0)) * 1000.0
    return float(row.get(field) or 0.0) * 1000.0


def efficiency_pct(rows: Sequence[Mapping[str, object]]) -> float | None:
    charge = sum(expected_wh(row, "battery_charge_kwh") for row in rows)
    discharge = sum(expected_wh(row, "battery_discharge_kwh") for row in rows)
    return (discharge / charge * 100.0) if charge > 0.0 else None


def validate(
    base_url: str,
    site_id: str,
    rows: Sequence[Mapping[str, object]],
    source: str,
    timezone_name: str,
    tolerance_wh: float,
) -> dict[str, object]:
    if not rows:
        raise ValueError("VRM cache contains no rows")
    start_day = min(dt.date.fromisoformat(str(row["day"])) for row in rows)
    end_day = max(dt.date.fromisoformat(str(row["day"])) for row in rows)
    expected_days = {str(row["day"]): row for row in rows}
    metric_results = []
    blocking = 0

    for field, metric in FIELD_METRICS.items():
        actual, duplicates = fetch_metric_days(base_url, metric, site_id, source, start_day, end_day, timezone_name)
        missing = sorted(set(expected_days) - set(actual))
        extra = sorted(set(actual) - set(expected_days))
        deltas = [
            abs(actual[day] - expected_wh(expected_days[day], field))
            for day in expected_days
            if day in actual and math.isfinite(actual[day])
        ]
        max_delta = max(deltas) if deltas else None
        status = "OK"
        if missing or extra or duplicates or max_delta is None or max_delta > tolerance_wh:
            status = "CHECK"
            blocking += 1
        metric_results.append(
            {
                "metric": metric,
                "status": status,
                "days": len(actual),
                "missing_days": len(missing),
                "extra_days": len(extra),
                "duplicate_days": len(duplicates),
                "max_delta_wh": max_delta,
                "examples": {"missing": missing[:3], "extra": extra[:3], "duplicates": duplicates[:3]},
            }
        )

    return {
        "site_id": site_id,
        "source": source,
        "range": {"start_day": start_day.isoformat(), "end_day": end_day.isoformat(), "days": len(expected_days)},
        "efficiency_pct": efficiency_pct(rows),
        "metrics": metric_results,
        "overall": "OK" if blocking == 0 else "CHECK",
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vm-base-url", required=True)
    parser.add_argument("--vrm-json", default="")
    parser.add_argument("--source", default="vrm")
    parser.add_argument("--start-day", type=dt.date.fromisoformat)
    parser.add_argument("--end-day", type=dt.date.fromisoformat)
    parser.add_argument("--timezone", default="Europe/Berlin")
    parser.add_argument("--tolerance-wh", type=float, default=0.1)
    parser.add_argument("--expected-efficiency-pct", type=float)
    parser.add_argument("--efficiency-tolerance-pp", type=float, default=0.2)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    path = Path(args.vrm_json) if args.vrm_json else newest_vrm_cache()
    if path is None or not path.exists():
        raise SystemExit("No VRM cache found. Pass --vrm-json.")
    site_id, rows = load_cache(path)
    if args.start_day:
        rows = [row for row in rows if dt.date.fromisoformat(str(row["day"])) >= args.start_day]
    if args.end_day:
        rows = [row for row in rows if dt.date.fromisoformat(str(row["day"])) <= args.end_day]
    result = validate(args.vm_base_url, site_id, rows, args.source, args.timezone, args.tolerance_wh)
    result["cache"] = str(path)
    expected_efficiency = args.expected_efficiency_pct
    if expected_efficiency is not None:
        actual_efficiency = result["efficiency_pct"]
        delta = abs(float(actual_efficiency) - expected_efficiency) if actual_efficiency is not None else None
        result["efficiency_regression"] = {
            "expected_pct": expected_efficiency,
            "actual_pct": actual_efficiency,
            "delta_pp": delta,
            "tolerance_pp": args.efficiency_tolerance_pp,
            "status": "OK" if delta is not None and delta <= args.efficiency_tolerance_pp else "CHECK",
        }
        if result["efficiency_regression"]["status"] != "OK":
            result["overall"] = "CHECK"

    if args.json:
        print(json.dumps({"script": {"name": SCRIPT_NAME, "version": SCRIPT_VERSION, "last_modified": SCRIPT_LAST_MODIFIED}, **result}, indent=2))
    else:
        print(f"{SCRIPT_NAME} v{SCRIPT_VERSION} (last modified {SCRIPT_LAST_MODIFIED})")
        print(f"Cache: {path}")
        print(f"Range: {result['range']['start_day']}..{result['range']['end_day']} ({result['range']['days']} days)")
        print(f"VRM efficiency: {result['efficiency_pct']:.3f}%")
        for item in result["metrics"]:
            print(
                f"{item['status']:<5} {item['metric']}: days={item['days']}, missing={item['missing_days']}, "
                f"extra={item['extra_days']}, duplicates={item['duplicate_days']}, max_delta_wh={item['max_delta_wh']}"
            )
        if "efficiency_regression" in result:
            item = result["efficiency_regression"]
            print(
                f"{item['status']:<5} efficiency regression: expected={item['expected_pct']:.3f}%, "
                f"actual={item['actual_pct']:.3f}%, delta={item['delta_pp']:.3f} pp"
            )
        print(f"Result: {result['overall']}")
    return 0 if result["overall"] == "OK" else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)