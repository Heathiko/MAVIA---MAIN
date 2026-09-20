"""A concept's questions come from the whole Normal bundle.

The Normal track speaks every object of that bundle, so a bank generated from
the lead object alone would ask about a third of what the student hears.
"""

from unittest.mock import patch

from django.test import TestCase

from lessons.models import (
    CourseGroup,
    LearningMaterial,
    LearningObject,
    LearningObjectGroup,
    OutlineNode,
)
from question_generation.services.pipeline import concept_source_text


class BundleQuestionSourceTests(TestCase):
    def setUp(self):
        self.course = CourseGroup.objects.create(title="Science")
        self.topic = OutlineNode.objects.create(course=self.course, title="States")
        self.material = LearningMaterial.objects.create(
            course=self.course, outline_node=self.topic, title="A",
            generated_json={"learning_objects_confirmed": True})
        self.group = LearningObjectGroup.objects.create(outline_node=self.topic, label="Solid")
        self.lead = LearningObject.objects.create(
            material=self.material, group=self.group, title="Solid", order=0,
            content="A solid keeps its shape.")
        self.tail = LearningObject.objects.create(
            material=self.material, group=self.group, title="Everyday examples", order=1,
            section_title="Solid", content="Ice cubes and a rock.")

    def test_the_source_text_is_the_whole_normal_bundle(self):
        self.assertEqual(
            concept_source_text(self.lead),
            "A solid keeps its shape.\nIce cubes and a rock.",
        )

    def test_an_ungrouped_object_uses_its_own_text(self):
        loose = LearningObject.objects.create(
            material=self.material, group=None, title="Loose", order=2, content="On its own.")

        self.assertEqual(concept_source_text(loose), "On its own.")

    def test_the_bank_fingerprint_follows_the_bundle(self):
        from question_generation.services.pipeline import question_bank_fingerprint, QUESTION_DISTRIBUTION

        before = question_bank_fingerprint(concept_source_text(self.lead), QUESTION_DISTRIBUTION)
        self.tail.content = "Ice cubes, a rock and a coin."
        self.tail.save(update_fields=["content"])

        after = question_bank_fingerprint(concept_source_text(self.lead), QUESTION_DISTRIBUTION)
        self.assertNotEqual(before, after)
