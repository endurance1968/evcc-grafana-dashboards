#!/usr/bin/env python3
"""Compare raw Influx measurement coverage against imported VictoriaMetrics metrics.

This helper is meant for the first validation step right after `vmctl influx`.
It compares the imported VM raw metrics against the Influx source and highlights
measurements that are missing entirely or look truncated in VM.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import urllib.parse
import urllib.request
import sys
from dataclasses import dataclass
from typing import Iterable, Iterator, List, Sequence
from zoneinfo import ZoneInfo

UTC = dt.timezone.utc
SCRIPT_NAME = "compare_import_coverage.py"
SCRIPT_VERSION = "2026.04.09.1"
SCRIPT_LAST_MODIFIED = "2026-04-09"

REPO_RELEVANT_MEASUREMENTS: Sequence[str] = (
    "auxPower",
    "batteryPower",
    "batterySoc",
    "chargePower",
    "extPower",
    "gridEnergy",
    "gridPower",
    "homePower",
    "prioritySoc",
    "pvPower",
    "tariffCo2",
    "tariffFeedIn",
    "tariffGrid",
    "tariffPriceLoadpoints",
    "tariffSolar",
    "vehicleOdometer",
    "vehicleSoc",
)

REPO_RELEVANT_SET = set(REPO_RELEVANT_MEASUREMENTS)


@dataclass(frozen=True)
class SpanStats:
    points: int
    series: int
    first: dt.datetime | None
    last: dt.datetime | None


@dataclass(frozen=True)
class MetricCoverage:
    measurement: str
    vm_metric: str
    group: str
    status: str
    influx: SpanStats
    vm: SpanStats
    reasons: Sequence[str]
    hint: str | None


@dataclass(frozen=True)
class EnergyCoverage:
    name: str
    group: str
    status: str
    checked_windows: int
    problem_windows: int
    reasons: Sequence[str]
    examples: Sequence[str]
    hint: str | None


def iso_z(value: dt.datetime | None) -> str:
    if value is None:
        return "-"
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_iso(value: str) -> dt.datetime:
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def local_now() -> dt.datetime:
    return dt.datetime.now().astimezone()


def local_timestamp() -> str:
    return local_now().replace(microsecond=0).isoformat()


def script_metadata(generated_at: str | None = None) -> dict[str, str]:
    return {
        "name": SCRIPT_NAME,
        "version": SCRIPT_VERSION,
        "last_modified": SCRIPT_LAST_MODIFIED,
        "generated_at": generated_at or local_timestamp(),
    }


def print_report_header(title: str, underline: str, generated_at: str | None = None) -> None:
    metadata = script_metadata(generated_at)
    print(title)
    print(underline)
    print(f"Script:       {metadata['name']}")
    print(f"Version:      {metadata['version']}")
    print(f"Last modified:{metadata['last_modified']:>12}")
    print(f"Run at:       {metadata['generated_at']}")


def progress(message: str, enabled: bool) -> None:
    if enabled:
        print(message, file=sys.stderr, flush=True)


def http_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=300) as response:
        return json.load(response)


def build_url(base_url: str, path: str, params: dict[str, str]) -> str:
    encoded = urllib.parse.urlencode(params)
    return f"{base_url.rstrip('/')}{path}?{encoded}"


def influx_query(base_url: str, db: str, query: str, username: str | None, password: str | None) -> dict:
    params = {"db": db, "q": query}
    if username:
        params["u"] = username
    if password:
        params["p"] = password
    return http_json(build_url(base_url, "/query", params))


def iter_influx_series(payload: dict) -> Iterator[dict]:
    for result in payload.get("results", []):
        for series in result.get("series", []) or []:
            if isinstance(series, dict):
                yield series


def measurement_group(measurement: str) -> str:
    return "repo-relevant" if measurement in REPO_RELEVANT_SET else "additional"


def influx_measurements(
    base_url: str,
    db: str,
    username: str | None,
    password: str | None,
    measurement_regex: str | None,
    repo_relevant_only: bool,
) -> List[str]:
    payload = influx_query(base_url, db, "SHOW MEASUREMENTS", username, password)
    measurements: List[str] = []
    rx = re.compile(measurement_regex) if measurement_regex else None
    for series in iter_influx_series(payload):
        for row in series.get("values", []) or []:
            if not isinstance(row, list) or not row:
                continue
            name = str(row[0])
            if rx and not rx.search(name):
                continue
            if repo_relevant_only and name not in REPO_RELEVANT_SET:
                continue
            measurements.append(name)
    return sorted(set(measurements))


def influx_field_types(base_url: str, db: str, measurement: str, username: str | None, password: str | None) -> List[str]:
    payload = influx_query(base_url, db, f'SHOW FIELD KEYS FROM "{measurement}"', username, password)
    values: List[str] = []
    for series in iter_influx_series(payload):
        for row in series.get("values", []) or []:
            if isinstance(row, list) and len(row) >= 2 and row[1] is not None:
                values.append(str(row[1]).lower())
    return sorted(set(values))


def influx_count_for_measurement(base_url: str, db: str, measurement: str, start: str, end: str, username: str | None, password: str | None) -> int:
    query = (
        f'SELECT COUNT("value") FROM "{measurement}" '
        f"WHERE time >= '{start}' AND time <= '{end}'"
    )
    payload = influx_query(base_url, db, query, username, password)
    total = 0
    for series in iter_influx_series(payload):
        for row in series.get("values", []) or []:
            if isinstance(row, list) and len(row) >= 2 and row[1] is not None:
                total += int(row[1])
    return total


def influx_series_count_for_measurement(
    base_url: str,
    db: str,
    measurement: str,
    start: str,
    end: str,
    username: str | None,
    password: str | None,
) -> int:
    query = (
        f'SELECT COUNT("value") FROM "{measurement}" '
        f"WHERE time >= '{start}' AND time <= '{end}' GROUP BY *"
    )
    payload = influx_query(base_url, db, query, username, password)
    return sum(1 for _ in iter_influx_series(payload))


def influx_edge_time(
    base_url: str,
    db: str,
    measurement: str,
    start: str,
    end: str,
    username: str | None,
    password: str | None,
    ascending: bool,
) -> dt.datetime | None:
    order = "ASC" if ascending else "DESC"
    query = (
        f'SELECT "value" FROM "{measurement}" '
        f"WHERE time >= '{start}' AND time <= '{end}' ORDER BY time {order} LIMIT 1"
    )
    payload = influx_query(base_url, db, query, username, password)
    for series in iter_influx_series(payload):
        for row in series.get("values", []) or []:
            if isinstance(row, list) and row and isinstance(row[0], str):
                return parse_iso(row[0])
    return None


def influx_stats(
    base_url: str,
    db: str,
    measurement: str,
    start: str,
    end: str,
    username: str | None,
    password: str | None,
) -> SpanStats:
    points = influx_count_for_measurement(base_url, db, measurement, start, end, username, password)
    if points <= 0:
        return SpanStats(points=0, series=0, first=None, last=None)
    series = influx_series_count_for_measurement(base_url, db, measurement, start, end, username, password)
    first = influx_edge_time(base_url, db, measurement, start, end, username, password, ascending=True)
    last = influx_edge_time(base_url, db, measurement, start, end, username, password, ascending=False)
    return SpanStats(points=points, series=series, first=first, last=last)


def export_lines(base_url: str, metric: str, start: str, end: str) -> Iterable[str]:
    params = [
        ("match[]", metric),
        ("start", start),
        ("end", end),
    ]
    query = urllib.parse.urlencode(params)
    url = f"{base_url.rstrip('/')}/api/v1/export?{query}"
    with urllib.request.urlopen(url, timeout=300) as response:
        for raw_line in response:
            line = raw_line.decode("utf-8").strip()
            if line:
                yield line


def export_lines_for_matcher(base_url: str, matcher: str, start: str, end: str) -> Iterable[str]:
    params = [
        ("match[]", matcher),
        ("start", start),
        ("end", end),
    ]
    query = urllib.parse.urlencode(params)
    url = f"{base_url.rstrip('/')}/api/v1/export?{query}"
    with urllib.request.urlopen(url, timeout=300) as response:
        for raw_line in response:
            line = raw_line.decode("utf-8").strip()
            if line:
                yield line


def vm_stats(base_url: str, metric: str, start: str, end: str) -> SpanStats:
    total_points = 0
    total_series = 0
    first: dt.datetime | None = None
    last: dt.datetime | None = None

    for line in export_lines(base_url, metric, start, end):
        payload = json.loads(line)
        timestamps = payload.get("timestamps", [])
        if not isinstance(timestamps, list) or not timestamps:
            continue
        total_series += 1
        total_points += len(timestamps)
        line_first = dt.datetime.fromtimestamp(int(timestamps[0]) / 1000, tz=UTC)
        line_last = dt.datetime.fromtimestamp(int(timestamps[-1]) / 1000, tz=UTC)
        if first is None or line_first < first:
            first = line_first
        if last is None or line_last > last:
            last = line_last

    return SpanStats(points=total_points, series=total_series, first=first, last=last)


def candidate_metrics(measurement: str) -> List[str]:
    candidates = [measurement]
    if not measurement.endswith("_value"):
        candidates.append(f"{measurement}_value")
    return candidates


def choose_vm_metric(base_url: str, measurement: str, start: str, end: str) -> tuple[str, SpanStats]:
    best_metric = candidate_metrics(measurement)[0]
    best_stats = SpanStats(points=0, series=0, first=None, last=None)
    for candidate in candidate_metrics(measurement):
        stats = vm_stats(base_url, candidate, start, end)
        if stats.points > best_stats.points:
            best_metric = candidate
            best_stats = stats
    return best_metric, best_stats


def has_full_span(influx: SpanStats, vm: SpanStats, tolerance_seconds: int) -> bool:
    if influx.first and vm.first and vm.first > influx.first + dt.timedelta(seconds=tolerance_seconds):
        return False
    if influx.last and vm.last and vm.last < influx.last - dt.timedelta(seconds=tolerance_seconds):
        return False
    return True


def infer_hint(measurement: str, field_types: Sequence[str], vm_metric: str, group: str, status: str) -> str | None:
    if status == "NORMALIZED":
        return "likely normalized after host-label cleanup or duplicate-sample merge; use the critical PV energy check to spot real raw-data loss"
    if group == "repo-relevant":
        return None
    if any(field_type in {"string", "boolean"} for field_type in field_types):
        return "likely string/boolean status or metadata measurement"
    if vm_metric == measurement and not measurement.endswith("_value"):
        return "likely field-name mapping mismatch or unsupported non-numeric import shape"
    if status in {"MISSING", "TRUNCATED"}:
        return "likely real import gap for an additional measurement"
    return None


def compare_measurement(
    influx_base_url: str,
    influx_db: str,
    vm_base_url: str,
    measurement: str,
    start: str,
    end: str,
    username: str | None,
    password: str | None,
    tolerance_seconds: int,
) -> MetricCoverage:
    influx = influx_stats(influx_base_url, influx_db, measurement, start, end, username, password)
    field_types = influx_field_types(influx_base_url, influx_db, measurement, username, password)
    vm_metric, vm = choose_vm_metric(vm_base_url, measurement, start, end)

    reasons: List[str] = []
    status = "OK"

    if influx.points <= 0:
        status = "SKIP"
        reasons.append("no source data in the selected Influx range")
    elif vm.points <= 0:
        status = "MISSING"
        reasons.append("no imported VM samples for this measurement")
    else:
        full_span = has_full_span(influx, vm, tolerance_seconds)
        series_reduced = influx.series > 0 and vm.series < influx.series
        points_reduced = influx.points > 0 and vm.points < influx.points

        if series_reduced and full_span:
            status = "NORMALIZED"
            reasons.append(
                f"VM has fewer series than Influx ({vm.series} < {influx.series}), but the full time span is present; likely merged infrastructure labels"
            )
        elif series_reduced:
            status = "TRUNCATED"
            reasons.append(f"fewer VM series than Influx ({vm.series} < {influx.series})")

        if influx.first and vm.first and vm.first > influx.first + dt.timedelta(seconds=tolerance_seconds):
            status = "TRUNCATED"
            reasons.append(f"VM starts later ({iso_z(vm.first)} > {iso_z(influx.first)})")
        if influx.last and vm.last and vm.last < influx.last - dt.timedelta(seconds=tolerance_seconds):
            status = "TRUNCATED"
            reasons.append(f"VM ends earlier ({iso_z(vm.last)} < {iso_z(influx.last)})")

        if points_reduced:
            if status == "NORMALIZED":
                reasons.append(
                    f"VM also has fewer samples than Influx ({vm.points} < {influx.points}); likely duplicate samples collapsed during label cleanup"
                )
            else:
                status = "TRUNCATED"
                reasons.append(f"fewer VM samples than Influx ({vm.points} < {influx.points})")

    group = measurement_group(measurement)
    return MetricCoverage(
        measurement=measurement,
        vm_metric=vm_metric,
        group=group,
        status=status,
        influx=influx,
        vm=vm,
        reasons=reasons,
        hint=infer_hint(measurement, field_types, vm_metric, group, status),
    )


def iter_month_windows(start: str, end: str, timezone_name: str) -> List[tuple[str, str, str]]:
    start_utc = parse_iso(start)
    end_utc = parse_iso(end)
    timezone = ZoneInfo(timezone_name)
    start_local = start_utc.astimezone(timezone)
    end_local = end_utc.astimezone(timezone)
    cursor = dt.datetime(start_local.year, start_local.month, 1, tzinfo=timezone)
    end_month = dt.datetime(end_local.year, end_local.month, 1, tzinfo=timezone)
    windows: List[tuple[str, str, str]] = []
    while cursor <= end_month:
        if cursor.month == 12:
            next_month = dt.datetime(cursor.year + 1, 1, 1, tzinfo=timezone)
        else:
            next_month = dt.datetime(cursor.year, cursor.month + 1, 1, tzinfo=timezone)
        window_start = max(start_utc, cursor.astimezone(UTC))
        window_end = min(end_utc, next_month.astimezone(UTC) - dt.timedelta(seconds=1))
        if window_start <= window_end:
            windows.append((f"{cursor.year:04d}-{cursor.month:02d}", iso_z(window_start), iso_z(window_end)))
        cursor = next_month
    return windows


def first_numeric_value(payload: dict) -> float | None:
    for series in iter_influx_series(payload):
        for row in series.get("values", []) or []:
            if isinstance(row, list) and len(row) >= 2 and row[1] is not None:
                return float(row[1])
    return None


def influx_legacy_pv_total_kwh(
    base_url: str,
    db: str,
    start: str,
    end: str,
    username: str | None,
    password: str | None,
    timezone_name: str,
    bucket_seconds: int,
    peak_power_limit: float,
) -> float:
    query = (
        'SELECT sum("integral") FROM ('
        'SELECT integral("subquery") / 3600000 AS "integral" FROM '
        '(SELECT max("value") AS "subquery" FROM "pvPower" '
        f"WHERE time >= '{start}' AND time <= '{end}' and value >=0 AND value < {peak_power_limit} "
        "AND (\"id\"::tag = '') "
        f"GROUP BY time({bucket_seconds}s) fill(0) tz('{timezone_name}')) "
        f"GROUP BY time(1d) fill(0) tz('{timezone_name}'))"
    )
    payload = influx_query(base_url, db, query, username, password)
    value = first_numeric_value(payload)
    return float(value) if value is not None else 0.0


def vm_legacy_bucket_energy_kwh(
    base_url: str,
    start: str,
    end: str,
    bucket_seconds: int,
    peak_power_limit: float,
) -> float:
    matcher = 'pvPower_value{id=""}'
    start_ms = int(parse_iso(start).timestamp() * 1000)
    end_ms = int(parse_iso(end).timestamp() * 1000) + 1000
    bucket_ms = bucket_seconds * 1000
    bucket_map: dict[int, list[float]] = {}
    try:
        lines = export_lines_for_matcher(base_url, matcher, start, end)
    except urllib.error.HTTPError:
        return 0.0
    for line in lines:
        payload = json.loads(line)
        timestamps = payload.get("timestamps", [])
        values = payload.get("values", [])
        for timestamp, value in zip(timestamps, values):
            ts = int(timestamp)
            val = float(value)
            if ts < start_ms or ts >= end_ms:
                continue
            if val < 0 or val >= peak_power_limit:
                continue
            bucket_start = start_ms + (((ts - start_ms) // bucket_ms) * bucket_ms)
            bucket_map.setdefault(bucket_start, []).append(val)
    total_wh = 0.0
    for bucket_start in range(start_ms, end_ms, bucket_ms):
        values = bucket_map.get(bucket_start)
        if not values:
            continue
        total_wh += max(values) * bucket_ms / 3600000.0
    return total_wh / 1000.0


def build_critical_energy_checks(
    influx_base_url: str,
    influx_db: str,
    vm_base_url: str,
    start: str,
    end: str,
    username: str | None,
    password: str | None,
    timezone_name: str,
    bucket_seconds: int,
    peak_power_limit: float,
    tolerance_ratio: float,
    show_progress: bool = False,
) -> List[EnergyCoverage]:
    checked_windows = 0
    problem_windows = 0
    examples: List[str] = []
    windows = iter_month_windows(start, end, timezone_name)
    total_windows = len(windows)
    for index, (label, window_start, window_end) in enumerate(windows, start=1):
        progress(f"Critical energy progress: month={index}/{total_windows} window={label}", show_progress)
        influx_kwh = influx_legacy_pv_total_kwh(
            influx_base_url,
            influx_db,
            window_start,
            window_end,
            username,
            password,
            timezone_name,
            bucket_seconds,
            peak_power_limit,
        )
        if influx_kwh <= 0:
            continue
        checked_windows += 1
        vm_kwh = vm_legacy_bucket_energy_kwh(
            vm_base_url,

            window_start,
            window_end,
            bucket_seconds,
            peak_power_limit,
        )
        lower_bound = influx_kwh * (1.0 - tolerance_ratio)
        upper_bound = influx_kwh * (1.0 + tolerance_ratio)
        if vm_kwh < lower_bound or vm_kwh > upper_bound:
            problem_windows += 1
            if len(examples) < 6:
                examples.append(f"{label}: Influx={influx_kwh:.1f} kWh, VM={vm_kwh:.1f} kWh")

    if checked_windows == 0:
        return [
            EnergyCoverage(
                name='pvPower{id=""} monthly legacy energy parity',
                group='critical-energy',
                status='SKIP',
                checked_windows=0,
                problem_windows=0,
                reasons=['no positive Influx pvPower total-series energy in the selected range'],
                examples=[],
                hint=None,
            )
        ]

    if problem_windows > 0:
        return [
            EnergyCoverage(
                name='pvPower{id=""} monthly legacy energy parity',
                group='critical-energy',
                status='TRUNCATED',
                checked_windows=checked_windows,
                problem_windows=problem_windows,
                reasons=[
                    f'VM legacy PV total-series energy drifted outside the allowed monthly tolerance in {problem_windows} of {checked_windows} checked month(s)'
                ],
                examples=examples,
                hint='raw pvPower total-series data in VictoriaMetrics is incomplete or materially different; re-import pvPower before rebuilding rollups',
            )
        ]

    return [
        EnergyCoverage(
            name='pvPower{id=""} monthly legacy energy parity',
            group='critical-energy',
            status='OK',
            checked_windows=checked_windows,
            problem_windows=0,
            reasons=['monthly PV total-series energy stayed within the allowed tolerance across the checked range'],
            examples=[],
            hint=None,
        )
    ]


def render_group(label: str, items: Sequence[MetricCoverage], only_problems: bool) -> None:
    relevant = [item for item in items if item.status != "SKIP"]
    shown = [item for item in relevant if not only_problems or item.status in {"MISSING", "TRUNCATED"}]
    problems = [item for item in relevant if item.status in {"MISSING", "TRUNCATED"}]

    print(label)
    print("-" * len(label))
    print(f"- Checked: {len(relevant)}")
    print(f"- OK: {sum(1 for item in relevant if item.status == 'OK')}")
    print(f"- Normalized: {sum(1 for item in relevant if item.status == 'NORMALIZED')}")
    print(f"- Problems: {len(problems)}")

    if shown:
        print()
        for item in shown:
            print(f"- {item.measurement} -> {item.vm_metric}: {item.status}")
            print(
                f"  Influx: series={item.influx.series}, points={item.influx.points}, "
                f"first={iso_z(item.influx.first)}, last={iso_z(item.influx.last)}"
            )
            print(
                f"  VM:     series={item.vm.series}, points={item.vm.points}, "
                f"first={iso_z(item.vm.first)}, last={iso_z(item.vm.last)}"
            )
            if item.reasons:
                print(f"  Reason: {'; '.join(item.reasons)}")
            if item.hint:
                print(f"  Hint:   {item.hint}")


def render_energy_checks(label: str, items: Sequence[EnergyCoverage], only_problems: bool) -> None:
    relevant = [item for item in items if item.status != "SKIP"]
    shown = [item for item in relevant if not only_problems or item.status in {"MISSING", "TRUNCATED"}]
    problems = [item for item in relevant if item.status in {"MISSING", "TRUNCATED"}]

    print(label)
    print("-" * len(label))
    print(f"- Checked: {len(relevant)}")
    print(f"- OK: {sum(1 for item in relevant if item.status == 'OK')}")
    print(f"- Normalized: {sum(1 for item in relevant if item.status == 'NORMALIZED')}")
    print(f"- Problems: {len(problems)}")

    if shown:
        print()
        for item in shown:
            print(f"- {item.name}: {item.status}")
            print(f"  Windows checked: {item.checked_windows}")
            print(f"  Problem windows: {item.problem_windows}")
            for reason in item.reasons:
                print(f"  Reason: {reason}")
            for example in item.examples:
                print(f"  Example: {example}")
            if item.hint:
                print(f"  Hint:   {item.hint}")


def render_report(
    results: Sequence[MetricCoverage],
    critical_checks: Sequence[EnergyCoverage],
    start: str,
    end: str,
    only_problems: bool,
    metadata: dict[str, str],
) -> int:
    filtered = [item for item in results if item.status != "SKIP"]
    repo_items = [item for item in filtered if item.group == "repo-relevant"]
    extra_items = [item for item in filtered if item.group == "additional"]
    energy_items = [item for item in critical_checks if item.status != "SKIP"]
    repo_problems = [item for item in repo_items if item.status in {"MISSING", "TRUNCATED"}]
    extra_problems = [item for item in extra_items if item.status in {"MISSING", "TRUNCATED"}]
    energy_problems = [item for item in energy_items if item.status in {"MISSING", "TRUNCATED"}]

    print_report_header("EVCC import coverage check", "==========================", metadata.get("generated_at"))
    print(f"Range: {start} -> {end}")
    print()
    print("Summary")
    print("-------")
    print(f"- Measurements checked: {len(filtered)}")
    print(f"- Repo-relevant checked: {len(repo_items)}")
    print(f"- Repo-relevant problems: {len(repo_problems)}")
    print(f"- Critical energy checks: {len(energy_items)}")
    print(f"- Critical energy problems: {len(energy_problems)}")
    print(f"- Additional checked: {len(extra_items)}")
    print(f"- Additional problems: {len(extra_problems)}")
    print()
    render_group("Repo-relevant measurements", repo_items, only_problems)
    if energy_items:
        print()
        render_energy_checks("Critical energy checks", energy_items, only_problems)
    if extra_items:
        print()
        render_group("Additional measurements", extra_items, only_problems)

    print()
    print("Result")
    print("------")
    if repo_problems or energy_problems:
        print("NOT OK: at least one repo-relevant raw measurement or critical PV energy check failed in VictoriaMetrics.")
        print("Stop before cleanup or rollups for those metrics, or explicitly re-import the affected raw measurement family.")
        return 2
    if extra_problems:
        print("OK FOR REPO: the repo-relevant raw measurements and critical PV energy checks look complete enough for cleanup and rollups.")
        print("REVIEW ADDITIONAL MEASUREMENTS: extra EVCC measurements are missing or truncated, but they are outside the active dashboard schema.")
        return 1
    print("OK: the checked raw measurements and critical PV energy checks look complete enough for the next migration step.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--influx-url", required=True, help="InfluxDB v1 base URL, e.g. http://127.0.0.1:8086")
    ap.add_argument("--influx-db", required=True, help="Influx database name, e.g. evcc")
    ap.add_argument("--influx-user")
    ap.add_argument("--influx-password")
    ap.add_argument("--vm-base-url", required=True, help="VictoriaMetrics base URL, e.g. http://127.0.0.1:8428")
    ap.add_argument(
        "--vm-db-label",
        default=None,
        help="deprecated compatibility argument; ignored because the VM side is scanned without requiring a db label",
    )
    ap.add_argument("--start", required=True, help="UTC start timestamp, e.g. 2026-03-21T00:00:00Z")
    ap.add_argument("--end", required=True, help="UTC end timestamp, e.g. 2026-04-03T23:59:59Z")
    ap.add_argument("--measurement-regex", help="only compare matching Influx measurements")
    ap.add_argument("--repo-relevant-only", action="store_true", help="limit the check to the repo-relevant raw measurements used by dashboards and rollups")
    ap.add_argument("--all-measurements", action="store_true", help="deprecated compatibility flag; full measurement coverage is now the default")
    ap.add_argument("--only-problems", action="store_true", help="show only non-OK measurements in the details section")
    ap.add_argument("--tolerance-seconds", type=int, default=3600, help="allowed clock/span drift before a metric is flagged as truncated")
    ap.add_argument("--timezone", default="Europe/Berlin", help="local timezone for the critical PV monthly energy parity check")
    ap.add_argument("--energy-sample-interval-seconds", type=int, default=60, help="bucket size in seconds for the critical PV monthly energy parity check")
    ap.add_argument("--peak-power-limit", type=float, default=40000.0, help="upper limit for valid PV power samples in watts during the critical PV monthly energy parity check")
    ap.add_argument("--pv-energy-tolerance-ratio", type=float, default=0.15, help="allowed relative monthly drift for the critical PV total-series parity check")
    ap.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    ap.add_argument("--progress", action="store_true", help="print progress updates to stderr while measurements are being checked")
    args = ap.parse_args()

    measurements = influx_measurements(
        args.influx_url,
        args.influx_db,
        args.influx_user,
        args.influx_password,
        args.measurement_regex,
        args.repo_relevant_only,
    )
    results: List[MetricCoverage] = []
    total_measurements = len(measurements)
    for index, measurement in enumerate(measurements, start=1):
        progress(f"Measurement progress: {index}/{total_measurements} measurement={measurement}", args.progress)
        results.append(
            compare_measurement(
                args.influx_url,
                args.influx_db,
                args.vm_base_url,
                measurement,
                args.start,
                args.end,
                args.influx_user,
                args.influx_password,
                args.tolerance_seconds,
            )
        )
    critical_checks = build_critical_energy_checks(
        args.influx_url,
        args.influx_db,
        args.vm_base_url,

        args.start,
        args.end,
        args.influx_user,
        args.influx_password,
        args.timezone,
        args.energy_sample_interval_seconds,
        args.peak_power_limit,
        args.pv_energy_tolerance_ratio,
    )

    if args.json:
        payload = {
            "script": script_metadata(),
            "range": {"start": args.start, "end": args.end},
            "critical_checks": [
                {
                    "name": item.name,
                    "group": item.group,
                    "status": item.status,
                    "checked_windows": item.checked_windows,
                    "problem_windows": item.problem_windows,
                    "reasons": list(item.reasons),
                    "examples": list(item.examples),
                    "hint": item.hint,
                }
                for item in critical_checks
            ],
            "results": [
                {
                    "measurement": item.measurement,
                    "vm_metric": item.vm_metric,
                    "group": item.group,
                    "status": item.status,
                    "reasons": list(item.reasons),
                    "hint": item.hint,
                    "influx": {
                        "series": item.influx.series,
                        "points": item.influx.points,
                        "first": iso_z(item.influx.first),
                        "last": iso_z(item.influx.last),
                    },
                    "vm": {
                        "series": item.vm.series,
                        "points": item.vm.points,
                        "first": iso_z(item.vm.first),
                        "last": iso_z(item.vm.last),
                    },
                }
                for item in results
            ],
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        repo_problems = any(item.group == "repo-relevant" and item.status in {"MISSING", "TRUNCATED"} for item in results if item.status != "SKIP")
        energy_problems = any(item.status in {"MISSING", "TRUNCATED"} for item in critical_checks if item.status != "SKIP")
        extra_problems = any(item.group == "additional" and item.status in {"MISSING", "TRUNCATED"} for item in results if item.status != "SKIP")
        if repo_problems or energy_problems:
            return 2
        if extra_problems:
            return 1
        return 0

    return render_report(results, critical_checks, args.start, args.end, args.only_problems, script_metadata())


if __name__ == "__main__":
    raise SystemExit(main())


