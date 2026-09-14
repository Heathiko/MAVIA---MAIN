"""The two endpoints: the review preview and the published path.

The published path is the contract the adaptive rules read, so its shape is
pinned here, including that students never receive correct answers.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from course.models import LessonVariant
from lessons.models import CourseGroup, LearningMaterial, LearningObject, LearningObjectGroup, OutlineNode
from question_generation.models import GeneratedQuestion

from .models import ConceptPrerequisite, LearningPathStep
from .services import get_published_path


class TopicFixture(TestCase):
    def setUp(self):
        self.course = CourseGroup.objects.create(title="Grade 1 Science")
        self.topic = OutlineNode.objects.create(course=self.course, title="Solid, Liquid and Gas", order=0, depth=0)
        self.material = LearningMaterial.objects.create(
            course=self.course, outline_node=self.topic, title="Lesson one",
            generated_json={"learning_objects_confirmed": True},
        )
        self.objects, self.groups = {}, {}
        for order, title in enumerate(["Matter", "Solid", "Liquid"]):
            group = LearningObjectGroup.objects.create(outline_node=self.topic, label=title)
            self.objects[title] = LearningObject.objects.create(
                material=self.material, group=group, title=title,
                content=f"{title} is taught here.", order=order,
            )
            self.groups[title] = group

    def _client(self, role=None):
        client = APIClient()
        if role:
            user = get_user_model().objects.create(
                username=f"user-{role.lower()}", email=f"{role.lower()}@example.com", role=role,
            )
            client.force_authenticate(user=user)
        return client

    def _link(self, before, after, status):
        return ConceptPrerequisite.objects.create(
            outline_node=self.topic, prerequisite=self.groups[before], dependent=self.groups[after],
            status=status, source="teacher" if status in ("approved", "rejected") else "derived",
        )


class TopicPreviewTests(TopicFixture):
    def _path(self):
        body = self._client().get(f"/api/learning-path/topics/{self.topic.id}/").json()
        return body["paths"][0] if body["paths"] else None

    def test_one_path_for_the_whole_topic(self):
        path = self._path()

        self.assertEqual([step["title"] for step in path["steps"]], ["Matter", "Solid", "Liquid"])
        self.assertEqual(path["diagnostics"]["ordering"], "document_order")

    def test_a_topic_with_no_grouped_content_has_no_path(self):
        empty = OutlineNode.objects.create(course=self.course, title="Empty", order=1, depth=0)

        body = self._client().get(f"/api/learning-path/topics/{empty.id}/").json()

        self.assertEqual(body["paths"], [])

    def test_the_preview_follows_stored_links(self):
        self._link("Liquid", "Solid", "approved")

        path = self._path()

        self.assertEqual([step["title"] for step in path["steps"]], ["Matter", "Liquid", "Solid"])
        self.assertEqual(path["diagnostics"]["ordering"], "prerequisite_links")
        solid = next(step for step in path["steps"] if step["title"] == "Solid")
        self.assertEqual(solid["prerequisite_ids"], [self.objects["Liquid"].id])

    def test_pending_and_rejected_links_do_not_shape_the_preview(self):
        self._link("Liquid", "Matter", "pending")
        self._link("Solid", "Matter", "rejected")

        path = self._path()

        self.assertEqual(path["steps"][0]["title"], "Matter")
        self.assertEqual(path["edges"], [])


class PublishedPathTests(TopicFixture):
    def setUp(self):
        super().setUp()
        now = timezone.now()
        for position, title in enumerate(["Matter", "Solid", "Liquid"], start=1):
            LearningPathStep.objects.create(
                outline_node=self.topic, concept=self.groups[title], position=position,
                depth=0 if title == "Matter" else 1, published_at=now,
            )
        self._link("Matter", "Solid", "accepted")
        self._link("Matter", "Liquid", "approved")
        self._link("Solid", "Liquid", "pending")
        LessonVariant.objects.create(
            learning_object=self.objects["Solid"], variant="SIMPLIFIED", narration="Solids keep shape.",
        )
        GeneratedQuestion.objects.create(
            node=self.objects["Solid"], question_text="Does a solid keep its shape?",
            question_format="TF", correct_answer="True", explanation="Its particles are fixed.",
            bloom_level="remember", thinking_order="LOT", difficulty="easy", status="final",
        )
        GeneratedQuestion.objects.create(
            node=self.objects["Solid"], question_text="A draft", question_format="TF",
            correct_answer="True", status="draft",
        )

    def _get(self, role):
        return self._client(role).get(f"/api/learning-path/topics/{self.topic.id}/published/")

    def test_signing_in_is_required(self):
        self.assertIn(self._client().get(f"/api/learning-path/topics/{self.topic.id}/published/").status_code, (401, 403))

    def test_steps_arrive_in_saved_order_with_their_content(self):
        body = self._get("TEACHER").json()

        self.assertEqual([step["title"] for step in body["steps"]], ["Matter", "Solid", "Liquid"])
        solid = body["steps"][1]
        self.assertEqual(solid["position"], 2)
        self.assertEqual(solid["depth"], 1)
        self.assertEqual(solid["concept_id"], self.groups["Solid"].id)
        self.assertEqual(solid["versions"]["normal"]["text"], "Solid is taught here.")
        self.assertEqual(solid["versions"]["simplified"]["text"], "Solids keep shape.")
        self.assertIsNone(solid["versions"]["elaborated"])
        self.assertEqual(solid["sources"], [{"material_id": self.material.id, "title": "Lesson one"}])

    def test_only_final_questions_are_served(self):
        questions = self._get("TEACHER").json()["steps"][1]["questions"]

        self.assertEqual([question["text"] for question in questions], ["Does a solid keep its shape?"])

    def test_prerequisites_are_accepted_and_approved_links_only(self):
        steps = {step["title"]: step for step in self._get("TEACHER").json()["steps"]}

        self.assertEqual(steps["Solid"]["prerequisites"], [self.groups["Matter"].id])
        self.assertEqual(steps["Liquid"]["prerequisites"], [self.groups["Matter"].id])
        self.assertEqual(steps["Matter"]["leads_to"], [self.groups["Solid"].id, self.groups["Liquid"].id])

    def test_teachers_receive_answers(self):
        body = self._get("TEACHER").json()

        self.assertTrue(body["includes_answers"])
        self.assertEqual(body["steps"][1]["questions"][0]["correct_answer"], "True")

    def test_students_never_receive_answers(self):
        body = self._get("STUDENT").json()

        self.assertFalse(body["includes_answers"])
        question = body["steps"][1]["questions"][0]
        self.assertNotIn("correct_answer", question)
        self.assertNotIn("explanation", question)

    def test_an_unpublished_topic_has_no_published_path(self):
        LearningPathStep.objects.filter(outline_node=self.topic).delete()

        response = self._get("STUDENT")

        self.assertEqual(response.status_code, 404)
        self.assertIsNone(get_published_path(self.topic))

    def test_the_python_function_and_the_api_agree(self):
        body = self._get("TEACHER").json()

        self.assertEqual(
            [step["concept_id"] for step in body["steps"]],
            [step["concept_id"] for step in get_published_path(self.topic)["steps"]],
        )
