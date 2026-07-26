import importlib.util
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SMA_PATH = ROOT / "scripts" / "helper" / "import-sma-pv-energy.py"

SMA_SPEC = importlib.util.spec_from_file_location("import_sma_pv_energy_helper", SMA_PATH)
SMA_MODULE = importlib.util.module_from_spec(SMA_SPEC)
sys.modules[SMA_SPEC.name] = SMA_MODULE
assert SMA_SPEC.loader is not None
SMA_SPEC.loader.exec_module(SMA_MODULE)


class SmaPvImportTests(unittest.TestCase):
    def test_timestamp_for_day_uses_local_noon_across_dst(self):
        timezone = SMA_MODULE.ZoneInfo("Europe/Berlin")
        self.assertEqual(
            SMA_MODULE.timestamp_for_day(SMA_MODULE.dt.date(2026, 3, 29), timezone),
            1774778400000,
        )
        self.assertEqual(
            SMA_MODULE.timestamp_for_day(SMA_MODULE.dt.date(2026, 10, 25), timezone),
            1792926000000,
        )

    def test_default_metric_is_evcc_compatible_daily_metric(self):
        self.assertEqual(SMA_MODULE.DEFAULT_METRIC, "evcc_pv_energy_by_title_daily_wh")

    def write_temp(self, text):
        handle = tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".csv", delete=False, newline="")
        with handle:
            handle.write(text)
        return pathlib.Path(handle.name)

    def test_long_format_maps_sma_names_to_evcc_titles(self):
        path = self.write_temp(
            "date,sma_name,energy_kwh\n"
            "2026-06-01,SMA Portal Nord,12.5\n"
            "2026-06-01,SMA Portal Sued,7.5\n"
        )
        rows, unmapped = SMA_MODULE.read_sma_energy(
            path,
            {"SMA Portal Nord": "SMA-Nord", "SMA Portal Sued": "SMA-Sued"},
            True,
            "long",
            None,
            None,
            None,
            "auto",
        )
        self.assertEqual(unmapped, set())
        self.assertEqual([row.title for row in rows], ["SMA-Nord", "SMA-Sued"])
        self.assertEqual([row.energy_wh for row in rows], [12500.0, 7500.0])

    def test_mapping_file_accepts_normalized_sma_names(self):
        data_path = self.write_temp("date,sma_name,energy_kwh\n2026-06-01,SMA Portal Nord,12.5\n")
        map_path = self.write_temp("sma_name,evcc_title\nsma_portal_nord,North Roof\n")
        rows, unmapped = SMA_MODULE.read_sma_energy(
            data_path,
            SMA_MODULE.read_mapping(map_path),
            True,
            "long",
            None,
            None,
            None,
            "auto",
        )
        self.assertEqual(unmapped, set())
        self.assertEqual(rows[0].title, "North Roof")

    def test_wide_format_uses_column_names_and_decimal_comma(self):
        path = self.write_temp(
            "date;SMA Portal Nord;SMA Portal Sued\n"
            "01.06.2026;12,5;7,5\n"
        )
        rows, unmapped = SMA_MODULE.read_sma_energy(
            path,
            {"SMA Portal Nord": "SMA-Nord", "SMA Portal Sued": "SMA-Sued"},
            True,
            "wide",
            None,
            None,
            None,
            "auto",
        )
        self.assertEqual(unmapped, set())
        self.assertEqual([(row.day.isoformat(), row.title, row.energy_wh) for row in rows], [
            ("2026-06-01", "SMA-Nord", 12500.0),
            ("2026-06-01", "SMA-Sued", 7500.0),
        ])

    def test_build_series_sums_duplicate_day_source_rows_into_evcc_labels(self):
        rows = [
            SMA_MODULE.SmaEnergyRow(SMA_MODULE.dt.date(2026, 6, 1), "SMA Portal Nord", "SMA-Nord", 1000.0),
            SMA_MODULE.SmaEnergyRow(SMA_MODULE.dt.date(2026, 6, 1), "SMA Portal Nord Replacement", "SMA-Nord", 1500.0),
        ]
        series, summary = SMA_MODULE.build_series(rows, "evcc_pv_energy_by_title_daily_wh", SMA_MODULE.ZoneInfo("Europe/Berlin"), None, None)
        self.assertEqual(summary["samples"], 1)
        metric, labels = next(iter(series.keys()))
        self.assertEqual(metric, "evcc_pv_energy_by_title_daily_wh")
        self.assertEqual(dict(labels), {"local_month": "06", "local_year": "2026", "title": "SMA-Nord"})
        self.assertEqual(summary["titles"][0]["sma_names"], ["SMA Portal Nord", "SMA Portal Nord Replacement"])
        only_samples = next(iter(series.values()))
        self.assertEqual(only_samples[0][1], 2500.0)


    def test_sma_portal_classic_analysis_dir_maps_components_and_skips_aggregate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            portal_file = root / "Analyse_2024_06.csv"
            portal_file.write_text(
                " ;Backnang Home / Gesamtertrag / Mittelwerte [kWh];Carport 4000TL-21 / Gesamtertrag / Mittelwerte [kWh];Süddach 5000TL-20 / Gesamtertrag / Mittelwerte [kWh]\n"
                '"=""01.06.""";"12,94";"2,54";"3,58"\n',
                encoding="utf-8",
            )
            rows, unmapped = SMA_MODULE.read_sma_portal_classic_analysis_dir(
                root,
                {"carport_4000tl-21": "SMA-Carport", "suddach_5000tl-20": "SMA-Sued"},
                True,
                ["^backnang_home$"],
            )
        self.assertEqual(unmapped, set())
        self.assertEqual([(row.day.isoformat(), row.sma_name, row.title, row.energy_wh) for row in rows], [
            ("2024-06-01", "carport_4000tl-21", "SMA-Carport", 2540.0),
            ("2024-06-01", "suddach_5000tl-20", "SMA-Sued", 3580.0),
        ])

    def test_require_mapping_fails_for_unknown_name(self):
        path = self.write_temp("date,sma_name,energy_kwh\n2026-06-01,Unknown SMA,1\n")
        with self.assertRaises(SystemExit):
            SMA_MODULE.read_sma_energy(path, {}, True, "long", None, None, None, "auto")


if __name__ == "__main__":
    unittest.main()
