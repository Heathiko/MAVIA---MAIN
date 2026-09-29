"""The gold report's v4 measures: reachability, closure precision, rules."""

from types import SimpleNamespace

from django.test import SimpleTestCase

from .services.gold import gold_report


def concept(id, key, order):
    return SimpleNamespace(id=id, key=key, order=order, title=key, kind="text", members=())


def decision(before, after, verdict, rule=None):
    row = {"prerequisite": before, "dependent": after, "verdict": verdict}
    if rule:
        row["evidence"] = {"rule": rule}
    return row


class GoldReportTests(SimpleTestCase):
    def setUp(self):
        self.matter, self.solid, self.comparing, self.figure = (
            concept(1, "matter", 0), concept(2, "solid", 1),
            concept(3, "comparing", 2), concept(4, "figure", 3),
        )
        self.concepts = [self.matter, self.solid, self.comparing, self.figure]
        self.data = {
            "topic_id": 999,
            "required": [["matter", "solid"], ["solid", "comparing"]],
            "parallel": [],
            "structural": [],
            "forbidden": [["figure", "matter"]],
            "expected_order": ["matter", "solid", "comparing", "figure"],
        }

    def test_pending_required_edges_are_reachable(self):
        report = gold_report(self.data, self.concepts, [
            decision(self.matter, self.solid, "accepted", "containment"),
            decision(self.solid, self.comparing, "pending", "reference"),
        ])

        self.assertEqual(report["unreachable"], [])
        self.assertEqual(report["reachable_count"], 2)

    def test_a_required_edge_with_no_decision_is_unreachable(self):
        report = gold_report(self.data, self.concepts, [
            decision(self.matter, self.solid, "accepted", "containment"),
        ])

        self.assertEqual(report["unreachable"], [["solid", "comparing"]])
        self.assertEqual(report["reachable_count"], 1)

    def test_an_edge_implied_by_the_required_chain_is_correct(self):
        report = gold_report(self.data, self.concepts, [
            decision(self.matter, self.solid, "accepted", "containment"),
            decision(self.matter, self.comparing, "accepted", "definition"),
        ])

        self.assertEqual(report["accepted_precision"], 1.0)

    def test_an_explicitly_forbidden_edge_is_reported(self):
        report = gold_report(self.data, self.concepts, [
            decision(self.figure, self.matter, "accepted", "definition"),
        ])

        self.assertEqual(report["forbidden_accepted"], [["figure", "matter"]])
        self.assertEqual(report["accepted_precision"], 0.0)

    def test_accepted_links_are_counted_by_rule(self):
        report = gold_report(self.data, self.concepts, [
            decision(self.matter, self.solid, "accepted", "containment"),
            decision(self.solid, self.comparing, "accepted"),
        ])

        self.assertEqual(report["accepted_by_rule"], {"containment": 1, "none": 1})

    def test_nothing_accepted_has_no_precision(self):
        self.assertIsNone(gold_report(self.data, self.concepts, [])["accepted_precision"])

    def test_kendall_tau_is_one_in_order_and_minus_one_reversed(self):
        from .services.gold import kendall_tau

        self.assertEqual(kendall_tau(["a", "b", "c"], ["a", "b", "c"]), 1.0)
        self.assertEqual(kendall_tau(["c", "b", "a"], ["a", "b", "c"]), -1.0)
        self.assertIsNone(kendall_tau(["a"], ["a", "b"]))

    def test_the_report_carries_kendall_tau(self):
        report = gold_report(self.data, self.concepts, [])

        self.assertEqual(report["kendall_tau"], 1.0)
