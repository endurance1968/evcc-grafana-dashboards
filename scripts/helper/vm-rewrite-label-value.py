#!/usr/bin/env python3
"""Safely rewrite one VictoriaMetrics label value across historical series.

Use this for business-label renames, for example changing a PV title from
``Balkon PV`` to ``Balkon Sued`` after the live EVCC configuration has already
been changed.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from time import perf_counter, sleep
from typing import Iterator


SCRIPT_NAME = "vm-rewrite-label-value.py"
SCRIPT_VERSION = "2026.05.16.15"
SCRIPT_LAST_MODIFIED = "2026-05-16"
DEFAULT_START = "1"


@dataclass(frozen=True)
class SeriesStats:
    points: int
    first: int | None
    last: int | None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rewrite VictoriaMetrics series by replacing one label value in exported series."
    )
    parser.add_argument("--base-url", required=True, help="VictoriaMetrics base URL, e.g. http://localhost:8428")
    parser.add_argument("--matcher", required=True, help='Source VM series matcher, e.g. {title="Balkon PV"}')
    parser.add_argument("--label", required=True, help="Label key whose value should be rewritten, e.g. title")
    parser.add_argument("--from", dest="from_value", required=True, help="Current label value to replace.")
    parser.add_argument("--to", dest="to_value", required=True, help="New label value.")
    parser.add_argument("--backup-jsonl", required=True, help="Path for the raw exported JSONL backup.")
    parser.add_argument("--rewritten-jsonl", help="Path for the transformed JSONL that will be imported.")
    parser.add_argument(
        "--start",
        default=DEFAULT_START,
        help="Export/search start time as Unix seconds or RFC3339. Defaults to 1 so historical-only series are included without triggering VictoriaMetrics start=0 edge cases.",
    )
    parser.add_argument(
        "--end",
        default="",
        help="Export/search end time as Unix seconds or RFC3339. Defaults to tomorrow UTC as Unix seconds to include live samples written during the run.",
    )
    parser.add_argument("--write", action="store_true", help="Actually import rewritten targets and delete source series.")
    parser.add_argument(
        "--merge-target",
        action="store_true",
        help="Merge with already existing target series before import. Required when target timestamps overlap.",
    )
    parser.add_argument(
        "--import-over-target",
        action="store_true",
        help="Recovery/live mode: import rewritten source over existing target series without deleting targets first.",
    )
    parser.add_argument(
        "--allow-value-conflicts",
        action="store_true",
        help="Allow identical timestamps with different values during merge; source values win.",
    )
    parser.add_argument(
        "--keep-target-values-on-conflict",
        action="store_true",
        help="Allow identical timestamps with different values during merge; existing target values win.",
    )
    parser.add_argument("--reset-cache", action="store_true", help="Reset VM rollup cache after a successful write.")
    parser.add_argument("--import-batch-size", type=int, default=1, help="Number of series chunks per import batch.")
    parser.add_argument(
        "--max-import-line-bytes",
        type=int,
        default=8_000_000,
        help="Maximum size per JSONL import line before splitting a series.",
    )
    parser.add_argument("--progress-every", type=int, default=10, help="Emit progress after this many series.")
    parser.add_argument(
        "--skip-import-verification",
        action="store_true",
        help="Skip target verification after import. Source deletion still happens, so prefer the default.",
    )
    return parser.parse_args()


def progress(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def local_timestamp() -> str:
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


def default_end_timestamp() -> str:
    return str(int((datetime.now(timezone.utc) + timedelta(days=1)).timestamp()))


def api_time(value: str) -> str:
    value = str(value or "").strip()
    if not value:
        return ""
    try:
        float(value)
        return value
    except ValueError:
        pass
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SystemExit(f"Unsupported timestamp {value!r}; use Unix seconds or RFC3339.") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return str(max(1, int(parsed.timestamp())))


def script_metadata(generated_at: str | None = None) -> dict[str, str]:
    return {
        "name": SCRIPT_NAME,
        "version": SCRIPT_VERSION,
        "last_modified": SCRIPT_LAST_MODIFIED,
        "generated_at": generated_at or local_timestamp(),
    }


def elapsed_seconds(start: float, end: float) -> float:
    return round(end - start, 3)


def rate_per_second(count: int, seconds: float) -> float | None:
    if seconds <= 0:
        return None
    return round(count / seconds, 2)


def export_url(base_url: str, matcher: str, start: str, end: str) -> str:
    query = [("match[]", matcher)]
    if start:
        query.append(("start", start))
    if end:
        query.append(("end", end))
    return f"{base_url.rstrip('/')}/api/v1/export?" + urllib.parse.urlencode(query)


def iter_export_lines(base_url: str, matcher: str, start: str, end: str) -> Iterator[dict]:
    try:
        with urllib.request.urlopen(export_url(base_url, matcher, start, end), timeout=300) as response:
            for raw in response:
                if not raw.strip():
                    continue
                yield json.loads(raw)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} while exporting matcher {matcher}: {body}") from exc


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def append_jsonl_line(handle, item: dict) -> None:
    handle.write(json.dumps(item, separators=(",", ":"), ensure_ascii=True))
    handle.write("\n")


def normalize_series(item: dict) -> dict:
    return {
        "metric": {str(key): str(value) for key, value in item.get("metric", {}).items()},
        "timestamps": [int(ts) for ts in item.get("timestamps", [])],
        "values": [float(value) for value in item.get("values", [])],
    }


def transform_series(item: dict, label: str, from_value: str, to_value: str) -> dict:
    metric = dict(item["metric"])
    if metric.get(label) != from_value:
        raise ValueError(f"Source series does not have {label}={from_value!r}: {metric}")
    metric[label] = to_value
    return {
        "metric": metric,
        "timestamps": [int(ts) for ts in item["timestamps"]],
        "values": [float(value) for value in item["values"]],
    }


def transformed_matcher(metric: dict[str, str]) -> str:
    metric_name = metric.get("__name__", "")
    parts = [f'{key}="{value}"' for key, value in sorted(metric.items()) if key != "__name__"]
    labels = "{" + ",".join(parts) + "}"
    return f"{metric_name}{labels}" if metric_name else labels


def fetch_exact_series(base_url: str, metric: dict[str, str], start: str, end: str) -> list[dict]:
    exact_metric = dict(metric)
    return [
        item
        for item in iter_export_lines(base_url, transformed_matcher(metric), start, end)
        if metric_matches(item.get("metric", {}), exact_metric)
    ]


def http_get_json(base_url: str, path: str, params: list[tuple[str, str]]) -> dict:
    url = f"{base_url.rstrip('/')}{path}?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} for {path}: {body}") from exc


def instant_query_has_metric(base_url: str, metric: dict[str, str], timestamp_ms: int) -> bool:
    payload = http_get_json(
        base_url,
        "/api/v1/query",
        [("query", transformed_matcher(metric)), ("time", str(timestamp_ms / 1000))],
    )
    for item in payload.get("data", {}).get("result", []):
        if metric_matches(item.get("metric", {}), metric):
            return True
    return False


def series_api_has_metric(base_url: str, metric: dict[str, str], start: str, end: str) -> bool:
    payload = http_get_json(base_url, "/api/v1/series", [("match[]", transformed_matcher(metric)), ("start", start), ("end", end)])
    return any(metric_matches(item, metric) for item in payload.get("data", []))


def metric_matches(actual: dict[str, str], expected: dict[str, str]) -> bool:
    for key, expected_value in expected.items():
        if key == "__name__" and key not in actual:
            continue
        if str(actual.get(key, "")) != str(expected_value):
            return False
    return all(key in expected or key == "__name__" for key in actual)


def series_key(item: dict) -> tuple[tuple[str, str], ...]:
    return tuple(sorted((str(key), str(value)) for key, value in item["metric"].items()))


def series_stats(items: list[dict]) -> SeriesStats:
    total_points = 0
    first: int | None = None
    last: int | None = None
    for item in items:
        timestamps = [int(ts) for ts in item.get("timestamps", [])]
        if not timestamps:
            continue
        total_points += len(timestamps)
        item_first = min(timestamps)
        item_last = max(timestamps)
        first = item_first if first is None else min(first, item_first)
        last = item_last if last is None else max(last, item_last)
    return SeriesStats(points=total_points, first=first, last=last)


def combine_series_stats(left: SeriesStats, right: SeriesStats) -> SeriesStats:
    first = right.first if left.first is None else left.first if right.first is None else min(left.first, right.first)
    last = right.last if left.last is None else left.last if right.last is None else max(left.last, right.last)
    return SeriesStats(points=left.points + right.points, first=first, last=last)


def merge_points(
    metric: dict[str, str],
    items: list[dict],
    allow_value_conflicts: bool,
    keep_existing_values_on_conflict: bool,
) -> dict:
    merged_points: dict[int, float] = {}
    for item in items:
        for ts, val in zip(item.get("timestamps", []), item.get("values", [])):
            ts = int(ts)
            val = float(val)
            existing_val = merged_points.get(ts)
            if existing_val is not None and existing_val != val:
                if keep_existing_values_on_conflict:
                    continue
                if not allow_value_conflicts:
                    raise SystemExit(
                        f"Value conflict for {metric} at timestamp {ts}: existing={existing_val} source={val}. "
                        "Use --allow-value-conflicts to prefer source values or "
                        "--keep-target-values-on-conflict to keep target values."
                    )
            merged_points[ts] = val
    timestamps = sorted(merged_points)
    return {
        "metric": metric,
        "timestamps": timestamps,
        "values": [merged_points[ts] for ts in timestamps],
    }


def combine_rewritten_series(items: list[dict], allow_value_conflicts: bool) -> dict:
    if not items:
        raise ValueError("items must not be empty")
    return merge_points(
        items[0]["metric"],
        items,
        allow_value_conflicts=allow_value_conflicts,
        keep_existing_values_on_conflict=False,
    )


def analyze_target_overlap(item: dict, existing: list[dict]) -> tuple[int, int]:
    existing_points: dict[int, float] = {}
    for candidate in existing:
        for ts, val in zip(candidate.get("timestamps", []), candidate.get("values", [])):
            existing_points[int(ts)] = float(val)
    overlaps = 0
    conflicts = 0
    for ts, val in zip(item.get("timestamps", []), item.get("values", [])):
        existing_val = existing_points.get(int(ts))
        if existing_val is None:
            continue
        overlaps += 1
        if existing_val != float(val):
            conflicts += 1
    return overlaps, conflicts


def http_post_form(base_url: str, path: str, form: list[tuple[str, str]]) -> str:
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}{path}",
        data=urllib.parse.urlencode(form).encode("utf-8"),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=300) as response:
        return response.read().decode("utf-8", errors="replace")


def http_post_bytes(base_url: str, path: str, payload: bytes) -> str:
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}{path}",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            return response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} for {path}: {body}") from exc


def serialize_jsonl(items: list[dict]) -> bytes:
    lines = [json.dumps(item, separators=(",", ":"), ensure_ascii=True) for item in items]
    return ("\n".join(lines) + ("\n" if lines else "")).encode("utf-8")


def estimate_series_line_bytes(item: dict) -> int:
    return len(json.dumps(item, separators=(",", ":"), ensure_ascii=True).encode("utf-8")) + 1


def split_series_for_import(item: dict, max_line_bytes: int) -> list[dict]:
    if max_line_bytes <= 0:
        raise ValueError("max_line_bytes must be greater than 0")
    timestamps = [int(ts) for ts in item.get("timestamps", [])]
    values = [float(value) for value in item.get("values", [])]
    if len(timestamps) != len(values):
        raise ValueError("timestamps and values length mismatch")
    if not timestamps:
        return [item]
    chunks: list[dict] = []
    start = 0
    while start < len(timestamps):
        low = start + 1
        high = len(timestamps)
        best_end: int | None = None
        while low <= high:
            mid = (low + high) // 2
            candidate = {
                "metric": item["metric"],
                "timestamps": timestamps[start:mid],
                "values": values[start:mid],
            }
            if estimate_series_line_bytes(candidate) <= max_line_bytes:
                best_end = mid
                low = mid + 1
            else:
                high = mid - 1
        if best_end is None:
            raise SystemExit(f"Single sample for {item['metric']} exceeds --max-import-line-bytes={max_line_bytes}.")
        chunks.append({"metric": item["metric"], "timestamps": timestamps[start:best_end], "values": values[start:best_end]})
        start = best_end
    return chunks


def flush_import_batch(base_url: str, batch: list[dict], imported_batches: int) -> int:
    if not batch:
        return imported_batches
    http_post_bytes(base_url, "/api/v1/import", serialize_jsonl(batch))
    batch.clear()
    return imported_batches + 1


def import_rows(base_url: str, rows: list[dict], batch_size: int, max_line_bytes: int) -> tuple[int, int]:
    batch: list[dict] = []
    imported_batches = 0
    imported_chunks = 0
    for row in rows:
        for chunk in split_series_for_import(row, max_line_bytes):
            batch.append(chunk)
            imported_chunks += 1
            if len(batch) >= batch_size:
                imported_batches = flush_import_batch(base_url, batch, imported_batches)
    imported_batches = flush_import_batch(base_url, batch, imported_batches)
    return imported_batches, imported_chunks


def delete_matcher(base_url: str, matcher: str) -> None:
    http_post_form(base_url, "/api/v1/admin/tsdb/delete_series", [("match[]", matcher)])


def verify_imported_targets(base_url: str, expected: dict[str, SeriesStats], start: str, end: str) -> list[str]:
    last_failures: list[str] = []
    for attempt in range(30):
        failures: list[str] = []
        for matcher, expected_stats in expected.items():
            metric = parse_exact_matcher(matcher)
            actual_stats = series_stats(fetch_exact_series(base_url, metric, start, end))
            if (
                actual_stats.points >= expected_stats.points
                and (expected_stats.first is None or (actual_stats.first is not None and actual_stats.first <= expected_stats.first))
                and (expected_stats.last is None or (actual_stats.last is not None and actual_stats.last >= expected_stats.last))
            ):
                continue

            first_ok = expected_stats.first is None or instant_query_has_metric(base_url, metric, expected_stats.first)
            last_ok = expected_stats.last is None or instant_query_has_metric(base_url, metric, expected_stats.last)
            if first_ok and last_ok:
                continue
            if series_api_has_metric(base_url, metric, start, end):
                continue

            if actual_stats.points < expected_stats.points:
                failures.append(f"{matcher}: expected at least {expected_stats.points} points, got {actual_stats.points}")
            if expected_stats.first is not None and not first_ok:
                failures.append(f"{matcher}: expected first timestamp {expected_stats.first} to be queryable")
            if expected_stats.last is not None and not last_ok:
                failures.append(f"{matcher}: expected last timestamp {expected_stats.last} to be queryable")
        if not failures:
            return []
        last_failures = failures
        if attempt < 29:
            sleep(0.5)
    return last_failures


def parse_exact_matcher(matcher: str) -> dict[str, str]:
    if matcher.endswith("}") and "{" in matcher:
        metric_name, body = matcher.split("{", 1)
        body = body[:-1].strip()
    elif matcher.startswith("{") and matcher.endswith("}"):
        metric_name = ""
        body = matcher[1:-1].strip()
    else:
        raise ValueError(f"Unsupported matcher format: {matcher}")
    metric: dict[str, str] = {}
    if metric_name:
        metric["__name__"] = metric_name
    if not body:
        return metric
    for part in body.split(","):
        key, value = part.split("=", 1)
        metric[key] = value.strip().strip('"')
    return metric


def build_write_flags(flags: list[str]) -> str:
    lines: list[str] = []
    for index, flag in enumerate(flags):
        suffix = " \\" if index < len(flags) - 1 else ""
        lines.append(f"  {flag}{suffix}")
    return "\n".join(lines)


def dry_run_recommendation(exported_series: int, overlaps: int, conflicts: int) -> dict[str, str | None]:
    if exported_series == 0:
        return {"status": "NOTHING TO DO", "message": "No matching source series were found.", "write_flags": None}
    if conflicts:
        return {
            "status": "STOP",
            "message": "Target value conflicts exist. Review the target history before writing.",
            "write_flags": build_write_flags(["--merge-target", "--keep-target-values-on-conflict", "--reset-cache", "--write"]),
        }
    if overlaps:
        return {
            "status": "REVIEW",
            "message": "Target series already contain overlapping timestamps. Use merge mode if this is expected.",
            "write_flags": build_write_flags(["--merge-target", "--reset-cache", "--write"]),
        }
    return {
        "status": "GO FOR IT",
        "message": "Dry-run is clean. Change EVCC live labels first, then run the write step.",
        "write_flags": build_write_flags(["--reset-cache", "--write"]),
    }


def should_delete_target_before_import(
    merge_target: bool,
    target_overlap: int,
    target_conflicts: int,
    existing_stats: SeriesStats,
) -> bool:
    return merge_target and (target_overlap > 0 or target_conflicts > 0) and existing_stats.points > 0


def print_recommendation(recommendation: dict[str, str | None]) -> None:
    print()
    print("Recommendation")
    print("--------------")
    print(f"{recommendation['status']}: {recommendation['message']}")
    if recommendation.get("write_flags"):
        print("Recommended write flags:")
        print(recommendation["write_flags"])


def main() -> int:
    args = parse_args()
    if not args.end:
        args.end = default_end_timestamp()
    args.start = api_time(args.start)
    args.end = api_time(args.end)
    if args.from_value == args.to_value:
        raise SystemExit("--from and --to must differ")
    if args.keep_target_values_on_conflict and args.allow_value_conflicts:
        raise SystemExit("Use either --allow-value-conflicts or --keep-target-values-on-conflict, not both.")
    if args.merge_target and args.import_over_target:
        raise SystemExit("Use either --merge-target or --import-over-target, not both.")

    generated_at = local_timestamp()
    metadata = script_metadata(generated_at)
    rewritten_path = Path(args.rewritten_jsonl or f"{args.backup_jsonl}.rewritten.jsonl")
    backup_path = Path(args.backup_jsonl)
    ensure_parent(backup_path)
    ensure_parent(rewritten_path)

    print(f"{SCRIPT_NAME} v{SCRIPT_VERSION} (last modified {SCRIPT_LAST_MODIFIED}, run {generated_at})")
    progress(
        f"Starting VM label value rewrite in {'write' if args.write else 'dry-run'} mode "
        f"for matcher {args.matcher}: {args.label}={args.from_value!r} -> {args.to_value!r}"
    )

    started_at = perf_counter()
    source_series = 0
    source_points = 0
    target_groups: dict[tuple[tuple[str, str], ...], list[dict]] = {}
    skipped_series = 0

    with backup_path.open("w", encoding="utf-8") as backup_handle:
        for exported in iter_export_lines(args.base_url, args.matcher, args.start, args.end):
            source = normalize_series(exported)
            append_jsonl_line(backup_handle, source)
            if source["metric"].get(args.label) != args.from_value:
                skipped_series += 1
                continue
            rewritten = transform_series(source, args.label, args.from_value, args.to_value)
            target_groups.setdefault(series_key(rewritten), []).append(rewritten)
            source_series += 1
            source_points += len(rewritten["timestamps"])
            if args.progress_every > 0 and source_series % args.progress_every == 0:
                progress(f"Analyze progress: source_series={source_series}, source_points={source_points}")

    if skipped_series:
        raise SystemExit(
            f"Refusing rewrite: {skipped_series} exported source series did not have "
            f"{args.label}={args.from_value!r}. Tighten --matcher before writing."
        )

    import_rows_for_write: list[dict] = []
    expected_targets: dict[str, SeriesStats] = {}
    target_delete_matchers: list[str] = []
    overlaps = 0
    conflicts = 0
    checked_targets = 0
    deleted_targets = 0

    for _, group_items in sorted(target_groups.items()):
        source_target = combine_rewritten_series(group_items, allow_value_conflicts=args.allow_value_conflicts)
        existing = fetch_exact_series(args.base_url, source_target["metric"], args.start, args.end)
        target_overlap, target_conflicts = analyze_target_overlap(source_target, existing)
        overlaps += target_overlap
        conflicts += target_conflicts
        checked_targets += 1

        if args.import_over_target:
            import_item = source_target
            expected_stats = series_stats([source_target])
        elif (target_overlap or target_conflicts) and not args.merge_target:
            import_item = source_target
            expected_stats = combine_series_stats(series_stats(existing), series_stats([source_target]))
        elif args.merge_target and (target_overlap or target_conflicts):
            import_item = merge_points(
                source_target["metric"],
                [*existing, source_target],
                allow_value_conflicts=args.allow_value_conflicts,
                keep_existing_values_on_conflict=args.keep_target_values_on_conflict,
            )
            expected_stats = series_stats([import_item])
        elif args.merge_target:
            import_item = source_target
            expected_stats = combine_series_stats(series_stats(existing), series_stats([source_target]))
        else:
            import_item = source_target
            expected_stats = combine_series_stats(series_stats(existing), series_stats([source_target]))

        import_rows_for_write.append(import_item)
        target_matcher = transformed_matcher(import_item["metric"])
        expected_targets[target_matcher] = expected_stats
        if should_delete_target_before_import(args.merge_target, target_overlap, target_conflicts, series_stats(existing)):
            target_delete_matchers.append(target_matcher)

    with rewritten_path.open("w", encoding="utf-8") as rewritten_handle:
        for row in import_rows_for_write:
            append_jsonl_line(rewritten_handle, row)

    analyze_seconds = elapsed_seconds(started_at, perf_counter())
    summary: dict[str, object] = {
        "script": metadata,
        "mode": "write" if args.write else "dry-run",
        "matcher": args.matcher,
        "start": args.start,
        "end": args.end,
        "label": args.label,
        "from": args.from_value,
        "to": args.to_value,
        "backup_jsonl": str(backup_path),
        "rewritten_jsonl": str(rewritten_path),
        "source_series": source_series,
        "source_points": source_points,
        "target_series": len(import_rows_for_write),
        "checked_target_series": checked_targets,
        "overlap_timestamps": overlaps,
        "value_conflicts": conflicts,
        "performance": {
            "analyze_seconds": analyze_seconds,
            "analyze_series_per_second": rate_per_second(source_series, analyze_seconds),
            "analyze_points_per_second": rate_per_second(source_points, analyze_seconds),
        },
    }

    if not args.write:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        print_recommendation(dry_run_recommendation(source_series, overlaps, conflicts))
        return 0

    if source_series == 0:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return 0
    if overlaps and not (args.merge_target or args.import_over_target):
        raise SystemExit("Refusing write: target timestamps overlap. Rerun with --merge-target or --import-over-target after reviewing the dry-run.")
    if args.import_over_target and conflicts:
        raise SystemExit("Refusing --import-over-target: target value conflicts exist and cannot be resolved without deleting or merging targets.")
    if conflicts and not (args.allow_value_conflicts or args.keep_target_values_on_conflict):
        raise SystemExit(
            "Refusing write: target value conflicts exist. Rerun with --merge-target and a conflict policy after reviewing the dry-run."
        )

    import_started_at = perf_counter()
    if args.merge_target:
        for matcher in target_delete_matchers:
            delete_matcher(args.base_url, matcher)
            deleted_targets += 1
    imported_batches, imported_chunks = import_rows(
        args.base_url,
        import_rows_for_write,
        args.import_batch_size,
        args.max_import_line_bytes,
    )
    import_seconds = elapsed_seconds(import_started_at, perf_counter())

    verification_failures: list[str] = []
    if not args.skip_import_verification:
        verification_failures = verify_imported_targets(args.base_url, expected_targets, args.start, args.end)
        if verification_failures:
            summary["import_verification"] = {"ok": False, "failures": verification_failures}
            print(json.dumps(summary, indent=2, ensure_ascii=False))
            raise SystemExit("Refusing to delete source series because target verification failed.")

    delete_started_at = perf_counter()
    delete_matcher(args.base_url, args.matcher)
    delete_seconds = elapsed_seconds(delete_started_at, perf_counter())

    reset_cache_seconds = 0.0
    if args.reset_cache:
        cache_started_at = perf_counter()
        http_post_form(args.base_url, "/internal/resetRollupResultCache", [])
        reset_cache_seconds = elapsed_seconds(cache_started_at, perf_counter())

    summary.update(
        {
            "deleted_target_series_before_import": deleted_targets,
            "import_batches": imported_batches,
            "imported_chunk_series": imported_chunks,
            "import_seconds": import_seconds,
            "source_delete_seconds": delete_seconds,
            "reset_cache_seconds": reset_cache_seconds,
            "import_verification": {
                "ok": not verification_failures,
                "skipped": args.skip_import_verification,
                "checked_targets": len(expected_targets) if not args.skip_import_verification else 0,
                "failures": verification_failures,
            },
        }
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
