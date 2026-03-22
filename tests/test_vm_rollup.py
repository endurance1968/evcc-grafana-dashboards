import importlib.util
import pathlib
import sys
import unittest


MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "evcc-vm-rollup.py"
SPEC = importlib.util.spec_from_file_location("evcc_vm_rollup", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class VmRollupTests(unittest.TestCase):
    def setUp(self):
        self.settings = MODULE.Settings(
            base_url="http://127.0.0.1:8428",
            db_label="evcc",
            host_label="",
            timezone="Europe/Berlin",
            metric_prefix="test_evcc",
            benchmark_start="2026-02-20T00:00:00Z",
            benchmark_end="2026-03-22T00:00:00Z",
            benchmark_step="1d",
        )

    def test_record_name_uses_prefix(self):
        self.assertEqual(
            MODULE.record_name(self.settings, "pv_energy_daily_wh"),
            "test_evcc_pv_energy_daily_wh",
        )

    def test_catalog_contains_phase_one_metrics(self):
        catalog = MODULE.build_catalog(self.settings)
        records = {item.record for item in catalog if item.implemented}
        self.assertIn("test_evcc_pv_energy_daily_wh", records)
        self.assertIn("test_evcc_vehicle_distance_daily_km", records)
        self.assertIn("test_evcc_grid_import_cost_daily_eur", records)
        self.assertIn("test_evcc_grid_import_price_effective_daily_ct_per_kwh", records)

    def test_catalog_marks_phase_two_items_as_deferred(self):
        catalog = MODULE.build_catalog(self.settings)
        deferred = {item.key for item in catalog if not item.implemented}
        self.assertIn("grid_import_daily_energy", deferred)
        self.assertIn("pricing_rollups", deferred)

    def test_vehicle_distance_rollup_collapses_to_vehicle_dimension(self):
        item = next(metric for metric in MODULE.build_catalog(self.settings) if metric.key == "vehicle_daily_distance")
        self.assertEqual(item.group_labels, ("vehicle",))
        self.assertIn("by (vehicle)", item.expr)
        self.assertNotIn("loadpoint", item.expr)

    def test_battery_soc_rollups_collapse_to_single_series(self):
        catalog = MODULE.build_catalog(self.settings)
        min_item = next(metric for metric in catalog if metric.key == "battery_soc_daily_min")
        max_item = next(metric for metric in catalog if metric.key == "battery_soc_daily_max")
        self.assertEqual(min_item.group_labels, ())
        self.assertEqual(max_item.group_labels, ())
        self.assertTrue(min_item.expr.startswith("min("))
        self.assertTrue(max_item.expr.startswith("max("))

    def test_matrix_values_ignores_non_numeric_rows(self):
        values = MODULE.matrix_values(
            {
                "values": [
                    [1772409600, "84"],
                    [1772410200, "bad"],
                    [1772410800, "69"],
                    [1772411400],
                ]
            }
        )
        self.assertEqual(values, [84.0, 69.0])

    def test_fetch_battery_soc_extrema_ignores_zero_and_uses_daily_window(self):
        calls = []

        def fake_http_get_json(settings, path, params=None):
            calls.append((path, params))
            return {
                "data": {
                    "result": [
                        {"values": [[1772409600, "0"], [1772410200, "84"], [1772410800, "69"]]},
                        {"values": [[1772411400, "99"]]},
                    ]
                }
            }

        original = MODULE.http_get_json
        MODULE.http_get_json = fake_http_get_json
        try:
            window = MODULE.DayWindow(
                day="2026-03-02",
                start_iso="2026-03-01T23:00:00Z",
                end_iso="2026-03-02T23:00:00Z",
                sample_timestamp_ms=1772406000000,
            )
            day_min, day_max = MODULE.fetch_battery_soc_extrema(self.settings, window)
        finally:
            MODULE.http_get_json = original

        self.assertEqual((day_min, day_max), (69.0, 99.0))
        self.assertEqual(calls[0][0], "/api/v1/query_range")
        self.assertEqual(calls[0][1]["start"], "2026-03-01T23:00:00Z")
        self.assertEqual(calls[0][1]["end"], "2026-03-02T23:00:00Z")

    def test_build_day_windows_uses_local_midnight_even_across_dst(self):
        windows = MODULE.build_day_windows(
            self.settings,
            MODULE.parse_local_day("2026-03-29", "--start-day"),
            MODULE.parse_local_day("2026-03-29", "--end-day"),
        )
        self.assertEqual(len(windows), 1)
        self.assertEqual(windows[0].start_iso, "2026-03-28T23:00:00Z")
        self.assertEqual(windows[0].end_iso, "2026-03-29T22:00:00Z")

    def test_normalize_rollup_labels_adds_namespace_and_dimension(self):
        item = next(metric for metric in MODULE.build_catalog(self.settings) if metric.key == "vehicle_daily_energy")
        labels = MODULE.normalize_rollup_labels(
            self.settings,
            item,
            {"vehicle": "BMW i3", "__name__": "chargePower_value"},
        )
        self.assertEqual(
            labels,
            {
                "__name__": "test_evcc_vehicle_energy_daily_wh",
                "db": "evcc",
                "vehicle": "BMW i3",
            },
        )

    def test_serialize_import_jsonl_creates_one_json_line_per_series(self):
        payload = MODULE.serialize_import_jsonl(
            [
                {
                    "metric": {
                        "__name__": "test_evcc_pv_energy_daily_wh",
                        "db": "evcc",
                            },
                    "values": [12.5],
                    "timestamps": [1774134000000],
                },
                {
                    "metric": {
                        "__name__": "test_evcc_home_energy_daily_wh",
                        "db": "evcc",
                            },
                    "values": [8.0],
                    "timestamps": [1774134000000],
                },
            ]
        ).decode("utf-8")
        lines = [line for line in payload.splitlines() if line.strip()]
        self.assertEqual(len(lines), 2)
        decoded = [MODULE.json.loads(line) for line in lines]
        self.assertEqual(decoded[0]["metric"]["__name__"], "test_evcc_pv_energy_daily_wh")
        self.assertEqual(decoded[1]["values"], [8.0])

    def test_build_window_chunks_groups_days_by_month(self):
        windows = MODULE.build_day_windows(
            self.settings,
            MODULE.parse_local_day("2026-01-30", "--start-day"),
            MODULE.parse_local_day("2026-02-02", "--end-day"),
        )
        chunks = MODULE.build_window_chunks(windows, "month")
        self.assertEqual([label for label, _ in chunks], ["2026-01", "2026-02"])
        self.assertEqual([len(items) for _, items in chunks], [2, 2])

    def test_build_window_chunks_all_keeps_single_chunk(self):
        windows = MODULE.build_day_windows(
            self.settings,
            MODULE.parse_local_day("2026-01-30", "--start-day"),
            MODULE.parse_local_day("2026-02-02", "--end-day"),
        )
        chunks = MODULE.build_window_chunks(windows, "all")
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0][0], "all")
        self.assertEqual(len(chunks[0][1]), 4)


    def test_quarter_hour_price_rollups_calculates_all_price_metrics(self):
        bucket_starts = [0, 900]
        grid_samples = []
        grid_samples.extend((timestamp, 1000.0) for timestamp in range(0, 900, 30))
        grid_samples.extend((timestamp, 2000.0) for timestamp in range(900, 1800, 30))
        tariff_samples = [
            (0, 0.20),
            (300, 0.22),
            (600, 0.24),
            (900, 0.40),
            (1200, 0.42),
            (1500, 0.44),
        ]

        result = MODULE.quarter_hour_price_rollups(
            grid_samples=grid_samples,
            tariff_samples=tariff_samples,
            bucket_starts=bucket_starts,
            raw_step_seconds=30,
            bucket_minutes=15,
        )

        self.assertAlmostEqual(result["grid_import_cost_daily"], 0.28, places=6)
        self.assertAlmostEqual(result["grid_import_price_avg_daily"], 32.0, places=6)
        self.assertAlmostEqual(
            result["grid_import_price_effective_daily"],
            37.333333333333336,
            places=6,
        )
        self.assertAlmostEqual(result["grid_import_price_min_daily"], 20.0, places=6)
        self.assertAlmostEqual(result["grid_import_price_max_daily"], 44.0, places=6)

    def test_quarter_hour_price_rollups_carries_forward_last_tariff(self):
        bucket_starts = [0, 900]
        grid_samples = []
        grid_samples.extend((timestamp, 1000.0) for timestamp in range(0, 900, 30))
        grid_samples.extend((timestamp, 1000.0) for timestamp in range(900, 1800, 30))
        tariff_samples = [
            (0, 0.18),
            (300, 0.21),
            (600, 0.24),
        ]

        result = MODULE.quarter_hour_price_rollups(
            grid_samples=grid_samples,
            tariff_samples=tariff_samples,
            bucket_starts=bucket_starts,
            raw_step_seconds=30,
            bucket_minutes=15,
        )

        self.assertAlmostEqual(result["grid_import_price_avg_daily"], 21.0, places=6)
        self.assertAlmostEqual(result["grid_import_price_effective_daily"], 24.0, places=6)
        self.assertAlmostEqual(result["grid_import_cost_daily"], 0.12, places=6)


if __name__ == "__main__":
    unittest.main()
