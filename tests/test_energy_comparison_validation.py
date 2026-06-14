import importlib.util
import os
import pathlib
import tempfile
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
VALIDATE_PATH = ROOT / "scripts" / "helper" / "validate_energy_comparison.py"

VALIDATE_SPEC = importlib.util.spec_from_file_location("validate_energy_comparison_helper", VALIDATE_PATH)
VALIDATE_MODULE = importlib.util.module_from_spec(VALIDATE_SPEC)
sys.modules[VALIDATE_SPEC.name] = VALIDATE_MODULE
assert VALIDATE_SPEC.loader is not None
VALIDATE_SPEC.loader.exec_module(VALIDATE_MODULE)
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "energy-comparison"


class EnergyComparisonValidationTests(unittest.TestCase):
    def test_parse_number_accepts_german_decimal_snapshot_values(self):
        self.assertEqual(VALIDATE_MODULE.parse_number("1.234,56"), 1234.56)
        self.assertEqual(VALIDATE_MODULE.parse_number("77,37"), 77.37)
        self.assertIsNone(VALIDATE_MODULE.parse_number(""))

    def test_tibber_vm_json_excludes_documented_months_and_totals_remaining_rows(self):
        rows = VALIDATE_MODULE.load_tibber_vm_months(FIXTURE_DIR / "tibber-vm.json", ("2025-10",))
        total = VALIDATE_MODULE.totals_for_cost_rows(rows)

        self.assertEqual([row.period for row in rows], ["2025-09"])
        self.assertEqual(total.reference_kwh, 100.0)
        self.assertEqual(total.candidate_kwh, 101.0)
        self.assertEqual(total.delta_kwh, 1.0)

    def test_default_exclusions_include_documented_april_and_october_anomalies(self):
        self.assertIn("2025-04", VALIDATE_MODULE.DEFAULT_EXCLUDED_MONTHS)
        self.assertIn("2025-10", VALIDATE_MODULE.DEFAULT_EXCLUDED_MONTHS)
        self.assertIn("transition anomaly", VALIDATE_MODULE.EXCLUDED_MONTH_RATIONALE["2025-04"])
        self.assertIn("billing/import anomaly", VALIDATE_MODULE.EXCLUDED_MONTH_RATIONALE["2025-10"])

    def test_required_cache_turns_missing_optional_cache_into_check(self):
        result = VALIDATE_MODULE.required_status(
            "Tibber vs VM",
            "SKIP",
            "no local cache",
            "tibber-vm",
            ("tibber-vm",),
        )

        self.assertEqual(result.status, "CHECK")
        self.assertIn("--require-cache tibber-vm", result.details)

    def test_tibber_influx_csv_reads_decimal_comma_values(self):
        rows = VALIDATE_MODULE.load_tibber_influx_months(FIXTURE_DIR / "tibber-influx.csv", ())

        self.assertEqual(len(rows), 1)
        self.assertAlmostEqual(rows[0].reference_kwh, 1686.32)
        self.assertAlmostEqual(rows[0].candidate_eur, 467.79)
        self.assertAlmostEqual(rows[0].delta_eur, -12.39)

    def test_default_tibber_influx_csv_ignores_current_evcc_agg_snapshots(self):
        original_dir = VALIDATE_MODULE.DEFAULT_TIBBER_DIR
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = pathlib.Path(tmpdir)
            baseline = tmp / "tibber-influx-cost-monthly-only-2025-04_2026-03-without-2025-10.csv"
            current = tmp / "tibber-influx-cost-monthly-only-2026-04_2026-05-current-evcc-agg.csv"
            baseline.write_text("month,tibber_kwh,influx_kwh,tibber_eur,influx_eur\n", encoding="utf-8")
            current.write_text("month,tibber_kwh,influx_kwh,tibber_eur,influx_eur\n", encoding="utf-8")
            os.utime(baseline, (1000, 1000))
            os.utime(current, (2000, 2000))

            VALIDATE_MODULE.DEFAULT_TIBBER_DIR = tmp
            try:
                self.assertEqual(VALIDATE_MODULE.default_tibber_influx_csv(), baseline)
            finally:
                VALIDATE_MODULE.DEFAULT_TIBBER_DIR = original_dir

    def test_cost_evaluation_flags_out_of_tolerance_rows(self):
        rows = [
            VALIDATE_MODULE.MonthlyCostRow(
                period="2026-01",
                reference_kwh=100.0,
                candidate_kwh=120.0,
                delta_kwh=20.0,
                reference_eur=30.0,
                candidate_eur=30.0,
                delta_eur=0.0,
            )
        ]

        result = VALIDATE_MODULE.evaluate_cost_rows(
            "test",
            rows,
            monthly_kwh_pct_tolerance=2.0,
            monthly_eur_pct_tolerance=12.0,
            total_kwh_pct_tolerance=1.0,
            total_eur_pct_tolerance=5.0,
        )

        self.assertEqual(result.status, "CHECK")
        self.assertIn("total_kwh_delta=20.00%", result.details)

    def test_vrm_monthly_aggregation_uses_total_pv_and_grid_import(self):
        rows = [
            {"day": "2026-01-01", "pv_total_kwh": 5.0, "grid_import_total_kwh": 2.0},
            {"day": "2026-01-02", "pv_total_kwh": 6.0, "grid_import_total_kwh": 3.0},
            {"day": "2026-02-01", "pv_total_kwh": 7.0, "grid_import_total_kwh": 4.0},
        ]

        months = VALIDATE_MODULE.aggregate_vrm_months(rows)

        self.assertEqual(months["2026-01"]["pv"], 11.0)
        self.assertEqual(months["2026-01"]["grid"], 5.0)
        self.assertEqual(months["2026-02"]["pv"], 7.0)

    def test_vrm_battery_efficiency_uses_charge_and_discharge_flows(self):
        rows = [
            {
                "day": "2026-01-01",
                "pv_to_battery_kwh": 4.0,
                "grid_to_battery_kwh": 1.0,
                "battery_to_consumers_kwh": 3.0,
                "battery_to_grid_kwh": 1.0,
            },
            {
                "day": "2026-01-02",
                "pv_to_battery_kwh": 5.0,
                "grid_to_battery_kwh": 0.0,
                "battery_to_consumers_kwh": 4.0,
                "battery_to_grid_kwh": 1.0,
            },
        ]

        monthly = VALIDATE_MODULE.build_vrm_battery_rows(rows)
        total = VALIDATE_MODULE.totals_for_battery_rows(monthly)
        result = VALIDATE_MODULE.evaluate_vrm_battery_rows(monthly, min_charge_kwh=1.0)

        self.assertEqual(len(monthly), 1)
        self.assertEqual(monthly[0].period, "2026-01")
        self.assertAlmostEqual(monthly[0].vrm_charge_kwh, 10.0)
        self.assertAlmostEqual(monthly[0].vrm_discharge_kwh, 9.0)
        self.assertAlmostEqual(monthly[0].vrm_efficiency_pct, 90.0)
        self.assertAlmostEqual(total.vrm_efficiency_pct, 90.0)
        self.assertEqual(result.status, "OK")

    def test_vrm_vm_battery_efficiency_reports_percentage_point_delta(self):
        rows = [
            VALIDATE_MODULE.BatteryEfficiencyRow(
                period="2026-01",
                vrm_charge_kwh=10.0,
                vrm_discharge_kwh=9.0,
                vrm_efficiency_pct=90.0,
                vm_charge_kwh=10.0,
                vm_discharge_kwh=8.5,
                vm_efficiency_pct=85.0,
                delta_efficiency_pct_points=-5.0,
            )
        ]

        result = VALIDATE_MODULE.evaluate_vrm_vm_battery_rows(rows, min_charge_kwh=1.0, pct_point_tolerance=6.0)

        self.assertEqual(result.status, "OK")
        self.assertIn("total_efficiency_delta=5.00 pp", result.details)


if __name__ == "__main__":
    unittest.main()
