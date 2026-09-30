"""v5 criteria end to end: gate, clues, fusion, verdicts (spec sections 5-7)."""

import json

from django.test import SimpleTestCase, TestCase

from lessons.models import CourseGroup, LearningMaterial, LearningObject, LearningObjectGroup, OutlineNode

from .services.concept_units import concepts_for_topic
from .services.criteria import ACCEPTED, PENDING, crosses_sections, decide_pairs
from .services.embeddings import EncoderUnavailable
from .testing import concept, member, word_vectors

CALIBRATION = {
    "weights": {"name": 1.0, "terms": 1.0, "meaning": 1.0, "heading": 1.0, "order": 0.5},
    "related_cutoff": 0.1,
    "meaning_cutoff": 0.3,
    "source": "test",
}


def flower():
    return [
        concept(1, "Stamen", "The anther makes pollen grains. " * 8),
        concept(2, "Pollination", "Pollen travels from an anther to a stigma."),
        concept(3, "Pistil", "The stigma is sticky and holds the style. " * 8),
    ]


def decide(concepts, embed=word_vectors):
    return {
        (row["prerequisite"].id, row["dependent"].id): row
        for row in decide_pairs(concepts, calibration=CALIBRATION, embed=embed)
    }


def no_encoder(sentences):
    raise EncoderUnavailable("offline")


class DecisionTests(SimpleTestCase):
    def test_a_concept_using_terms_another_explains_comes_after_it(self):
        decided = decide(flower())

        self.assertIn((1, 2), decided)
        self.assertIn(decided[(1, 2)]["verdict"], (ACCEPTED, PENDING))
        self.assertEqual(decided[(1, 2)]["evidence"]["votes"]["terms"], 1)

    def test_unrelated_concepts_get_no_link(self):
        decided = decide([concept(1, "Stamen", "The anther makes pollen grains."),
                          concept(2, "Weather", "Clouds bring heavy rain showers.")])

        self.assertEqual(decided, {})

    def test_pdf_order_alone_never_makes_a_link(self):
        first = concept(1, "Heat", member("Heat changes water into steam.", material_id=10, order=0),
                        member("Heat changes water into steam.", material_id=11, order=0))
        second = concept(2, "Steam", member("Heat changes water into steam.", material_id=10, order=1),
                         member("Heat changes water into steam.", material_id=11, order=1))

        self.assertEqual(decide([first, second]), {})

    def test_without_the_encoder_links_are_only_pending(self):
        decided = decide(flower(), embed=no_encoder)

        self.assertTrue(decided)
        self.assertEqual({row["verdict"] for row in decided.values()}, {PENDING})
        self.assertFalse(decided[(1, 2)]["evidence"]["semantic"])

    def test_a_concept_with_no_full_sentence_takes_part_in_no_link(self):
        concepts = flower() + [concept(4, "Figure", "Stamen")]

        self.assertFalse(any(4 in pair for pair in decide(concepts)))

    def test_without_the_encoder_a_concept_with_no_full_sentence_still_takes_part_in_no_link(self):
        concepts = flower() + [concept(4, "Anther diagram", "Anther diagram")]

        self.assertFalse(any(4 in pair for pair in decide(concepts, embed=no_encoder)))

    def test_votes_are_stored_for_prerequisite_first(self):
        row = decide(flower())[(1, 2)]

        supporting = [clue for clue, vote in row["evidence"]["votes"].items() if vote == 1]
        self.assertIn("terms", supporting)
        self.assertGreater(row["evidence"]["confidence"], 0)

    def test_text_and_headings_agreeing_is_accepted(self):
        matter = concept(1, "Matter", "Matter is anything with mass and volume.")
        solid = concept(2, "Solid", member("A solid is matter with a fixed shape.", section_title="Matter"))

        row = decide([matter, solid])[(1, 2)]

        self.assertEqual(row["verdict"], ACCEPTED)
        self.assertEqual(row["evidence"]["votes"]["heading"], 1)

    def test_an_overview_naming_its_child_stays_pending_parent_first(self):
        """The overview's text names the child, so the text alone reads child-first;
        the child sits under the parent's heading, so the link follows the author
        and waits for the teacher (Solid -> Matter on gold 62)."""
        matter = concept(1, "Matter", member("Matter comes as a solid or a liquid in daily life.", section_title="Matter"))
        solid = concept(2, "Solid", member("A solid keeps its own shape well.", section_title="Matter"))

        row = decide([matter, solid])[(1, 2)]

        self.assertEqual(row["verdict"], PENDING)
        self.assertTrue(row["evidence"]["disagreement"])

    def test_siblings_under_one_heading_are_never_accepted(self):
        solid = concept(1, "Solid", member("A solid keeps its own shape well.", section_title="Matter"))
        gas = concept(2, "Gas", member("A gas spreads out more than a solid does.", section_title="Matter"))

        decided = decide([solid, gas])

        self.assertTrue(decided)
        self.assertEqual({row["verdict"] for row in decided.values()}, {PENDING})
        self.assertTrue(all(row["evidence"]["parallel"] for row in decided.values()))

    def test_a_clue_can_be_left_out_for_an_ablation(self):
        matter = concept(1, "Matter", "Matter is anything with mass and volume.")
        solid = concept(2, "Solid", member("A solid is matter with a fixed shape.", section_title="Matter"))

        rows = decide_pairs([matter, solid], calibration=CALIBRATION, embed=word_vectors, without=("heading",))

        self.assertEqual(rows[0]["evidence"]["votes"]["heading"], 0)

    def test_evidence_is_json_serialisable(self):
        for row in decide(flower()).values():
            json.dumps(row["evidence"])

    def test_too_few_concepts_decide_nothing(self):
        self.assertEqual(decide([concept(1, "Matter", "Matter has mass and takes up space.")]), {})


class SectionTests(SimpleTestCase):
    def test_different_headings_cross_sections(self):
        solid = concept(1, "Solid", member("x", section_title="Solids"))
        comparing = concept(2, "Comparing", member("x", section_title="Comparing the Three States"))

        self.assertTrue(crosses_sections(solid, comparing))

    def test_a_concept_without_a_heading_crosses_nothing(self):
        self.assertFalse(crosses_sections(concept(1, "Matter", "x"), concept(2, "Solid", member("x", section_title="Solids"))))


class MemberTextTests(TestCase):
    """Concepts built the way the topic path builds them carry every PDF's text."""

    def test_member_text_joins_every_pdf(self):
        course = CourseGroup.objects.create(title="Grade 1 Science")
        topic = OutlineNode.objects.create(course=course, title="Solid, Liquid and Gas", order=0, depth=0)
        first = LearningMaterial.objects.create(course=course, outline_node=topic, title="A", status="completed")
        second = LearningMaterial.objects.create(course=course, outline_node=topic, title="B", status="completed")
        group = LearningObjectGroup.objects.create(outline_node=topic, label="Solid")
        LearningObject.objects.create(material=first, group=group, title="Solid", content="A solid is matter that keeps its shape.", order=0)
        LearningObject.objects.create(material=second, group=group, title="Solids", content="Solid particles vibrate.", order=0)

        concept_unit = next(c for c in concepts_for_topic(topic) if c.id == group.id)

        self.assertIn("A solid is matter that keeps its shape.", concept_unit.member_text)
        self.assertIn("Solid particles vibrate.", concept_unit.member_text)
