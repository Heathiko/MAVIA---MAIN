from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from lessons.models import (
    CourseGroup,
    LearningMaterial,
    LearningObject,
    LearningObjectGroup,
    OutlineNode,
)

from .models import LessonVariant
from .version_assignment import (
    bundle_roles,
    release_from_group,
    release_learning_object,
    settle_group,
)


SHORT = "Solid has a fixed shape. It holds its form. It does not flow."
LONG = (
    "A solid is a state of matter that maintains a fixed shape and a fixed volume. "
    "The particles inside it are packed tightly together in a regular arrangement. "
    "Because those particles cannot move past one another, a solid does not flow."
)
MIDDLING = "A solid keeps its shape. The particles are packed closely. It will not flow away."


@override_settings(
    ADAPTIVE_VARIANT_GENERATION_ENABLED=True,
    ADAPTIVE_VARIANT_LLM_MODEL="gemma3:4b",
)
class RepresentationTests(TestCase):
    def setUp(self):
        classifier_patcher = patch("course.version_assignment.classify_group_versions")
        self.classify_group_versions = classifier_patcher.start()
        self.addCleanup(classifier_patcher.stop)
        def classify(members, representative=None):
            original = representative or members[0]
            return {
                item.id: {
                    "slot": "ORIGINAL" if item.id == original.id else "ELABORATED",
                    "confidence": 0.95,
                    "reason": "Balanced original." if item.id == original.id else "More detailed.",
                }
                for item in members
            }
        self.classify_group_versions.side_effect = classify
        self.course = CourseGroup.objects.create(title="Grade 1 Science")
        self.node = OutlineNode.objects.create(
            course=self.course, title="Matter", order=0, depth=0
        )
        self.group = LearningObjectGroup.objects.create(outline_node=self.node)
        now = timezone.now()
        self.first = self._object("PDF one", now, SHORT)
        self.second = self._object("PDF two", now + timedelta(minutes=5), LONG)

    def _object(self, title, created_at, content):
        material = LearningMaterial.objects.create(
            course=self.course, outline_node=self.node, title=title
        )
        LearningMaterial.objects.filter(pk=material.pk).update(created_at=created_at)
        material.refresh_from_db()
        return LearningObject.objects.create(
            material=material, group=self.group, title="Solid", content=content, order=0
        )

    @patch("course.variant_generator._request_variants")
    def test_partner_is_flagged_and_representative_is_not(self, request_variants):
        request_variants.return_value = {"SIMPLIFIED": "Solid keeps shape.", "ELABORATED": "x"}

        settle_group(self.group)

        self.first.refresh_from_db()
        self.second.refresh_from_db()
        self.assertIsNone(self.first.represented_by)
        self.assertEqual(self.second.represented_by, self.first)

    @patch("course.variant_generator._request_variants")
    def test_gap_is_filled_after_real_text_is_placed(self, request_variants):
        request_variants.return_value = {"SIMPLIFIED": "Solid keeps shape.", "ELABORATED": "ignored"}

        result = settle_group(self.group)

        self.assertEqual(result["generated"], ["SIMPLIFIED"])
        # Changed 2026-09-20: roles are per bundle; a PDF-supplied version is its own objects.
        self.assertEqual(result["bundle_roles"], {self.second.material_id: "ELABORATED"})
        simplified = LessonVariant.objects.get(learning_object=self.first, variant="SIMPLIFIED")
        self.assertEqual(simplified.origin, "generated")
        self.assertFalse(
            LessonVariant.objects.filter(origin=LessonVariant.Origin.SOURCE_PDF).exists()
        )

    @patch("course.variant_generator._request_variants")
    def test_llm_selects_original_and_only_missing_slot_is_generated(self, request_variants):
        self.classify_group_versions.side_effect = None
        self.classify_group_versions.return_value = {
            self.first.id: {"slot": "SIMPLIFIED", "confidence": 0.96, "reason": "Clearer."},
            self.second.id: {"slot": "ORIGINAL", "confidence": 0.94, "reason": "Balanced."},
        }
        request_variants.return_value = {
            "SIMPLIFIED": "ignored",
            "ELABORATED": "A fuller generated explanation.",
        }

        result = settle_group(self.group)

        self.assertEqual(result["representative_id"], self.second.id)
        self.assertEqual(result["generated"], ["ELABORATED"])
        # Changed 2026-09-20: roles are per bundle; a PDF-supplied version is its own objects.
        self.assertEqual(result["bundle_roles"], {self.first.material_id: "SIMPLIFIED"})
        elaborated = LessonVariant.objects.get(
            learning_object=self.second,
            variant="ELABORATED",
        )
        self.assertEqual(elaborated.origin, "generated")

    @patch("course.variant_generator._request_variants")
    def test_release_takes_back_its_own_text_and_drops_generated_rows(self, request_variants):
        request_variants.return_value = {"SIMPLIFIED": "Solid keeps shape.", "ELABORATED": "ignored"}
        settle_group(self.group)

        release_learning_object(self.second)

        self.second.refresh_from_db()
        self.assertIsNone(self.second.represented_by)
        # Changed 2026-09-20: roles are per bundle; a PDF-supplied version is its own objects.
        # The released object supplied the elaborated rung as its own text; no
        # copy of it was ever stored on the original.
        self.assertFalse(
            LessonVariant.objects.filter(origin=LessonVariant.Origin.SOURCE_PDF).exists()
        )
        # The generated rung existed only to complete a triple that no longer
        # has a partner, so it goes too.
        self.assertFalse(
            LessonVariant.objects.filter(learning_object=self.first, origin="generated").exists()
        )

    @patch("course.variant_generator._request_variants")
    def test_release_keeps_text_supplied_by_other_members(self, request_variants):
        request_variants.return_value = {"SIMPLIFIED": "Solid keeps shape.", "ELABORATED": "ignored"}
        third = self._object(
            "PDF three",
            timezone.now() + timedelta(minutes=9),
            "A solid keeps a fixed shape at all times. The particles inside it are packed "
            "together very closely. It cannot flow the way that water does.",
        )
        settle_group(self.group)
        # Changed 2026-09-20: roles are per bundle; a PDF-supplied version is its own objects.
        self.group.refresh_from_db()
        self.assertIn(third.material_id, bundle_roles(self.group))

        release_learning_object(self.second)

        # Another member's teacher-written text is untouched by this release.
        self.group.refresh_from_db()
        self.assertIn(third.material_id, bundle_roles(self.group))

    @patch("course.variant_generator._request_variants")
    def test_llm_classified_member_is_represented_despite_thin_readability_margin(self, request_variants):
        request_variants.return_value = {"SIMPLIFIED": "a", "ELABORATED": "b"}
        LearningObject.objects.filter(pk=self.second.pk).update(group=None)
        middling = self._object(
            "PDF three", timezone.now() + timedelta(minutes=9), MIDDLING
        )

        settle_group(self.group)

        middling.refresh_from_db()
        self.assertEqual(middling.represented_by, self.first)


class ReleaseFromGroupTests(TestCase):
    """Leaving a group must not leave version links pointing across concepts."""

    def setUp(self):
        self.course = CourseGroup.objects.create(title="Grade 1 Science")
        self.node = OutlineNode.objects.create(course=self.course, title="Matter", order=0, depth=0)
        self.group = LearningObjectGroup.objects.create(outline_node=self.node)
        material = LearningMaterial.objects.create(course=self.course, outline_node=self.node, title="PDF")
        self.original = LearningObject.objects.create(
            material=material, group=self.group, title="Solid examples", content=SHORT, order=0,
        )
        self.member = LearningObject.objects.create(
            material=material, group=self.group, title="Liquid examples", content=LONG, order=1,
            represented_by=self.original,
        )
        self.other = LearningObject.objects.create(
            material=material, group=self.group, title="Gas examples", content=MIDDLING, order=2,
            represented_by=self.original,
        )
        # Changed 2026-09-20: roles are per bundle; a PDF-supplied version is its own objects.
        self.generated = LessonVariant.objects.create(
            learning_object=self.original, variant="SIMPLIFIED", narration="Short.",
            origin=LessonVariant.Origin.GENERATED, assigned_by=LessonVariant.AssignedBy.TEACHER,
        )

    def test_a_leaving_member_takes_back_only_its_own_text(self):
        # Changed 2026-09-20: roles are per bundle; a PDF-supplied version is its own objects.
        # All three objects come from one PDF, so the bundle -- and its role --
        # stays behind with the companions; only the flag on the leaver goes.
        outcome = release_from_group(self.member, [self.original, self.other])

        self.member.refresh_from_db()
        self.assertIsNone(self.member.represented_by_id)
        self.assertTrue(LessonVariant.objects.filter(pk=self.generated.pk).exists())
        self.assertEqual(outcome, {"was_original": False, "removed_version_slots": []})

    def test_a_leaving_original_releases_everyone_it_represented(self):
        # Changed 2026-09-20: roles are per bundle; a PDF-supplied version is its own objects.
        self.group.version_selection = {
            "normal_material_id": self.original.material_id,
            "bundle_roles": {str(self.original.material_id): "EXTRA"},
        }
        self.group.save()

        outcome = release_from_group(self.original, [self.member, self.other])

        self.assertTrue(outcome["was_original"])
        self.assertEqual(outcome["removed_version_slots"], ["extra"])
        self.member.refresh_from_db()
        self.other.refresh_from_db()
        self.group.refresh_from_db()
        self.assertIsNone(self.member.represented_by_id)
        self.assertIsNone(self.other.represented_by_id)
        self.assertEqual(self.group.version_selection, {})
        # Generated text, including a teacher's edit, is never removed here.
        self.assertTrue(LessonVariant.objects.filter(pk=self.generated.pk).exists())

    def test_leaving_with_nobody_staying_changes_nothing(self):
        release_from_group(self.member, [])

        self.member.refresh_from_db()
        self.assertEqual(self.member.represented_by_id, self.original.id)


class CrossGroupRepairMigrationTests(TestCase):
    """The one-time repair for links left behind before the fix."""

    def test_links_and_texts_across_concepts_are_removed_and_nothing_else(self):
        from importlib import import_module

        from django.apps import apps

        course = CourseGroup.objects.create(title="Grade 1 Science")
        node = OutlineNode.objects.create(course=course, title="Matter", order=0, depth=0)
        solid_group = LearningObjectGroup.objects.create(outline_node=node)
        liquid_group = LearningObjectGroup.objects.create(outline_node=node)
        material = LearningMaterial.objects.create(course=course, outline_node=node, title="PDF")
        solid = LearningObject.objects.create(
            material=material, group=solid_group, title="Solid", content=SHORT, order=0,
        )
        partner = LearningObject.objects.create(
            material=material, group=solid_group, title="Solids", content=MIDDLING, order=1,
            represented_by=solid,
        )
        # Separated into another concept without its links being undone.
        liquid = LearningObject.objects.create(
            material=material, group=liquid_group, title="Liquid", content=LONG, order=2,
            represented_by=solid,
        )
        stale = LessonVariant.objects.create(
            learning_object=solid, variant="SIMPLIFIED", narration=LONG,
            origin=LessonVariant.Origin.SOURCE_PDF, source_learning_object=liquid,
        )
        valid = LessonVariant.objects.create(
            learning_object=solid, variant="ELABORATED", narration=MIDDLING,
            origin=LessonVariant.Origin.SOURCE_PDF, source_learning_object=partner,
        )

        migration = import_module("course.migrations.0007_repair_cross_group_version_links")
        migration.repair_cross_group_version_links(apps, None)

        liquid.refresh_from_db()
        partner.refresh_from_db()
        self.assertIsNone(liquid.represented_by_id)
        self.assertEqual(partner.represented_by_id, solid.id)
        self.assertFalse(LessonVariant.objects.filter(pk=stale.pk).exists())
        self.assertTrue(LessonVariant.objects.filter(pk=valid.pk).exists())
