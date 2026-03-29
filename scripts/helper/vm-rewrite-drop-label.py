#!/usr/bin/env python3
"""Export VM series, drop a label, and optionally rewrite them back safely."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


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
        help="Number of series per VM import batch during write mode.",
    )
    return parser.parse_args()


def fetch_export_lines(base_url: str, matcher: str, start_ms: int | None = None, end_ms: int | None = None) -> list[dict]:
    params: list[tuple[str, str]] = [("match[]", matcher)]
    if start_ms is not None:
        params.append(("start", str(start_ms)))
    if end_ms is not None:
        params.append(("end", str(end_ms)))
    url = f"{base_url.rstrip('/')}/api/v1/export?" + urllib.parse.urlencode(params)
    lines: list[dict] = []
    try:
        with urllib.request.urlopen(url, timeout=300) as response:
            for raw in response:
                if not raw.strip():
                    continue
                lines.append(json.loads(raw))
    except urllib.error.HTTPError as exc:
        if exc.code != 422:
            raise
    return lines


def write_jsonl(path: Path, items: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for item in items:
            handle.write(json.dumps(item, separators=(",", ":"), ensure_ascii=True))
            handle.write("\n")


def transform_series(items: list[dict], drop_label: str) -> list[dict]:
    transformed: list[dict] = []
    for item in items:
        metric = {k: v for k, v in item["metric"].items() if k != drop_label}
        transformed.append(
            {
                "metric": metric,
                "timestamps": [int(ts) for ts in item["timestamps"]],
                "values": [float(value) for value in item["values"]],
            }
        )
    return transformed


def transformed_matcher(metric: dict[str, str]) -> str:
    parts = [f'{key}="{value}"' for key, value in sorted(metric.items())]
    return "{" + ",".join(parts) + "}"


def target_matcher(metric: dict[str, str], dropped_label: str) -> str:
    target_metric = dict(metric)
    target_metric.setdefault(dropped_label, "")
    return transformed_matcher(target_metric)


def index_existing_targets(base_url: str, rewritten: list[dict], dropped_label: str) -> dict[tuple[tuple[str, str], ...], list[dict]]:
    indexed: dict[tuple[tuple[str, str], ...], list[dict]] = {}
    for item in rewritten:
        key = tuple(sorted(item["metric"].items()))
        if key in indexed:
            continue
        # Always fetch the full target history before merge/delete.
        # Limiting the export to the host-tag window can truncate older hostless data
        # when the merged target series is deleted and re-imported.
        existing = fetch_export_lines(
            base_url,
            target_matcher(item["metric"], dropped_label),
        )
        indexed[key] = existing
    return indexed


def analyze_targets(rewritten: list[dict], existing_index: dict[tuple[tuple[str, str], ...], list[dict]]) -> tuple[int, int, int, list[dict]]:
    series_checked = 0
    overlap_timestamps = 0
    value_conflicts = 0
    examples: list[dict] = []
    for item in rewritten:
        series_checked += 1
        key = tuple(sorted(item["metric"].items()))
        existing = existing_index.get(key, [])
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
        overlap_timestamps += current_overlap
        value_conflicts += current_conflicts
        if (current_overlap or current_conflicts) and len(examples) < 10:
            examples.append(
                {
                    "metric": item["metric"],
                    "overlap_timestamps": current_overlap,
                    "value_conflicts": current_conflicts,
                    "host_points": len(item["timestamps"]),
                }
            )
    return series_checked, overlap_timestamps, value_conflicts, examples


def merge_with_targets(
    rewritten: list[dict],
    existing_index: dict[tuple[tuple[str, str], ...], list[dict]],
    allow_value_conflicts: bool,
) -> list[dict]:
    merged: list[dict] = []
    for item in rewritten:
        key = tuple(sorted(item["metric"].items()))
        merged_points: dict[int, float] = {}
        for candidate in existing_index.get(key, []):
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
        merged.append(
            {
                "metric": item["metric"],
                "timestamps": merged_ts,
                "values": [merged_points[ts] for ts in merged_ts],
            }
        )
    return merged


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
    chunks = []
    for item in items:
        chunks.append(json.dumps(item, separators=(",", ":"), ensure_ascii=True))
    return ("\n".join(chunks) + "\n").encode("utf-8")


def verify_matcher_count(base_url: str, matcher: str) -> int:
    url = f"{base_url.rstrip('/')}/prometheus/api/v1/series?" + urllib.parse.urlencode([("match[]", matcher)])
    with urllib.request.urlopen(url, timeout=120) as response:
        payload = json.load(response)
    return len(payload.get("data", []))


def delete_target_matchers(base_url: str, rewritten: list[dict], dropped_label: str) -> int:
    deleted = 0
    seen: set[str] = set()
    for item in rewritten:
        matcher = target_matcher(item["metric"], dropped_label)
        if matcher in seen:
            continue
        http_post_form(base_url, "/api/v1/admin/tsdb/delete_series", [("match[]", matcher)])
        seen.add(matcher)
        deleted += 1
    return deleted


def batched(items: list[dict], batch_size: int) -> list[list[dict]]:
    return [items[index:index + batch_size] for index in range(0, len(items), batch_size)]


def import_rewritten_series(
    base_url: str,
    rewritten: list[dict],
    dropped_label: str,
    batch_size: int,
    delete_targets_first: bool,
) -> tuple[int, int]:
    deleted_targets = 0
    imported_batches = 0
    for batch in batched(rewritten, max(batch_size, 1)):
        if delete_targets_first:
            deleted_targets += delete_target_matchers(base_url, batch, dropped_label)
        http_post_bytes(base_url, "/api/v1/import", serialize_jsonl(batch))
        imported_batches += 1
    return deleted_targets, imported_batches


def main() -> int:
    args = parse_args()
    backup_path = Path(args.backup_jsonl)
    rewritten_path = Path(args.rewritten_jsonl) if args.rewritten_jsonl else None

    exported = fetch_export_lines(args.base_url, args.matcher)
    write_jsonl(backup_path, exported)
    rewritten = transform_series(exported, args.drop_label)
    existing_index = index_existing_targets(args.base_url, rewritten, args.drop_label)
    checked_series, overlaps, value_conflicts, overlap_examples = analyze_targets(rewritten, existing_index)

    final_output = rewritten
    if args.merge_target:
        final_output = merge_with_targets(rewritten, existing_index, args.allow_value_conflicts)

    if rewritten_path:
        write_jsonl(rewritten_path, final_output)

    total_points = sum(len(item.get("timestamps", [])) for item in exported)
    total_series = len(exported)
    output_points = sum(len(item.get("timestamps", [])) for item in final_output)

    summary = {
        "mode": "write" if args.write else "dry-run",
        "matcher": args.matcher,
        "drop_label": args.drop_label,
        "merge_target": args.merge_target,
        "backup_jsonl": str(backup_path),
        "rewritten_jsonl": str(rewritten_path) if rewritten_path else None,
        "exported_series": total_series,
        "exported_points": total_points,
        "checked_target_series": checked_series,
        "overlap_timestamps": overlaps,
        "value_conflicts": value_conflicts,
        "overlap_examples": overlap_examples,
        "output_points": output_points,
    }

    if overlaps and not (args.allow_overlap or args.merge_target):
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
        print(json.dumps(summary, indent=2))
        return 0

    deleted_targets, imported_batches = import_rewritten_series(
        args.base_url,
        final_output,
        args.drop_label,
        args.import_batch_size,
        delete_targets_first=args.merge_target,
    )
    http_post_form(args.base_url, "/api/v1/admin/tsdb/delete_series", [("match[]", args.matcher)])
    if args.reset_cache:
        http_post_form(args.base_url, "/internal/resetRollupResultCache", [])

    source_count = verify_matcher_count(args.base_url, args.matcher)
    summary["deleted_target_series"] = deleted_targets
    summary["import_batches"] = imported_batches
    summary["import_batch_size"] = args.import_batch_size
    summary["source_series_after_delete"] = source_count
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
