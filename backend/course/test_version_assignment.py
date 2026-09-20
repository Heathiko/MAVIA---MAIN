from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
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
    assign_group_versions,
    assign_source_to_slot,
    choose_representative,
    clean_group_label,
    set_bundle_role,
    version_bundles,
)


SHORT = "Solid has a fixed shape. It holds its form. It does not flow."
LONG = (
    "A solid is a state of matter that maintains a fixed shape and a fixed volume. "
    "The particles inside it are packed tightly together in a regular arrangement. "
    "Because those particles cannot move past one another, a solid does not flow."
)
MIDDLING = "A solid keeps its shape. The particles are packed closely. It will not flow away."


class VersionAssignmentTests(TestCase):
    def setUp(self):
        self.course = CourseGroup.objects.create(title="Grade 1 Science")
        self.node = OutlineNode.objects.create(
            course=self.course, title="Matter", order=0, depth=0
        )
        self.group = LearningObjectGroup.objects.create(outline_node=self.node)
        self.now = timezone.now()

    def _material(self, title, minutes_offset):
        material = LearningMaterial.objects.create(
            course=self.course, outline_node=self.node, title=title
        )
        LearningMaterial.objects.filter(pk=material.pk).update(
            created_at=self.now + timedelta(minutes=minutes_offset)
        )
        material.refresh_from_db()
        return material

    def _object(self, material, content, title="Solid"):
        return LearningObject.objects.create(
            material=material, group=self.group, title=title, content=content, order=0
        )

    def test_representative_is_the_earliest_uploaded_member(self):
        first = self._object(self._material("PDF one", 0), SHORT)
        second = self._object(self._material("PDF two", 5), LONG)
        self.assertEqual(choose_representative([second, first]), first)

    def test_group_label_cleaner_removes_only_structural_title_markers(self):
        self.assertEqual(clean_group_label("3.1 Matter (Part 1 of 2)"), "Matter")
        self.assertEqual(clean_group_label("Lesson 4: Properties of Gases"), "Properties of Gases")
        self.assertEqual(clean_group_label("3D Shapes"), "3D Shapes")

    def test_singleton_uses_its_cleaned_title_as_group_label(self):
        self._object(
            self._material("PDF one", 0),
            SHORT,
            title="2.1 Solid (Part 1 of 3)",
        )

        assign_group_versions(self.group)

        self.group.refresh_from_db()
        self.assertEqual(self.group.label, "Solid")

    @patch("course.version_assignment.classify_group_versions")
    def test_group_uses_cleaned_llm_selected_normal_title(self, classify):
        first = self._object(
            self._material("PDF one", 0), SHORT, title="1. Solid (Part 1 of 2)"
        )
        second = self._object(
            self._material("PDF two", 5), LONG, title="2. Properties of Solids (Part 2 of 2)"
        )
        classify.return_value = {
            first.id: {"slot": "SIMPLIFIED", "confidence": 0.96, "reason": "Shorter."},
            second.id: {"slot": "ORIGINAL", "confidence": 0.94, "reason": "Balanced."},
        }

        assign_group_versions(self.group, use_llm=True)

        self.group.refresh_from_db()
        self.assertEqual(self.group.label, "Properties of Solids")

    @patch("course.version_assignment.classify_group_versions")
    def test_teacher_group_label_is_not_overwritten(self, classify):
        self.group.label = "Teacher's concept name"
        self.group.version_selection = {"label_locked": True}
        self.group.save(update_fields=["label", "version_selection"])
        first = self._object(self._material("PDF one", 0), SHORT, title="Solid Part 1 of 2")
        second = self._object(self._material("PDF two", 5), LONG, title="Solid Part 2 of 2")
        classify.return_value = {
            first.id: {"slot": "ORIGINAL", "confidence": 0.95, "reason": "Balanced."},
            second.id: {"slot": "ELABORATED", "confidence": 0.95, "reason": "Longer."},
        }

        assign_group_versions(self.group, use_llm=True)

        self.group.refresh_from_db()
        self.assertEqual(self.group.label, "Teacher's concept name")

    def test_legacy_custom_group_label_is_inferred_as_teacher_written(self):
        self.group.label = "States of Matter"
        self.group.save(update_fields=["label"])
        self._object(self._material("PDF one", 0), SHORT, title="Solid (Part 1 of 1)")

        assign_group_versions(self.group)

        self.group.refresh_from_db()
        self.assertEqual(self.group.label, "States of Matter")
        self.assertTrue(self.group.version_selection["label_locked"])

    @patch("course.version_assignment.classify_group_versions")
    def test_llm_and_readability_agreement_is_assigned_with_provenance(self, classify):
        first = self._object(self._material("PDF one", 0), SHORT)
        second = self._object(self._material("PDF two", 5), LONG)
        classify.return_value = {
            first.id: {"slot": "ORIGINAL", "confidence": 0.93, "reason": "Balanced."},
            second.id: {"slot": "ELABORATED", "confidence": 0.94, "reason": "More explanation."}
        }

        result = assign_group_versions(self.group, use_llm=True)

        self.assertEqual(result["representative_id"], first.id)
        self.assertEqual(len(result["assigned"]), 1)
        self.assertEqual(result["needs_confirmation"], [])

        # Changed 2026-09-20: roles are per bundle; a PDF-supplied version is its own objects.
        self.assertEqual(result["bundle_roles"], {second.material_id: "ELABORATED"})
        self.assertFalse(LessonVariant.objects.filter(learning_object=first).exists())
        self.assertEqual(
            self.group.version_selection["bundle_roles_assigned_by"][str(second.material_id)],
            "llm_validated",
        )
        self.assertTrue(result["classification_complete"])

        # The model result is durable: opening the review payload again does
        # not make another expensive classification request.
        self.group.refresh_from_db()
        refreshed = assign_group_versions(self.group)
        self.assertTrue(refreshed["classification_complete"])
        self.assertEqual(refreshed["representative_id"], first.id)
        classify.assert_called_once()

    @patch("course.version_assignment.classify_group_versions")
    def test_llm_classification_is_applied_when_readability_disagrees(self, classify):
        first = self._object(self._material("PDF one", 0), SHORT)
        second = self._object(self._material("PDF two", 5), LONG)
        classify.return_value = {
            first.id: {"slot": "ORIGINAL", "confidence": 0.93, "reason": "Balanced."},
            second.id: {"slot": "SIMPLIFIED", "confidence": 0.99, "reason": "Model guess."}
        }

        result = assign_group_versions(self.group, use_llm=True)

        self.assertEqual(result["needs_confirmation"], [])
        self.assertEqual(result["assigned"][0]["slot"], "SIMPLIFIED")
        # Changed 2026-09-20: roles are per bundle; a PDF-supplied version is its own objects.
        self.assertEqual(result["bundle_roles"], {second.material_id: "SIMPLIFIED"})

    @patch("course.version_assignment.classify_group_versions")
    def test_grouped_original_is_selected_by_llm_not_upload_order(self, classify):
        first = self._object(self._material("PDF one", 0), SHORT)
        second = self._object(self._material("PDF two", 5), LONG)
        classify.return_value = {
            first.id: {"slot": "SIMPLIFIED", "confidence": 0.96, "reason": "Clearer."},
            second.id: {"slot": "ORIGINAL", "confidence": 0.94, "reason": "Balanced."},
        }

        result = assign_group_versions(self.group, use_llm=True)

        self.assertEqual(result["representative_id"], second.id)
        # Changed 2026-09-20: roles are per bundle; a PDF-supplied version is its own objects.
        self.assertEqual(result["bundle_roles"], {first.material_id: "SIMPLIFIED"})

    @patch("course.version_assignment.classify_group_versions")
    def test_llm_extra_is_stored_automatically(self, classify):
        first = self._object(self._material("PDF one", 0), SHORT)
        second = self._object(self._material("PDF two", 5), MIDDLING)
        classify.return_value = {
            first.id: {"slot": "ORIGINAL", "confidence": 0.91, "reason": "Baseline."},
            second.id: {"slot": "EXTRA", "confidence": 0.72, "reason": "Equivalent wording."},
        }

        result = assign_group_versions(self.group, use_llm=True)

        self.assertEqual(result["needs_confirmation"], [])
        # Changed 2026-09-20: roles are per bundle; a PDF-supplied version is its own objects.
        self.assertEqual(result["bundle_roles"], {second.material_id: "EXTRA"})
        self.assertEqual(result["extras"], 1)

    def test_thin_margin_is_routed_to_the_teacher_for_confirmation(self):
        first = self._object(self._material("PDF one", 0), SHORT)
        self._object(self._material("PDF two", 5), MIDDLING)

        result = assign_group_versions(self.group)

        self.assertEqual(result["assigned"], [])
        self.assertEqual(len(result["needs_confirmation"]), 1)
        self.assertFalse(result["needs_confirmation"][0]["confident"])
        self.assertFalse(result["classification_complete"])
        self.assertFalse(LessonVariant.objects.filter(learning_object=first).exists())

    @patch("course.version_assignment.classify_group_versions")
    def test_a_bundle_the_model_skipped_is_asked_about_again(self, classify):
        """A run is only complete when every bundle was actually ruled on.

        Recording a partial run as complete would turn the readability guess
        for the bundle Gemma ignored into a settled decision, and the teacher
        would never be asked about it again.
        """
        first = self._object(self._material("PDF one", 0), SHORT)
        second = self._object(self._material("PDF two", 5), LONG)
        third = self._object(self._material("PDF three", 10), MIDDLING)
        classify.return_value = {
            first.id: {"slot": "ORIGINAL", "confidence": 0.93, "reason": "Balanced."},
            second.id: {"slot": "ELABORATED", "confidence": 0.94, "reason": "Fuller."},
        }

        result = assign_group_versions(self.group, use_llm=True)

        self.assertFalse(result["classification_complete"])
        self.assertEqual(
            [entry["material_id"] for entry in result["needs_confirmation"]],
            [third.material_id],
        )

        self.group.refresh_from_db()
        again = assign_group_versions(self.group)

        self.assertEqual(
            [entry["material_id"] for entry in again["needs_confirmation"]],
            [third.material_id],
        )
        # The bundle Gemma did rule on keeps its role.
        self.assertEqual(again["bundle_roles"][second.material_id], "ELABORATED")

    @patch("course.version_assignment.classify_group_versions")
    def test_a_displaced_automatic_role_keeps_its_own_provenance(self, classify):
        """Displacement is not a teacher's ruling about the bundle displaced.

        Stamping it as the teacher's would freeze a readability guess the
        teacher never saw, and no later classification could correct it.
        """
        first = self._object(self._material("PDF one", 0), LONG)
        second = self._object(self._material("PDF two", 5), SHORT)
        third = self._object(self._material("PDF three", 10), MIDDLING)
        assign_group_versions(self.group)
        self.group.refresh_from_db()
        self.assertEqual(
            self.group.version_selection["bundle_roles_assigned_by"][str(second.material_id)],
            "heuristic",
        )

        assign_source_to_slot(first, third, "SIMPLIFIED")

        self.group.refresh_from_db()
        provenance = self.group.version_selection["bundle_roles_assigned_by"]
        self.assertEqual(provenance[str(third.material_id)], "teacher")
        self.assertEqual(provenance[str(second.material_id)], "heuristic")

        # Still reclassifiable: a teacher-stamped role would stay an extra.
        classify.return_value = {
            first.id: {"slot": "ORIGINAL", "confidence": 0.9, "reason": "Baseline."},
            second.id: {"slot": "ELABORATED", "confidence": 0.9, "reason": "Fuller."},
            third.id: {"slot": "EXTRA", "confidence": 0.9, "reason": "Alternative."},
        }
        outcome = assign_group_versions(self.group, use_llm=True)

        self.assertEqual(
            outcome["bundle_roles"],
            {second.material_id: "ELABORATED", third.material_id: "SIMPLIFIED"},
        )

    def test_the_newest_teacher_decision_wins_a_contested_slot(self):
        """Two teacher rulings cannot both hold one slot.

        The later ruling is the teacher's current intent; the earlier one is
        recorded as displaced rather than as a role they chose.
        """
        first = self._object(self._material("PDF one", 0), LONG)
        second = self._object(self._material("PDF two", 5), SHORT)
        third = self._object(self._material("PDF three", 10), MIDDLING)

        assign_source_to_slot(first, second, "SIMPLIFIED")
        assign_source_to_slot(first, third, "SIMPLIFIED")

        self.group.refresh_from_db()
        roles = self.group.version_selection["bundle_roles"]
        provenance = self.group.version_selection["bundle_roles_assigned_by"]
        self.assertEqual(roles[str(third.material_id)], "SIMPLIFIED")
        self.assertEqual(provenance[str(third.material_id)], "teacher")
        self.assertEqual(roles[str(second.material_id)], "EXTRA")
        self.assertEqual(provenance[str(second.material_id)], "displaced_by_teacher")

    def test_two_teacher_roles_for_one_slot_are_settled_by_recency(self):
        first = self._object(self._material("PDF one", 0), LONG)
        second = self._object(self._material("PDF two", 5), SHORT)
        third = self._object(self._material("PDF three", 10), MIDDLING)
        # Written straight into the record, so nothing displaced either one.
        set_bundle_role(self.group, second.material_id, "SIMPLIFIED")
        set_bundle_role(self.group, third.material_id, "SIMPLIFIED")

        outcome = assign_group_versions(self.group)

        self.assertEqual(outcome["bundle_roles"][third.material_id], "SIMPLIFIED")
        self.assertEqual(outcome["bundle_roles"][second.material_id], "EXTRA")
        self.group.refresh_from_db()
        self.assertEqual(
            self.group.version_selection["bundle_roles_assigned_by"][str(second.material_id)],
            "displaced_by_teacher",
        )
        self.assertEqual(first.id, outcome["representative_id"])

    def test_a_teacher_label_matching_a_section_heading_is_kept(self):
        """A teacher who names a concept after its heading is still a teacher.

        The label this function writes is recorded, so anything else in the
        field was typed by somebody and is never overwritten.
        """
        LearningObject.objects.create(
            material=self._material("PDF one", 0), group=self.group,
            title="Solid", section_title="States of Matter", content=SHORT, order=0,
        )
        self.group.label = "States of Matter"
        self.group.save(update_fields=["label"])

        assign_group_versions(self.group)

        self.group.refresh_from_db()
        self.assertEqual(self.group.label, "States of Matter")
        self.assertTrue(self.group.version_selection["label_locked"])

    def test_a_label_this_module_wrote_is_still_followed(self):
        self._object(self._material("PDF one", 0), SHORT, title="Solid")

        assign_group_versions(self.group)

        self.group.refresh_from_db()
        self.assertEqual(self.group.label, "Solid")
        self.assertEqual(self.group.version_selection["auto_label"], "Solid")
        self.assertFalse(self.group.version_selection.get("label_locked"))

    @patch("course.version_assignment.classify_group_versions")
    def test_slot_collision_keeps_the_larger_margin_and_stores_an_extra(self, classify):
        first = self._object(self._material("PDF one", 0), SHORT)
        bigger = self._object(self._material("PDF two", 5), LONG)
        # Also confidently "elaborated", but by a narrower Flesch-Kincaid
        # margin than LONG, so it loses the slot and becomes an extra.
        smaller = self._object(
            self._material("PDF three", 10),
            "A solid keeps a fixed shape at all times. The particles inside it are packed "
            "together very closely. It cannot flow the way that water does.",
        )

        classify.return_value = {
            first.id: {"slot": "ORIGINAL", "confidence": 0.93, "reason": "Balanced."},
            bigger.id: {"slot": "ELABORATED", "confidence": 0.96, "reason": "Fuller."},
            smaller.id: {"slot": "ELABORATED", "confidence": 0.91, "reason": "Also fuller."},
        }
        result = assign_group_versions(self.group, use_llm=True)

        # Changed 2026-09-20: roles are per bundle; a PDF-supplied version is its own objects.
        self.assertEqual(
            result["bundle_roles"],
            {bigger.material_id: "ELABORATED", smaller.material_id: "EXTRA"},
        )
        self.assertEqual(result["extras"], 1)

    def test_singleton_group_assigns_nothing(self):
        self._object(self._material("PDF one", 0), SHORT)
        result = assign_group_versions(self.group)
        self.assertEqual(result["assigned"], [])
        self.assertEqual(result["needs_confirmation"], [])

    @patch("course.version_assignment.classify_group_versions")
    def test_reassignment_is_idempotent(self, classify):
        first = self._object(self._material("PDF one", 0), SHORT)
        second = self._object(self._material("PDF two", 5), LONG)
        classify.return_value = {
            first.id: {"slot": "ORIGINAL", "confidence": 0.93, "reason": "Balanced."},
            second.id: {"slot": "ELABORATED", "confidence": 0.95, "reason": "Fuller."}
        }

        assign_group_versions(self.group, use_llm=True)
        self.group.refresh_from_db()
        outcome = assign_group_versions(self.group, use_llm=True)

        # Changed 2026-09-20: roles are per bundle; a PDF-supplied version is its own objects.
        self.assertEqual(outcome["bundle_roles"], {second.material_id: "ELABORATED"})
        self.assertFalse(LessonVariant.objects.exists())

    def test_saved_teacher_decision_is_not_returned_for_confirmation_again(self):
        self._object(self._material("PDF one", 0), SHORT)
        second = self._object(self._material("PDF two", 5), MIDDLING)
        # Changed 2026-09-20: roles are per bundle; a PDF-supplied version is its own objects.
        set_bundle_role(self.group, second.material_id, "SIMPLIFIED")

        result = assign_group_versions(self.group)

        self.assertEqual(result["needs_confirmation"], [])
        self.assertEqual(result["assigned"][0]["learning_object_id"], second.id)
        self.assertTrue(result["assigned"][0]["persisted"])

    @patch("course.version_assignment.classify_group_versions")
    def test_old_singleton_generation_does_not_choose_group_baseline(self, classify):
        first = self._object(self._material("First PDF", 0), SHORT)
        LessonVariant.objects.create(learning_object=first, variant="SIMPLIFIED", narration="Previously generated.")
        second = self._object(self._material("New PDF", 5), MIDDLING)
        classify.return_value = {
            first.id: {"slot": "EXTRA", "confidence": 0.9, "reason": "Alternative."},
            second.id: {"slot": "ORIGINAL", "confidence": 0.9, "reason": "Balanced."},
        }
        result = assign_group_versions(self.group, use_llm=True)
        self.assertEqual(result["representative_id"], second.id)
        self.assertFalse(LessonVariant.objects.filter(learning_object=first).exists())
        self.assertEqual(assign_group_versions(self.group)["representative_id"], second.id)


class BundleRoleTests(TestCase):
    """Roles are decided per bundle, not per object.

    One PDF teaches Solid as a section, its diagram and its examples; the other
    as a single passage. The whole bundle takes one role.
    """

    def setUp(self):
        self.course = CourseGroup.objects.create(title="Science")
        self.topic = OutlineNode.objects.create(course=self.course, title="States")
        confirmed = {"learning_objects_confirmed": True}
        self.first = LearningMaterial.objects.create(
            course=self.course, outline_node=self.topic, title="A", generated_json=dict(confirmed))
        self.second = LearningMaterial.objects.create(
            course=self.course, outline_node=self.topic, title="B", generated_json=dict(confirmed))
        self.group = LearningObjectGroup.objects.create(outline_node=self.topic, label="Solid")
        self.normal = LearningObject.objects.create(
            material=self.first, group=self.group, title="Solid", order=0,
            content=(
                "A solid has a definite shape and a definite volume because its constituent "
                "particles occupy fixed positions within a rigid lattice arrangement."
            ),
        )
        self.simple_lead = LearningObject.objects.create(
            material=self.second, group=self.group, title="Solids", order=0, section_title="Solids",
            content="In a solid, bits are packed tight. They stay in place.",
        )
        self.simple_tail = LearningObject.objects.create(
            material=self.second, group=self.group, title="Everyday examples", order=1,
            section_title="Solids", content="Ice cubes. A rock. A book.",
        )

    def test_the_whole_bundle_takes_one_role(self):
        outcome = assign_group_versions(self.group)

        self.assertEqual(outcome["normal_material_id"], self.first.id)
        self.assertEqual(outcome["representative_id"], self.normal.id)
        self.assertEqual(outcome["bundle_roles"], {self.second.id: "SIMPLIFIED"})

    def test_a_pdf_supplied_version_stores_no_copied_text(self):
        assign_group_versions(self.group)

        self.assertFalse(
            LessonVariant.objects.filter(origin=LessonVariant.Origin.SOURCE_PDF).exists()
        )
        self.assertEqual(
            version_bundles(self.group)["SIMPLIFIED"], [self.simple_lead, self.simple_tail],
        )

    def test_a_teacher_role_change_survives_a_refresh(self):
        assign_group_versions(self.group)

        set_bundle_role(self.group, self.second.id, "EXTRA")
        outcome = assign_group_versions(self.group)

        self.assertEqual(outcome["bundle_roles"], {self.second.id: "EXTRA"})

    def test_the_normal_bundle_is_reported_in_document_order(self):
        extra = LearningObject.objects.create(
            material=self.first, group=self.group, title="Particle diagram", order=1,
            section_title="Solid", content="Particles sit in a grid.",
        )

        self.assertEqual(version_bundles(self.group)["NORMAL"], [self.normal, extra])
