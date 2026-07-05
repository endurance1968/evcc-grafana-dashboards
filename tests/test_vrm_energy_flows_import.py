import datetime as dt
import importlib.util
import unittest
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "helper" / "import-vrm-energy-flows.py"

spec = importlib.util.spec_from_file_location("import_vrm_energy_flows", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


def epoch_seconds(day: str) -> int:
    timezone = ZoneInfo("Europe/Berlin")
    return int(
        dt.datetime.combine(
            dt.date.fromisoformat(day), dt.time(hour=12), tzinfo=timezone
        ).timestamp()
    )


class VrmEnergyFlowImportTests(unittest.TestCase):
    def test_normalize_api_records_uses_vrm_timestamps_for_sparse_daily_arrays(self):
        rows = module.normalize_api_records(
            {
                "Pb": [[epoch_seconds("2026-01-02"), 1.5]],
                "Gb": [[epoch_seconds("2026-01-02"), 0.5]],
                "Bc": [[epoch_seconds("2026-01-03"), 1.25]],
                "Bg": [],
            },
            dt.date(2026, 1, 1),
            dt.date(2026, 1, 3),
            "Europe/Berlin",
        )

        self.assertEqual(
            [row["day"] for row in rows],
            ["2026-01-02", "2026-01-03"],
        )
        self.assertEqual(rows[0]["pv_to_battery_kwh"], 1.5)
        self.assertEqual(rows[0]["grid_to_battery_kwh"], 0.5)
        self.assertEqual(rows[0]["battery_charge_kwh"], 2.0)
        self.assertEqual(rows[1]["battery_to_consumers_kwh"], 1.25)
        self.assertEqual(rows[1]["battery_discharge_kwh"], 1.25)

    def test_normalize_api_records_converts_cumulative_vrm_counters_to_daily_deltas(self):
        rows = module.normalize_api_records(
            {
                "Pb": [
                    [epoch_seconds("2026-01-01"), 1000.0],
                    [epoch_seconds("2026-01-02"), 1010.0],
                    [epoch_seconds("2026-01-03"), 1024.0],
                    [epoch_seconds("2026-01-04"), 1040.0],
                ],
                "Gb": [],
                "Bc": [
                    [epoch_seconds("2026-01-01"), 2000.0],
                    [epoch_seconds("2026-01-02"), 2008.0],
                    [epoch_seconds("2026-01-03"), 2017.0],
                    [epoch_seconds("2026-01-04"), 2030.0],
                ],
                "Bg": [],
            },
            dt.date(2026, 1, 1),
            dt.date(2026, 1, 4),
            "Europe/Berlin",
        )

        self.assertEqual(rows[0]["pv_to_battery_kwh"], 0.0)
        self.assertEqual(rows[1]["pv_to_battery_kwh"], 10.0)
        self.assertEqual(rows[2]["pv_to_battery_kwh"], 14.0)
        self.assertEqual(rows[3]["pv_to_battery_kwh"], 16.0)
        self.assertEqual(rows[1]["battery_to_consumers_kwh"], 8.0)
        self.assertEqual(rows[2]["battery_to_consumers_kwh"], 9.0)
        self.assertEqual(rows[3]["battery_to_consumers_kwh"], 13.0)
        self.assertEqual(rows[3]["battery_charge_kwh"], 16.0)
        self.assertEqual(rows[3]["battery_discharge_kwh"], 13.0)

    def test_normalize_api_records_keeps_index_fallback_for_fixture_rows(self):
        rows = module.normalize_api_records(
            {"Pb": [[0, 1.0], [0, 2.0]], "Gb": [], "Bc": [], "Bg": []},
            dt.date(2026, 1, 1),
            dt.date(2026, 1, 2),
        )

        self.assertEqual(rows[0]["pv_to_battery_kwh"], 1.0)
        self.assertEqual(rows[1]["pv_to_battery_kwh"], 2.0)


    def test_normalize_api_records_keeps_explicit_zero_samples(self):
        rows = module.normalize_api_records(
            {
                "Pb": [[epoch_seconds("2026-01-02"), 0.0]],
                "Gb": [],
                "Bc": [],
                "Bg": [],
            },
            dt.date(2026, 1, 1),
            dt.date(2026, 1, 3),
            "Europe/Berlin",
        )

        self.assertEqual([row["day"] for row in rows], ["2026-01-02"])
        self.assertEqual(rows[0]["battery_charge_kwh"], 0.0)

    def test_chunk_date_ranges_splits_inclusive_ranges(self):
        chunks = list(module.chunk_date_ranges(dt.date(2026, 1, 1), dt.date(2026, 1, 5), 2))

        self.assertEqual(
            chunks,
            [
                (dt.date(2026, 1, 1), dt.date(2026, 1, 2)),
                (dt.date(2026, 1, 3), dt.date(2026, 1, 4)),
                (dt.date(2026, 1, 5), dt.date(2026, 1, 5)),
            ],
        )

if __name__ == "__main__":
    unittest.main()
