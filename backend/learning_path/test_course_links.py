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
