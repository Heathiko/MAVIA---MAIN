"""Cross-topic concept links: model, derivation storage, roll-up, edits (course spec)."""

from django.db import IntegrityError
from django.test import TestCase

from lessons.models import CourseGroup, LearningObjectGroup, OutlineNode

from .models import CourseConceptLink


class CourseConceptLinkModelTests(TestCase):
    def test_one_row_per_ordered_pair(self):
        course = CourseGroup.objects.create(title="Grade 1 Science")
        first = OutlineNode.objects.create(course=course, title="Solid, Liquid and Gas", order=0, depth=0)
        second = OutlineNode.objects.create(course=course, title="Changes", order=1, depth=0)
        liquid = LearningObjectGroup.objects.create(outline_node=first, label="Liquid")
        evaporation = LearningObjectGroup.objects.create(outline_node=second, label="Evaporation")
        CourseConceptLink.objects.create(course=course, prerequisite=liquid, dependent=evaporation, status="accepted")

        with self.assertRaises(IntegrityError):
            CourseConceptLink.objects.create(course=course, prerequisite=liquid, dependent=evaporation, status="pending")

    def test_statuses_match_the_topic_links(self):
        self.assertEqual(CourseConceptLink.SHAPES_PATH, ("accepted", "approved"))
        self.assertEqual(CourseConceptLink.TEACHER_DECIDED, ("approved", "rejected"))


from unittest.mock import patch

from lessons.models import LearningMaterial, LearningObject

from .services.course_links import course_path, refresh_course_links
from .testing import word_vectors


class CourseFixture(TestCase):
    """A unit with two topics that build on each other, and an unrelated one."""

    def setUp(self):
        self.course = CourseGroup.objects.create(title="Grade 1 Science")
        unit = OutlineNode.objects.create(course=self.course, title="Plants", order=0, depth=0)
        self.flowers = OutlineNode.objects.create(course=self.course, parent=unit, title="Flower parts", order=0, depth=1)
        self.reproduction = OutlineNode.objects.create(course=self.course, parent=unit, title="Reproduction", order=1, depth=1)
        self.weather = OutlineNode.objects.create(course=self.course, parent=unit, title="Weather", order=2, depth=1)
        self.empty = OutlineNode.objects.create(course=self.course, parent=unit, title="Empty topic", order=3, depth=1)
        self.groups = {}
        for topic, title, content in (
            (self.flowers, "Stamen", "The anther makes pollen grains. The filament is a thin green stalk. The filament holds the anther up high. Each grain carries a male cell."),
            (self.reproduction, "Pollination", "Pollen travels from the stamen anther to a stigma."),
            (self.weather, "Rain", "Clouds bring heavy rain showers today. " * 8),
        ):
            material = LearningMaterial.objects.create(course=self.course, outline_node=topic, title=f"{title} PDF")
            group = LearningObjectGroup.objects.create(outline_node=topic, label=title)
            LearningObject.objects.create(material=material, group=group, title=title, content=content, order=0)
            self.groups[title] = group

    def _refresh(self):
        with patch("learning_path.services.embeddings.embed", word_vectors):
            return refresh_course_links(self.course)


class RefreshCourseLinksTests(CourseFixture):
    def test_links_are_derived_between_topics_that_build_on_each_other(self):
        counts = self._refresh()

        link = CourseConceptLink.objects.get()
        self.assertEqual((link.prerequisite, link.dependent), (self.groups["Stamen"], self.groups["Pollination"]))
        self.assertEqual(link.status, "accepted")
        self.assertEqual(counts["accepted"], 1)

    def test_a_teacher_rejection_is_never_overwritten(self):
        self._refresh()
        CourseConceptLink.objects.update(status="rejected", source="teacher")

        self._refresh()

        self.assertEqual(CourseConceptLink.objects.get().status, "rejected")

    def test_a_link_the_criteria_stop_producing_is_removed(self):
        self._refresh()
        LearningObject.objects.filter(group=self.groups["Pollination"]).update(content="Seeds grow slowly inside a fruit.")

        self._refresh()

        self.assertFalse(CourseConceptLink.objects.exists())

    def test_a_course_with_one_topic_of_content_gets_no_links(self):
        LearningObjectGroup.objects.exclude(outline_node=self.flowers).delete()

        self.assertEqual(self._refresh(), {"accepted": 0, "pending": 0, "teacher_decided": 0})


class CoursePathTests(CourseFixture):
    def test_every_outline_topic_is_listed_in_order(self):
        path = course_path(self.course)

        self.assertEqual(
            [(topic["title"], topic["has_content"]) for topic in path["topics"]],
            [("Flower parts", True), ("Reproduction", True), ("Weather", True), ("Empty topic", False)],
        )

    def test_concept_links_roll_up_into_one_arrow_per_topic_pair(self):
        self._refresh()

        [arrow] = course_path(self.course)["arrows"]

        self.assertEqual((arrow["from_topic"], arrow["to_topic"]), (self.flowers.id, self.reproduction.id))
        self.assertEqual((arrow["shaping"], arrow["pending"], arrow["contradicts_outline"]), (1, 0, False))
        self.assertEqual(arrow["links"][0]["prerequisite"]["title"], "Stamen")
        self.assertTrue(arrow["links"][0]["reason"])

    def test_rejected_links_are_not_shown(self):
        self._refresh()
        CourseConceptLink.objects.update(status="rejected", source="teacher")

        self.assertEqual(course_path(self.course)["arrows"], [])

    def test_a_deleted_concept_takes_its_links_with_it(self):
        self._refresh()
        self.groups["Pollination"].delete()

        self.assertEqual(course_path(self.course)["arrows"], [])
