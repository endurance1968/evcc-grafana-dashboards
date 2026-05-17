import importlib.util
import pathlib
import sys
import unittest

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "helper" / "vm-rewrite-label-value.py"
SPEC = importlib.util.spec_from_file_location("vm_rewrite_label_value", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class VmRewriteLabelValueTests(unittest.TestCase):
    def test_transform_series_replaces_only_requested_label_value(self):
        item = {
            "metric": {"__name__": "pvPower_value", "id": "6", "title": "Balkon PV"},
            "timestamps": [1000, 2000],
            "values": [1.0, 2.0],
        }

        rewritten = MODULE.transform_series(item, "title", "Balkon PV", "Balkon Sued")

        self.assertEqual(
            rewritten["metric"],
            {"__name__": "pvPower_value", "id": "6", "title": "Balkon Sued"},
        )
        self.assertEqual(rewritten["timestamps"], [1000, 2000])
        self.assertEqual(rewritten["values"], [1.0, 2.0])

    def test_transform_series_rejects_unexpected_source_label_value(self):
        item = {
            "metric": {"__name__": "pvPower_value", "id": "6", "title": "Balkon West"},
            "timestamps": [1000],
            "values": [1.0],
        }

        with self.assertRaises(ValueError):
            MODULE.transform_series(item, "title", "Balkon PV", "Balkon Sued")

    def test_analyze_target_overlap_counts_conflicting_values(self):
        source = {
            "metric": {"__name__": "pvPower_value", "title": "Balkon Sued"},
            "timestamps": [1000, 2000],
            "values": [10.0, 20.0],
        }
        existing = [
            {
                "metric": {"__name__": "pvPower_value", "title": "Balkon Sued"},
                "timestamps": [1000, 3000],
                "values": [11.0, 30.0],
            }
        ]

        self.assertEqual(MODULE.analyze_target_overlap(source, existing), (1, 1))

    def test_merge_points_can_keep_existing_target_values_on_conflict(self):
        metric = {"__name__": "pvPower_value", "title": "Balkon Sued"}
        existing = {"metric": metric, "timestamps": [1000, 3000], "values": [1.0, 3.0]}
        source = {"metric": metric, "timestamps": [1000, 2000], "values": [10.0, 2.0]}

        merged = MODULE.merge_points(
            metric,
            [existing, source],
            allow_value_conflicts=False,
            keep_existing_values_on_conflict=True,
        )

        self.assertEqual(merged["timestamps"], [1000, 2000, 3000])
        self.assertEqual(merged["values"], [1.0, 2.0, 3.0])

    def test_dry_run_recommendation_for_clean_rename_is_write_ready(self):
        recommendation = MODULE.dry_run_recommendation(exported_series=4, overlaps=0, conflicts=0)

        self.assertEqual(recommendation["status"], "GO FOR IT")
        self.assertIn("--write", recommendation["write_flags"])
        self.assertNotIn("--merge-target", recommendation["write_flags"])

    def test_dry_run_recommendation_requires_merge_for_overlap(self):
        recommendation = MODULE.dry_run_recommendation(exported_series=4, overlaps=2, conflicts=0)

        self.assertEqual(recommendation["status"], "REVIEW")
        self.assertIn("--merge-target", recommendation["write_flags"])

    def test_merge_target_keeps_non_overlapping_existing_target_series(self):
        self.assertFalse(
            MODULE.should_delete_target_before_import(
                merge_target=True,
                target_overlap=0,
                target_conflicts=0,
                existing_stats=MODULE.SeriesStats(points=1, first=3000, last=3000),
            )
        )
        self.assertTrue(
            MODULE.should_delete_target_before_import(
                merge_target=True,
                target_overlap=1,
                target_conflicts=0,
                existing_stats=MODULE.SeriesStats(points=1, first=1000, last=1000),
            )
        )

    def test_transformed_matcher_uses_metric_name_syntax(self):
        matcher = MODULE.transformed_matcher({"__name__": "pvPower_value", "id": "1", "title": "New PV"})

        self.assertEqual(matcher, 'pvPower_value{id="1",title="New PV"}')
        self.assertEqual(
            MODULE.parse_exact_matcher(matcher),
            {"__name__": "pvPower_value", "id": "1", "title": "New PV"},
        )

    def test_metric_matches_tolerates_missing_metric_name_only(self):
        expected = {"__name__": "pvPower_value", "id": "1", "title": "New PV"}

        self.assertTrue(MODULE.metric_matches({"id": "1", "title": "New PV"}, expected))
        self.assertFalse(MODULE.metric_matches({"id": "1", "title": "Other"}, expected))
        self.assertFalse(MODULE.metric_matches({"id": "1", "title": "New PV", "host": "vm"}, expected))

    def test_api_time_accepts_rfc3339_and_unix_seconds(self):
        self.assertEqual(MODULE.api_time("1970-01-01T00:00:00Z"), "1")
        self.assertEqual(MODULE.api_time("1710000000"), "1710000000")

    def test_export_url_includes_explicit_history_range(self):
        url = MODULE.export_url(
            "http://127.0.0.1:8428",
            '{title="Old PV"}',
            "1",
            "1710000100",
        )

        self.assertIn("match%5B%5D=%7Btitle%3D%22Old+PV%22%7D", url)
        self.assertIn("start=1", url)
        self.assertIn("end=1710000100", url)
    def test_verify_imported_targets_accepts_live_samples_after_expected_range(self):
        expected = {
            '{__name__="pvPower_value",id="6",title="Balkon Sued"}': MODULE.SeriesStats(
                points=2,
                first=1000,
                last=2000,
            )
        }

        original_fetch_exact_series = MODULE.fetch_exact_series
        try:
            MODULE.fetch_exact_series = lambda base_url, metric, start, end: [
                {"metric": metric, "timestamps": [1000, 2000, 3000], "values": [1.0, 2.0, 3.0]}
            ]

            failures = MODULE.verify_imported_targets("http://127.0.0.1:8428", expected, "1", "1710000100")
        finally:
            MODULE.fetch_exact_series = original_fetch_exact_series

        self.assertEqual(failures, [])

    def test_verify_imported_targets_rejects_missing_history_prefix(self):
        expected = {
            '{__name__="pvPower_value",id="6",title="Balkon Sued"}': MODULE.SeriesStats(
                points=2,
                first=1000,
                last=2000,
            )
        }

        original_fetch_exact_series = MODULE.fetch_exact_series
        original_instant_query_has_metric = MODULE.instant_query_has_metric
        original_series_api_has_metric = MODULE.series_api_has_metric
        try:
            MODULE.fetch_exact_series = lambda base_url, metric, start, end: [
                {"metric": metric, "timestamps": [2000, 3000], "values": [2.0, 3.0]}
            ]
            MODULE.instant_query_has_metric = lambda base_url, metric, timestamp_ms: False
            MODULE.series_api_has_metric = lambda base_url, metric, start, end: False

            failures = MODULE.verify_imported_targets("http://127.0.0.1:8428", expected, "1", "1710000100")
        finally:
            MODULE.fetch_exact_series = original_fetch_exact_series
            MODULE.instant_query_has_metric = original_instant_query_has_metric
            MODULE.series_api_has_metric = original_series_api_has_metric

        self.assertTrue(any("expected first timestamp" in failure for failure in failures))

    def test_verify_imported_targets_accepts_instant_query_fallback(self):
        expected = {
            'pvPower_value{id="6",title="Balkon Sued"}': MODULE.SeriesStats(
                points=2,
                first=1000,
                last=2000,
            )
        }

        original_fetch_exact_series = MODULE.fetch_exact_series
        original_instant_query_has_metric = MODULE.instant_query_has_metric
        original_series_api_has_metric = MODULE.series_api_has_metric
        try:
            MODULE.fetch_exact_series = lambda base_url, metric, start, end: []
            MODULE.instant_query_has_metric = lambda base_url, metric, timestamp_ms: timestamp_ms in {1000, 2000}
            MODULE.series_api_has_metric = lambda base_url, metric, start, end: False

            failures = MODULE.verify_imported_targets("http://127.0.0.1:8428", expected, "1", "1710000100")
        finally:
            MODULE.fetch_exact_series = original_fetch_exact_series
            MODULE.instant_query_has_metric = original_instant_query_has_metric
            MODULE.series_api_has_metric = original_series_api_has_metric

        self.assertEqual(failures, [])

    def test_verify_imported_targets_accepts_series_api_fallback(self):
        expected = {
            'pvPower_value{id="6",title="Balkon Sued"}': MODULE.SeriesStats(
                points=2,
                first=1000,
                last=2000,
            )
        }

        original_fetch_exact_series = MODULE.fetch_exact_series
        original_instant_query_has_metric = MODULE.instant_query_has_metric
        original_series_api_has_metric = MODULE.series_api_has_metric
        try:
            MODULE.fetch_exact_series = lambda base_url, metric, start, end: []
            MODULE.instant_query_has_metric = lambda base_url, metric, timestamp_ms: False
            MODULE.series_api_has_metric = lambda base_url, metric, start, end: True

            failures = MODULE.verify_imported_targets("http://127.0.0.1:8428", expected, "1", "1710000100")
        finally:
            MODULE.fetch_exact_series = original_fetch_exact_series
            MODULE.instant_query_has_metric = original_instant_query_has_metric
            MODULE.series_api_has_metric = original_series_api_has_metric

        self.assertEqual(failures, [])


if __name__ == "__main__":
    unittest.main()
