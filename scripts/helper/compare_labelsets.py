#!/usr/bin/env python3
"""Compare labelsets per metric between two benchmark/export JSON files.

Typical usage for before/after or import-state comparisons:
  python3 compare_labelsets.py \
    --left-json /tmp/.../before-cleanup/target-stats.json --left-name before \
    --right-json /tmp/.../after-cleanup/target-stats.json --right-name after

You can also compare the source baseline against a target-stats file.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Set, Tuple


def load_stats(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def series_iter(payload: dict) -> Iterable[dict]:
    per_series = payload.get("per_series", {})
    if isinstance(per_series, dict):
        for entry in per_series.values():
            if isinstance(entry, dict):
                yield entry


def labels_key(labels: dict) -> str:
    return json.dumps(labels, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def build_metric_map(payload: dict) -> Dict[str, Set[str]]:
    result: Dict[str, Set[str]] = {}
    for entry in series_iter(payload):
        labels = dict(entry.get("labels", {}))
        metric = entry.get("metric") or labels.get("__name__")
        if not metric:
            continue
        result.setdefault(str(metric), set()).add(labels_key(labels))
    return result


def maybe_filter(metrics: Dict[str, Set[str]], pattern: str | None) -> Dict[str, Set[str]]:
    if not pattern:
        return metrics
    rx = re.compile(pattern)
    return {name: values for name, values in metrics.items() if rx.search(name)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--left-json", required=True)
    ap.add_argument("--right-json", required=True)
    ap.add_argument("--left-name", default="left")
    ap.add_argument("--right-name", default="right")
    ap.add_argument("--metric-regex", help="only compare matching metric names")
    ap.add_argument("--limit", type=int, default=10, help="example labelsets per side and metric")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    left_payload = load_stats(Path(args.left_json))
    right_payload = load_stats(Path(args.right_json))

    left_metrics = maybe_filter(build_metric_map(left_payload), args.metric_regex)
    right_metrics = maybe_filter(build_metric_map(right_payload), args.metric_regex)

    all_metrics = sorted(set(left_metrics) | set(right_metrics))
    report: List[dict] = []

    for metric in all_metrics:
        left_set = left_metrics.get(metric, set())
        right_set = right_metrics.get(metric, set())
        common = left_set & right_set
        only_left = left_set - right_set
        only_right = right_set - left_set
        if not only_left and not only_right:
            continue
        report.append(
            {
                "metric": metric,
                "common": len(common),
                f"only_{args.left_name}": len(only_left),
                f"only_{args.right_name}": len(only_right),
                f"examples_only_{args.left_name}": [json.loads(item) for item in sorted(only_left)[: args.limit]],
                f"examples_only_{args.right_name}": [json.loads(item) for item in sorted(only_right)[: args.limit]],
            }
        )

    summary = {
        "left": args.left_name,
        "right": args.right_name,
        "metric_count_left": len(left_metrics),
        "metric_count_right": len(right_metrics),
        "metrics_with_differences": len(report),
        "differences": report,
    }

    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 1 if report else 0

    print("Labelset comparison")
    print("===================")
    print(f"Left:  {args.left_name} -> {args.left_json}")
    print(f"Right: {args.right_name} -> {args.right_json}")
    if args.metric_regex:
        print(f"Metric filter: {args.metric_regex}")
    print(f"Metrics with differences: {len(report)}")

    for item in report:
        print()
        print(item["metric"])
        print("-" * len(item["metric"]))
        print(f"common: {item['common']}")
        print(f"only {args.left_name}: {item[f'only_{args.left_name}']}")
        print(f"only {args.right_name}: {item[f'only_{args.right_name}']}")
        left_examples = item[f"examples_only_{args.left_name}"]
        right_examples = item[f"examples_only_{args.right_name}"]
        if left_examples:
            print(f"examples only {args.left_name}:")
            for example in left_examples:
                print(f"  - {json.dumps(example, sort_keys=True, ensure_ascii=True)}")
        if right_examples:
            print(f"examples only {args.right_name}:")
            for example in right_examples:
                print(f"  - {json.dumps(example, sort_keys=True, ensure_ascii=True)}")

    return 1 if report else 0


if __name__ == "__main__":
    raise SystemExit(main())

