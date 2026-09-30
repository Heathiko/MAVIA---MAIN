"""Acceptance: v5 on real lesson text, against the answer keys.

Uses the real encoder; skipped when it cannot load. The hard gate is 0 forbidden
links accepted. Reachability and Kendall's tau floors are set from measured v5
numbers (spec section 9) -- see the evaluation report.
"""

import json
import unittest

from django.test import SimpleTestCase

from .services import criteria
from .services.embeddings import EncoderUnavailable, load_encoder
from .services.gold import gold_report, load_gold

# Measured v5 values from docs/learning-path-v5-evaluation-2026-09-30.md.
REACHABLE_FLOOR = {62: 5, 79: 3, 152: 10, 340: 18, 357: 14}
TAU_FLOOR = {62: 1.0, 79: 1.0, 152: 0.80, 340: 0.75, 357: 1.0}


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
        self.assertEqual(report["forbidden_accepted"], [], json.dumps(report, indent=2))
        self.assertGreaterEqual(report["reachable_count"], REACHABLE_FLOOR[topic_id], json.dumps(report, indent=2))
        self.assertGreaterEqual(report["kendall_tau"], TAU_FLOOR[topic_id], json.dumps(report, indent=2))

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
