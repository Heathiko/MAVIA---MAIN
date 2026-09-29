"""The v4 decision table, its vetoes, and the helpers it keeps from v3.

R1 and R3 are measured on their own in ``test_evidence.py``; this file pins how
they combine with R2 into a verdict. See
``docs/superpowers/specs/2026-09-29-learning-path-criteria-v4-design.md``.
"""

import json

from django.test import SimpleTestCase, TestCase

from lessons.models import CourseGroup, LearningMaterial, LearningObject, LearningObjectGroup, OutlineNode

from .services.concept_units import concepts_for_topic
from .services.criteria import (
    ACCEPTED,
    PENDING,
    PRD_THRESHOLD,
    concept_names,
    contained_in,
    crosses_sections,
    decide_pairs,
    head_words,
    only_contrastive_mentions,
    presented_in_parallel,
)
from .services.publishing import order_with_links


class Headed:
    """A concept stub whose members carry their own title, content and heading."""

    def __init__(self, id, order, title, contents, sections=None):
        if isinstance(contents, str):
            contents = (contents,)
        sections = sections or ("",) * len(contents)
        self.id = id
        self.order = order
        self.title = title
        self.content = contents[0]
        self.member_text = "\n".join(contents)
        self.section_title = sections[0]
        self.kind = "text"
        self.members = tuple(
            type("Member", (), {"title": title, "content": content, "section_title": section})()
            for content, section in zip(contents, sections)
        )


def rows(concepts):
    return {(row["prerequisite"].id, row["dependent"].id): row for row in decide_pairs(concepts)}


class ConceptNameTests(SimpleTestCase):
    def test_a_structural_label_names_nothing(self):
        self.assertEqual(concept_names([Headed(1, 0, "Everyday Examples", "A rock.")]), {1: None})


class ContrastTests(SimpleTestCase):
    def test_a_mention_only_after_a_contrast_marker_is_contrastive(self):
        self.assertTrue(only_contrastive_mentions("solid", "A gas spreads out, unlike a solid."))

    def test_contrast_is_scoped_to_the_clause_not_the_sentence(self):
        text = "Liquids and gases can flow, while solids normally do not."
        self.assertFalse(only_contrastive_mentions("liquid", text))
        self.assertTrue(only_contrastive_mentions("solid", text))

    def test_a_comparison_with_than_is_contrastive(self):
        self.assertTrue(only_contrastive_mentions("solid", "Gas particles have more energy than in a solid."))

    def test_no_mention_is_not_a_contrast(self):
        self.assertFalse(only_contrastive_mentions("solid", "Gases spread out."))


class SectionTests(SimpleTestCase):
    def test_different_headings_cross_sections(self):
        self.assertTrue(crosses_sections(
            Headed(1, 0, "A", "x", ("Solids",)), Headed(2, 1, "B", "y", ("Gases",)),
        ))

    def test_the_same_heading_does_not(self):
        self.assertFalse(crosses_sections(
            Headed(1, 0, "A", "x", ("Solids",)), Headed(2, 1, "B", "y", (" solids ",)),
        ))

    def test_a_concept_without_a_heading_crosses_nothing(self):
        self.assertFalse(crosses_sections(Headed(1, 0, "A", "x", ("Solids",)), Headed(2, 1, "B", "y")))


class HeadWordTests(SimpleTestCase):
    def test_the_head_word_is_the_first_significant_word(self):
        self.assertEqual(
            head_words({1: "seed formation", 2: "stamen male part", 3: "solid"}),
            {1: "seed", 2: "stamen"},
        )

    def test_a_shared_head_word_is_ambiguous(self):
        self.assertEqual(head_words({1: "seed formation", 2: "seed dispersal"}), {})

    def test_a_single_word_name_makes_its_word_ambiguous(self):
        self.assertEqual(head_words({1: "seed", 2: "seed dispersal"}), {})


class ContainmentTests(SimpleTestCase):
    def test_a_concept_under_anothers_heading_is_contained(self):
        solid = Headed(2, 1, "Solid", ("A solid keeps its shape.", "Solids vibrate."), ("Matter", "Solids"))
        self.assertTrue(contained_in(solid, "matter"))

    def test_no_heading_contains_nothing(self):
        self.assertFalse(contained_in(Headed(2, 1, "Roots", "Roots take in water."), "matter"))
        self.assertFalse(contained_in(Headed(2, 1, "Solid", "x", ("Matter",)), None))


class ParallelPresentationTests(SimpleTestCase):
    def test_two_passages_under_one_heading_are_parallel(self):
        solid = Headed(1, 0, "Solid", "Particles are drawn as evenly spaced dots.", ("Matter",))
        gas = Headed(2, 1, "Gas", "Particles are drawn as widely spaced dots.", ("Matter",))
        self.assertTrue(presented_in_parallel(solid, gas, {1: "solid", 2: "gas"}))

    def test_the_concept_the_heading_names_is_the_parent_not_a_sibling(self):
        matter = Headed(1, 0, "Matter", "Matter has mass.", ("Matter",))
        solid = Headed(2, 1, "Solid", "A solid keeps its shape.", ("Matter",))
        self.assertFalse(presented_in_parallel(matter, solid, {1: "matter", 2: "solid"}))

    def test_passages_under_different_headings_are_not_parallel(self):
        solid = Headed(1, 0, "Solid", "A solid keeps its shape.", ("Matter",))
        comparing = Headed(2, 1, "Comparing", "The table compares them.", ("Comparing the Three States",))
        self.assertFalse(presented_in_parallel(solid, comparing, {1: "solid", 2: "comparing"}))

    def test_a_concept_under_no_heading_is_parallel_to_nothing(self):
        solid = Headed(1, 0, "Solid", "A solid keeps its shape.", ("Matter",))
        changing = Headed(2, 1, "Changing", "Heat changes the state.")
        self.assertFalse(presented_in_parallel(solid, changing, {1: "solid", 2: "changing"}))


class DecisionTableTests(SimpleTestCase):
    """Spec Section 6, row by row."""

    def matter_and_solid(self, matter_order=0, solid_order=1):
        matter = Headed(1, matter_order, "Matter", "Matter is anything that has mass.", ("Matter",))
        solid = Headed(2, solid_order, "Solid", "It keeps its shape.", ("Matter",))
        return matter, solid

    def test_containment_is_accepted(self):
        decided = rows(list(self.matter_and_solid()))

        self.assertEqual(decided[(1, 2)]["verdict"], ACCEPTED)
        self.assertEqual(decided[(1, 2)]["evidence"], {"rule": "containment", "containment": {"heading": "matter"}})

    def test_a_definition_is_accepted(self):
        solid = Headed(1, 0, "Solid", "It keeps its shape.")
        liquid = Headed(2, 1, "Liquid", "It flows.")
        melting = Headed(3, 2, "Melting", "Melting is when a solid turns into a liquid.")

        decided = rows([solid, liquid, melting])

        self.assertEqual(decided[(1, 3)]["verdict"], ACCEPTED)
        self.assertEqual(decided[(1, 3)]["evidence"]["rule"], "definition")
        self.assertEqual(
            decided[(1, 3)]["evidence"]["definition"]["sentence"],
            "Melting is when a solid turns into a liquid",
        )
        self.assertNotIn((3, 1), decided)

    def test_strong_evidence_both_ways_is_a_conflict_for_the_teacher(self):
        matter = Headed(1, 0, "Matter", "Matter is what a solid is made of.")
        solid = Headed(2, 1, "Solid", "It keeps its shape.", ("Matter",))

        decided = rows([matter, solid])

        for pair in ((1, 2), (2, 1)):
            self.assertEqual(decided[pair]["verdict"], PENDING)
            self.assertEqual(decided[pair]["evidence"]["rule"], "conflict")
        self.assertEqual(decided[(1, 2)]["evidence"]["forward"]["rule"], "containment")
        self.assertEqual(decided[(1, 2)]["evidence"]["backward"]["rule"], "definition")

    def test_reference_alone_is_pending(self):
        solid = Headed(1, 0, "Solid", "It keeps its shape.", ("Solids",))
        comparing = Headed(2, 1, "Comparing", "The table puts the solid beside the gas.", ("Comparing the Three States",))

        decided = rows([solid, comparing])

        self.assertEqual(decided[(1, 2)]["verdict"], PENDING)
        self.assertEqual(decided[(1, 2)]["evidence"], {
            "rule": "reference",
            "reference": {"prw_forward": 1.0, "prw_backward": 0.0, "prd": 1.0, "theta": PRD_THRESHOLD},
        })

    def test_reference_at_or_below_the_threshold_decides_nothing(self):
        solid = Headed(1, 0, "Solid", "A solid can become a liquid.")
        liquid = Headed(2, 1, "Liquid", "A liquid can become a solid.")

        self.assertEqual(rows([solid, liquid]), {})

    def test_reference_never_overrides_containment(self):
        """Review Focus 3: Matter's overview names Solid, so R3 alone reads
        Solid -> Matter. Containment keeps Matter -> Solid accepted."""
        matter = Headed(1, 0, "Matter", "Matter can be a solid, a liquid or a gas.")
        solid = Headed(2, 1, "Solid", "It keeps its shape.", ("Matter",))

        decided = rows([matter, solid])

        self.assertEqual(decided[(1, 2)]["verdict"], ACCEPTED)
        self.assertEqual(decided[(1, 2)]["evidence"]["opposing_reference"], {"prd": 1.0})
        self.assertNotIn((2, 1), decided)

    def test_siblings_need_a_definition_not_a_reference(self):
        solid = Headed(1, 0, "Solid", "It keeps its shape.", ("Matter",))
        gas = Headed(2, 1, "Gas", "A gas can become a solid when cooled.", ("Matter",))

        self.assertNotIn((1, 2), rows([solid, gas]))

    def test_a_sibling_defined_through_another_keeps_its_link(self):
        seed = Headed(1, 0, "Seed", "It holds a tiny plant.", ("How Flowering Plants Reproduce",))
        fruit = Headed(2, 1, "Fruit", "A fruit is the ripened ovary that holds the seed.", ("How Flowering Plants Reproduce",))

        decided = rows([seed, fruit])

        self.assertEqual(decided[(1, 2)]["verdict"], ACCEPTED)
        self.assertEqual(decided[(1, 2)]["evidence"]["rule"], "definition")

    def test_a_contrastive_mention_supports_nothing(self):
        solid = Headed(1, 0, "Solid", "It keeps its shape.")
        gas = Headed(2, 1, "Gas", "A gas is a state that spreads out, unlike a solid.")

        self.assertNotIn((1, 2), rows([solid, gas]))

    def test_two_concepts_with_the_same_name_are_never_linked(self):
        first = Headed(1, 0, "Solid", "A solid keeps its shape.")
        second = Headed(2, 1, "Solid", "A solid is rigid because of the solid bonds.")

        self.assertEqual(rows([first, second]), {})

    def test_document_order_never_changes_a_decision(self):
        """Review Focus 1: the whole point of v4 (spec goal 1)."""
        forward = rows(list(self.matter_and_solid(matter_order=0, solid_order=1)))
        reversed_ = rows(list(self.matter_and_solid(matter_order=1, solid_order=0)))

        self.assertEqual(
            {pair: (row["verdict"], row["evidence"]) for pair, row in forward.items()},
            {pair: (row["verdict"], row["evidence"]) for pair, row in reversed_.items()},
        )

    def test_a_link_can_point_against_document_order(self):
        """Review Focus 2: Solid sits first in the PDF, Matter second; the link
        is still Matter -> Solid, and the path teaches Matter first."""
        matter, solid = self.matter_and_solid(matter_order=1, solid_order=0)

        decided = rows([solid, matter])
        ordered, _, _ = order_with_links([solid, matter], [
            pair for pair, row in decided.items() if row["verdict"] == ACCEPTED
        ])

        self.assertEqual(decided[(1, 2)]["verdict"], ACCEPTED)
        self.assertEqual([concept.id for concept in ordered], [1, 2])

    def test_evidence_is_json_serialisable(self):
        """Review Focus 5: evidence goes into a JSONField at publish."""
        matter = Headed(1, 0, "Matter", "Matter can be a solid, a liquid or a gas.")
        solid = Headed(2, 1, "Solid", "It keeps its shape.", ("Matter",))
        melting = Headed(3, 2, "Melting", "Melting is when a solid turns into a liquid.")
        comparing = Headed(4, 3, "Comparing", "The solid is beside the matter.", ("Comparing the Three States",))

        for row in decide_pairs([matter, solid, melting, comparing]):
            json.dumps(row["evidence"])

    def test_crossing_sections_is_recorded(self):
        solid = Headed(1, 0, "Solid", "It keeps its shape.", ("Solids",))
        comparing = Headed(2, 1, "Comparing", "The table puts the solid beside the gas.", ("Comparing the Three States",))

        self.assertTrue(rows([solid, comparing])[(1, 2)]["cross_section"])

    def test_a_concept_is_never_its_own_prerequisite(self):
        for (before, after) in rows(list(self.matter_and_solid())):
            self.assertNotEqual(before, after)

    def test_too_few_concepts_decide_nothing(self):
        self.assertEqual(decide_pairs([Headed(1, 0, "Matter", "Matter has mass.")]), [])

    def test_structural_concepts_take_part_in_no_pair(self):
        matter, solid = self.matter_and_solid()
        examples = Headed(3, 2, "7. Everyday Examples", "Matter, a solid, a liquid and a gas.", ("Matter",))

        decided = rows([matter, solid, examples])

        self.assertFalse(any(3 in pair for pair in decided))


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

        concept = next(c for c in concepts_for_topic(topic) if c.id == group.id)

        self.assertIn("A solid is matter that keeps its shape.", concept.member_text)
        self.assertIn("Solid particles vibrate.", concept.member_text)
