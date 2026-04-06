import importlib.util
import pathlib
import sys
import unittest

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "helper" / "check_data.py"
SPEC = importlib.util.spec_from_file_location("check_data", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class CheckDataTests(unittest.TestCase):
    def test_missing_warning_metric_reports_historical_presence(self):
        calls = []

        def fake_series_count(_base_url, metric, _db_label, start, _end):
            calls.append((metric, start))
            if start == "raw-start":
                return 0
            if start == "feature-start":
                return 1
            raise AssertionError(f"unexpected start {start}")

        original_series_count = MODULE.series_count
        try:
            MODULE.series_count = fake_series_count
            result = MODULE.run_metric_checks(
                "http://127.0.0.1:8428",
                "evcc",
                [MODULE.MetricCheck("prioritySoc_value", "warning", "Priority SOC gauge uses this.")],
                "raw-start",
                "end",
                lookback_start="feature-start",
                window_label="raw window",
            )
        finally:
            MODULE.series_count = original_series_count

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["level"], "WARNING")
        self.assertEqual(result[0]["series"], 0)
        self.assertEqual(result[0]["historical_series"], 1)
        self.assertIn("Historically present, but not active in raw window.", result[0]["reason"])
        self.assertEqual(calls, [("prioritySoc_value", "raw-start"), ("prioritySoc_value", "feature-start")])

    def test_missing_warning_metric_reports_absent_history(self):
        def fake_series_count(_base_url, _metric, _db_label, _start, _end):
            return 0

        original_series_count = MODULE.series_count
        try:
            MODULE.series_count = fake_series_count
            result = MODULE.run_metric_checks(
                "http://127.0.0.1:8428",
                "evcc",
                [MODULE.MetricCheck("prioritySoc_value", "warning", "Priority SOC gauge uses this.")],
                "raw-start",
                "end",
                lookback_start="feature-start",
                window_label="raw window",
            )
        finally:
            MODULE.series_count = original_series_count

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["level"], "WARNING")
        self.assertEqual(result[0]["historical_series"], 0)
        self.assertIn("Not found in raw window or historical lookback.", result[0]["reason"])


if __name__ == "__main__":
    unittest.main()
