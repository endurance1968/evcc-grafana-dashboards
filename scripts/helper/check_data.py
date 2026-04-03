#!/usr/bin/env python3
"""Check whether expected EVCC raw metrics and VM rollups exist in VictoriaMetrics.

This script is intended to run after the Influx -> VM import and after the initial
rollup backfill. It does not compare values point-by-point. Instead it answers the
operator question:

    "Do we have the raw and daily metrics that the dashboards and rollups expect?"

It distinguishes between:
- core metrics that every EVCC VM dashboard installation should have
- conditional metrics that depend on detected features such as battery, loadpoints,
  tariffs, EXT or AUX consumers
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Dict, List, Sequence

UTC = dt.timezone.utc


def iso_z(value: dt.datetime) -> str:
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def utc_now() -> dt.datetime:
    return dt.datetime.now(tz=UTC)


@dataclass(frozen=True)
class MetricCheck:
    metric: str
    severity: str
    reason: str


FEATURES: Dict[str, Dict[str, object]] = {
    "battery": {
        "detect": ["batteryPower_value", "batterySoc_value"],
        "raw": [
            MetricCheck("batteryPower_value", "critical", "Battery dashboards need battery power."),
            MetricCheck("batterySoc_value", "critical", "Battery dashboards need battery state of charge."),
        ],
        "rollups": [
            MetricCheck("evcc_battery_charge_daily_wh", "critical", "Month/Year/All-time use battery charge."),
            MetricCheck("evcc_battery_discharge_daily_wh", "critical", "Month/Year/All-time use battery discharge."),
            MetricCheck("evcc_battery_soc_daily_min_pct", "critical", "Battery min panels need daily min SOC."),
            MetricCheck("evcc_battery_soc_daily_max_pct", "critical", "Battery max panels need daily max SOC."),
            MetricCheck("evcc_battery_discharge_value_daily_eur", "warning", "All-time savings panels use this daily value."),
            MetricCheck("evcc_battery_charge_feedin_cost_daily_eur", "warning", "All-time savings panels use this daily value."),
        ],
    },
    "loadpoints": {
        "detect": ["chargePower_value"],
        "raw": [
            MetricCheck("chargePower_value", "critical", "Loadpoint dashboards need charge power."),
        ],
        "rollups": [
            MetricCheck("evcc_loadpoint_energy_daily_wh", "critical", "Month/Year/All-time need loadpoint daily energy."),
            MetricCheck("evcc_loadpoint_energy_from_pv_daily_wh", "critical", "Consumer mix panels need PV attribution."),
            MetricCheck("evcc_loadpoint_energy_from_battery_daily_wh", "critical", "Consumer mix panels need battery attribution."),
            MetricCheck("evcc_loadpoint_energy_from_grid_daily_wh", "critical", "Consumer mix panels need grid attribution."),
        ],
    },
    "ext": {
        "detect": ["extPower_value"],
        "raw": [MetricCheck("extPower_value", "warning", "Today detail dashboard can show EXT consumers.")],
        "rollups": [
            MetricCheck("evcc_ext_energy_daily_wh", "warning", "Month/Year panels use EXT daily energy."),
            MetricCheck("evcc_ext_energy_from_pv_daily_wh", "warning", "Consumer attribution for EXT uses this."),
            MetricCheck("evcc_ext_energy_from_battery_daily_wh", "warning", "Consumer attribution for EXT uses this."),
            MetricCheck("evcc_ext_energy_from_grid_daily_wh", "warning", "Consumer attribution for EXT uses this."),
        ],
    },
    "aux": {
        "detect": ["auxPower_value"],
        "raw": [MetricCheck("auxPower_value", "warning", "Today detail dashboard can show AUX consumers.")],
        "rollups": [
            MetricCheck("evcc_aux_energy_daily_wh", "warning", "Month/Year panels use AUX daily energy."),
            MetricCheck("evcc_aux_energy_from_pv_daily_wh", "warning", "Consumer attribution for AUX uses this."),
            MetricCheck("evcc_aux_energy_from_battery_daily_wh", "warning", "Consumer attribution for AUX uses this."),
            MetricCheck("evcc_aux_energy_from_grid_daily_wh", "warning", "Consumer attribution for AUX uses this."),
        ],
    },
    "tariffs": {
        "detect": ["tariffGrid_value", "tariffSolar_value", "tariffFeedIn_value", "tariffCo2_value"],
        "raw": [
            MetricCheck("tariffGrid_value", "warning", "Price panels use grid tariff data."),
            MetricCheck("tariffSolar_value", "warning", "PV forecast/cost panels can use solar tariff data."),
            MetricCheck("tariffFeedIn_value", "warning", "Feed-in credit panels use feed-in tariff data."),
            MetricCheck("tariffCo2_value", "warning", "CO2 tariff panels use this metric."),
        ],
        "rollups": [
            MetricCheck("evcc_grid_import_price_avg_daily_ct_per_kwh", "warning", "Month/Year/All-time price panels use this."),
            MetricCheck("evcc_grid_import_price_effective_daily_ct_per_kwh", "warning", "Month/Year/All-time price panels use this."),
            MetricCheck("evcc_grid_import_price_min_daily_ct_per_kwh", "warning", "Month/Year/All-time price panels use this."),
            MetricCheck("evcc_grid_import_price_max_daily_ct_per_kwh", "warning", "Month/Year/All-time price panels use this."),
            MetricCheck("evcc_grid_import_cost_daily_eur", "warning", "Cost panels use this."),
            MetricCheck("evcc_grid_export_credit_daily_eur", "warning", "Feed-in credit panels use this."),
            MetricCheck("evcc_potential_home_cost_daily_eur", "warning", "Savings panels use this."),
            MetricCheck("evcc_potential_loadpoint_cost_daily_eur", "warning", "Savings panels use this."),
            MetricCheck("evcc_potential_vehicle_charge_cost_daily_eur", "warning", "Vehicle cost panels use this."),
            MetricCheck("evcc_vehicle_charge_cost_daily_eur", "warning", "Vehicle cost panels use this."),
        ],
    },
    "vehicles": {
        "detect": ["vehicleOdometer_value", "vehicleSoc_value"],
        "raw": [
            MetricCheck("vehicleOdometer_value", "warning", "Vehicle distance panels use odometer data."),
            MetricCheck("vehicleSoc_value", "warning", "Vehicle gauges use vehicle SOC."),
            MetricCheck("prioritySoc_value", "warning", "Priority SOC gauge uses this."),
        ],
        "rollups": [
            MetricCheck("evcc_vehicle_distance_daily_km", "warning", "Vehicle distance panels use this rollup."),
            MetricCheck("evcc_vehicle_energy_daily_wh", "warning", "Vehicle energy panels use this rollup."),
        ],
    },
}

CORE_RAW: Sequence[MetricCheck] = (
    MetricCheck("pvPower_value", "critical", "Today dashboard needs PV power."),
    MetricCheck("gridPower_value", "critical", "Today dashboard needs grid power."),
    MetricCheck("homePower_value", "critical", "Today dashboard needs home power."),
)

CORE_ROLLUPS: Sequence[MetricCheck] = (
    MetricCheck("evcc_pv_energy_daily_wh", "critical", "Month/Year/All-time need PV daily energy."),
    MetricCheck("evcc_grid_import_daily_wh", "critical", "Month/Year/All-time need grid import daily energy."),
    MetricCheck("evcc_grid_export_daily_wh", "critical", "Month/Year/All-time need grid export daily energy."),
    MetricCheck("evcc_home_energy_daily_wh", "critical", "Month/Year/All-time need home daily energy."),
    MetricCheck("evcc_pv_top30_mean_yearly_wh", "warning", "All-time uses yearly yield reference."),
    MetricCheck("evcc_pv_top5_mean_monthly_wh", "warning", "All-time uses monthly yield reference."),
)


def http_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def build_series_url(base_url: str, metric: str, db_label: str, start: str, end: str) -> str:
    params = urllib.parse.urlencode({"match[]": f'{metric}{{db="{db_label}"}}', "start": start, "end": end})
    return f"{base_url.rstrip('/')}/api/v1/series?{params}"


def series_count(base_url: str, metric: str, db_label: str, start: str, end: str) -> int:
    payload = http_json(build_series_url(base_url, metric, db_label, start, end))
    return len(payload.get("data") or [])


def classify_level(existing: int, severity: str) -> str:
    if existing > 0:
        return "OK"
    return "CRITICAL" if severity == "critical" else "WARNING"


def worst_level(levels: Sequence[str]) -> str:
    if "CRITICAL" in levels:
        return "CRITICAL"
    if "WARNING" in levels:
        return "WARNING"
    return "OK"


def render_section(title: str, checks: List[dict]) -> None:
    print(f"\n{title}")
    print("-" * len(title))
    if not checks:
        print("SKIP")
        return
    for item in checks:
        print(f"{item['level']:<8} {item['metric']:<48} series={item['series']:<5} {item['reason']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8428", help="VictoriaMetrics base URL")
    parser.add_argument("--db", default="evcc", help="db label value")
    parser.add_argument("--raw-hours", type=int, default=48, help="recent window for raw metric checks")
    parser.add_argument("--rollup-days", type=int, default=90, help="recent window for daily rollup checks")
    parser.add_argument("--feature-lookback-days", type=int, default=3650, help="lookback window to detect optional features")
    parser.add_argument("--end-time", help="override logical end time in RFC3339 (default: now)")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON only")
    args = parser.parse_args()

    if args.end_time:
        normalized = args.end_time.replace("Z", "+00:00")
        now = dt.datetime.fromisoformat(normalized)
        if now.tzinfo is None:
            now = now.replace(tzinfo=UTC)
        else:
            now = now.astimezone(UTC)
    else:
        now = utc_now()
    raw_start = iso_z(now - dt.timedelta(hours=args.raw_hours))
    rollup_start = iso_z(now - dt.timedelta(days=args.rollup_days))
    feature_start = iso_z(now - dt.timedelta(days=args.feature_lookback_days))
    end = iso_z(now)

    feature_flags: Dict[str, bool] = {}
    for feature_name, config in FEATURES.items():
        detectors: Sequence[str] = config["detect"]  # type: ignore[assignment]
        feature_flags[feature_name] = any(series_count(args.base_url, metric, args.db, feature_start, end) > 0 for metric in detectors)

    sections: List[dict] = []

    def run_checks(title: str, items: Sequence[MetricCheck], start: str, end_time: str) -> None:
        results: List[dict] = []
        for item in items:
            count = series_count(args.base_url, item.metric, args.db, start, end_time)
            results.append({"metric": item.metric, "level": classify_level(count, item.severity), "series": count, "reason": item.reason})
        sections.append({"title": title, "items": results})

    run_checks("Core raw metrics", CORE_RAW, raw_start, end)

    conditional_raw: List[dict] = []
    for feature_name, enabled in feature_flags.items():
        if not enabled:
            conditional_raw.append({"title": f"Conditional raw metrics ({feature_name})", "items": []})
            continue
        items: Sequence[MetricCheck] = FEATURES[feature_name]["raw"]  # type: ignore[index]
        results = []
        for item in items:
            count = series_count(args.base_url, item.metric, args.db, raw_start, end)
            results.append({"metric": item.metric, "level": classify_level(count, item.severity), "series": count, "reason": item.reason})
        conditional_raw.append({"title": f"Conditional raw metrics ({feature_name})", "items": results})

    run_checks("Core rollup metrics", CORE_ROLLUPS, rollup_start, end)

    conditional_rollups: List[dict] = []
    for feature_name, enabled in feature_flags.items():
        if not enabled:
            conditional_rollups.append({"title": f"Conditional rollups ({feature_name})", "items": []})
            continue
        items = FEATURES[feature_name]["rollups"]  # type: ignore[index]
        results = []
        for item in items:
            count = series_count(args.base_url, item.metric, args.db, rollup_start, end)
            results.append({"metric": item.metric, "level": classify_level(count, item.severity), "series": count, "reason": item.reason})
        conditional_rollups.append({"title": f"Conditional rollups ({feature_name})", "items": results})

    all_sections = sections + conditional_raw + conditional_rollups
    levels = [item["level"] for section in all_sections for item in section["items"]]
    overall = worst_level(levels)

    payload = {
        "base_url": args.base_url,
        "db": args.db,
        "windows": {"raw_start": raw_start, "rollup_start": rollup_start, "feature_start": feature_start, "end": end},
        "detected_features": feature_flags,
        "overall": overall,
        "sections": all_sections,
    }

    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 2 if overall == "CRITICAL" else 1 if overall == "WARNING" else 0

    print("EVCC VM data check")
    print("==================")
    print(f"Base URL:           {args.base_url}")
    print(f"db label:           {args.db}")
    print(f"Raw window:         {raw_start} -> {end}")
    print(f"Rollup window:      {rollup_start} -> {end}")
    print(f"Feature lookback:   {feature_start} -> {end}")
    print("\nDetected features")
    print("-----------------")
    for name in sorted(feature_flags):
        print(f"{name:<10} {'yes' if feature_flags[name] else 'no'}")

    for section in sections:
        render_section(section["title"], section["items"])
    for section in conditional_raw:
        render_section(section["title"], section["items"])
    for section in conditional_rollups:
        render_section(section["title"], section["items"])

    print("\nOverall")
    print("-------")
    print(overall)
    print("\nExit codes: OK=0, WARNING=1, CRITICAL=2")
    return 2 if overall == "CRITICAL" else 1 if overall == "WARNING" else 0


if __name__ == "__main__":
    sys.exit(main())
