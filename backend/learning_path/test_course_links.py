"""Cross-topic concept links: model, derivation storage, roll-up, edits (course spec)."""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from lessons.models import CourseGroup, LearningMaterial, LearningObject, LearningObjectGroup, OutlineNode

from .models import CourseConceptLink, LearningPathStep
from .services.course_links import (
    CourseLinkError,
    course_path,
    decide_course_link,
    refresh_course_links,
    restore_course_links,
)
from .services.published import course_prerequisites
from .testing import word_vectors


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


class CourseLinkEditTests(CourseFixture):
    def setUp(self):
        super().setUp()
        self.link = CourseConceptLink.objects.create(
            course=self.course, prerequisite=self.groups["Stamen"], dependent=self.groups["Pollination"],
            status="pending", evidence={"rule": "course"},
        )

    def test_approving_a_suggestion_records_the_teacher(self):
        undo = decide_course_link(self.course, self.link.id, "approved")

        self.link.refresh_from_db()
        self.assertEqual((self.link.status, self.link.source), ("approved", "teacher"))
        self.assertIsNotNone(self.link.decided_at)
        self.assertEqual(undo[0]["prior"]["status"], "pending")

    def test_undo_puts_the_link_back(self):
        undo = decide_course_link(self.course, self.link.id, "rejected")

        restore_course_links(self.course, undo)

        self.link.refresh_from_db()
        self.assertEqual((self.link.status, self.link.source), ("pending", "derived"))

    def test_only_approve_or_reject(self):
        with self.assertRaises(CourseLinkError):
            decide_course_link(self.course, self.link.id, "accepted")

    def test_a_link_of_another_course_is_not_found(self):
        other = CourseGroup.objects.create(title="Other course")

        with self.assertRaises(CourseLinkError):
            decide_course_link(other, self.link.id, "approved")

    def test_a_malformed_undo_is_refused(self):
        with self.assertRaises(CourseLinkError):
            restore_course_links(self.course, [{"prerequisite_id": "x"}])


class CoursePathApiTests(CourseFixture):
    def _client(self, role):
        user = get_user_model().objects.create(username=f"user-{role}", email=f"{role}@example.com", role=role)
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    def test_a_student_cannot_open_the_course_path(self):
        response = self._client("STUDENT").get(f"/api/learning-path/courses/{self.course.id}/")

        self.assertEqual(response.status_code, 403)

    def test_a_teacher_gets_topics_and_arrows(self):
        with patch("learning_path.services.embeddings.embed", word_vectors):
            response = self._client("TEACHER").get(f"/api/learning-path/courses/{self.course.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["topics"]), 4)
        self.assertEqual(len(response.data["arrows"]), 1)

    def test_a_decision_returns_the_path_and_an_undo(self):
        link = CourseConceptLink.objects.create(
            course=self.course, prerequisite=self.groups["Stamen"], dependent=self.groups["Pollination"], status="pending",
        )
        client = self._client("TEACHER")

        response = client.post(
            f"/api/learning-path/courses/{self.course.id}/links/{link.id}/decision/", {"status": "approved"}, format="json",
        )
        restored = client.post(
            f"/api/learning-path/courses/{self.course.id}/links/restore/", {"undo": response.data["undo"]}, format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(restored.status_code, 200)
        link.refresh_from_db()
        self.assertEqual(link.status, "pending")

    def test_an_unknown_course_is_404(self):
        response = self._client("TEACHER").get("/api/learning-path/courses/999999/")

        self.assertEqual(response.status_code, 404)


class CoursePrerequisiteTests(CourseFixture):
    def setUp(self):
        super().setUp()
        for topic in (self.flowers, self.reproduction):
            OutlineNode.objects.filter(pk=topic.pk).update(published=True)
        now = timezone.now()
        LearningPathStep.objects.create(outline_node=self.flowers, concept=self.groups["Stamen"], position=1, depth=0, published_at=now)
        LearningPathStep.objects.create(outline_node=self.reproduction, concept=self.groups["Pollination"], position=1, depth=0, published_at=now)

    def _link(self, before, after, status):
        return CourseConceptLink.objects.create(
            course=self.course, prerequisite=self.groups[before], dependent=self.groups[after], status=status,
        )

    def _for(self, topic, title):
        topic.refresh_from_db()
        return course_prerequisites(topic, {self.groups[title].id}).get(self.groups[title].id, [])

    def test_an_accepted_link_from_an_earlier_topic_is_published(self):
        self._link("Stamen", "Pollination", "accepted")

        self.assertEqual(self._for(self.reproduction, "Pollination"), [{
            "topic_id": self.flowers.id, "concept_id": self.groups["Stamen"].id, "position": 1, "status": "accepted",
        }])

    def test_pending_and_rejected_links_are_never_published(self):
        self._link("Stamen", "Pollination", "pending")

        self.assertEqual(self._for(self.reproduction, "Pollination"), [])

    def test_an_approved_link_from_a_later_topic_is_never_published(self):
        self._link("Pollination", "Stamen", "approved")

        self.assertEqual(self._for(self.flowers, "Stamen"), [])

    def test_a_prerequisite_in_an_unpublished_topic_is_never_published(self):
        OutlineNode.objects.filter(pk=self.flowers.pk).update(published=False)
        self._link("Stamen", "Pollination", "accepted")

        self.assertEqual(self._for(self.reproduction, "Pollination"), [])
