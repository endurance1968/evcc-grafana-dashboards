#!/usr/bin/env python3
"""Export VM series, drop a label, and optionally rewrite them back safely."""

from __future__ import annotations

import argparse
import json
import socket
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from time import perf_counter, sleep
from pathlib import Path
from dataclasses import dataclass
from typing import Callable, Iterator


SCRIPT_NAME = "vm-rewrite-drop-label.py"
SCRIPT_VERSION = "2026.04.05.4"
SCRIPT_CREATED = "2026-03-29"


@dataclass(frozen=True)
class SeriesStats:
    points: int
    first: int | None
    last: int | None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rewrite VictoriaMetrics series by dropping one label from exported series."
    )
    parser.add_argument("--base-url", required=True, help="VictoriaMetrics base URL, e.g. http://192.168.1.160:8428")
    parser.add_argument(
        "--matcher",
        default='{db="evcc",host!=""}',
        help='VM series matcher for the source series, e.g. {db="evcc",host!=""}',
    )
    parser.add_argument(
        "--drop-label",
        default="host",
        help="Label key to remove from the exported series before reimport.",
    )
    parser.add_argument(
        "--backup-jsonl",
        required=True,
        help="Path for the raw exported JSONL backup.",
    )
    parser.add_argument(
        "--rewritten-jsonl",
        help="Optional path for the transformed JSONL that will be reimported.",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Actually delete the source matcher series and import the rewritten data.",
    )
    parser.add_argument(
        "--allow-overlap",
        action="store_true",
        help="Allow rewrite even if transformed target series overlap existing timestamps.",
    )
    parser.add_argument(
        "--merge-target",
        action="store_true",
        help="Advanced: merge with the full existing hostless target series before import.",
    )
    parser.add_argument(
        "--allow-value-conflicts",
        action="store_true",
        help="Allow merge when identical timestamps have different values; source values win.",
    )
    parser.add_argument(
        "--reset-cache",
        action="store_true",
        help="Reset VM rollup cache after a write.",
    )
    parser.add_argument(
        "--import-batch-size",
        type=int,
        default=1,
        help="Number of series chunks per VM import batch during write mode.",
    )
    parser.add_argument(
        "--max-import-line-bytes",
        type=int,
        default=8_000_000,
        help="Maximum size per vmimport JSONL line before a series is split into multiple chunks (default: 8000000).",
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=10,
        help="Emit progress after this many processed source series (default: 10).",
    )
    parser.add_argument(
        "--verify-retries",
        type=int,
        default=3,
        help="Number of verification attempts after import before refusing source deletion (default: 3).",
    )
    parser.add_argument(
        "--verify-retry-delay",
        type=float,
        default=2.0,
        help="Seconds to wait between failed verification attempts (default: 2.0).",
    )
    return parser.parse_args()


def progress(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def local_timestamp() -> str:
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


def script_metadata(generated_at: str | None = None) -> dict[str, str]:
    return {
        "name": SCRIPT_NAME,
        "version": SCRIPT_VERSION,
        "created": SCRIPT_CREATED,
        "generated_at": generated_at or local_timestamp(),
    }


def elapsed_seconds(start: float, end: float) -> float:
    return round(end - start, 3)


def rate_per_second(count: int, seconds: float) -> float | None:
    if seconds <= 0:
        return None
    return round(count / seconds, 2)


def export_url(base_url: str, matcher: str, start_ms: int | None = None, end_ms: int | None = None) -> str:
    params: list[tuple[str, str]] = [("match[]", matcher)]
    if start_ms is not None:
        params.append(("start", str(start_ms)))
    if end_ms is not None:
        params.append(("end", str(end_ms)))
    return f"{base_url.rstrip('/')}/api/v1/export?" + urllib.parse.urlencode(params)


def iter_export_lines(base_url: str, matcher: str, start_ms: int | None = None, end_ms: int | None = None) -> Iterator[dict]:
    url = export_url(base_url, matcher, start_ms, end_ms)
    try:
        with urllib.request.urlopen(url, timeout=300) as response:
            for raw in response:
                if not raw.strip():
                    continue
                yield json.loads(raw)
    except urllib.error.HTTPError as exc:
        if exc.code != 422:
            raise
        return


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def append_jsonl_line(handle, item: dict) -> None:
    handle.write(json.dumps(item, separators=(",", ":"), ensure_ascii=True))
    handle.write("\n")


def transform_series(item: dict, drop_label: str) -> dict:
    metric = {k: v for k, v in item["metric"].items() if k != drop_label}
    return {
        "metric": metric,
        "timestamps": [int(ts) for ts in item["timestamps"]],
        "values": [float(value) for value in item["values"]],
    }


def transformed_matcher(metric: dict[str, str]) -> str:
    parts = [f'{key}="{value}"' for key, value in sorted(metric.items())]
    return "{" + ",".join(parts) + "}"


def target_matcher(metric: dict[str, str], dropped_label: str) -> str:
    target_metric = dict(metric)
    target_metric.setdefault(dropped_label, "")
    return transformed_matcher(target_metric)


def fetch_target_series(base_url: str, metric: dict[str, str], dropped_label: str) -> list[dict]:
    return list(iter_export_lines(base_url, target_matcher(metric, dropped_label)))


def series_stats(items: list[dict]) -> SeriesStats:
    total_points = 0
    first: int | None = None
    last: int | None = None
    for item in items:
        timestamps = [int(ts) for ts in item.get("timestamps", [])]
        if not timestamps:
            continue
        total_points += len(timestamps)
        item_first = timestamps[0]
        item_last = timestamps[-1]
        first = item_first if first is None else min(first, item_first)
        last = item_last if last is None else max(last, item_last)
    return SeriesStats(points=total_points, first=first, last=last)


def analyze_target_overlap(item: dict, existing: list[dict]) -> tuple[int, int]:
    existing_points: dict[int, float] = {}
    for candidate in existing:
        existing_points.update({int(ts): float(val) for ts, val in zip(candidate.get("timestamps", []), candidate.get("values", []))})

    current_overlap = 0
    current_conflicts = 0
    for ts, val in zip(item["timestamps"], item["values"]):
        existing_val = existing_points.get(int(ts))
        if existing_val is None:
            continue
        current_overlap += 1
        if float(existing_val) != float(val):
            current_conflicts += 1
    return current_overlap, current_conflicts


def merge_with_targets(item: dict, existing: list[dict], allow_value_conflicts: bool) -> dict:
    merged_points: dict[int, float] = {}
    for candidate in existing:
        merged_points.update({int(ts): float(val) for ts, val in zip(candidate.get("timestamps", []), candidate.get("values", []))})
    for ts, val in zip(item["timestamps"], item["values"]):
        ts = int(ts)
        val = float(val)
        if ts in merged_points and merged_points[ts] != val and not allow_value_conflicts:
            raise SystemExit(
                f"Value conflict for {item['metric']} at timestamp {ts}: existing={merged_points[ts]} source={val}. "
                "Use --allow-value-conflicts to prefer source values."
            )
        merged_points[ts] = val
    merged_ts = sorted(merged_points)
    return {
        "metric": item["metric"],
        "timestamps": merged_ts,
        "values": [merged_points[ts] for ts in merged_ts],
    }


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
        headers={"Content-Type": "application/stream+json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            return response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} for {path}: {body}") from exc


def serialize_jsonl(items: list[dict]) -> bytes:
    chunks = [json.dumps(item, separators=(",", ":"), ensure_ascii=True) for item in items]
    return ("\n".join(chunks) + "\n").encode("utf-8")


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

    metric = item["metric"]
    chunks: list[dict] = []
    start = 0
    total = len(timestamps)

    while start < total:
        low = start + 1
        high = total
        best_end: int | None = None
        while low <= high:
            mid = (low + high) // 2
            candidate = {
                "metric": metric,
                "timestamps": timestamps[start:mid],
                "values": values[start:mid],
            }
            size = estimate_series_line_bytes(candidate)
            if size <= max_line_bytes:
                best_end = mid
                low = mid + 1
            else:
                high = mid - 1

        if best_end is None:
            raise SystemExit(
                f"Single sample for metric {metric} exceeds --max-import-line-bytes={max_line_bytes}. "
                "Increase the limit and retry."
            )

        chunks.append(
            {
                "metric": metric,
                "timestamps": timestamps[start:best_end],
                "values": values[start:best_end],
            }
        )
        start = best_end

    return chunks


def verify_matcher_count(base_url: str, matcher: str) -> int:
    url = f"{base_url.rstrip('/')}/prometheus/api/v1/series?" + urllib.parse.urlencode([("match[]", matcher)])
    with urllib.request.urlopen(url, timeout=120) as response:
        payload = json.load(response)
    return len(payload.get("data", []))


def delete_target_matcher(base_url: str, matcher: str) -> None:
    http_post_form(base_url, "/api/v1/admin/tsdb/delete_series", [("match[]", matcher)])


def iter_jsonl(path: Path) -> Iterator[dict]:
    with path.open("r", encoding="utf-8") as handle:
        for raw in handle:
            if not raw.strip():
                continue
            yield json.loads(raw)


def flush_import_batch(base_url: str, batch: list[dict], imported_batches: int) -> int:
    if not batch:
        return imported_batches
    http_post_bytes(base_url, "/api/v1/import", serialize_jsonl(batch))
    imported_batches += 1
    batch.clear()
    return imported_batches


def import_rewritten_file(
    base_url: str,
    rewritten_path: Path,
    dropped_label: str,
    batch_size: int,
    max_line_bytes: int,
    delete_targets_first: bool,
    progress_every: int,
    progress_cb: Callable[[str], None] | None = None,
) -> tuple[int, int, int, int, dict[str, SeriesStats]]:
    deleted_targets = 0
    imported_batches = 0
    imported_source_series = 0
    imported_chunk_series = 0
    batch: list[dict] = []
    deleted_matchers: set[str] = set()
    expected_targets: dict[str, SeriesStats] = {}

    for item in iter_jsonl(rewritten_path):
        imported_source_series += 1
        matcher = target_matcher(item["metric"], dropped_label)
        expected_targets[matcher] = series_stats([item])
        if delete_targets_first and matcher not in deleted_matchers:
            delete_target_matcher(base_url, matcher)
            deleted_matchers.add(matcher)
            deleted_targets += 1

        chunks = split_series_for_import(item, max_line_bytes)
        for chunk in chunks:
            batch.append(chunk)
            imported_chunk_series += 1
            if len(batch) >= max(batch_size, 1):
                imported_batches = flush_import_batch(base_url, batch, imported_batches)

        if progress_cb is not None and len(chunks) > 1:
            progress_cb(
                f"Chunked metric {transformed_matcher(item['metric'])} into {len(chunks)} import lines "
                f"(source_series={imported_source_series}, chunk_series={imported_chunk_series})"
            )

        if progress_cb is not None and progress_every > 0 and imported_source_series % progress_every == 0:
            progress_cb(
                "Import progress: "
                f"source_series={imported_source_series}, chunk_series={imported_chunk_series}, batches={imported_batches}"
            )

    imported_batches = flush_import_batch(base_url, batch, imported_batches)
    if progress_cb is not None:
        progress_cb(
            "Import phase complete: "
            f"source_series={imported_source_series}, chunk_series={imported_chunk_series}, batches={imported_batches}"
        )
    return deleted_targets, imported_batches, imported_source_series, imported_chunk_series, expected_targets


def verify_imported_targets(
    base_url: str,
    dropped_label: str,
    expected_targets: dict[str, SeriesStats],
) -> list[str]:
    failures: list[str] = []
    for matcher in sorted(expected_targets):
        expected = expected_targets[matcher]
        if expected.points <= 0 or expected.first is None or expected.last is None:
            continue
        actual_items = list(iter_export_lines(base_url, matcher, expected.first, expected.last))
        actual = series_stats(actual_items)
        if actual.points < expected.points or actual.first != expected.first or actual.last != expected.last:
            failures.append(
                f"{matcher}: expected points>={expected.points}, first={expected.first}, last={expected.last}; "
                f"got points={actual.points}, first={actual.first}, last={actual.last}"
            )
            if len(failures) >= 10:
                break
    return failures


def describe_url_error(base_url: str, exc: urllib.error.URLError) -> str:
    reason = exc.reason
    if isinstance(reason, socket.gaierror):
        return (
            f"Could not resolve the VictoriaMetrics host in --base-url {base_url!r}. "
            "Check the hostname spelling and port, for example http://localhost:8428."
        )
    if isinstance(reason, ConnectionRefusedError):
        return (
            f"VictoriaMetrics is not reachable at {base_url!r}. "
            "Check the port and whether the service is running."
        )
    if isinstance(reason, ConnectionResetError):
        return (
            f"VictoriaMetrics reset the connection at {base_url!r}. "
            "Check service logs; oversized vmimport lines are a common cause during writes."
        )
    return (
        f"Could not reach VictoriaMetrics at {base_url!r}: {reason}. "
        "Check the URL, port, and service health."
    )


def default_rewritten_path(backup_path: Path) -> Path:
    return backup_path.with_name(backup_path.stem + ".rewritten.jsonl")


def main() -> int:
    args = parse_args()
    backup_path = Path(args.backup_jsonl)
    ensure_parent(backup_path)

    rewritten_path = Path(args.rewritten_jsonl) if args.rewritten_jsonl else None
    temp_rewritten = False
    if args.write and rewritten_path is None:
        rewritten_path = default_rewritten_path(backup_path)
        temp_rewritten = True
    if rewritten_path is not None:
        ensure_parent(rewritten_path)

    try:
        metadata = script_metadata()
        total_started_at = perf_counter()
        progress(
            f"{metadata['name']} v{metadata['version']} (created {metadata['created']}, run {metadata['generated_at']})"
        )
        progress(
            f"Starting vm label rewrite in {'write' if args.write else 'dry-run'} mode for matcher {args.matcher} at {args.base_url}"
        )
        exported_series = 0
        exported_points = 0
        checked_series = 0
        overlap_timestamps = 0
        value_conflicts = 0
        overlap_examples: list[dict] = []
        output_points = 0

        analyze_started_at = perf_counter()
        with backup_path.open("w", encoding="utf-8", newline="\n") as backup_handle:
            rewritten_handle = None
            try:
                if rewritten_path is not None:
                    rewritten_handle = rewritten_path.open("w", encoding="utf-8", newline="\n")

                for exported in iter_export_lines(args.base_url, args.matcher):
                    exported_series += 1
                    exported_points += len(exported.get("timestamps", []))
                    append_jsonl_line(backup_handle, exported)

                    rewritten = transform_series(exported, args.drop_label)
                    existing = fetch_target_series(args.base_url, rewritten["metric"], args.drop_label)
                    checked_series += 1
                    current_overlap, current_conflicts = analyze_target_overlap(rewritten, existing)
                    overlap_timestamps += current_overlap
                    value_conflicts += current_conflicts
                    if (current_overlap or current_conflicts) and len(overlap_examples) < 10:
                        overlap_examples.append(
                            {
                                "metric": rewritten["metric"],
                                "overlap_timestamps": current_overlap,
                                "value_conflicts": current_conflicts,
                                "host_points": len(rewritten["timestamps"]),
                            }
                        )

                    final_item = rewritten
                    if args.merge_target:
                        final_item = merge_with_targets(rewritten, existing, args.allow_value_conflicts)

                    output_points += len(final_item.get("timestamps", []))
                    if rewritten_handle is not None:
                        append_jsonl_line(rewritten_handle, final_item)

                    if args.progress_every > 0 and exported_series % args.progress_every == 0:
                        progress(
                            "Analyze progress: "
                            f"series={exported_series}, source_points={exported_points}, overlaps={overlap_timestamps}, conflicts={value_conflicts}"
                        )
            finally:
                if rewritten_handle is not None:
                    rewritten_handle.close()

        analyze_finished_at = perf_counter()
        analyze_seconds = elapsed_seconds(analyze_started_at, analyze_finished_at)
        progress(
            "Analyze phase complete: "
            f"series={exported_series}, source_points={exported_points}, overlaps={overlap_timestamps}, conflicts={value_conflicts}, seconds={analyze_seconds}"
        )

        summary = {
            "script": metadata,
            "mode": "write" if args.write else "dry-run",
            "matcher": args.matcher,
            "drop_label": args.drop_label,
            "merge_target": args.merge_target,
            "backup_jsonl": str(backup_path),
            "rewritten_jsonl": str(rewritten_path) if rewritten_path else None,
            "exported_series": exported_series,
            "exported_points": exported_points,
            "checked_target_series": checked_series,
            "overlap_timestamps": overlap_timestamps,
            "value_conflicts": value_conflicts,
            "overlap_examples": overlap_examples,
            "output_points": output_points,
            "streaming": True,
            "max_import_line_bytes": args.max_import_line_bytes,
            "performance": {
                "analyze_seconds": analyze_seconds,
                "analyze_series_per_second": rate_per_second(exported_series, analyze_seconds),
                "analyze_points_per_second": rate_per_second(exported_points, analyze_seconds),
                "target_fetch_requests": checked_series,
            },
        }

        if overlap_timestamps and not (args.allow_overlap or args.merge_target):
            print(json.dumps(summary, indent=2))
            print(
                "Refusing to rewrite because transformed timestamps overlap existing target series. Use --merge-target or --allow-overlap to override.",
                file=sys.stderr,
            )
            return 2

        if value_conflicts and not args.allow_value_conflicts:
            print(json.dumps(summary, indent=2))
            print(
                "Refusing to rewrite because transformed timestamps conflict with existing target values. Use --allow-value-conflicts to prefer source values.",
                file=sys.stderr,
            )
            return 3

        if not args.write:
            total_finished_at = perf_counter()
            summary["performance"]["total_seconds"] = elapsed_seconds(total_started_at, total_finished_at)
            print(json.dumps(summary, indent=2))
            return 0

        if rewritten_path is None:
            raise RuntimeError("Internal error: no rewritten JSONL path available for write mode")

        progress(
            f"Starting import phase from {rewritten_path} with batch_size={args.import_batch_size} and max_line_bytes={args.max_import_line_bytes}"
        )
        import_started_at = perf_counter()
        deleted_targets, imported_batches, imported_source_series, imported_chunk_series, expected_targets = import_rewritten_file(
            args.base_url,
            rewritten_path,
            args.drop_label,
            args.import_batch_size,
            args.max_import_line_bytes,
            delete_targets_first=args.merge_target,
            progress_every=args.progress_every,
            progress_cb=progress,
        )
        import_finished_at = perf_counter()
        import_seconds = elapsed_seconds(import_started_at, import_finished_at)
        progress(
            "Import stats: "
            f"source_series={imported_source_series}, chunk_series={imported_chunk_series}, batches={imported_batches}, seconds={import_seconds}"
        )
        verify_started_at = perf_counter()
        verification_failures: list[str] = []
        verification_attempts = max(args.verify_retries, 1)
        verification_attempt = 0
        for verification_attempt in range(1, verification_attempts + 1):
            verification_failures = verify_imported_targets(args.base_url, args.drop_label, expected_targets)
            if not verification_failures:
                break
            if verification_attempt < verification_attempts:
                progress(
                    "Verification retry scheduled: "
                    f"attempt={verification_attempt}/{verification_attempts}, failures={len(verification_failures)}, delay={args.verify_retry_delay}s"
                )
                sleep(max(args.verify_retry_delay, 0.0))
        verify_finished_at = perf_counter()
        verify_seconds = elapsed_seconds(verify_started_at, verify_finished_at)
        progress(
            "Verification stats: "
            f"targets={len(expected_targets)}, attempts={verification_attempt}, seconds={verify_seconds}"
        )
        summary["performance"].update({
            "import_seconds": import_seconds,
            "import_source_series_per_second": rate_per_second(imported_source_series, import_seconds),
            "import_chunk_series_per_second": rate_per_second(imported_chunk_series, import_seconds),
            "import_batches_per_second": rate_per_second(imported_batches, import_seconds),
            "verification_seconds": verify_seconds,
            "verification_attempts": verification_attempt,
            "verification_targets_per_second": rate_per_second(len(expected_targets), verify_seconds),
        })
        if verification_failures:
            total_finished_at = perf_counter()
            summary["performance"]["total_seconds"] = elapsed_seconds(total_started_at, total_finished_at)
            summary["import_verification"] = {
                "ok": False,
                "checked_targets": len(expected_targets),
                "failures": verification_failures,
            }
            print(json.dumps(summary, indent=2))
            print(
                "Refusing to delete the source matcher because imported target verification failed. "
                "The host-tagged source series are still present.",
                file=sys.stderr,
            )
            return 5

        delete_source_started_at = perf_counter()
        http_post_form(args.base_url, "/api/v1/admin/tsdb/delete_series", [("match[]", args.matcher)])
        delete_source_finished_at = perf_counter()
        delete_source_seconds = elapsed_seconds(delete_source_started_at, delete_source_finished_at)
        reset_cache_seconds = 0.0
        if args.reset_cache:
            reset_cache_started_at = perf_counter()
            http_post_form(args.base_url, "/internal/resetRollupResultCache", [])
            reset_cache_finished_at = perf_counter()
            reset_cache_seconds = elapsed_seconds(reset_cache_started_at, reset_cache_finished_at)

        source_count = verify_matcher_count(args.base_url, args.matcher)
        total_finished_at = perf_counter()
        summary["deleted_target_series"] = deleted_targets
        summary["import_batches"] = imported_batches
        summary["import_batch_size"] = args.import_batch_size
        summary["imported_source_series"] = imported_source_series
        summary["imported_chunk_series"] = imported_chunk_series
        summary["source_series_after_delete"] = source_count
        summary["import_verification"] = {"ok": True, "checked_targets": len(expected_targets), "failures": []}
        summary["performance"].update({
            "delete_source_seconds": delete_source_seconds,
            "reset_cache_seconds": reset_cache_seconds,
            "total_seconds": elapsed_seconds(total_started_at, total_finished_at),
        })
        if temp_rewritten:
            summary["rewritten_jsonl_note"] = "temporary rewritten file was created automatically for write mode"
        progress(
            "Write complete: "
            f"batches={imported_batches}, source_series={imported_source_series}, chunk_series={imported_chunk_series}, "
            f"deleted_target_series={deleted_targets}, source_series_after_delete={source_count}"
        )
        print(json.dumps(summary, indent=2))
        return 0
    except urllib.error.URLError as exc:
        print(describe_url_error(args.base_url, exc), file=sys.stderr)
        return 4


if __name__ == "__main__":
    raise SystemExit(main())



