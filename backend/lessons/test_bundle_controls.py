"""The teacher's corrections to an automatic bundle.

Bundles are placed without asking, so every correction is a plain button: move
an object out, move it to another concept, or change its place in the bundle.
"""

from django.test import TestCase

from course.models import LessonVariant
from course.version_assignment import set_bundle_role

from .models import (
    CourseGroup,
    LearningMaterial,
    LearningObject,
    LearningObjectGroup,
    OutlineNode,
)
from .tests import authenticated_api_client


class BundleControlFixture(TestCase):
    def setUp(self):
        self.course = CourseGroup.objects.create(title="Science")
        self.topic = OutlineNode.objects.create(course=self.course, title="States")
        confirmed = {"learning_objects_confirmed": True}
        self.first = LearningMaterial.objects.create(
            course=self.course, outline_node=self.topic, title="A", generated_json=dict(confirmed))
        self.second = LearningMaterial.objects.create(
            course=self.course, outline_node=self.topic, title="B", generated_json=dict(confirmed))
        self.group = LearningObjectGroup.objects.create(outline_node=self.topic, label="Solid")
        self.solid = LearningObject.objects.create(
            material=self.first, group=self.group, title="Solid", order=0,
            content="A solid keeps its shape.")
        self.solids = LearningObject.objects.create(
            material=self.second, group=self.group, title="Solids", order=0,
            section_title="Solids", content="Packed tightly.")
        self.diagram = LearningObject.objects.create(
            material=self.second, group=self.group, title="Diagram description", order=1,
            section_title="Solids", content="Particles drawn in a grid.")

    def _url(self, suffix):
        return f"/api/courses/{self.course.id}/outline-nodes/{self.topic.id}/{suffix}"


class MoveOutTests(BundleControlFixture):
    def test_move_out_gives_the_object_its_own_concept(self):
        client = authenticated_api_client()

        response = client.post(self._url(f"learning-objects/{self.diagram.id}/move-out/"), format="json")

        self.assertEqual(response.status_code, 200, response.data)
        self.diagram.refresh_from_db()
        self.assertNotEqual(self.diagram.group_id, self.solid.group_id)
        self.assertEqual(self.diagram.group.learning_objects.count(), 1)


class MoveToTests(BundleControlFixture):
    def test_move_to_puts_the_object_in_the_named_concept(self):
        other = LearningObjectGroup.objects.create(outline_node=self.topic, label="Liquid")
        client = authenticated_api_client()

        response = client.post(
            self._url(f"learning-objects/{self.diagram.id}/move-to/"),
            {"group_id": other.id}, format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.diagram.refresh_from_db()
        self.assertEqual(self.diagram.group_id, other.id)

    def test_move_to_rejects_a_concept_from_another_topic(self):
        elsewhere = OutlineNode.objects.create(course=self.course, title="Other", order=1)
        foreign = LearningObjectGroup.objects.create(outline_node=elsewhere, label="Nope")
        client = authenticated_api_client()

        response = client.post(
            self._url(f"learning-objects/{self.diagram.id}/move-to/"),
            {"group_id": foreign.id}, format="json",
        )

        self.assertEqual(response.status_code, 400)


class ReorderTests(BundleControlFixture):
    def test_reorder_swaps_with_the_neighbour_in_the_same_bundle(self):
        client = authenticated_api_client()

        response = client.post(
            self._url(f"learning-objects/{self.diagram.id}/reorder/"),
            {"direction": "up"}, format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.solids.refresh_from_db()
        self.diagram.refresh_from_db()
        self.assertLess(self.diagram.order, self.solids.order)

    def test_reorder_at_the_edge_is_a_no_op(self):
        client = authenticated_api_client()

        response = client.post(
            self._url(f"learning-objects/{self.solids.id}/reorder/"),
            {"direction": "up"}, format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.solids.refresh_from_db()
        self.assertEqual(self.solids.order, 0)


class PayloadTests(BundleControlFixture):
    def _group_row(self, response):
        return next(
            row for row in response.data["learning_object_groups"] if row["id"] == self.solid.group_id
        )

    def test_the_payload_lists_bundles_per_pdf_in_order(self):
        client = authenticated_api_client()

        response = client.get(self._url("learning-resources/"))

        group = self._group_row(response)
        bundles = {row["material"]: [item["id"] for item in row["learning_objects"]] for row in group["bundles"]}
        self.assertEqual(bundles[self.first.id], [self.solid.id])
        self.assertEqual(bundles[self.second.id], [self.solids.id, self.diagram.id])

    def test_a_pdf_supplied_simplified_fills_its_slot(self):
        """A version a PDF supplies writes no ``LessonVariant`` row.

        Building the slots from the variant table alone therefore showed the
        concept an empty Simplified and refused to call it complete.
        """
        set_bundle_role(self.group, self.second.id, "SIMPLIFIED")
        LessonVariant.objects.create(
            learning_object=self.solid,
            variant="ELABORATED",
            narration="A solid holds its own shape because its particles barely move.",
            origin=LessonVariant.Origin.GENERATED,
        )
        client = authenticated_api_client()

        response = client.get(self._url("learning-resources/"))

        versions = self._group_row(response)["versions"]
        simplified = versions["slots"]["simplified"]
        self.assertIn("Packed tightly.", simplified["text"])
        self.assertIn("Particles drawn in a grid.", simplified["text"])
        self.assertEqual(simplified["origin"], LessonVariant.Origin.SOURCE_PDF)
        self.assertEqual(simplified["source_learning_object_id"], self.solids.id)
        self.assertTrue(versions["complete"])
