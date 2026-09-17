"""Units: several objects of one PDF that another PDF teaches as one.

Scores alone cannot find them (measured: every item scored 0.5-0.65 against
every section), and structure alone over-merges (a "Matter" section holding
Matter, Solid, Liquid and Gas). A unit is proposed only when a heading in the
other PDF names it, and never merged without the teacher.
"""

import os
from unittest.mock import patch

from django.test import TestCase

from .models import (
    CourseGroup,
    LearningMaterial,
    LearningObject,
    LearningObjectGroup,
    LearningObjectMatchSuggestion,
    OutlineNode,
)
from .services.unit_matching import (
    find_units,
    heading_key,
    heading_unit_candidates,
    refresh_heading_unit_suggestions,
)
from .test_semantic_grouping import FakeRuntime
from .tests import authenticated_api_client


class UnitFixture(TestCase):
    """Shaped like topic 62: material A itemises, material B uses sections."""

    def setUp(self):
        self.course = CourseGroup.objects.create(title="Science")
        self.topic = OutlineNode.objects.create(course=self.course, title="States")
        confirmed = {"learning_objects_confirmed": True}
        self.a = LearningMaterial.objects.create(course=self.course, outline_node=self.topic, title="A", generated_json=dict(confirmed))
        self.b = LearningMaterial.objects.create(course=self.course, outline_node=self.topic, title="B", generated_json=dict(confirmed))
        o = self._object
        self.matter = o(self.a, "Matter", "Matter", 0)
        self.solid_a = o(self.a, "Solid", "Matter", 1)
        self.liquid_a = o(self.a, "Liquid", "Matter", 2)
        self.shape = o(self.a, "Shape", "Comparing the Three States", 3)
        self.volume = o(self.a, "Volume", "Comparing the Three States", 4)
        self.examples_a = o(self.a, "Everyday Examples", "", 5)
        self.solids_b = o(self.b, "Solids", "Solids", 0)
        self.diagram_b = o(self.b, "Diagram description", "Solids", 1)
        self.liquids_b = o(self.b, "Liquids", "Liquids", 2)
        self.compare_b = o(self.b, "Comparing the Three States", "Comparing the Three States", 3)
        self.table_b = o(self.b, "5. Comparing the Three States", "", 4, kind="image")
        self.changing_b = o(self.b, "Changing From One State to Another", "", 5)
        self.changing_fig = o(self.b, "6. Changing From One State to Another", "", 6, kind="image")
        self.examples_b = o(self.b, "Everyday Examples", "Everyday Examples", 7)
        self.examples_table = o(self.b, "7. Everyday Examples", "", 8, kind="image")

    def _object(self, material, title, section, order, kind="text"):
        group = LearningObjectGroup.objects.create(outline_node=self.topic, label=title)
        return LearningObject.objects.create(
            material=material, group=group, title=title, content=f"{title} text.",
            section_title=section, order=order, kind=kind,
        )

    def _labels(self, candidates):
        return {
            (c["label"], tuple(item.id for item in c["left"]), tuple(item.id for item in c["right"]))
            for c in candidates
        }


class HeadingKeyTests(UnitFixture):
    def test_numbering_case_and_plural_fold_away(self):
        self.assertEqual(heading_key("5. Comparing the Three States"), "comparing the three state")
        self.assertEqual(heading_key("Solids"), heading_key("Solid"))


class FindUnitTests(UnitFixture):
    def test_units_follow_shared_sections_and_repeated_titles(self):
        units_b = {unit.label: unit.ids for unit in find_units(list(self.b.learning_objects.all()))}

        self.assertEqual(units_b[heading_key("Solids")], [self.solids_b.id, self.diagram_b.id])
        self.assertEqual(units_b[heading_key("Comparing the Three States")], [self.compare_b.id, self.table_b.id])
        self.assertEqual(units_b[heading_key("Changing From One State to Another")], [self.changing_b.id, self.changing_fig.id])
        self.assertEqual(units_b[heading_key("Everyday Examples")], [self.examples_b.id, self.examples_table.id])
        self.assertNotIn(heading_key("Liquids"), units_b)

    def test_a_section_of_itemised_concepts_is_still_a_unit(self):
        units_a = {unit.label: unit.ids for unit in find_units(list(self.a.learning_objects.all()))}

        self.assertEqual(units_a["matter"], [self.matter.id, self.solid_a.id, self.liquid_a.id])


class CandidateTests(UnitFixture):
    def test_units_are_proposed_only_where_the_other_pdf_names_them(self):
        labels = self._labels(heading_unit_candidates(self.topic))

        self.assertIn(
            (heading_key("Comparing the Three States"), (self.shape.id, self.volume.id), (self.compare_b.id, self.table_b.id)),
            labels,
        )
        self.assertIn(("solid", (self.solid_a.id,), (self.solids_b.id, self.diagram_b.id)), labels)
        self.assertIn(
            (heading_key("Everyday Examples"), (self.examples_a.id,), (self.examples_b.id, self.examples_table.id)),
            labels,
        )
        self.assertFalse(any(label == "matter" for label, _, _ in labels))
        self.assertFalse(any(label == heading_key("Changing From One State to Another") for label, _, _ in labels))

    def test_a_unit_whose_members_already_agree_across_pdfs_is_not_proposed(self):
        self.solids_b.group = self.solid_a.group
        self.solids_b.save(update_fields=["group"])
        self.diagram_b.group = self.liquid_a.group
        self.diagram_b.save(update_fields=["group"])

        labels = self._labels(heading_unit_candidates(self.topic))

        self.assertFalse(any(label == "solid" for label, _, _ in labels))

    def test_an_ambiguous_label_is_not_proposed(self):
        self._object(self.a, "Solid", "", 9)

        labels = self._labels(heading_unit_candidates(self.topic))

        self.assertFalse(any(label == "solid" for label, _, _ in labels))


SEMANTIC_ENV = {
    "SEMANTIC_GROUPING_MODE": "auto",
    "SEMANTIC_GROUPING_CALIBRATION": "",
    "SEMANTIC_GROUPING_AUTO_THRESHOLD": "",
    "SEMANTIC_GROUPING_REVIEW_THRESHOLD": "",
    "SEMANTIC_GROUPING_MINIMUM_SBERT_COSINE": "",
    "SEMANTIC_GROUPING_MINIMUM_MARGIN": "",
}


class SuggestionTests(UnitFixture):
    def _refresh(self, score=0.5):
        runtime = FakeRuntime()
        runtime.pair_scores = lambda pairs: [score for _ in pairs]
        with patch.dict(os.environ, SEMANTIC_ENV):
            return refresh_heading_unit_suggestions(self.topic, runtime_instance=runtime)

    def test_suggestions_are_pending_and_carry_every_member(self):
        self._refresh()

        suggestion = LearningObjectMatchSuggestion.objects.get(
            evidence__label=heading_key("Comparing the Three States"),
        )
        self.assertEqual(suggestion.status, LearningObjectMatchSuggestion.Status.PENDING)
        self.assertEqual(suggestion.evidence["method"], "heading_unit_v1")
        members = {suggestion.source_learning_object_id, suggestion.candidate_learning_object_id,
                   *suggestion.source_extra_ids, *suggestion.candidate_extra_ids}
        self.assertEqual(members, {self.shape.id, self.volume.id, self.compare_b.id, self.table_b.id})

    def test_a_score_below_the_review_threshold_proposes_nothing(self):
        self._refresh(score=0.1)

        self.assertFalse(LearningObjectMatchSuggestion.objects.exists())

    def test_even_a_high_score_never_merges_automatically(self):
        self._refresh(score=0.99)

        self.assertEqual(self.a.learning_objects.count(), 6)
        self.assertFalse(
            LearningObjectMatchSuggestion.objects.exclude(
                status=LearningObjectMatchSuggestion.Status.PENDING,
            ).exists()
        )

    def test_a_rejected_unit_suggestion_is_not_reopened(self):
        self._refresh()
        LearningObjectMatchSuggestion.objects.update(status=LearningObjectMatchSuggestion.Status.REJECTED)

        self._refresh()

        self.assertFalse(
            LearningObjectMatchSuggestion.objects.filter(status=LearningObjectMatchSuggestion.Status.PENDING).exists()
        )

    def test_accepting_merges_both_sides_and_connects_them(self):
        self._refresh()
        suggestion = LearningObjectMatchSuggestion.objects.get(
            evidence__label=heading_key("Comparing the Three States"),
        )
        client = authenticated_api_client()

        response = client.post(
            f"/api/courses/{self.course.id}/outline-nodes/{self.topic.id}/match-suggestions/{suggestion.id}/accept/",
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        merged_a = LearningObject.objects.get(pk=self.shape.id)
        merged_b = LearningObject.objects.get(pk=self.compare_b.id)
        self.assertEqual(merged_a.title, "Comparing the Three States")
        self.assertEqual(len(merged_a.merged_from), 2)
        self.assertEqual(len(merged_b.merged_from), 2)
        self.assertEqual(merged_a.group_id, merged_b.group_id)
        self.assertFalse(LearningObject.objects.filter(pk__in=[self.volume.id, self.table_b.id]).exists())
