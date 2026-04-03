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
from dataclasses import dataclass
from typing import Iterable, Iterator, List, Sequence

UTC = dt.timezone.utc

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


def iso_z(value: dt.datetime | None) -> str:
    if value is None:
        return "-"
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_iso(value: str) -> dt.datetime:
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


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


def export_lines(base_url: str, metric: str, db_label: str, start: str, end: str) -> Iterable[str]:
    params = [
        ("match[]", f'{metric}{{db="{db_label}"}}'),
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


def vm_stats(base_url: str, metric: str, db_label: str, start: str, end: str) -> SpanStats:
    total_points = 0
    total_series = 0
    first: dt.datetime | None = None
    last: dt.datetime | None = None

    for line in export_lines(base_url, metric, db_label, start, end):
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


def choose_vm_metric(base_url: str, db_label: str, measurement: str, start: str, end: str) -> tuple[str, SpanStats]:
    best_metric = candidate_metrics(measurement)[0]
    best_stats = SpanStats(points=0, series=0, first=None, last=None)
    for candidate in candidate_metrics(measurement):
        stats = vm_stats(base_url, candidate, db_label, start, end)
        if stats.points > best_stats.points:
            best_metric = candidate
            best_stats = stats
    return best_metric, best_stats


def infer_hint(measurement: str, field_types: Sequence[str], vm_metric: str, group: str, status: str) -> str | None:
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
    vm_db_label: str,
    measurement: str,
    start: str,
    end: str,
    username: str | None,
    password: str | None,
    tolerance_seconds: int,
) -> MetricCoverage:
    influx = influx_stats(influx_base_url, influx_db, measurement, start, end, username, password)
    field_types = influx_field_types(influx_base_url, influx_db, measurement, username, password)
    vm_metric, vm = choose_vm_metric(vm_base_url, vm_db_label, measurement, start, end)

    reasons: List[str] = []
    status = "OK"

    if influx.points <= 0:
        status = "SKIP"
        reasons.append("no source data in the selected Influx range")
    elif vm.points <= 0:
        status = "MISSING"
        reasons.append("no imported VM samples for this measurement")
    else:
        if influx.series > 0 and vm.series < influx.series:
            status = "TRUNCATED"
            reasons.append(f"fewer VM series than Influx ({vm.series} < {influx.series})")
        if influx.first and vm.first and vm.first > influx.first + dt.timedelta(seconds=tolerance_seconds):
            status = "TRUNCATED"
            reasons.append(f"VM starts later ({iso_z(vm.first)} > {iso_z(influx.first)})")
        if influx.last and vm.last and vm.last < influx.last - dt.timedelta(seconds=tolerance_seconds):
            status = "TRUNCATED"
            reasons.append(f"VM ends earlier ({iso_z(vm.last)} < {iso_z(influx.last)})")
        if influx.points > 0 and vm.points < influx.points:
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


def render_group(label: str, items: Sequence[MetricCoverage], only_problems: bool) -> None:
    relevant = [item for item in items if item.status != "SKIP"]
    shown = [item for item in relevant if not only_problems or item.status != "OK"]
    problems = [item for item in relevant if item.status in {"MISSING", "TRUNCATED"}]

    print(label)
    print("-" * len(label))
    print(f"- Checked: {len(relevant)}")
    print(f"- OK: {sum(1 for item in relevant if item.status == 'OK')}")
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


def render_report(results: Sequence[MetricCoverage], start: str, end: str, only_problems: bool) -> int:
    filtered = [item for item in results if item.status != "SKIP"]
    repo_items = [item for item in filtered if item.group == "repo-relevant"]
    extra_items = [item for item in filtered if item.group == "additional"]
    repo_problems = [item for item in repo_items if item.status in {"MISSING", "TRUNCATED"}]
    extra_problems = [item for item in extra_items if item.status in {"MISSING", "TRUNCATED"}]

    print("EVCC import coverage check")
    print("==========================")
    print(f"Range: {start} -> {end}")
    print()
    print("Summary")
    print("-------")
    print(f"- Measurements checked: {len(filtered)}")
    print(f"- Repo-relevant checked: {len(repo_items)}")
    print(f"- Repo-relevant problems: {len(repo_problems)}")
    print(f"- Additional checked: {len(extra_items)}")
    print(f"- Additional problems: {len(extra_problems)}")
    print()
    render_group("Repo-relevant measurements", repo_items, only_problems)
    if extra_items:
        print()
        render_group("Additional measurements", extra_items, only_problems)

    print()
    print("Result")
    print("------")
    if repo_problems:
        print("NOT OK: at least one repo-relevant raw measurement is missing or truncated in VictoriaMetrics.")
        print("Stop before cleanup or rollups for those metrics, or explicitly re-import the affected measurements.")
        return 2
    if extra_problems:
        print("OK FOR REPO: the repo-relevant raw measurements look complete enough for cleanup and rollups.")
        print("REVIEW ADDITIONAL MEASUREMENTS: extra EVCC measurements are missing or truncated, but they are outside the active dashboard schema.")
        return 1
    print("OK: the checked raw measurements look complete enough for the next migration step.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--influx-url", required=True, help="InfluxDB v1 base URL, e.g. http://127.0.0.1:8086")
    ap.add_argument("--influx-db", required=True, help="Influx database name, e.g. evcc")
    ap.add_argument("--influx-user")
    ap.add_argument("--influx-password")
    ap.add_argument("--vm-base-url", required=True, help="VictoriaMetrics base URL, e.g. http://127.0.0.1:8428")
    ap.add_argument("--vm-db-label", default="evcc", help='value of the db label in VM, default: "evcc"')
    ap.add_argument("--start", required=True, help="UTC start timestamp, e.g. 2026-03-21T00:00:00Z")
    ap.add_argument("--end", required=True, help="UTC end timestamp, e.g. 2026-04-03T23:59:59Z")
    ap.add_argument("--measurement-regex", help="only compare matching Influx measurements")
    ap.add_argument("--repo-relevant-only", action="store_true", help="limit the check to the repo-relevant raw measurements used by dashboards and rollups")
    ap.add_argument("--all-measurements", action="store_true", help="deprecated compatibility flag; full measurement coverage is now the default")
    ap.add_argument("--only-problems", action="store_true", help="show only non-OK measurements in the details section")
    ap.add_argument("--tolerance-seconds", type=int, default=3600, help="allowed clock/span drift before a metric is flagged as truncated")
    ap.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = ap.parse_args()

    measurements = influx_measurements(
        args.influx_url,
        args.influx_db,
        args.influx_user,
        args.influx_password,
        args.measurement_regex,
        args.repo_relevant_only,
    )
    results = [
        compare_measurement(
            args.influx_url,
            args.influx_db,
            args.vm_base_url,
            args.vm_db_label,
            measurement,
            args.start,
            args.end,
            args.influx_user,
            args.influx_password,
            args.tolerance_seconds,
        )
        for measurement in measurements
    ]

    if args.json:
        payload = {
            "range": {"start": args.start, "end": args.end},
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
        extra_problems = any(item.group == "additional" and item.status in {"MISSING", "TRUNCATED"} for item in results if item.status != "SKIP")
        if repo_problems:
            return 2
        if extra_problems:
            return 1
        return 0

    return render_report(results, args.start, args.end, args.only_problems)


if __name__ == "__main__":
    raise SystemExit(main())
