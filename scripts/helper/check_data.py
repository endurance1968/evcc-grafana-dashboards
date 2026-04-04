#!/usr/bin/env python3
"""Check whether expected EVCC raw metrics and VM rollups exist in VictoriaMetrics.

The checker supports different phases of the migration flow:

- raw import only
- rollup validation only
- full validation
- auto mode that checks raw data first and only evaluates rollups once they exist

It also reports whether host-tagged raw series are present and therefore a first
cleanup step with vm-rewrite-drop-label.py is recommended.
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
SCRIPT_NAME = "check_data.py"
SCRIPT_VERSION = "2026.04.04.1"
SCRIPT_CREATED = "2026-04-03"


def iso_z(value: dt.datetime) -> str:
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def utc_now() -> dt.datetime:
    return dt.datetime.now(tz=UTC)


def local_now() -> dt.datetime:
    return dt.datetime.now().astimezone()


def local_timestamp() -> str:
    return local_now().replace(microsecond=0).isoformat()


def script_metadata(generated_at: str | None = None) -> Dict[str, str]:
    return {
        "name": SCRIPT_NAME,
        "version": SCRIPT_VERSION,
        "created": SCRIPT_CREATED,
        "generated_at": generated_at or local_timestamp(),
    }


def print_report_header(title: str, underline: str, generated_at: str | None = None) -> None:
    metadata = script_metadata(generated_at)
    print(title)
    print(underline)
    print(f"Script:              {metadata['name']}")
    print(f"Version:             {metadata['version']}")
    print(f"Created:             {metadata['created']}")
    print(f"Run at:              {metadata['generated_at']}")


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
        "raw": [MetricCheck("chargePower_value", "critical", "Loadpoint dashboards need charge power.")],
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


def build_matcher_url(base_url: str, matcher: str, start: str, end: str) -> str:
    params = urllib.parse.urlencode({"match[]": matcher, "start": start, "end": end})
    return f"{base_url.rstrip('/')}/api/v1/series?{params}"


def build_series_url(base_url: str, metric: str, db_label: str, start: str, end: str) -> str:
    return build_matcher_url(base_url, f'{metric}{{db="{db_label}"}}', start, end)


def series_count(base_url: str, metric: str, db_label: str, start: str, end: str) -> int:
    payload = http_json(build_series_url(base_url, metric, db_label, start, end))
    return len(payload.get("data") or [])


def matcher_count(base_url: str, matcher: str, start: str, end: str) -> int:
    payload = http_json(build_matcher_url(base_url, matcher, start, end))
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


def render_section(title: str, checks: List[dict], skipped_reason: str | None = None) -> None:
    print(f"\n{title}")
    print("-" * len(title))
    if skipped_reason:
        print(f"SKIP     {skipped_reason}")
        return
    if not checks:
        print("SKIP")
        return
    for item in checks:
        print(f"{item['level']:<8} {item['metric']:<48} series={item['series']:<5} {item['reason']}")


def run_metric_checks(base_url: str, db_label: str, items: Sequence[MetricCheck], start: str, end: str) -> List[dict]:
    results: List[dict] = []
    for item in items:
        count = series_count(base_url, item.metric, db_label, start, end)
        results.append({"metric": item.metric, "level": classify_level(count, item.severity), "series": count, "reason": item.reason})
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8428", help="VictoriaMetrics base URL")
    parser.add_argument("--db", default="evcc", help="db label value")
    parser.add_argument("--raw-hours", type=int, default=48, help="recent window for raw metric checks")
    parser.add_argument("--rollup-days", type=int, default=90, help="recent window for daily rollup checks")
    parser.add_argument("--feature-lookback-days", type=int, default=3650, help="lookback window to detect optional features")
    parser.add_argument("--end-time", help="override logical end time in RFC3339 (default: now)")
    parser.add_argument(
        "--phase",
        choices=["auto", "raw", "rollup", "full"],
        default="auto",
        help="validation phase: raw import only, rollup only, full, or auto (default)",
    )
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
    live_now = utc_now()
    live_raw_start = iso_z(live_now - dt.timedelta(hours=args.raw_hours))
    live_end = iso_z(live_now)

    feature_flags: Dict[str, bool] = {}
    raw_feature_flags: Dict[str, bool] = {}
    live_raw_feature_flags: Dict[str, bool] = {}
    rollup_feature_flags: Dict[str, bool] = {}
    for feature_name, config in FEATURES.items():
        detectors: Sequence[str] = config["detect"]  # type: ignore[assignment]
        feature_flags[feature_name] = any(series_count(args.base_url, metric, args.db, feature_start, end) > 0 for metric in detectors)
        raw_feature_flags[feature_name] = any(series_count(args.base_url, metric, args.db, raw_start, end) > 0 for metric in detectors)
        live_raw_feature_flags[feature_name] = any(series_count(args.base_url, metric, args.db, live_raw_start, live_end) > 0 for metric in detectors)
        rollup_feature_flags[feature_name] = any(series_count(args.base_url, metric, args.db, rollup_start, end) > 0 for metric in detectors)

    detected_rollup_presence = any(series_count(args.base_url, item.metric, args.db, rollup_start, end) > 0 for item in CORE_ROLLUPS)
    host_matcher = f'{{db="{args.db}",host!=""}}'
    host_series_count = matcher_count(args.base_url, host_matcher, feature_start, end)

    effective_phase = args.phase
    if args.phase == "auto":
        effective_phase = "full" if detected_rollup_presence else "raw"

    sections: List[dict] = []

    if effective_phase in {"raw", "full"}:
        sections.append({"title": "Core raw metrics", "items": run_metric_checks(args.base_url, args.db, CORE_RAW, raw_start, end)})
        for feature_name, enabled in raw_feature_flags.items():
            if not enabled:
                skipped_reason = (
                    "feature detected historically, but not active in raw window"
                    if feature_flags[feature_name]
                    else "feature not detected"
                )
                sections.append({"title": f"Conditional raw metrics ({feature_name})", "items": [], "skipped_reason": skipped_reason})
                continue
            items: Sequence[MetricCheck] = FEATURES[feature_name]["raw"]  # type: ignore[index]
            sections.append({"title": f"Conditional raw metrics ({feature_name})", "items": run_metric_checks(args.base_url, args.db, items, raw_start, end)})
    else:
        sections.append({"title": "Core raw metrics", "items": [], "skipped_reason": f"phase={effective_phase}"})

    if effective_phase in {"rollup", "full"}:
        sections.append({"title": "Core rollup metrics", "items": run_metric_checks(args.base_url, args.db, CORE_ROLLUPS, rollup_start, end)})
        for feature_name, enabled in rollup_feature_flags.items():
            if not enabled:
                skipped_reason = (
                    "feature detected historically, but not active in rollup window"
                    if feature_flags[feature_name]
                    else "feature not detected"
                )
                sections.append({"title": f"Conditional rollups ({feature_name})", "items": [], "skipped_reason": skipped_reason})
                continue
            items: Sequence[MetricCheck] = FEATURES[feature_name]["rollups"]  # type: ignore[index]
            sections.append({"title": f"Conditional rollups ({feature_name})", "items": run_metric_checks(args.base_url, args.db, items, rollup_start, end)})
    else:
        sections.append({
            "title": "Core rollup metrics",
            "items": [],
            "skipped_reason": "rollup phase not active yet" if args.phase == "auto" and not detected_rollup_presence else f"phase={effective_phase}",
        })

    cleanup_items = [{
        "metric": host_matcher,
        "level": "WARNING" if host_series_count > 0 else "OK",
        "series": host_series_count,
        "reason": "Host-tagged raw series detected. Run vm-rewrite-drop-label.py if you want to normalize away infrastructure labels.",
    }]
    sections.append({"title": "Cleanup checks", "items": cleanup_items})

    levels = [item["level"] for section in sections for item in section["items"]]
    overall = worst_level(levels)
    code = 2 if overall == "CRITICAL" else 1 if overall == "WARNING" else 0

    payload = {
        "script": script_metadata(),
        "base_url": args.base_url,
        "db": args.db,
        "requested_phase": args.phase,
        "effective_phase": effective_phase,
        "detected_rollup_presence": detected_rollup_presence,
        "host_series_count": host_series_count,
        "windows": {
            "raw_start": raw_start,
            "rollup_start": rollup_start,
            "feature_start": feature_start,
            "end": end,
            "live_raw_start": live_raw_start,
            "live_end": live_end,
        },
        "detected_features": feature_flags,
        "raw_window_features": raw_feature_flags,
        "live_raw_window_features": live_raw_feature_flags,
        "rollup_window_features": rollup_feature_flags,
        "overall": overall,
        "sections": sections,
    }

    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return code

    print_report_header("EVCC VM data check", "==================", str(payload.get("script", {}).get("generated_at", "")) or None)
    print(f"Base URL:           {args.base_url}")
    print(f"db label:           {args.db}")
    print(f"Requested phase:    {args.phase}")
    print(f"Effective phase:    {effective_phase}")
    print(f"Rollups detected:   {'yes' if detected_rollup_presence else 'no'}")
    print(f"Host-tagged series: {host_series_count}")
    print(f"Raw window:         {raw_start} -> {end}")
    print(f"Live raw window:    {live_raw_start} -> {live_end}")
    print(f"Rollup window:      {rollup_start} -> {end}")
    print(f"Feature lookback:   {feature_start} -> {end}")
    print("\nDetected features")
    print("-----------------")
    for name in sorted(feature_flags):
        print(f"{name:<10} {'yes' if feature_flags[name] else 'no'}")

    for section in sections:
        render_section(section["title"], section["items"], section.get("skipped_reason"))

    print("\nOverall")
    print("-------")
    print(overall)
    print("\nExit codes: OK=0, WARNING=1, CRITICAL=2")
    return code


if __name__ == "__main__":
    sys.exit(main())
