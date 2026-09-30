"""Acceptance: v6 on real lesson text, against the answer keys.

Development set only; the test set is added after its single frozen run
(plan Task 7). Uses the real encoder; skipped when it cannot load. Floors are
the measured v6 values in docs/learning-path-v6-evaluation/eval-v6-dev.json.
"""

import json
import unittest

from django.test import SimpleTestCase

from .services import criteria
from .services.embeddings import EncoderUnavailable, load_encoder
from .services.gold import gold_report, load_gold

# Measured v6 values from docs/learning-path-v6-evaluation/eval-v6-dev.json.
REACHABLE_FLOOR = {62: 9, 79: 5, 152: 9, 340: 19, 357: 16}
COVERED_FLOOR = {62: 9, 79: 5, 152: 7, 340: 10, 357: 16}
TAU_FLOOR = {62: 1.0, 79: 1.0, 152: 0.80, 340: 0.63, 357: 1.0}
# Accepted against the key, explained in the v6 evaluation report: the PDF puts
# "As a general rule" before the states; only the AI-drafted key disagrees.
KNOWN_FORBIDDEN = {340: [["energy_rule", "gas"], ["energy_rule", "liquid"]]}


class GoldPathTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        try:
            load_encoder()
        except EncoderUnavailable as exc:
            raise unittest.SkipTest(f"encoder unavailable: {exc}")

    def _report(self, topic_id):
        data, concepts = load_gold(topic_id)
        return gold_report(data, concepts, criteria.decide_pairs(concepts))

    def _assert_gold(self, topic_id):
        report = self._report(topic_id)
        shown = json.dumps(report, indent=2)
        self.assertEqual(
            sorted(map(tuple, report["forbidden_accepted"])),
            sorted(map(tuple, KNOWN_FORBIDDEN.get(topic_id, []))),
            shown,
        )
        self.assertGreaterEqual(report["reachable_count"], REACHABLE_FLOOR[topic_id], shown)
        self.assertGreaterEqual(report["covered_count"], COVERED_FLOOR[topic_id], shown)
        self.assertGreaterEqual(report["kendall_tau"], TAU_FLOOR[topic_id], shown)

    def test_solid_liquid_and_gas(self):
        self._assert_gold(62)

    def test_reproduction_among_flowering_plants(self):
        self._assert_gold(79)

    def test_solid_liquid_and_gas_as_the_pipeline_groups_it_today(self):
        self._assert_gold(152)

    def test_topic_340_against_the_recommended_arrangement(self):
        self._assert_gold(340)

    def test_topic_357_against_the_recommended_arrangement(self):
        self._assert_gold(357)
