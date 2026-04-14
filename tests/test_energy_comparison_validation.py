import importlib.util
import pathlib
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

    def test_tibber_influx_csv_reads_decimal_comma_values(self):
        rows = VALIDATE_MODULE.load_tibber_influx_months(FIXTURE_DIR / "tibber-influx.csv", ())

        self.assertEqual(len(rows), 1)
        self.assertAlmostEqual(rows[0].reference_kwh, 1686.32)
        self.assertAlmostEqual(rows[0].candidate_eur, 467.79)
        self.assertAlmostEqual(rows[0].delta_eur, -12.39)

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


if __name__ == "__main__":
    unittest.main()
