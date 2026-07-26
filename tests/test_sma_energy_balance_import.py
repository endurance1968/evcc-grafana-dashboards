import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BALANCE_PATH = ROOT / "scripts" / "helper" / "import-sma-energy-balance.py"
BALANCE_SPEC = importlib.util.spec_from_file_location("import_sma_energy_balance_helper", BALANCE_PATH)
BALANCE_MODULE = importlib.util.module_from_spec(BALANCE_SPEC)
sys.modules[BALANCE_SPEC.name] = BALANCE_MODULE
assert BALANCE_SPEC.loader is not None
BALANCE_SPEC.loader.exec_module(BALANCE_MODULE)


class SmaEnergyBalanceTests(unittest.TestCase):
    def test_timestamp_for_day_uses_local_noon_across_dst(self):
        timezone = BALANCE_MODULE.ZoneInfo("Europe/Berlin")
        self.assertEqual(
            BALANCE_MODULE.timestamp_for_day(BALANCE_MODULE.dt.date(2026, 3, 29), timezone),
            1774778400000,
        )
        self.assertEqual(
            BALANCE_MODULE.timestamp_for_day(BALANCE_MODULE.dt.date(2026, 10, 25), timezone),
            1792926000000,
        )

    def write_month(self, directory: Path, name: str, body: str) -> Path:
        path = directory / name
        path.write_text(body, encoding="utf-8")
        return path

    def test_parse_monthly_energy_balance_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_month(
                Path(tmp),
                "Energiebilanz_2024_06.csv",
                " ;Gesamtverbrauch / Zähleränderung [kWh];Direktverbrauch / Zähleränderung [kWh] ;Batterieentladung / Zähleränderung [kWh] ;Netzbezug / Zähleränderung [kWh] ;PV-Erzeugung / Zähleränderung [kWh] ;Netzeinspeisung / Zähleränderung [kWh] ;Direktverbrauch / Zähleränderung [kWh]  ;Batterieladung / Zähleränderung [kWh]\n"
                '"=""01.06.2024""";"77,83";"12,66";"0,10";"65,06";"12,94";"0,04";"12,66";"0,40"\n',
            )
            rows = BALANCE_MODULE.parse_monthly_file(path)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row.day.isoformat(), "2024-06-01")
        self.assertAlmostEqual(row.home_wh, 77830.0)
        self.assertAlmostEqual(row.direct_consumption_wh, 12660.0)
        self.assertAlmostEqual(row.battery_discharge_wh, 100.0)
        self.assertAlmostEqual(row.grid_import_wh, 65060.0)
        self.assertAlmostEqual(row.pv_wh, 12940.0)
        self.assertAlmostEqual(row.grid_export_wh, 40.0)
        self.assertAlmostEqual(row.battery_charge_wh, 400.0)

    def test_build_series_writes_evcc_compatible_daily_rollups(self):
        rows = [
            BALANCE_MODULE.EnergyBalanceRow(
                day=BALANCE_MODULE.dt.date(2024, 6, 1),
                home_wh=77830.0,
                direct_consumption_wh=12660.0,
                battery_discharge_wh=100.0,
                grid_import_wh=65060.0,
                pv_wh=12940.0,
                grid_export_wh=40.0,
                battery_charge_wh=400.0,
            )
        ]
        series, summary = BALANCE_MODULE.build_series(
            rows,
            BALANCE_MODULE.ZoneInfo("Europe/Berlin"),
            None,
            None,
            "sma_energy_balance",
        )
        labels = {"local_month": "06", "local_year": "2024", "source": "sma_energy_balance"}
        expected_metrics = {
            "evcc_home_energy_daily_wh": 77830.0,
            "evcc_pv_energy_daily_wh": 12940.0,
            "evcc_grid_import_daily_wh": 65060.0,
            "evcc_grid_export_daily_wh": 40.0,
            "evcc_battery_charge_daily_wh": 400.0,
            "evcc_battery_discharge_daily_wh": 100.0,
            "evcc_pv_direct_consumption_daily_wh": 12660.0,
        }
        for metric, value in expected_metrics.items():
            key = (metric, tuple(sorted(labels.items())))
            self.assertIn(key, series)
            self.assertEqual(series[key][0][1], value)
        self.assertEqual(summary["days"], 1)
        self.assertEqual(summary["samples"], 7)
        self.assertEqual(summary["totals_kwh"]["pv_wh"], 12.94)

    def test_read_directory_ignores_yearly_summary_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_month(root, "Energiebilanz_2014_2025.csv", "year;PV-Erzeugung / Zähleränderung [MWh]\n2024;7,1\n")
            self.write_month(
                root,
                "Energiebilanz_2024_06.csv",
                " ;Gesamtverbrauch / Zähleränderung [kWh];Direktverbrauch / Zähleränderung [kWh] ;Batterieentladung / Zähleränderung [kWh] ;Netzbezug / Zähleränderung [kWh] ;PV-Erzeugung / Zähleränderung [kWh] ;Netzeinspeisung / Zähleränderung [kWh] ;Direktverbrauch / Zähleränderung [kWh]  ;Batterieladung / Zähleränderung [kWh]\n"
                '"=""01.06.2024""";"1";"2";"3";"4";"5";"6";"2";"7"\n',
            )
            rows = BALANCE_MODULE.read_energy_balance_dir(root)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].day.isoformat(), "2024-06-01")


if __name__ == "__main__":
    unittest.main()


