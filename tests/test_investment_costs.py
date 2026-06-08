import contextlib
import importlib.util
import io
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
INVESTMENT_PATH = ROOT / "scripts" / "helper" / "import-investment-costs.py"

INVESTMENT_SPEC = importlib.util.spec_from_file_location("import_investment_costs_helper", INVESTMENT_PATH)
INVESTMENT_MODULE = importlib.util.module_from_spec(INVESTMENT_SPEC)
sys.modules[INVESTMENT_SPEC.name] = INVESTMENT_MODULE
assert INVESTMENT_SPEC.loader is not None
INVESTMENT_SPEC.loader.exec_module(INVESTMENT_MODULE)


class InvestmentCostImportTests(unittest.TestCase):
    def test_parse_float_accepts_fraction_allocation(self):
        self.assertAlmostEqual(
            INVESTMENT_MODULE.parse_float("1/3", "allocation_percent", "shared row"),
            1.0 / 3.0,
        )

    def test_pv_shared_requires_allocation_percent(self):
        row = {
            "asset_id": "shared_inverter",
            "asset_type": "pv_shared",
            "evcc_title": "South Roof",
            "commissioning_date": "2026-01-01",
            "purchase_price_eur": "1200",
            "lifetime_years": "20",
            "yearly_opex_eur": "0",
            "include_in_effective_price": "yes",
        }
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            normalized = INVESTMENT_MODULE.normalize_row(row, 2)
        self.assertFalse(normalized["include"])
        self.assertIn("misses allocation_percent", buffer.getvalue())

    def test_daily_cost_applies_shared_allocation(self):
        asset = {
            "commissioning_date": INVESTMENT_MODULE.dt.date(2026, 1, 1),
            "purchase_price_eur": 365.25,
            "lifetime_years": 1.0,
            "yearly_opex_eur": 0.0,
            "allocation_percent": 1.0 / 3.0,
        }
        self.assertAlmostEqual(
            INVESTMENT_MODULE.daily_cost(asset, INVESTMENT_MODULE.dt.date(2026, 6, 1)),
            1.0 / 3.0,
        )

    def test_build_rollups_can_use_preimported_daily_energy_metric(self):
        assets = [{
            "asset_id": "pv_nord",
            "asset_type": "pv",
            "include": True,
            "evcc_title": "SMA-Nord",
            "commissioning_date": INVESTMENT_MODULE.dt.date(2026, 1, 1),
            "purchase_price_eur": 365.25,
            "lifetime_years": 1.0,
            "yearly_opex_eur": 0.0,
            "allocation_percent": 1.0,
        }]
        original = INVESTMENT_MODULE.fetch_daily_energy_from_daily_metric
        calls = {}
        try:
            def fake_fetch(_base_url, asset, start_day, end_day, _tz, metric):
                calls["title"] = asset["evcc_title"]
                calls["metric"] = metric
                return {start_day: 1000.0}
            INVESTMENT_MODULE.fetch_daily_energy_from_daily_metric = fake_fetch
            series, summary = INVESTMENT_MODULE.build_rollups(
                "http://vm.invalid",
                assets,
                INVESTMENT_MODULE.dt.date(2026, 1, 1),
                INVESTMENT_MODULE.dt.date(2026, 1, 2),
                INVESTMENT_MODULE.ZoneInfo("Europe/Berlin"),
                30000.0,
                "30s",
                energy_source="daily-metric",
            )
        finally:
            INVESTMENT_MODULE.fetch_daily_energy_from_daily_metric = original
        self.assertEqual(calls, {"title": "SMA-Nord", "metric": "evcc_pv_energy_by_title_daily_wh"})
        self.assertEqual(summary["pv_sources"][0]["energy_kwh"], 1.0)
        self.assertTrue(any(key[0] == "evcc_pv_lcoe_daily_ct_per_kwh" for key in series))
        self.assertTrue(any(key[0] == "evcc_pv_lcoe_energy_monthly_wh" for key in series))
        self.assertFalse(any(key[0] == "evcc_pv_energy_by_title_daily_wh" for key in series))
        self.assertFalse(any(key[0] == "evcc_pv_energy_by_title_monthly_wh" for key in series))


    def test_optional_sma_energy_rollup_writes_standard_pv_metric(self):
        assets = [{
            "asset_id": "pv_nord",
            "asset_type": "pv",
            "include": True,
            "evcc_title": "SMA-Nord",
            "commissioning_date": INVESTMENT_MODULE.dt.date(2026, 1, 1),
            "purchase_price_eur": 365.25,
            "lifetime_years": 1.0,
            "yearly_opex_eur": 0.0,
            "allocation_percent": 1.0,
        }]
        original = INVESTMENT_MODULE.fetch_daily_energy_from_daily_metric
        try:
            def fake_fetch(_base_url, _asset, start_day, _end_day, _tz, _metric):
                return {
                    start_day: 1000.0,
                    start_day + INVESTMENT_MODULE.dt.timedelta(days=1): 2000.0,
                }
            INVESTMENT_MODULE.fetch_daily_energy_from_daily_metric = fake_fetch
            series, summary = INVESTMENT_MODULE.build_rollups(
                "http://vm.invalid",
                assets,
                INVESTMENT_MODULE.dt.date(2026, 1, 1),
                INVESTMENT_MODULE.dt.date(2026, 1, 3),
                INVESTMENT_MODULE.ZoneInfo("Europe/Berlin"),
                30000.0,
                "30s",
                energy_source="daily-metric",
                pv_energy_metric="evcc_pv_energy_by_title_daily_wh",
                write_pv_energy_rollup=True,
            )
        finally:
            INVESTMENT_MODULE.fetch_daily_energy_from_daily_metric = original

        rollup_keys = [dict(label_items) for metric, label_items in series if metric == "evcc_pv_energy_daily_wh"]
        self.assertEqual(rollup_keys, [{"local_month": "01", "local_year": "2026", "source": "sma"}])
        key = ("evcc_pv_energy_daily_wh", tuple(sorted(rollup_keys[0].items())))
        self.assertEqual([value for _timestamp, value in series[key]], [1000.0, 2000.0])
        self.assertTrue(summary["write_pv_energy_rollup"])

    def test_rolling_lcoe_metric_has_one_series_per_title_and_year(self):
        assets = [{
            "asset_id": "pv_nord",
            "asset_type": "pv",
            "include": True,
            "evcc_title": "SMA-Nord",
            "commissioning_date": INVESTMENT_MODULE.dt.date(2026, 1, 1),
            "purchase_price_eur": 365.25,
            "lifetime_years": 1.0,
            "yearly_opex_eur": 0.0,
            "allocation_percent": 1.0,
        }]
        original = INVESTMENT_MODULE.fetch_daily_energy_from_daily_metric
        try:
            def fake_fetch(_base_url, _asset, start_day, end_day, _tz, _metric):
                values = {}
                day = start_day
                while day < end_day:
                    values[day] = 2000.0
                    day += INVESTMENT_MODULE.dt.timedelta(days=1)
                return values
            INVESTMENT_MODULE.fetch_daily_energy_from_daily_metric = fake_fetch
            series, _summary = INVESTMENT_MODULE.build_rollups(
                "http://vm.invalid",
                assets,
                INVESTMENT_MODULE.dt.date(2026, 1, 1),
                INVESTMENT_MODULE.dt.date(2026, 1, 10),
                INVESTMENT_MODULE.ZoneInfo("Europe/Berlin"),
                30000.0,
                "30s",
                energy_source="daily-metric",
            )
        finally:
            INVESTMENT_MODULE.fetch_daily_energy_from_daily_metric = original
        rolling_keys = [dict(label_items) for metric, label_items in series if metric == "evcc_pv_lcoe_rolling_7d_ct_per_kwh"]
        self.assertEqual(rolling_keys, [{"local_year": "2026", "title": "SMA-Nord"}])

    def test_shared_allocation_ok_and_warning(self):
        ok_assets = [
            {"asset_id": "shared", "asset_type": "pv_shared", "include": True, "evcc_title": "A", "allocation_percent": 2.0 / 3.0},
            {"asset_id": "shared", "asset_type": "pv_shared", "include": True, "evcc_title": "B", "allocation_percent": 1.0 / 3.0},
        ]
        ok_buffer = io.StringIO()
        with contextlib.redirect_stdout(ok_buffer):
            ok_summary = INVESTMENT_MODULE.validate_shared_allocations(ok_assets)
        self.assertEqual(ok_summary[0]["status"], "ok")
        self.assertIn("Shared asset allocation OK", ok_buffer.getvalue())

        bad_assets = [
            {"asset_id": "shared", "asset_type": "pv_shared", "include": True, "evcc_title": "A", "allocation_percent": 0.5},
            {"asset_id": "shared", "asset_type": "pv_shared", "include": True, "evcc_title": "B", "allocation_percent": 0.25},
        ]
        bad_buffer = io.StringIO()
        with contextlib.redirect_stdout(bad_buffer):
            bad_summary = INVESTMENT_MODULE.validate_shared_allocations(bad_assets)
        self.assertEqual(bad_summary[0]["status"], "warning")
        self.assertIn("WARNING shared asset allocation does not sum to 100%", bad_buffer.getvalue())



    def test_merge_daily_energy_prefers_evcc_by_default(self):
        day1 = INVESTMENT_MODULE.dt.date(2026, 1, 1)
        day2 = INVESTMENT_MODULE.dt.date(2026, 1, 2)
        day3 = INVESTMENT_MODULE.dt.date(2026, 1, 3)
        merged, stats = INVESTMENT_MODULE.merge_daily_energy(
            {day1: 1000.0, day2: 2000.0},
            {day2: 9999.0, day3: 3000.0},
            "prefer-evcc",
        )
        self.assertEqual(merged, {day1: 1000.0, day2: 2000.0, day3: 3000.0})
        self.assertEqual(stats, {"evcc_days": 2, "metric_days": 2, "overlap_days": 1, "merged_days": 3})

    def test_merge_daily_energy_can_fail_on_overlap(self):
        day = INVESTMENT_MODULE.dt.date(2026, 1, 1)
        with self.assertRaises(RuntimeError):
            INVESTMENT_MODULE.merge_daily_energy({day: 1000.0}, {day: 2000.0}, "error")

    def test_build_rollups_combines_evcc_and_sma_energy_without_double_counting(self):
        assets = [{
            "asset_id": "pv_nord",
            "asset_type": "pv",
            "include": True,
            "evcc_title": "SMA-Nord",
            "commissioning_date": INVESTMENT_MODULE.dt.date(2026, 1, 1),
            "purchase_price_eur": 365.25,
            "lifetime_years": 1.0,
            "yearly_opex_eur": 0.0,
            "allocation_percent": 1.0,
        }]
        original_evcc = INVESTMENT_MODULE.fetch_daily_energy
        original_metric = INVESTMENT_MODULE.fetch_daily_energy_from_daily_metric
        try:
            def fake_evcc(_base_url, _asset, start_day, _end_day, _tz, _peak_limit, _sample_interval):
                return {start_day + INVESTMENT_MODULE.dt.timedelta(days=1): 2000.0}
            def fake_metric(_base_url, _asset, start_day, _end_day, _tz, _metric):
                return {
                    start_day: 1000.0,
                    start_day + INVESTMENT_MODULE.dt.timedelta(days=1): 9999.0,
                    start_day + INVESTMENT_MODULE.dt.timedelta(days=2): 3000.0,
                }
            INVESTMENT_MODULE.fetch_daily_energy = fake_evcc
            INVESTMENT_MODULE.fetch_daily_energy_from_daily_metric = fake_metric
            series, summary = INVESTMENT_MODULE.build_rollups(
                "http://vm.invalid",
                assets,
                INVESTMENT_MODULE.dt.date(2026, 1, 1),
                INVESTMENT_MODULE.dt.date(2026, 1, 4),
                INVESTMENT_MODULE.ZoneInfo("Europe/Berlin"),
                30000.0,
                "30s",
                energy_source="combined",
                pv_energy_metric="evcc_pv_energy_by_title_daily_wh",
                write_pv_energy_rollup=True,
            )
        finally:
            INVESTMENT_MODULE.fetch_daily_energy = original_evcc
            INVESTMENT_MODULE.fetch_daily_energy_from_daily_metric = original_metric

        self.assertEqual(summary["pv_sources"][0]["energy_kwh"], 6.0)
        self.assertEqual(summary["pv_sources"][0]["energy_merge"], {
            "evcc_days": 1,
            "metric_days": 3,
            "overlap_days": 1,
            "merged_days": 3,
        })
        rollup_keys = [dict(label_items) for metric, label_items in series if metric == "evcc_pv_energy_daily_wh"]
        self.assertEqual(rollup_keys, [{"local_month": "01", "local_year": "2026", "source": "combined"}])
        key = ("evcc_pv_energy_daily_wh", tuple(sorted(rollup_keys[0].items())))
        self.assertEqual([value for _timestamp, value in series[key]], [1000.0, 2000.0, 3000.0])


    def test_skip_titles_without_energy_ignores_zero_only_sources(self):
        assets = [{
            "asset_id": "pv_zero",
            "asset_type": "pv",
            "include": True,
            "evcc_title": "Zero PV",
            "commissioning_date": INVESTMENT_MODULE.dt.date(2026, 1, 1),
            "purchase_price_eur": 365.25,
            "lifetime_years": 1.0,
            "yearly_opex_eur": 0.0,
            "allocation_percent": 1.0,
        }]
        original = INVESTMENT_MODULE.fetch_daily_energy_from_daily_metric
        try:
            def fake_metric(_base_url, _asset, start_day, _end_day, _tz, _metric):
                return {start_day: 0.0}
            INVESTMENT_MODULE.fetch_daily_energy_from_daily_metric = fake_metric
            _series, summary = INVESTMENT_MODULE.build_rollups(
                "http://vm.invalid",
                assets,
                INVESTMENT_MODULE.dt.date(2026, 1, 1),
                INVESTMENT_MODULE.dt.date(2026, 1, 2),
                INVESTMENT_MODULE.ZoneInfo("Europe/Berlin"),
                30000.0,
                "30s",
                energy_source="daily-metric",
                skip_titles_without_energy=True,
            )
        finally:
            INVESTMENT_MODULE.fetch_daily_energy_from_daily_metric = original
        self.assertEqual(summary["pv_sources"], [])
        self.assertEqual(summary["assets"], [])

    def test_partial_title_coverage_prorates_lcoe_costs_and_marks_partial(self):
        assets = [{
            "asset_id": "pv_partial",
            "asset_type": "pv",
            "include": True,
            "evcc_title": "Partial PV",
            "commissioning_date": INVESTMENT_MODULE.dt.date(2026, 1, 1),
            "purchase_price_eur": 365.25,
            "lifetime_years": 1.0,
            "yearly_opex_eur": 0.0,
            "allocation_percent": 1.0,
        }]
        original = INVESTMENT_MODULE.fetch_daily_energy_from_daily_metric
        try:
            def fake_fetch(_base_url, _asset, start_day, _end_day, _tz, _metric):
                return {
                    start_day: 1000.0,
                    start_day + INVESTMENT_MODULE.dt.timedelta(days=1): 1000.0,
                }
            INVESTMENT_MODULE.fetch_daily_energy_from_daily_metric = fake_fetch
            series, summary = INVESTMENT_MODULE.build_rollups(
                "http://vm.invalid",
                assets,
                INVESTMENT_MODULE.dt.date(2026, 1, 1),
                INVESTMENT_MODULE.dt.date(2026, 1, 11),
                INVESTMENT_MODULE.ZoneInfo("Europe/Berlin"),
                30000.0,
                "30s",
                energy_source="daily-metric",
            )
        finally:
            INVESTMENT_MODULE.fetch_daily_energy_from_daily_metric = original

        yearly_key = (
            "evcc_pv_lcoe_yearly_ct_per_kwh",
            tuple(sorted({"coverage": "1%", "local_year": "2026", "title": "Partial PV"}.items())),
        )
        self.assertIn(yearly_key, series)
        self.assertAlmostEqual(series[yearly_key][0][1], 100.0)

        monthly_cost_key = (
            "evcc_pv_lcoe_cost_monthly_eur",
            tuple(sorted({
                "local_year": "2026",
                "title": "Partial PV",
            }.items())),
        )
        self.assertIn(monthly_cost_key, series)
        self.assertAlmostEqual(series[monthly_cost_key][0][1], 2.0)

        self.assertFalse(any(key[0] == "evcc_pv_lcoe_coverage_ratio" for key in series))
        self.assertFalse(any(key[0] == "evcc_pv_lcoe_partial" for key in series))
        self.assertAlmostEqual(summary["pv_sources"][0]["coverage_ratio"], 2 / 365)
        self.assertEqual(summary["pv_sources"][0]["partial"], True)
        self.assertEqual(summary["pv_sources"][0]["covered_days"], 2)
        self.assertEqual(summary["pv_sources"][0]["expected_days"], 365)
        self.assertAlmostEqual(summary["pv_sources"][0]["covered_cost_eur"], 2.0)
        self.assertAlmostEqual(summary["pv_sources"][0]["active_cost_eur"], 10.0)

    def test_min_lcoe_coverage_ratio_can_suppress_partial_lcoe_values(self):
        assets = [{
            "asset_id": "pv_partial",
            "asset_type": "pv",
            "include": True,
            "evcc_title": "Partial PV",
            "commissioning_date": INVESTMENT_MODULE.dt.date(2026, 1, 1),
            "purchase_price_eur": 365.25,
            "lifetime_years": 1.0,
            "yearly_opex_eur": 0.0,
            "allocation_percent": 1.0,
        }]
        original = INVESTMENT_MODULE.fetch_daily_energy_from_daily_metric
        try:
            def fake_fetch(_base_url, _asset, start_day, _end_day, _tz, _metric):
                return {start_day: 2000.0}
            INVESTMENT_MODULE.fetch_daily_energy_from_daily_metric = fake_fetch
            series, summary = INVESTMENT_MODULE.build_rollups(
                "http://vm.invalid",
                assets,
                INVESTMENT_MODULE.dt.date(2026, 1, 1),
                INVESTMENT_MODULE.dt.date(2026, 1, 11),
                INVESTMENT_MODULE.ZoneInfo("Europe/Berlin"),
                30000.0,
                "30s",
                energy_source="daily-metric",
                min_lcoe_coverage_ratio=0.5,
            )
        finally:
            INVESTMENT_MODULE.fetch_daily_energy_from_daily_metric = original

        yearly_keys = [key for key in series if key[0] == "evcc_pv_lcoe_yearly_ct_per_kwh"]
        self.assertEqual(yearly_keys, [])
        self.assertEqual(summary["pv_sources"][0]["lcoe_ct_per_kwh"], None)

if __name__ == "__main__":
    unittest.main()
