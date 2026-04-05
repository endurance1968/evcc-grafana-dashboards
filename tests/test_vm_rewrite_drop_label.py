import importlib.util
import json
import pathlib
import shutil
import sys
import unittest
import uuid

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "helper" / "vm-rewrite-drop-label.py"
SPEC = importlib.util.spec_from_file_location("vm_rewrite_drop_label", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class VmRewriteDropLabelTests(unittest.TestCase):
    def test_transform_series_removes_label_without_reinserting_empty_value(self):
        item = {
            "metric": {
                "__name__": "pvPower_value",
                "db": "evcc",
                "host": "lx-telemetry-ingest",
            },
            "timestamps": [1, 2],
            "values": [3.0, 4.0],
        }

        rewritten = MODULE.transform_series(item, "host")

        self.assertEqual(
            rewritten["metric"],
            {
                "__name__": "pvPower_value",
                "db": "evcc",
            },
        )
        self.assertEqual(
            MODULE.target_matcher(rewritten["metric"], "host"),
            '{__name__="pvPower_value",db="evcc"}',
        )

    def test_combine_rewritten_series_merges_multiple_sources_for_same_target(self):
        items = [
            {
                "metric": {"__name__": "batterySoc_value", "db": "evcc", "id": "1"},
                "timestamps": [1000, 2000],
                "values": [10.0, 20.0],
            },
            {
                "metric": {"__name__": "batterySoc_value", "db": "evcc", "id": "1"},
                "timestamps": [3000, 4000],
                "values": [30.0, 40.0],
            },
        ]

        combined = MODULE.combine_rewritten_series(items, allow_value_conflicts=False)

        self.assertEqual(combined["timestamps"], [1000, 2000, 3000, 4000])
        self.assertEqual(combined["values"], [10.0, 20.0, 30.0, 40.0])

    def test_import_rewritten_file_accumulates_expected_stats_per_target_matcher(self):
        rows = [
            {
                "metric": {"__name__": "pvPower_value", "db": "evcc"},
                "timestamps": [1000],
                "values": [1.0],
            },
            {
                "metric": {"__name__": "pvPower_value", "db": "evcc"},
                "timestamps": [2000, 3000],
                "values": [2.0, 3.0],
            },
        ]

        temp_root = pathlib.Path(__file__).resolve().parent / "_tmp_vm_rewrite_drop_label"
        temp_root.mkdir(exist_ok=True)
        temp_dir = temp_root / str(uuid.uuid4())
        temp_dir.mkdir()
        rewritten_path = temp_dir / "rewritten.jsonl"

        try:
            rewritten_path.write_text(
                "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in rows),
                encoding="utf-8",
            )

            original_http_post_bytes = MODULE.http_post_bytes
            original_delete_target_matcher = MODULE.delete_target_matcher
            try:
                MODULE.http_post_bytes = lambda base_url, path, payload: "ok"
                MODULE.delete_target_matcher = lambda base_url, matcher: None
                _, _, _, _, expected_targets = MODULE.import_rewritten_file(
                    "http://127.0.0.1:8428",
                    rewritten_path,
                    "host",
                    batch_size=10,
                    max_line_bytes=8_000_000,
                    delete_targets_first=False,
                    progress_every=0,
                    progress_cb=None,
                )
            finally:
                MODULE.http_post_bytes = original_http_post_bytes
                MODULE.delete_target_matcher = original_delete_target_matcher
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        matcher = '{__name__="pvPower_value",db="evcc"}'
        self.assertEqual(list(expected_targets), [matcher])
        self.assertEqual(expected_targets[matcher], MODULE.SeriesStats(points=3, first=1000, last=3000))

    def test_merge_with_targets_can_keep_existing_target_values_on_conflict(self):
        item = {
            "metric": {"__name__": "pvPower_value", "db": "evcc"},
            "timestamps": [1000, 2000],
            "values": [10.0, 20.0],
        }
        existing = [
            {
                "metric": {"__name__": "pvPower_value", "db": "evcc"},
                "timestamps": [1000, 3000],
                "values": [1.0, 30.0],
            }
        ]

        merged = MODULE.merge_with_targets(
            item,
            existing,
            allow_value_conflicts=False,
            keep_target_values_on_conflict=True,
        )

        self.assertEqual(merged["timestamps"], [1000, 2000, 3000])
        self.assertEqual(merged["values"], [1.0, 20.0, 30.0])

    def test_should_delete_source_only_when_every_point_is_fully_shadowed(self):
        item = {
            "metric": {"__name__": "pvPower_value", "db": "evcc"},
            "timestamps": [1000, 2000],
            "values": [10.0, 20.0],
        }

        self.assertTrue(MODULE.should_delete_source_only(item, 2, 2, True))
        self.assertFalse(MODULE.should_delete_source_only(item, 2, 1, True))
        self.assertFalse(MODULE.should_delete_source_only(item, 2, 2, False))

    def test_remaining_value_conflicts_subtracts_delete_only_points(self):
        self.assertEqual(MODULE.remaining_value_conflicts(2387, 2387), 0)
        self.assertEqual(MODULE.remaining_value_conflicts(10, 4), 6)
        self.assertEqual(MODULE.remaining_value_conflicts(3, 10), 0)


if __name__ == "__main__":
    unittest.main()
