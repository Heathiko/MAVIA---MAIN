"""Acceptance: the two real lessons produce the teacher's learning paths.

Runs the real sentence encoder over real lesson text, so it is skipped when the
semantic models are not installed. Everything else in the learning-path suite
uses deterministic stand-ins; this is the one test that says whether the
criteria work on actual content.
"""

import json
import unittest

from django.test import SimpleTestCase

from lessons.services.semantic_grouping import SemanticUnavailable, runtime

from .services import criteria
from .services.gold import gold_report, load_gold


class GoldPathTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        try:
            cls.engine = runtime()
        except SemanticUnavailable as exc:
            raise unittest.SkipTest(f"Semantic models unavailable: {exc}")

    def _report(self, topic_id):
        data, concepts = load_gold(topic_id)
        report = gold_report(data, concepts, criteria.decide_pairs(concepts, self.engine))
        print(json.dumps(report, indent=2))
        return report

    def _assert_gold(self, report):
        self.assertEqual(report["missing_required"], [], "required edges not accepted")
        self.assertEqual(report["forbidden_accepted"], [], "forbidden edges accepted")
        self.assertTrue(report["order_matches"], f"order was {report['order']}")

    def test_solid_liquid_and_gas(self):
        self._assert_gold(self._report(62))

    def test_reproduction_among_flowering_plants(self):
        self._assert_gold(self._report(79))
