import importlib.util
import pathlib
import subprocess
import sys
import unittest

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "helper" / "vm-dedup-series.py"
SPEC = importlib.util.spec_from_file_location("vm_dedup_series", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class VmDedupSeriesTests(unittest.TestCase):
    def test_live_rehearsal_module_imports_cleanly(self):
        repo_root = pathlib.Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import importlib.util, pathlib, sys; "
                    "p=pathlib.Path('scripts/test/live-dedup-rehearsal.py').resolve(); "
                    "s=importlib.util.spec_from_file_location('live_dedup_rehearsal_test', p); "
                    "m=importlib.util.module_from_spec(s); sys.modules[s.name]=m; s.loader.exec_module(m)"
                ),
            ],
            cwd=repo_root,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_dedup_series_items_collapses_identical_duplicate_timestamps(self):
        item = {
            "metric": {"__name__": "pvPower_value", "title": "Balkon Sued"},
            "timestamps": [1000, 1000, 2000],
            "values": [1.0, 1.0, 2.0],
        }

        deduped, stats = MODULE.dedup_series_items([item], "reject")

        self.assertEqual(deduped["timestamps"], [1000, 2000])
        self.assertEqual(deduped["values"], [1.0, 2.0])
        self.assertEqual(stats.input_points, 3)
        self.assertEqual(stats.output_points, 2)
        self.assertEqual(stats.duplicate_extra_samples, 1)
        self.assertEqual(stats.identical_duplicate_samples, 1)
        self.assertEqual(stats.conflict_samples, 0)

    def test_dedup_series_items_counts_value_conflicts_without_overwriting_on_reject(self):
        item = {
            "metric": {"__name__": "pvPower_value", "title": "Balkon Sued"},
            "timestamps": [1000, 1000],
            "values": [1.0, 2.0],
        }

        deduped, stats = MODULE.dedup_series_items([item], "reject")

        self.assertEqual(deduped["timestamps"], [1000])
        self.assertEqual(deduped["values"], [1.0])
        self.assertEqual(stats.duplicate_extra_samples, 1)
        self.assertEqual(stats.conflict_samples, 1)

    def test_dedup_series_items_can_keep_last_on_conflict(self):
        item = {
            "metric": {"__name__": "pvPower_value", "title": "Balkon Sued"},
            "timestamps": [1000, 1000],
            "values": [1.0, 2.0],
        }

        deduped, stats = MODULE.dedup_series_items([item], "keep-last")

        self.assertEqual(deduped["timestamps"], [1000])
        self.assertEqual(deduped["values"], [2.0])
        self.assertEqual(stats.conflict_samples, 1)

    def test_metric_matches_exact_does_not_allow_superset_labels(self):
        expected = {"__name__": "pvPower_value", "title": "Balkon Sued"}

        self.assertTrue(MODULE.metric_matches_exact(expected, expected))
        self.assertFalse(MODULE.metric_matches_exact({"__name__": "pvPower_value", "title": "Balkon Sued", "host": "vm"}, expected))

    def test_dry_run_recommendation_flags_identical_duplicates_as_write_ready(self):
        recommendation = MODULE.dry_run_recommendation(exported_series=1, duplicate_extra_samples=5, conflict_samples=0)

        self.assertEqual(recommendation["status"], "GO FOR IT")
        self.assertIn("--write", recommendation["write_flags"])

    def test_dry_run_recommendation_stops_on_conflicts(self):
        recommendation = MODULE.dry_run_recommendation(exported_series=1, duplicate_extra_samples=5, conflict_samples=1)

        self.assertEqual(recommendation["status"], "STOP")
        self.assertIsNone(recommendation["write_flags"])


if __name__ == "__main__":
    unittest.main()
