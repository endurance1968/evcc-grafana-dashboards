import importlib.util
import csv
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "helper" / "collect-evcc-grid-control-audit.py"

SPEC = importlib.util.spec_from_file_location("grid_control_audit", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class GridControlAuditTests(unittest.TestCase):
    def test_build_state_metrics_detects_consumption_limit_and_grid_split(self):
        state = {
            "site": {"gridPower": 3500, "homePower": 2800},
            "hems": {"status": {"dimmed": True, "maxConsumptionPower": 4200, "maxProductionPower": 0}},
            "loadpoints": [{"title": "Garage", "chargePower": 1800, "enabled": True}],
        }
        metrics = MODULE.build_state_metrics(state, "home")
        text = "\n".join(metrics)

        self.assertIn('evcc_audit_site_grid_import_power_w{site="home"} 3500.0', text)
        self.assertIn('evcc_audit_site_grid_export_power_w{site="home"} 0.0', text)
        self.assertIn('evcc_audit_hems_effective_max_consumption_power_w{site="home"} 4200.0', text)
        self.assertIn('evcc_audit_vnb_signal_active{site="home"} 1', text)
        self.assertIn('evcc_audit_loadpoint_charge_power_w{loadpoint="1",name="Garage",site="home"} 1800.0', text)

    def test_build_state_metrics_detects_feed_in_limit_and_export_split(self):
        state = {
            "site": {"gridPower": -1200},
            "hems": {"status": {"curtailed": True, "maxProductionPower": -800}},
        }
        metrics = MODULE.build_state_metrics(state, "home")
        text = "\n".join(metrics)

        self.assertIn('evcc_audit_site_grid_import_power_w{site="home"} 0.0', text)
        self.assertIn('evcc_audit_site_grid_export_power_w{site="home"} 1200.0', text)
        self.assertIn('evcc_audit_hems_effective_max_production_power_w{site="home"} 800.0', text)

    def test_control_group_and_minimum_power_metrics(self):
        groups = MODULE.parse_control_groups("wallboxes|Loadpoints|loadpoints|Garage+Carport;wp1|Heat pump|heat_pump|Heat pump;battery|Battery|battery_grid_charge|")
        state = {
            "site": {"gridPower": 1000, "batteryGridChargeActive": True},
            "battery": {"power": -900},
            "loadpoints": [{"title": "Garage", "chargePower": 1500}, {"title": "Carport", "chargePower": 2500}, {"title": "Heat pump", "chargePower": 900}],
        }
        metrics = MODULE.build_state_metrics(state, "home", groups, control_unit_count=None)
        text = "\n".join(metrics)

        self.assertIn('evcc_audit_control_group_power_w{group="wallboxes",kind="loadpoints",name="Loadpoints",site="home"} 4000.0', text)
        self.assertIn('evcc_audit_control_group_power_w{group="wp1",kind="heat_pump",name="Heat pump",site="home"} 900.0', text)
        self.assertIn('evcc_audit_control_group_power_w{group="battery",kind="battery_grid_charge",name="Battery",site="home"} 900.0', text)
        self.assertIn('evcc_audit_minimum_allowed_power_w{site="home"} 7560.0', text)

    def test_control_group_legacy_loadpoints_alias_still_works(self):
        groups = MODULE.parse_control_groups("lp|Loadpoints|loadpoints|1+2")
        state = {"loadpoints": [{"title": "A", "chargePower": 1000}, {"title": "B", "chargePower": 2000}]}
        metrics = MODULE.build_state_metrics(state, "home", groups)
        text = "\n".join(metrics)

        self.assertIn('evcc_audit_control_group_power_w{group="lp",kind="loadpoints",name="Loadpoints",site="home"} 3000.0', text)

    def test_gridsession_event_metric_contains_table_labels(self):
        sessions = [
            {
                "created": "2026-06-20T08:00:00Z",
                "finished": "2026-06-20T08:15:00Z",
                "type": "limit",
                "limit": 4200,
                "grid": 3900,
            }
        ]
        events = MODULE.normalize_sessions(sessions, "home")
        metrics = MODULE.build_event_metrics(events, "home")
        text = "\n".join(metrics)

        self.assertIn('evcc_audit_gridsession_event_start_timestamp_seconds{', text)
        self.assertIn('site="home"', text)
        self.assertIn('start="2026-06-20 08:00"', text)
        self.assertIn('end="2026-06-20 08:15"', text)
        self.assertIn('limit_w="4200"', text)
        self.assertIn('grid_power_start_w="3900"', text)

    def test_gridsession_event_keeps_intervention_source_and_ski(self):
        sessions = [
            {
                "created": "2026-06-20T08:00:00Z",
                "finished": "2026-06-20T08:15:00Z",
                "type": "eebus-limit",
                "limit": 4200,
                "grid": 3900,
                "sourceSki": "001122334455",
            }
        ]
        events = MODULE.normalize_sessions(sessions, "home", seen_at_utc="2026-06-20T08:01:00Z")
        self.assertEqual(events[0]["intervention_source"], "EEBUS")
        self.assertEqual(events[0]["source_ski"], "001122334455")

        metrics = MODULE.build_event_metrics(events, "home")
        text = "\n".join(metrics)
        self.assertIn('intervention_source="EEBUS"', text)
        self.assertIn('source_ski="001122334455"', text)

    def test_write_events_csv_merges_existing_event_by_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            initial = [
                {
                    "event_id": "abc",
                    "site_id": "home",
                    "start_time_utc": "2026-06-20T08:00:00Z",
                    "end_time_utc": "",
                    "type": "eebus-limit",
                    "status": "active",
                    "limit_w": "4200",
                    "grid_power_start_w": "3900",
                    "intervention_source": "EEBUS",
                    "source_ski": "001122334455",
                    "source": "evcc_gridsessions",
                    "first_seen_utc": "2026-06-20T08:01:00Z",
                    "last_seen_utc": "2026-06-20T08:01:00Z",
                }
            ]
            updated = [dict(initial[0], end_time_utc="2026-06-20T08:15:00Z", status="finished", last_seen_utc="2026-06-20T08:16:00Z")]

            csv_path = MODULE.write_events_csv(tmpdir, initial)
            MODULE.write_events_csv(tmpdir, updated)

            self.assertIsNotNone(csv_path)
            with csv_path.open("r", encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["first_seen_utc"], "2026-06-20T08:01:00Z")
            self.assertEqual(rows[0]["last_seen_utc"], "2026-06-20T08:16:00Z")
            self.assertEqual(rows[0]["status"], "finished")
            self.assertEqual(rows[0]["intervention_source"], "EEBUS")
            self.assertEqual(rows[0]["source_ski"], "001122334455")


if __name__ == "__main__":
    unittest.main()
