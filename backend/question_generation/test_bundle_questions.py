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

    def test_every_telling_of_the_concept_reaches_the_prompt(self):
        """A second PDF's telling is text the learner hears on remediation,
        so questions must be written from it too."""
        other = LearningMaterial.objects.create(
            course=self.course, outline_node=self.topic, title="B",
            generated_json={"learning_objects_confirmed": True})
        LearningObject.objects.create(
            material=other, group=self.group, title="Solids", order=0,
            represented_by=self.lead,
            content="Solid particles vibrate in place.")
        text = concept_source_text(self.lead)
        self.assertIn("A solid keeps its shape.", text)
        self.assertIn("Ice cubes and a rock.", text)
        self.assertIn("Solid particles vibrate in place.", text)

    def test_a_single_telling_concept_is_unchanged(self):
        """10 of topic 276's 19 concepts come from one PDF. They must read
        exactly as before, with no blank lines and nothing duplicated."""
        self.assertEqual(
            concept_source_text(self.lead),
            "A solid keeps its shape.\nIce cubes and a rock.",
        )

    def test_an_extra_bundle_is_not_offered_to_the_generator(self):
        """EXTRA is excluded from what a learner is served (published.py
        _versions, course/services.py _build_chunk), so it is not something
        to write questions about either."""
        extra = LearningMaterial.objects.create(
            course=self.course, outline_node=self.topic, title="C",
            generated_json={"learning_objects_confirmed": True})
        LearningObject.objects.create(
            material=extra, group=self.group, title="Aside", order=0,
            represented_by=self.lead, content="An unrelated aside.")
        self.group.version_selection = {
            "normal_material_id": self.material.id,
            "bundle_roles": {str(extra.id): "EXTRA"},
        }
        self.group.save(update_fields=["version_selection"])
        self.assertNotIn("An unrelated aside.", concept_source_text(self.lead))


class BundleGenerationScopeTests(TestCase):
    """One concept generates one bank, from its Normal bundle's lead.

    Every object of the bundle reads the same source text, so generating per
    object would write the same bank two or three times and charge the teacher
    for each.
    """

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

    def _run(self, **kwargs):
        from question_generation.services import pipeline

        with patch.object(pipeline, "_get_classifier", return_value=object()), patch.object(
            pipeline, "generate_questions_for_node", return_value=[],
        ) as generate_node:
            pipeline.generate_questions_for_material(self.material, **kwargs)
        return generate_node

    def test_a_two_object_bundle_generates_once_from_its_lead(self):
        generate_node = self._run()

        generate_node.assert_called_once()
        self.assertEqual(generate_node.call_args.args[0].id, self.lead.id)

    def test_asking_for_a_non_lead_object_generates_nothing_and_says_so(self):
        """Today's behaviour, pinned rather than endorsed: a bundle member that
        is not the lead has no bank of its own, so an explicit request for it
        does nothing. It is now logged instead of passing in silence."""
        from question_generation.services import pipeline

        with self.assertLogs(pipeline.logger, level="INFO") as logs:
            generate_node = self._run(node_ids=[self.tail.id])

        generate_node.assert_not_called()
        self.assertEqual(self.tail.generated_questions.count(), 0)
        self.assertTrue(
            any("Everyday examples" in line for line in logs.output),
            logs.output,
        )
