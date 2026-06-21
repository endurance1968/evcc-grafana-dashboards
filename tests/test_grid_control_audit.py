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
        self.assertIn('evcc_audit_minimum_allowed_power_w{site="home"} 10500.0', text)

    def test_minimum_allowed_power_uses_gzf_table_for_ems_mode(self):
        self.assertEqual(MODULE.minimum_allowed_power_w(1), 4200.0)
        self.assertEqual(MODULE.minimum_allowed_power_w(2), 7560.0)
        self.assertEqual(MODULE.minimum_allowed_power_w(3), 10500.0)
        self.assertEqual(MODULE.minimum_allowed_power_w(9), 19320.0)

    def test_minimum_allowed_power_supports_direct_and_override_modes(self):
        self.assertEqual(MODULE.minimum_allowed_power_w(2, mode="direct"), 8400.0)
        self.assertEqual(MODULE.minimum_allowed_power_w(4, mode="linear", additional_factor=0.4), 9240.0)
        self.assertEqual(MODULE.minimum_allowed_power_w(99, override_w=6300), 6300.0)

    def test_build_parser_accepts_minimum_override(self):
        parser = MODULE.build_parser()
        args = parser.parse_args(["--minimum-override-w", "6300", "--minimum-mode", "direct"])
        self.assertEqual(args.minimum_override_w, 6300.0)
        self.assertEqual(args.minimum_mode, "direct")

    def test_build_parser_accepts_intervention_source_fallback(self):
        parser = MODULE.build_parser()
        args = parser.parse_args(["--intervention-source", "FNN"])
        self.assertEqual(args.intervention_source, "FNN")

    def test_detect_state_intervention_source_uses_hems_config_type(self):
        state = {"hems": {"config": {"type": "eebus"}, "status": {"curtailed": True}}}
        self.assertEqual(MODULE.detect_state_intervention_source(state), "EEBUS")

    def test_detect_state_intervention_source_supports_fnn_and_relay(self):
        self.assertEqual(MODULE.detect_state_intervention_source({"hems": {"config": {"type": "fnn"}}}), "FNN")
        self.assertEqual(MODULE.detect_state_intervention_source({"hems": {"config": {"type": "relays"}}}), "Relay")

    def test_control_group_legacy_loadpoints_alias_still_works(self):
        groups = MODULE.parse_control_groups("lp|Loadpoints|loadpoints|1+2")
        state = {"loadpoints": [{"title": "A", "chargePower": 1000}, {"title": "B", "chargePower": 2000}]}
        metrics = MODULE.build_state_metrics(state, "home", groups)
        text = "\n".join(metrics)

        self.assertIn('evcc_audit_control_group_power_w{group="lp",kind="loadpoints",name="Loadpoints",site="home"} 3000.0', text)

    def test_gridsession_event_metric_contains_table_labels(self):
        sessions = [
            {
                "Created": "2026-06-20T08:00:00Z",
                "Finished": "2026-06-20T08:15:00Z",
                "Type": "production",
                "LimitPower": -3600,
                "GridPower": 199,
            }
        ]
        events = MODULE.normalize_sessions(sessions, "home")
        metrics = MODULE.build_event_metrics(events, "home")
        text = "\n".join(metrics)

        self.assertIn('evcc_audit_gridsession_event_start_timestamp_seconds{', text)
        self.assertIn('site="home"', text)
        self.assertIn('source="evcc_gridsessions"', text)
        self.assertIn('start="2026-06-20 08:00"', text)
        self.assertIn('end="2026-06-20 08:15"', text)
        self.assertIn('type="production"', text)
        self.assertIn('limit_w="-3600"', text)
        self.assertIn('grid_power_start_w="199"', text)
        self.assertIn('intervention_source=""', text)

    def test_gridsession_event_keeps_intervention_source_and_ski(self):
        sessions = [
            {
                "created": "2026-06-20T08:00:00Z",
                "finished": "2026-06-20T08:15:00Z",
                "type": "production",
                "limit": -1000,
                "grid": 3900,
                "source": "eebus",
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

    def test_gridsession_event_maps_explicit_hems_source_only(self):
        hems_events = MODULE.normalize_sessions(
            [
                {
                    "created": "2026-06-20T08:00:00Z",
                    "type": "consumption",
                    "limit": 7000,
                    "source": "external-hems",
                }
            ],
            "home",
        )
        self.assertEqual(hems_events[0]["intervention_source"], "HEMS")

        unknown_events = MODULE.normalize_sessions(
            [
                {
                    "created": "2026-06-20T08:00:00Z",
                    "type": "consumption",
                    "limit": 7000,
                    "source": "external-controller",
                }
            ],
            "home",
        )
        self.assertEqual(unknown_events[0]["intervention_source"], "")

    def test_gridsession_event_uses_configured_source_fallback(self):
        events = MODULE.normalize_sessions(
            [
                {
                    "created": "2026-06-20T08:00:00Z",
                    "type": "production",
                    "limit": -3000,
                }
            ],
            "home",
            fallback_source="eebus",
        )
        self.assertEqual(events[0]["intervention_source"], "EEBUS")

    def test_gridsession_event_source_from_evcc_wins_over_fallback(self):
        events = MODULE.normalize_sessions(
            [
                {
                    "created": "2026-06-20T08:00:00Z",
                    "type": "consumption",
                    "limit": 7000,
                    "source": "relay",
                }
            ],
            "home",
            fallback_source="eebus",
        )
        self.assertEqual(events[0]["intervention_source"], "Relay")

    def test_gridsession_event_supports_fnn_fallback(self):
        events = MODULE.normalize_sessions(
            [
                {
                    "created": "2026-06-20T08:00:00Z",
                    "type": "production",
                    "limit": -1000,
                    "source": "external-controller",
                }
            ],
            "home",
            fallback_source="fnn",
        )
        self.assertEqual(events[0]["intervention_source"], "FNN")

    def test_gridsession_event_ids_use_evcc_id_when_available(self):
        sessions = [
            {"id": 1, "created": "2026-06-20T08:00:00Z", "type": "consumption", "limit": 7000},
            {"id": 2, "created": "2026-06-20T08:00:00Z", "type": "consumption", "limit": 7000},
        ]
        events = MODULE.normalize_sessions(sessions, "home")

        self.assertNotEqual(events[0]["event_id"], events[1]["event_id"])

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

            csv_path, changed_initial = MODULE.write_events_csv(tmpdir, initial)
            _, changed_updated = MODULE.write_events_csv(tmpdir, updated)

            self.assertIsNotNone(csv_path)
            self.assertEqual([event["event_id"] for event in changed_initial], ["abc"])
            self.assertEqual([event["event_id"] for event in changed_updated], ["abc"])
            _, unchanged = MODULE.write_events_csv(tmpdir, updated)
            self.assertEqual(unchanged, [])
            with csv_path.open("r", encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["first_seen_utc"], "2026-06-20T08:01:00Z")
            self.assertEqual(rows[0]["last_seen_utc"], "2026-06-20T08:16:00Z")
            self.assertEqual(rows[0]["status"], "finished")
            self.assertEqual(rows[0]["intervention_source"], "EEBUS")
            self.assertEqual(rows[0]["source_ski"], "001122334455")

    def test_write_events_csv_merges_active_and_finished_with_different_evcc_ids(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            active = {
                "event_id": "active-id",
                "site_id": "home",
                "start_time_utc": "2026-06-21T04:55:56Z",
                "end_time_utc": "",
                "type": "production",
                "status": "active",
                "limit_w": "-10000",
                "grid_power_start_w": "199",
                "intervention_source": "EEBUS",
                "source_ski": "",
                "source": "evcc_gridsessions",
                "first_seen_utc": "2026-06-21T04:55:58Z",
                "last_seen_utc": "2026-06-21T05:53:03Z",
            }
            finished = dict(
                active,
                event_id="finished-id",
                end_time_utc="2026-06-21T05:56:06Z",
                status="finished",
                last_seen_utc="2026-06-21T10:54:47Z",
            )

            csv_path, _ = MODULE.write_events_csv(tmpdir, [active])
            _, changed = MODULE.write_events_csv(tmpdir, [finished])

            self.assertEqual([event["status"] for event in changed], ["finished"])
            with csv_path.open("r", encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["event_id"], "active-id")
            self.assertEqual(rows[0]["status"], "finished")
            self.assertEqual(rows[0]["end_time_utc"], "2026-06-21T05:56:06Z")
            self.assertEqual(rows[0]["last_seen_utc"], "2026-06-21T10:54:47Z")

    def test_write_events_csv_collapses_existing_active_finished_duplicate_rows(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = MODULE.events_csv_path(tmpdir)
            csv_path.parent.mkdir(parents=True, exist_ok=True)
            rows = [
                {
                    "event_id": "finished-id",
                    "site_id": "home",
                    "start_time_utc": "2026-06-21T04:55:56Z",
                    "end_time_utc": "2026-06-21T05:56:06Z",
                    "type": "production",
                    "status": "finished",
                    "limit_w": "-10000",
                    "grid_power_start_w": "199",
                    "intervention_source": "EEBUS",
                    "source_ski": "",
                    "source": "evcc_gridsessions",
                    "first_seen_utc": "2026-06-21T05:53:04Z",
                    "last_seen_utc": "2026-06-21T10:54:47Z",
                },
                {
                    "event_id": "active-id",
                    "site_id": "home",
                    "start_time_utc": "2026-06-21T04:55:56Z",
                    "end_time_utc": "",
                    "type": "production",
                    "status": "active",
                    "limit_w": "-10000",
                    "grid_power_start_w": "199",
                    "intervention_source": "EEBUS",
                    "source_ski": "",
                    "source": "evcc_gridsessions",
                    "first_seen_utc": "2026-06-21T04:55:58Z",
                    "last_seen_utc": "2026-06-21T05:53:03Z",
                },
            ]
            with csv_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=MODULE.CSV_EVENT_FIELDS)
                writer.writeheader()
                writer.writerows(rows)

            _, changed = MODULE.write_events_csv(tmpdir, [])

            self.assertEqual(changed, [])
            with csv_path.open("r", encoding="utf-8", newline="") as handle:
                collapsed = list(csv.DictReader(handle))
            self.assertEqual(len(collapsed), 1)
            self.assertEqual(collapsed[0]["event_id"], "finished-id")
            self.assertEqual(collapsed[0]["status"], "finished")
            self.assertEqual(collapsed[0]["end_time_utc"], "2026-06-21T05:56:06Z")

    def test_collect_once_replays_event_metrics_from_local_csv_when_requested(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            MODULE.write_events_csv(
                tmpdir,
                [
                    {
                        "event_id": "historic",
                        "site_id": "home",
                        "start_time_utc": "2026-06-20T08:00:00Z",
                        "end_time_utc": "2026-06-20T08:15:00Z",
                        "type": "production",
                        "status": "finished",
                        "limit_w": "-3600",
                        "grid_power_start_w": "199",
                        "intervention_source": "EEBUS",
                        "source_ski": "001122334455",
                        "source": "evcc_gridsessions",
                        "first_seen_utc": "2026-06-20T08:01:00Z",
                        "last_seen_utc": "2026-06-20T08:16:00Z",
                    }
                ],
            )
            parser = MODULE.build_parser()
            args = parser.parse_args(
                [
                    "--evcc-url",
                    "http://evcc.local",
                    "--audit-dir",
                    tmpdir,
                    "--once",
                    "--replay-events",
                ]
            )

            original_http_get_json = MODULE.http_get_json
            try:
                def fake_http_get_json(url, timeout, user_agent):
                    if url.endswith("/api/state"):
                        return {"site": {"gridPower": 0}, "hems": {"config": {"type": "eebus"}}}
                    if url.endswith("/api/gridsessions"):
                        return []
                    raise AssertionError(url)

                MODULE.http_get_json = fake_http_get_json
                metrics = MODULE.collect_once(args)
            finally:
                MODULE.http_get_json = original_http_get_json

            text = "\n".join(metrics)
            self.assertIn('event_id="historic"', text)
            self.assertIn('intervention_source="EEBUS"', text)
            self.assertIn('source_ski="001122334455"', text)

    def test_recent_event_history_filters_to_lookback_window(self):
        events = [
            {"event_id": "old", "start_time_utc": "2026-06-01T00:00:00Z"},
            {"event_id": "recent", "start_time_utc": "2026-06-20T00:00:00Z"},
            {"event_id": "invalid", "start_time_utc": "not-a-date"},
        ]
        now_seconds = MODULE.datetime(2026, 6, 21, tzinfo=MODULE.timezone.utc).timestamp()

        recent = MODULE.recent_event_history(events, now_seconds, 8)

        self.assertEqual([event["event_id"] for event in recent], ["recent"])

    def test_collect_once_replays_recent_csv_events_by_default(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            MODULE.write_events_csv(
                tmpdir,
                [
                    {
                        "event_id": "historic",
                        "site_id": "home",
                        "start_time_utc": "2026-06-20T08:00:00Z",
                        "end_time_utc": "2026-06-20T08:15:00Z",
                        "type": "production",
                        "status": "finished",
                        "limit_w": "-3600",
                        "grid_power_start_w": "199",
                        "intervention_source": "EEBUS",
                        "source_ski": "001122334455",
                        "source": "evcc_gridsessions",
                        "first_seen_utc": "2026-06-20T08:01:00Z",
                        "last_seen_utc": "2026-06-20T08:16:00Z",
                    }
                ],
            )
            parser = MODULE.build_parser()
            args = parser.parse_args(
                [
                    "--evcc-url",
                    "http://evcc.local",
                    "--audit-dir",
                    tmpdir,
                    "--once",
                    "--event-replay-lookback-days",
                    "99999",
                ]
            )

            original_http_get_json = MODULE.http_get_json
            try:
                def fake_http_get_json(url, timeout, user_agent):
                    if url.endswith("/api/state"):
                        return {"site": {"gridPower": 0}, "hems": {"config": {"type": "eebus"}}}
                    if url.endswith("/api/gridsessions"):
                        return []
                    raise AssertionError(url)

                MODULE.http_get_json = fake_http_get_json
                metrics = MODULE.collect_once(args)
            finally:
                MODULE.http_get_json = original_http_get_json

            text = "\n".join(metrics)
            self.assertIn('event_id="historic"', text)

if __name__ == "__main__":
    unittest.main()
