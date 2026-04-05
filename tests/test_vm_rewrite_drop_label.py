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


if __name__ == "__main__":
    unittest.main()

