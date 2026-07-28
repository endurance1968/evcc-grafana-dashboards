import importlib.util
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "helper" / "validate-vrm-import.py"
SPEC = importlib.util.spec_from_file_location("validate_vrm_import", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class VrmImportValidationTests(unittest.TestCase):
    def test_expected_combined_flows_and_efficiency(self):
        rows = [
            {
                "day": "2026-06-01",
                "pv_to_battery_kwh": 4.0,
                "grid_to_battery_kwh": 1.0,
                "battery_to_consumers_kwh": 3.0,
                "battery_to_grid_kwh": 1.0,
            }
        ]

        self.assertEqual(MODULE.expected_wh(rows[0], "battery_charge_kwh"), 5000.0)
        self.assertEqual(MODULE.expected_wh(rows[0], "battery_discharge_kwh"), 4000.0)
        self.assertAlmostEqual(MODULE.efficiency_pct(rows), 80.0)

    def test_validate_rejects_duplicate_or_different_vm_values(self):
        original_fetch = MODULE.fetch_metric_days
        try:
            MODULE.fetch_metric_days = lambda *args, **kwargs: ({"2026-06-01": 999.0}, ["2026-06-01"])
            result = MODULE.validate(
                "http://127.0.0.1:8428",
                "site",
                [
                    {
                        "day": "2026-06-01",
                        "pv_to_battery_kwh": 1.0,
                        "grid_to_battery_kwh": 0.0,
                        "battery_to_consumers_kwh": 0.8,
                        "battery_to_grid_kwh": 0.0,
                    }
                ],
                "vrm",
                "Europe/Berlin",
                0.1,
            )
        finally:
            MODULE.fetch_metric_days = original_fetch

        self.assertEqual(result["overall"], "CHECK")
        self.assertTrue(all(item["status"] == "CHECK" for item in result["metrics"]))


if __name__ == "__main__":
    unittest.main()