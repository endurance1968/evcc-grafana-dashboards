import contextlib
import importlib.util
import io
import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
CHECK_DATA_PATH = ROOT / "scripts" / "helper" / "check_data.py"
COMPARE_PATH = ROOT / "scripts" / "helper" / "compare_import_coverage.py"


CHECK_SPEC = importlib.util.spec_from_file_location("check_data_helper", CHECK_DATA_PATH)
CHECK_MODULE = importlib.util.module_from_spec(CHECK_SPEC)
sys.modules[CHECK_SPEC.name] = CHECK_MODULE
assert CHECK_SPEC.loader is not None
CHECK_SPEC.loader.exec_module(CHECK_MODULE)

COMPARE_SPEC = importlib.util.spec_from_file_location("compare_import_coverage_helper", COMPARE_PATH)
COMPARE_MODULE = importlib.util.module_from_spec(COMPARE_SPEC)
sys.modules[COMPARE_SPEC.name] = COMPARE_MODULE
assert COMPARE_SPEC.loader is not None
COMPARE_SPEC.loader.exec_module(COMPARE_MODULE)


class CheckDataCliTests(unittest.TestCase):
    def test_main_accepts_deprecated_db_argument(self):
        original_argv = sys.argv[:]
        original_series_count = CHECK_MODULE.series_count
        original_matcher_count = CHECK_MODULE.matcher_count
        try:
            CHECK_MODULE.series_count = lambda base_url, metric, start, end: 1 if metric in {"pvPower_value", "gridPower_value", "homePower_value"} else 0
            CHECK_MODULE.matcher_count = lambda base_url, matcher, start, end: 0
            sys.argv = [
                "check_data.py",
                "--base-url",
                "http://127.0.0.1:8428",
                "--db",
                "evcc",
                "--phase",
                "raw",
            ]
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(CHECK_MODULE.main(), 0)
        finally:
            sys.argv = original_argv
            CHECK_MODULE.series_count = original_series_count
            CHECK_MODULE.matcher_count = original_matcher_count


class CompareImportCoverageCliTests(unittest.TestCase):
    def test_main_accepts_deprecated_vm_db_label_argument(self):
        original_argv = sys.argv[:]
        original_influx_measurements = COMPARE_MODULE.influx_measurements
        original_build_critical_energy_checks = COMPARE_MODULE.build_critical_energy_checks
        original_render_report = COMPARE_MODULE.render_report
        try:
            COMPARE_MODULE.influx_measurements = lambda *args, **kwargs: []
            COMPARE_MODULE.build_critical_energy_checks = lambda *args, **kwargs: []
            COMPARE_MODULE.render_report = lambda results, critical_checks, start, end, only_problems, metadata: 0
            sys.argv = [
                "compare_import_coverage.py",
                "--influx-url",
                "http://127.0.0.1:8086",
                "--influx-db",
                "evcc",
                "--vm-base-url",
                "http://127.0.0.1:8428",
                "--vm-db-label",
                "evcc",
                "--start",
                "2025-01-01T00:00:00Z",
                "--end",
                "2025-01-31T23:59:59Z",
            ]
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(COMPARE_MODULE.main(), 0)
        finally:
            sys.argv = original_argv
            COMPARE_MODULE.influx_measurements = original_influx_measurements
            COMPARE_MODULE.build_critical_energy_checks = original_build_critical_energy_checks
            COMPARE_MODULE.render_report = original_render_report


class CompareImportCoverageVmTests(unittest.TestCase):
    def test_vm_stats_reads_mixed_host_and_db_labeled_series(self):
        original_export_lines = COMPARE_MODULE.export_lines
        lines = [
            json.dumps(
                {
                    "metric": {"__name__": "gridPower_value", "db": "evcc"},
                    "timestamps": [1000, 2000],
                    "values": [10.0, 20.0],
                }
            ),
            json.dumps(
                {
                    "metric": {"__name__": "gridPower_value", "host": "lx-telegraf"},
                    "timestamps": [3000],
                    "values": [30.0],
                }
            ),
        ]
        try:
            COMPARE_MODULE.export_lines = lambda base_url, metric, start, end: iter(lines)
            stats = COMPARE_MODULE.vm_stats(
                "http://127.0.0.1:8428",
                "gridPower_value",
                "2025-01-01T00:00:00Z",
                "2025-01-01T00:00:03Z",
            )
        finally:
            COMPARE_MODULE.export_lines = original_export_lines

        self.assertEqual(stats.series, 2)
        self.assertEqual(stats.points, 3)
        self.assertEqual(COMPARE_MODULE.iso_z(stats.first), "1970-01-01T00:00:01Z")
        self.assertEqual(COMPARE_MODULE.iso_z(stats.last), "1970-01-01T00:00:03Z")

    def test_vm_legacy_bucket_energy_reads_db_and_host_labeled_total_series(self):
        original_export_lines_for_matcher = COMPARE_MODULE.export_lines_for_matcher
        line = json.dumps(
            {
                "metric": {"__name__": "pvPower_value", "id": "", "db": "evcc", "host": "lx-telegraf"},
                "timestamps": [0, 10000],
                "values": [600.0, 1200.0],
            }
        )
        try:
            COMPARE_MODULE.export_lines_for_matcher = lambda base_url, matcher, start, end: iter([line])
            value = COMPARE_MODULE.vm_legacy_bucket_energy_kwh(
                "http://127.0.0.1:8428",
                "1970-01-01T00:00:00Z",
                "1970-01-01T00:00:59Z",
                60,
                40000.0,
            )
        finally:
            COMPARE_MODULE.export_lines_for_matcher = original_export_lines_for_matcher

        self.assertAlmostEqual(value, 0.02, places=6)


    def test_compare_measurement_skips_ignored_additional_status_measurement(self):
        original_influx_stats = COMPARE_MODULE.influx_stats
        original_influx_field_types = COMPARE_MODULE.influx_field_types
        original_choose_vm_metric = COMPARE_MODULE.choose_vm_metric
        try:
            COMPARE_MODULE.influx_stats = lambda *args, **kwargs: COMPARE_MODULE.SpanStats(points=738, series=8, first=None, last=None)
            COMPARE_MODULE.influx_field_types = lambda *args, **kwargs: ["string"]
            COMPARE_MODULE.choose_vm_metric = lambda *args, **kwargs: ("chargerIcon", COMPARE_MODULE.SpanStats(points=0, series=0, first=None, last=None))
            result = COMPARE_MODULE.compare_measurement(
                "http://127.0.0.1:8086",
                "evcc",
                "http://127.0.0.1:8428",
                "chargerIcon",
                "2025-01-01T00:00:00Z",
                "2025-01-31T23:59:59Z",
                None,
                None,
                3600,
            )
        finally:
            COMPARE_MODULE.influx_stats = original_influx_stats
            COMPARE_MODULE.influx_field_types = original_influx_field_types
            COMPARE_MODULE.choose_vm_metric = original_choose_vm_metric

        self.assertEqual(result.group, "additional")
        self.assertEqual(result.status, "SKIP")
        self.assertIsNone(result.hint)

    def test_compare_measurement_keeps_non_ignored_additional_gap_as_missing(self):
        original_influx_stats = COMPARE_MODULE.influx_stats
        original_influx_field_types = COMPARE_MODULE.influx_field_types
        original_choose_vm_metric = COMPARE_MODULE.choose_vm_metric
        try:
            COMPARE_MODULE.influx_stats = lambda *args, **kwargs: COMPARE_MODULE.SpanStats(points=1, series=1, first=None, last=None)
            COMPARE_MODULE.influx_field_types = lambda *args, **kwargs: ["float"]
            COMPARE_MODULE.choose_vm_metric = lambda *args, **kwargs: ("auth_test", COMPARE_MODULE.SpanStats(points=0, series=0, first=None, last=None))
            result = COMPARE_MODULE.compare_measurement(
                "http://127.0.0.1:8086",
                "evcc",
                "http://127.0.0.1:8428",
                "auth_test",
                "2025-01-01T00:00:00Z",
                "2025-01-31T23:59:59Z",
                None,
                None,
                3600,
            )
        finally:
            COMPARE_MODULE.influx_stats = original_influx_stats
            COMPARE_MODULE.influx_field_types = original_influx_field_types
            COMPARE_MODULE.choose_vm_metric = original_choose_vm_metric

        self.assertEqual(result.group, "additional")
        self.assertEqual(result.status, "MISSING")
if __name__ == "__main__":
    unittest.main()

