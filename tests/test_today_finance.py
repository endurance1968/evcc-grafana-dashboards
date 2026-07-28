import json
import pathlib
import unittest


SOURCE = pathlib.Path(__file__).resolve().parents[1] / "dashboards" / "original" / "en"


def v2_queries(panel):
    return panel["spec"]["data"]["spec"]["queries"]


def query_ref(query):
    return query["spec"]["refId"]


def query_expression(query):
    spec = query["spec"]["query"]["spec"]
    return spec.get("expr", spec.get("expression", ""))


class TodayFinanceTests(unittest.TestCase):
    def test_directional_cost_fixture_uses_same_timestamp_tariffs(self):
        samples = [
            # grid W, import EUR/kWh, feed-in EUR/kWh, interval hours
            (1000.0, 0.30, 0.08, 0.25),
            (-500.0, 0.32, 0.09, 0.25),
            (2000.0, 0.28, 0.10, 0.25),
            (-1000.0, 0.35, 0.11, 0.25),
        ]

        purchase_cost = -sum(max(power, 0.0) / 1000 * hours * import_tariff for power, import_tariff, _feed_in_tariff, hours in samples)
        feed_in_credit = sum(max(-power, 0.0) / 1000 * hours * feed_in_tariff for power, _import_tariff, feed_in_tariff, hours in samples)
        balance = purchase_cost + feed_in_credit

        self.assertAlmostEqual(purchase_cost, -0.215)
        self.assertAlmostEqual(feed_in_credit, 0.03875)
        self.assertAlmostEqual(balance, -0.17625)

    def test_today_dashboards_use_negative_cost_positive_credit_and_balance(self):
        cases = [
            ("VM_EVCC_Today.json", lambda dashboard: v2_queries(dashboard["spec"]["elements"]["panel-73"])),
            ("VM_EVCC_Today-Mobile.json", lambda dashboard: dashboard["panels"][6]["targets"]),
            ("VM_EVCC_Today-Details.json", lambda dashboard: v2_queries(dashboard["spec"]["elements"]["panel-24"])),
        ]
        for file_name, select_queries in cases:
            with self.subTest(file_name=file_name):
                dashboard = json.loads((SOURCE / file_name).read_text(encoding="utf-8"))
                queries = {query_ref(query) if "spec" in query else query["refId"]: query for query in select_queries(dashboard)}
                purchase_ref = "bought" if file_name.endswith("Details.json") else "boughtTotal"
                credit_ref = "sold" if file_name.endswith("Details.json") else "soldTotal"
                balance_ref = "dailyTotal"
                purchase = query_expression(queries[purchase_ref]) if "spec" in queries[purchase_ref] else queries[purchase_ref]["expr"]
                credit = query_expression(queries[credit_ref]) if "spec" in queries[credit_ref] else queries[credit_ref]["expr"]
                balance = query_expression(queries[balance_ref]) if "spec" in queries[balance_ref] else queries[balance_ref]["expression"]

                self.assertTrue(purchase.startswith("-range_sum("), purchase)
                self.assertIn("clamp_min(avg(gridPower_value), 0)", purchase)
                self.assertIn("clamp_min(-avg(gridPower_value), 0)", credit)
                self.assertNotIn("clamp_max(avg(gridPower_value), 0)", credit)
                self.assertIn(purchase_ref, balance)
                self.assertIn(credit_ref, balance)

    def test_today_details_interval_costs_have_no_negative_tariff_offset(self):
        dashboard = json.loads((SOURCE / "VM_EVCC_Today-Details.json").read_text(encoding="utf-8"))
        panel = dashboard["spec"]["elements"]["panel-23"]
        expressions = [query_expression(query) for query in v2_queries(panel)]

        self.assertEqual(len(expressions), 2)
        self.assertTrue(all("offset -$tariffPriceInterval" not in expression for expression in expressions))
        self.assertIn("same timestamp", panel["spec"]["description"])


if __name__ == "__main__":
    unittest.main()
