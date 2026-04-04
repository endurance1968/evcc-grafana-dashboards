import contextlib
import importlib.util
import io
import pathlib
import sys
import unittest
from types import SimpleNamespace

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "rollup" / "evcc-vm-rollup.py"
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
            metric_prefix="evcc",
            raw_sample_step="10s",
            energy_rollup_step="60s",
            price_bucket_minutes=15,
            max_fetch_points_per_series=28000,
            benchmark_start="2026-02-20T00:00:00Z",
            benchmark_end="2026-03-22T00:00:00Z",
            benchmark_step="1d",
        )

    def test_record_name_uses_prefix(self):
        self.assertEqual(
            MODULE.record_name(self.settings, "pv_energy_daily_wh"),
            "evcc_pv_energy_daily_wh",
        )

    def test_catalog_contains_phase_one_metrics(self):
        catalog = MODULE.build_catalog(self.settings)
        records = {item.record for item in catalog if item.implemented}
        self.assertIn("evcc_pv_energy_daily_wh", records)
        self.assertIn("evcc_vehicle_distance_daily_km", records)
        self.assertIn("evcc_vehicle_charge_cost_daily_eur", records)
        self.assertIn("evcc_potential_vehicle_charge_cost_daily_eur", records)
        self.assertIn("evcc_grid_import_cost_daily_eur", records)
        self.assertIn("evcc_grid_import_price_effective_daily_ct_per_kwh", records)

    def test_catalog_marks_only_remaining_phase_two_items_as_deferred(self):
        catalog = MODULE.build_catalog(self.settings)
        deferred = {item.key for item in catalog if not item.implemented}
        self.assertNotIn("grid_import_daily_energy", deferred)
        self.assertNotIn("battery_charge_daily_energy", deferred)
        self.assertNotIn("grid_export_credit_daily", deferred)
        self.assertEqual(deferred, set())

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
                local_year="2026",
                local_month="03",
                local_day="02",
                local_date="2026-03-02",
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
        self.assertEqual(windows[0].local_year, "2026")
        self.assertEqual(windows[0].local_month, "03")
        self.assertEqual(windows[0].local_day, "29")
        self.assertEqual(windows[0].local_date, "2026-03-29")

    def test_normalize_rollup_labels_adds_namespace_dimension_and_local_month_labels(self):
        item = next(metric for metric in MODULE.build_catalog(self.settings) if metric.key == "vehicle_daily_energy")
        window = MODULE.DayWindow(
            day="2026-03-02",
            start_iso="2026-03-01T23:00:00Z",
            end_iso="2026-03-02T23:00:00Z",
            sample_timestamp_ms=1772406000000,
            local_year="2026",
            local_month="03",
            local_day="02",
            local_date="2026-03-02",
        )
        labels = MODULE.normalize_rollup_labels(
            self.settings,
            item,
            {"vehicle": "BMW i3", "__name__": "chargePower_value"},
            window,
        )
        self.assertEqual(
            labels,
            {
                "__name__": "evcc_vehicle_energy_daily_wh",
                "db": "evcc",
                "local_year": "2026",
                "local_month": "03",
                "vehicle": "BMW i3",
            },
        )

    def test_summarize_positive_bucket_energy_samples_uses_bucket_means(self):
        value = MODULE.summarize_positive_bucket_energy_samples(
            [
                (0, 600.0),
                (10, 1200.0),
                (60, 300.0),
                (70, -5.0),
                (80, 50000.0),
            ],
            bucket_seconds=60,
        )
        self.assertAlmostEqual(value, 20.0, places=6)

    def test_positive_energy_query_uses_expected_grouping(self):
        catalog = MODULE.build_catalog(self.settings)
        loadpoint_item = next(metric for metric in catalog if metric.key == "loadpoint_daily_energy")
        vehicle_item = next(metric for metric in catalog if metric.key == "vehicle_daily_energy")
        self.assertEqual(
            MODULE.positive_energy_query(self.settings, loadpoint_item),
            'sum by (loadpoint) (chargePower_value{db="evcc"})',
        )
        self.assertEqual(
            MODULE.positive_energy_query(self.settings, vehicle_item),
            'sum by (vehicle) (chargePower_value{db="evcc"})',
        )

    def test_positive_energy_rollups_use_direct_integrate_queries(self):
        catalog = MODULE.build_catalog(self.settings)
        pv_item = next(metric for metric in catalog if metric.key == "pv_daily_energy")
        home_item = next(metric for metric in catalog if metric.key == "home_daily_energy")
        loadpoint_item = next(metric for metric in catalog if metric.key == "loadpoint_daily_energy")
        self.assertEqual(
            pv_item.expr,
            'sum(integrate(pvPower_value{db="evcc",id=""}[1d])) / 3600',
        )
        self.assertEqual(
            home_item.expr,
            'sum(integrate(homePower_value{db="evcc"}[1d])) / 3600',
        )
        self.assertEqual(
            loadpoint_item.expr,
            'sum(integrate(chargePower_value{db="evcc"}[1d])) by (loadpoint) / 3600',
        )

    def test_backfill_positive_energy_uses_direct_rollup_query_path(self):
        pv_item = next(metric for metric in MODULE.build_catalog(self.settings) if metric.key == "pv_daily_energy")
        args = SimpleNamespace(start_day="2026-03-02", end_day="2026-03-02", batch_size=200, progress=False, write=False, json=True)
        captured = {}

        def fake_build_catalog(settings):
            return [pv_item]

        def fake_fetch_rollup_vector(settings, item, window):
            captured["query"] = item.expr
            return [{"metric": {"db": "evcc"}, "value": [window.sample_timestamp_ms / 1000, "4200"]}]

        def fail_positive_matrix(*_args, **_kwargs):
            raise AssertionError("legacy positive-energy matrix path should not be used")

        def fake_build_health(*_args, **_kwargs):
            return []

        original_build_catalog = MODULE.build_catalog
        original_fetch_rollup_vector = MODULE.fetch_rollup_vector
        original_positive_matrix = MODULE.fetch_chunk_positive_energy_matrix
        original_build_health = MODULE.build_pv_health_rollups
        MODULE.build_catalog = fake_build_catalog
        MODULE.fetch_rollup_vector = fake_fetch_rollup_vector
        MODULE.fetch_chunk_positive_energy_matrix = fail_positive_matrix
        MODULE.build_pv_health_rollups = fake_build_health
        try:
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                result = MODULE.backfill(self.settings, args)
        finally:
            MODULE.build_catalog = original_build_catalog
            MODULE.fetch_rollup_vector = original_fetch_rollup_vector
            MODULE.fetch_chunk_positive_energy_matrix = original_positive_matrix
            MODULE.build_pv_health_rollups = original_build_health

        summary = MODULE.json.loads(stdout.getvalue())
        self.assertEqual(result, 0)
        self.assertEqual(captured["query"], 'sum(integrate(pvPower_value{db="evcc",id=""}[1d])) / 3600')
        self.assertEqual(summary["samples"], 1)
        self.assertEqual(summary["series"], 1)
        self.assertEqual(summary["skipped"], 0)
    def test_serialize_import_jsonl_creates_one_json_line_per_series(self):
        payload = MODULE.serialize_import_jsonl(
            [
                {
                    "metric": {
                        "__name__": "evcc_pv_energy_daily_wh",
                        "db": "evcc",
                            },
                    "values": [12.5],
                    "timestamps": [1774134000000],
                },
                {
                    "metric": {
                        "__name__": "evcc_home_energy_daily_wh",
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
        self.assertEqual(decoded[0]["metric"]["__name__"], "evcc_pv_energy_daily_wh")
        self.assertEqual(decoded[1]["values"], [8.0])

    def test_build_window_chunks_groups_days_by_month(self):
        windows = MODULE.build_day_windows(
            self.settings,
            MODULE.parse_local_day("2026-01-30", "--start-day"),
            MODULE.parse_local_day("2026-02-02", "--end-day"),
        )
        chunks = MODULE.build_window_chunks(windows)
        self.assertEqual([label for label, _ in chunks], ["2026-01", "2026-02"])
        self.assertEqual([len(items) for _, items in chunks], [2, 2])

    def test_build_window_chunks_keeps_single_chunk_for_single_month(self):
        windows = MODULE.build_day_windows(
            self.settings,
            MODULE.parse_local_day("2026-01-30", "--start-day"),
            MODULE.parse_local_day("2026-01-31", "--end-day"),
        )
        chunks = MODULE.build_window_chunks(windows)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0][0], "2026-01")
        self.assertEqual(len(chunks[0][1]), 2)

    def test_build_fetch_blocks_splits_large_month_into_multiple_blocks(self):
        windows = MODULE.build_day_windows(
            self.settings,
            MODULE.parse_local_day("2026-01-01", "--start-day"),
            MODULE.parse_local_day("2026-01-08", "--end-day"),
        )
        blocks, block_by_day = MODULE.build_fetch_blocks("2026-01", windows, step_seconds=10, max_points_per_series=28000)
        self.assertGreater(len(blocks), 1)
        self.assertEqual(block_by_day["2026-01-01"].name, "2026-01-b1")
        self.assertEqual(block_by_day["2026-01-08"].name, blocks[-1].name)

    def test_slice_samples_can_include_last_sample_before_range(self):
        samples = [(90, 1.0), (100, 2.0), (110, 3.0)]
        sliced = MODULE.slice_samples(samples, 100, 111, include_last_before=True)
        self.assertEqual(sliced, [(90, 1.0), (100, 2.0), (110, 3.0)])

    def test_slice_samples_limits_previous_sample_by_lookback(self):
        samples = [(0, 1.0), (200, 2.0), (310, 3.0)]
        sliced = MODULE.slice_samples(
            samples,
            300,
            320,
            include_last_before=True,
            max_lookback_seconds=30,
        )
        self.assertEqual(sliced, [(310, 3.0)])


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
            feed_in_tariff_samples=[(0, 0.08), (900, 0.10)],
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
            feed_in_tariff_samples=[(0, 0.08), (900, 0.10)],
            bucket_starts=bucket_starts,
            raw_step_seconds=30,
            bucket_minutes=15,
        )

        self.assertAlmostEqual(result["grid_import_price_avg_daily"], 21.0, places=6)
        self.assertAlmostEqual(result["grid_import_price_effective_daily"], 24.0, places=6)
        self.assertAlmostEqual(result["grid_import_cost_daily"], 0.12, places=6)

    def test_bucket_price_rollups_uses_bucket_import_kwh(self):
        result = MODULE.bucket_price_rollups(
            bucket_import_samples=[(900, 0.25), (1800, 0.50)],
            bucket_export_samples=[(900, 0.10), (1800, 0.20)],
            tariff_samples=[(0, 0.20), (600, 0.24), (900, 0.40), (1500, 0.44)],
            feed_in_tariff_samples=[(0, 0.08), (900, 0.10)],
            bucket_starts=[0, 900],
            bucket_minutes=15,
        )

        self.assertAlmostEqual(result["grid_import_cost_daily"], 0.28, places=6)
        self.assertAlmostEqual(result["grid_import_price_avg_daily"], 32.0, places=6)
        self.assertAlmostEqual(result["grid_import_price_effective_daily"], 37.333333333333336, places=6)
        self.assertAlmostEqual(result["grid_import_price_min_daily"], 20.0, places=6)
        self.assertAlmostEqual(result["grid_import_price_max_daily"], 44.0, places=6)
        self.assertAlmostEqual(result["grid_export_credit_daily"], 0.028, places=6)

    def test_summarize_grid_energy_samples_uses_legacy_60s_mean_buckets(self):
        result = MODULE.summarize_grid_energy_samples(
            [
                (0, -100.0), (10, 200.0), (20, -300.0), (30, 400.0), (40, 0.0), (50, 0.0),
                (60, -60.0), (70, -120.0), (80, 180.0), (90, 0.0), (100, 0.0), (110, 0.0),
            ],
            bucket_seconds=60,
        )

        self.assertAlmostEqual(result["grid_import_daily_energy"], 3.25, places=6)
        self.assertAlmostEqual(result["grid_export_daily_energy"], 2.2666666666666666, places=6)

    def test_summarize_counter_spread_samples_converts_kwh_to_wh(self):
        value = MODULE.summarize_counter_spread_samples(
            [
                (0, -1.0),
                (10, 100.0),
                (20, float("nan")),
                (30, 101.25),
                (40, 100.75),
            ]
        )

        self.assertAlmostEqual(value, 1250.0, places=6)

    def test_fetch_grid_energy_rollups_prefers_counter_spread_for_import(self):
        def fake_fetch_single_series_range(settings, query, start_iso, end_iso, step):
            if "gridPower_value" in query:
                return [
                    (0, -100.0), (10, 200.0), (20, -300.0), (30, 400.0), (40, 0.0), (50, 0.0),
                ]
            if "gridEnergy_value" in query:
                return [(0, 1000.0), (10, 1000.5), (20, 1001.2)]
            raise AssertionError(query)

        original = MODULE.fetch_single_series_range
        MODULE.fetch_single_series_range = fake_fetch_single_series_range
        try:
            window = MODULE.DayWindow(
                day="2026-03-02",
                start_iso="2026-03-01T23:00:00Z",
                end_iso="2026-03-02T23:00:00Z",
                sample_timestamp_ms=1772406000000,
                local_year="2026",
                local_month="03",
                local_day="02",
                local_date="2026-03-02",
            )
            result = MODULE.fetch_grid_energy_rollups(self.settings, window)
        finally:
            MODULE.fetch_single_series_range = original

        self.assertAlmostEqual(result["grid_import_daily_energy"], 1200.0, places=6)
        self.assertAlmostEqual(result["grid_export_daily_energy"], 1.6666666666666667, places=6)

    def test_fetch_vehicle_price_rollups_uses_matching_tariffs(self):
        def fake_fetch_single_series_range(settings, query, start_iso, end_iso, step):
            if "tariffPriceLoadpoints_value" in query:
                return [(0, 0.10), (900, 0.20)]
            if "tariffGrid_value" in query:
                return [(0, 0.30), (900, 0.40)]
            raise AssertionError(query)

        def fake_fetch_series_range(settings, query, start_iso, end_iso, step):
            if 'chargePower_value' not in query:
                raise AssertionError(query)
            return [
                {
                    'metric': {'vehicle': 'BMW i3'},
                    'samples': [(0, 1000.0), (30, 1000.0), (900, 2000.0), (930, 2000.0)],
                }
            ]

        original_single = MODULE.fetch_single_series_range
        original_series = MODULE.fetch_series_range
        MODULE.fetch_single_series_range = fake_fetch_single_series_range
        MODULE.fetch_series_range = fake_fetch_series_range
        try:
            window = MODULE.DayWindow(
                day="2026-03-02",
                start_iso="1970-01-01T00:00:00Z",
                end_iso="1970-01-01T00:30:00Z",
                sample_timestamp_ms=0,
                local_year="1970",
                local_month="01",
                local_day="01",
                local_date="1970-01-01",
            )
            actual_item = next(metric for metric in MODULE.build_catalog(self.settings) if metric.key == 'vehicle_charge_cost_daily')
            potential_item = next(metric for metric in MODULE.build_catalog(self.settings) if metric.key == 'potential_vehicle_charge_cost_daily')
            actual = MODULE.fetch_vehicle_price_rollups(self.settings, actual_item, window)
            potential = MODULE.fetch_vehicle_price_rollups(self.settings, potential_item, window)
        finally:
            MODULE.fetch_single_series_range = original_single
            MODULE.fetch_series_range = original_series

        self.assertEqual(actual[0][0]['vehicle'], 'BMW i3')
        self.assertAlmostEqual(actual[0][1], 0.002777777777777778, places=6)
        self.assertAlmostEqual(potential[0][1], 0.006111111111111111, places=6)

    def test_summarize_bucket_grid_energy_converts_kwh_to_wh(self):
        result = MODULE.summarize_bucket_grid_energy(
            bucket_import_samples=[(900, 0.25), (1800, 0.5)],
            bucket_export_samples=[(900, 0.1), (1800, 0.2)],
        )

        self.assertAlmostEqual(result["grid_import_daily_energy"], 750.0, places=6)
        self.assertAlmostEqual(result["grid_export_daily_energy"], 300.0, places=6)

    def test_summarize_battery_energy_samples_uses_legacy_60s_mean_buckets(self):
        result = MODULE.summarize_battery_energy_samples(
            [
                (0, -500.0), (10, 250.0), (20, -250.0), (30, 750.0), (40, 0.0), (50, 0.0),
                (60, -200.0), (70, -400.0), (80, 600.0), (90, 0.0), (100, 0.0), (110, 0.0),
            ],
            bucket_seconds=60,
        )

        self.assertAlmostEqual(result["battery_charge_daily_energy"], 5.125, places=6)
        self.assertAlmostEqual(result["battery_discharge_daily_energy"], 6.666666666666667, places=6)

    def test_summarize_bucket_battery_energy_converts_kwh_to_wh(self):
        result = MODULE.summarize_bucket_battery_energy(
            bucket_charge_samples=[(900, 0.25), (1800, 0.5)],
            bucket_discharge_samples=[(900, 0.1), (1800, 0.2)],
        )

        self.assertAlmostEqual(result["battery_charge_daily_energy"], 750.0, places=6)
        self.assertAlmostEqual(result["battery_discharge_daily_energy"], 300.0, places=6)

    def test_mean_of_top_uses_available_values_when_fewer_than_limit(self):
        self.assertAlmostEqual(MODULE.mean_of_top([5.0, 10.0, 7.0], 5), 22.0 / 3.0, places=6)
        self.assertIsNone(MODULE.mean_of_top([], 5))

    def test_build_pv_health_rollups_creates_yearly_and_monthly_series(self):
        result = MODULE.build_pv_health_rollups(
            self.settings,
            {
                "2025": {"values": [10.0, 30.0, 20.0], "timestamp_ms": 1738281600000},
            },
            {
                ("2025", "01"): {"values": [5.0, 15.0, 10.0], "timestamp_ms": 1735689600000},
            },
        )

        self.assertEqual(len(result), 2)
        yearly = next(row for row in result if row["metric"]["__name__"] == "evcc_pv_top30_mean_yearly_wh")
        monthly = next(row for row in result if row["metric"]["__name__"] == "evcc_pv_top5_mean_monthly_wh")
        self.assertEqual(yearly["metric"], {"__name__": "evcc_pv_top30_mean_yearly_wh", "db": "evcc", "local_year": "2025"})
        self.assertEqual(monthly["metric"], {"__name__": "evcc_pv_top5_mean_monthly_wh", "db": "evcc", "local_year": "2025", "local_month": "01"})
        self.assertAlmostEqual(yearly["values"][0], 20.0, places=6)
        self.assertAlmostEqual(monthly["values"][0], 10.0, places=6)


if __name__ == "__main__":
    unittest.main()







