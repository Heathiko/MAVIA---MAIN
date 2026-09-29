"""Acceptance: the v4 criteria on real lesson text, against the teacher's maps.

v4 calls no model, so this runs everywhere. Assertions follow the spec's
acceptance criteria (Section 10): no forbidden link accepted, the expected
order, and at least the measured number of required links reachable
(accepted or pending). Accepted recall is reported, not gated: most links are
teacher suggestions by design. See
docs/superpowers/specs/2026-09-29-learning-path-criteria-v4-design.md, 10.1.
"""

import json

from django.test import SimpleTestCase

from .services import criteria
from .services.gold import gold_report, load_gold

REACHABLE_FLOOR = {62: 9, 79: 3, 152: 8}


class GoldPathTests(SimpleTestCase):
    def _report(self, topic_id):
        data, concepts = load_gold(topic_id)
        return gold_report(data, concepts, criteria.decide_pairs(concepts))

    def _assert_gold(self, report):
        details = f"\nFull report:\n{json.dumps(report, indent=2)}"
        self.assertEqual(report["forbidden_accepted"], [], "forbidden edges accepted" + details)
        self.assertTrue(report["order_matches"], f"order was {report['order']}" + details)
        self.assertGreaterEqual(
            report["reachable_count"], REACHABLE_FLOOR[report["topic"]],
            "fewer required edges reachable than the measured v4 baseline" + details,
        )

    def test_solid_liquid_and_gas(self):
        self._assert_gold(self._report(62))

    def test_reproduction_among_flowering_plants(self):
        self._assert_gold(self._report(79))

    def test_solid_liquid_and_gas_as_the_pipeline_groups_it_today(self):
        """Topic 152 freezes the pipeline's own 14 concepts for the lesson
        topic 62 holds in the teacher's grouping (see export_live_concepts)."""
        self._assert_gold(self._report(152))

    def test_topic_340_against_the_recommended_arrangement(self):
        """Topic 340 is measured against a draft key built from an outside
        recommendation (fixtures/gold_map_340.json), so it is a floor, not an
        acceptance: no forbidden link accepted, and the required links the
        rules reach must not fall. The expected order is not asserted yet -- it
        needs rules that read sentence titles and figures (open-issues 1.4)."""
        report = self._report(340)
        self.assertEqual(report["forbidden_accepted"], [], json.dumps(report, indent=2))
        self.assertGreaterEqual(report["reachable_count"], 11, json.dumps(report, indent=2))
