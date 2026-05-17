#!/usr/bin/env python3
"""Safely deduplicate identical VictoriaMetrics timestamps inside exact series."""

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


SCRIPT_NAME = "vm-dedup-series.py"
SCRIPT_VERSION = "2026.05.16.1"
SCRIPT_LAST_MODIFIED = "2026-05-16"
DEFAULT_START = "1"


@dataclass(frozen=True)
class DedupStats:
    input_points: int
    output_points: int
    duplicate_extra_samples: int
    identical_duplicate_samples: int
    conflict_samples: int
    first: int | None
    last: int | None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Export VM series, collapse duplicate timestamps per exact series, and optionally replace the "
            "source series with deduplicated data."
        )
    )
    parser.add_argument("--base-url", required=True, help="VictoriaMetrics base URL, e.g. http://localhost:8428")
    parser.add_argument("--matcher", required=True, help='VM series matcher, e.g. pvPower_value{title="Balkon Sued"}')
    parser.add_argument("--backup-jsonl", required=True, help="Path for the raw exported JSONL backup.")
    parser.add_argument("--deduped-jsonl", help="Path for the deduplicated JSONL that will be imported.")
    parser.add_argument(
        "--start",
        default=DEFAULT_START,
        help="Export/search start time as Unix seconds or RFC3339. Defaults to 1.",
    )
    parser.add_argument(
        "--end",
        default="",
        help="Export/search end time as Unix seconds or RFC3339. Defaults to tomorrow UTC as Unix seconds.",
    )
    parser.add_argument(
        "--conflict-policy",
        choices=("reject", "keep-first", "keep-last"),
        default="reject",
        help="How to handle duplicate timestamps with different values. Default rejects the write.",
    )
    parser.add_argument("--write", action="store_true", help="Delete exact source series and import the deduplicated data.")
    parser.add_argument("--reset-cache", action="store_true", help="Reset VM rollup cache after successful write.")
    parser.add_argument("--import-batch-size", type=int, default=1, help="Number of series chunks per import batch.")
    parser.add_argument(
        "--max-import-line-bytes",
        type=int,
        default=8_000_000,
        help="Maximum size per JSONL import line before splitting a series.",
    )
    parser.add_argument("--progress-every", type=int, default=10, help="Emit progress after this many series.")
    parser.add_argument("--verify-retries", type=int, default=30, help="Import verification retry count.")
    parser.add_argument("--verify-retry-delay", type=float, default=0.5, help="Seconds between verification retries.")
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


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


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


def http_get_json(base_url: str, path: str, params: list[tuple[str, str]]) -> dict:
    url = f"{base_url.rstrip('/')}{path}?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=120) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} for {path}: {body}") from exc


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


def append_jsonl_line(handle, item: dict) -> None:
    handle.write(json.dumps(item, separators=(",", ":"), ensure_ascii=True))
    handle.write("\n")


def normalize_series(item: dict) -> dict:
    return {
        "metric": {str(key): str(value) for key, value in item.get("metric", {}).items()},
        "timestamps": [int(ts) for ts in item.get("timestamps", [])],
        "values": [float(value) for value in item.get("values", [])],
    }


def series_key(metric: dict[str, str]) -> tuple[tuple[str, str], ...]:
    return tuple(sorted((str(key), str(value)) for key, value in metric.items()))


def transformed_matcher(metric: dict[str, str]) -> str:
    metric_name = metric.get("__name__", "")
    parts = [f'{key}="{value}"' for key, value in sorted(metric.items()) if key != "__name__"]
    labels = "{" + ",".join(parts) + "}"
    return f"{metric_name}{labels}" if metric_name else labels


def metric_matches_exact(actual: dict[str, str], expected: dict[str, str]) -> bool:
    return {str(key): str(value) for key, value in actual.items()} == {
        str(key): str(value) for key, value in expected.items()
    }


def dedup_series_items(items: list[dict], conflict_policy: str) -> tuple[dict, DedupStats]:
    if not items:
        raise ValueError("items must not be empty")
    metric = dict(items[0]["metric"])
    point_values: dict[int, float] = {}
    input_points = 0
    duplicate_extra_samples = 0
    identical_duplicate_samples = 0
    conflict_samples = 0

    for item in items:
        if item["metric"] != metric:
            raise ValueError("all grouped items must have the same metric")
        for ts_raw, value_raw in zip(item.get("timestamps", []), item.get("values", []), strict=False):
            input_points += 1
            ts = int(ts_raw)
            value = float(value_raw)
            if ts not in point_values:
                point_values[ts] = value
                continue
            duplicate_extra_samples += 1
            if point_values[ts] == value:
                identical_duplicate_samples += 1
                continue
            conflict_samples += 1
            if conflict_policy == "keep-last":
                point_values[ts] = value
            elif conflict_policy == "reject":
                continue
            elif conflict_policy == "keep-first":
                continue
            else:
                raise ValueError(f"Unsupported conflict policy: {conflict_policy}")

    timestamps = sorted(point_values)
    deduped = {"metric": metric, "timestamps": timestamps, "values": [point_values[ts] for ts in timestamps]}
    stats = DedupStats(
        input_points=input_points,
        output_points=len(timestamps),
        duplicate_extra_samples=duplicate_extra_samples,
        identical_duplicate_samples=identical_duplicate_samples,
        conflict_samples=conflict_samples,
        first=timestamps[0] if timestamps else None,
        last=timestamps[-1] if timestamps else None,
    )
    return deduped, stats


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
            candidate = {"metric": item["metric"], "timestamps": timestamps[start:mid], "values": values[start:mid]}
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


def import_rows(base_url: str, rows: list[dict], batch_size: int, max_line_bytes: int) -> tuple[int, int]:
    batch: list[dict] = []
    imported_batches = 0
    imported_chunks = 0
    for row in rows:
        for chunk in split_series_for_import(row, max_line_bytes):
            batch.append(chunk)
            imported_chunks += 1
            if len(batch) >= batch_size:
                http_post_bytes(base_url, "/api/v1/import", serialize_jsonl(batch))
                imported_batches += 1
                batch.clear()
    if batch:
        http_post_bytes(base_url, "/api/v1/import", serialize_jsonl(batch))
        imported_batches += 1
    return imported_batches, imported_chunks


def delete_matcher(base_url: str, matcher: str) -> None:
    http_post_form(base_url, "/api/v1/admin/tsdb/delete_series", [("match[]", matcher)])


def series_api_metrics(base_url: str, matcher: str, start: str, end: str) -> list[dict[str, str]]:
    payload = http_get_json(base_url, "/api/v1/series", [("match[]", matcher), ("start", start), ("end", end)])
    return payload.get("data", [])


def validate_no_superset_delete(base_url: str, rows: list[dict], start: str, end: str) -> list[str]:
    failures: list[str] = []
    for row in rows:
        metric = row["metric"]
        matcher = transformed_matcher(metric)
        candidates = series_api_metrics(base_url, matcher, start, end)
        unexpected = [candidate for candidate in candidates if not metric_matches_exact(candidate, metric)]
        if unexpected:
            failures.append(f"{matcher}: delete matcher would also match non-exact series: {unexpected[:3]}")
    return failures


def export_exact_rows(base_url: str, metric: dict[str, str], start: str, end: str) -> list[dict]:
    matcher = transformed_matcher(metric)
    return [
        item
        for item in iter_export_lines(base_url, matcher, start, end)
        if metric_matches_exact(item.get("metric", {}), metric)
    ]


def verify_rows(base_url: str, expected_rows: list[dict], start: str, end: str) -> list[str]:
    failures: list[str] = []
    for expected in expected_rows:
        actual_rows = export_exact_rows(base_url, expected["metric"], start, end)
        actual_points: dict[int, float] = {}
        duplicate_timestamps = 0
        conflicts = 0
        for row in actual_rows:
            for ts_raw, value_raw in zip(row.get("timestamps", []), row.get("values", []), strict=False):
                ts = int(ts_raw)
                value = float(value_raw)
                if ts in actual_points:
                    duplicate_timestamps += 1
                    if actual_points[ts] != value:
                        conflicts += 1
                else:
                    actual_points[ts] = value
        expected_points = {int(ts): float(value) for ts, value in zip(expected["timestamps"], expected["values"], strict=False)}
        if actual_points != expected_points:
            failures.append(
                f"{transformed_matcher(expected['metric'])}: expected {len(expected_points)} points, got {len(actual_points)}"
            )
        if duplicate_timestamps:
            failures.append(
                f"{transformed_matcher(expected['metric'])}: still has duplicate timestamps={duplicate_timestamps}, conflicts={conflicts}"
            )
    return failures


def verify_imported_rows(
    base_url: str,
    expected_rows: list[dict],
    start: str,
    end: str,
    retries: int,
    delay: float,
) -> list[str]:
    last_failures: list[str] = []
    for attempt in range(max(retries, 1)):
        failures = verify_rows(base_url, expected_rows, start, end)
        if not failures:
            return []
        last_failures = failures
        if attempt < max(retries, 1) - 1:
            sleep(max(delay, 0.0))
    return last_failures


def build_write_flags() -> str:
    return "  --reset-cache \\\n  --write"


def dry_run_recommendation(exported_series: int, duplicate_extra_samples: int, conflict_samples: int) -> dict[str, str | None]:
    if exported_series == 0:
        return {"status": "NOTHING TO DO", "message": "No matching source series were found.", "write_flags": None}
    if conflict_samples:
        return {
            "status": "STOP",
            "message": "Duplicate timestamps with different values exist. Review them or choose an explicit conflict policy.",
            "write_flags": None,
        }
    if duplicate_extra_samples == 0:
        return {"status": "NOTHING TO DO", "message": "No duplicate timestamps were found.", "write_flags": None}
    return {
        "status": "GO FOR IT",
        "message": "Dry-run found only identical duplicate timestamp samples. The series can be replaced with deduplicated data.",
        "write_flags": build_write_flags(),
    }


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

    generated_at = local_timestamp()
    metadata = script_metadata(generated_at)
    backup_path = Path(args.backup_jsonl)
    deduped_path = Path(args.deduped_jsonl or f"{args.backup_jsonl}.deduped.jsonl")
    ensure_parent(backup_path)
    ensure_parent(deduped_path)

    print(f"{SCRIPT_NAME} v{SCRIPT_VERSION} (last modified {SCRIPT_LAST_MODIFIED}, run {generated_at})")
    progress(f"Starting VM dedup in {'write' if args.write else 'dry-run'} mode for matcher {args.matcher}")

    started_at = perf_counter()
    grouped: dict[tuple[tuple[str, str], ...], list[dict]] = {}
    exported_series = 0
    exported_points = 0

    with backup_path.open("w", encoding="utf-8") as backup_handle:
        for exported in iter_export_lines(args.base_url, args.matcher, args.start, args.end):
            series = normalize_series(exported)
            append_jsonl_line(backup_handle, series)
            grouped.setdefault(series_key(series["metric"]), []).append(series)
            exported_series += 1
            exported_points += len(series["timestamps"])
            if args.progress_every > 0 and exported_series % args.progress_every == 0:
                progress(f"Analyze progress: exported_series={exported_series}, exported_points={exported_points}")

    deduped_rows: list[dict] = []
    per_series: list[dict[str, object]] = []
    duplicate_extra_samples = 0
    identical_duplicate_samples = 0
    conflict_samples = 0
    output_points = 0

    with deduped_path.open("w", encoding="utf-8") as deduped_handle:
        for _key, items in sorted(grouped.items()):
            deduped, stats = dedup_series_items(items, args.conflict_policy)
            deduped_rows.append(deduped)
            append_jsonl_line(deduped_handle, deduped)
            duplicate_extra_samples += stats.duplicate_extra_samples
            identical_duplicate_samples += stats.identical_duplicate_samples
            conflict_samples += stats.conflict_samples
            output_points += stats.output_points
            per_series.append(
                {
                    "metric": deduped["metric"],
                    "input_points": stats.input_points,
                    "output_points": stats.output_points,
                    "duplicate_extra_samples": stats.duplicate_extra_samples,
                    "identical_duplicate_samples": stats.identical_duplicate_samples,
                    "conflict_samples": stats.conflict_samples,
                    "first": stats.first,
                    "last": stats.last,
                }
            )

    analyze_seconds = elapsed_seconds(started_at, perf_counter())
    summary: dict[str, object] = {
        "script": metadata,
        "mode": "write" if args.write else "dry-run",
        "matcher": args.matcher,
        "start": args.start,
        "end": args.end,
        "backup_jsonl": str(backup_path),
        "deduped_jsonl": str(deduped_path),
        "exported_series": exported_series,
        "exported_points": exported_points,
        "deduped_series": len(deduped_rows),
        "output_points": output_points,
        "duplicate_extra_samples": duplicate_extra_samples,
        "identical_duplicate_samples": identical_duplicate_samples,
        "conflict_samples": conflict_samples,
        "per_series": per_series,
        "performance": {
            "analyze_seconds": analyze_seconds,
            "analyze_series_per_second": rate_per_second(exported_series, analyze_seconds),
            "analyze_points_per_second": rate_per_second(exported_points, analyze_seconds),
        },
    }

    recommendation = dry_run_recommendation(exported_series, duplicate_extra_samples, conflict_samples)
    if not args.write:
        summary["recommendation"] = recommendation
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        print_recommendation(recommendation)
        return 0

    if exported_series == 0 or duplicate_extra_samples == 0:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return 0
    if conflict_samples and args.conflict_policy == "reject":
        summary["recommendation"] = recommendation
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        print_recommendation(recommendation)
        raise SystemExit("Refusing write: duplicate timestamp value conflicts exist.")

    superset_failures = validate_no_superset_delete(args.base_url, deduped_rows, args.start, args.end)
    if superset_failures:
        summary["superset_delete_check"] = {"ok": False, "failures": superset_failures}
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        raise SystemExit("Refusing write: exact delete matchers would also match non-exact series.")

    write_started_at = perf_counter()
    for row in deduped_rows:
        delete_matcher(args.base_url, transformed_matcher(row["metric"]))
    deleted_series = len(deduped_rows)
    imported_batches, imported_chunks = import_rows(
        args.base_url,
        deduped_rows,
        args.import_batch_size,
        args.max_import_line_bytes,
    )
    verification_failures = verify_imported_rows(
        args.base_url,
        deduped_rows,
        args.start,
        args.end,
        args.verify_retries,
        args.verify_retry_delay,
    )
    if verification_failures:
        summary["import_verification"] = {"ok": False, "failures": verification_failures}
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        raise SystemExit("Dedup import verification failed.")
    reset_cache_seconds = 0.0
    if args.reset_cache:
        cache_started_at = perf_counter()
        http_post_form(args.base_url, "/internal/resetRollupResultCache", [])
        reset_cache_seconds = elapsed_seconds(cache_started_at, perf_counter())
    write_seconds = elapsed_seconds(write_started_at, perf_counter())

    summary.update(
        {
            "deleted_series": deleted_series,
            "import_batches": imported_batches,
            "imported_chunk_series": imported_chunks,
            "import_verification": {"ok": True, "failures": []},
        }
    )
    summary["performance"].update({"write_seconds": write_seconds, "reset_cache_seconds": reset_cache_seconds})
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
