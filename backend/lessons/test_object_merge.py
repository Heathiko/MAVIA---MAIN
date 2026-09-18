"""Merging several objects of one PDF into one, and splitting them back.

A concept may be taught as four short items in one PDF and one section in
another. Grouping admits one object per PDF, so the four become one row. The
merge must be fully reversible: split restores metadata ids, order and question
links exactly.
"""

from django.test import TestCase

from course.models import LessonVariant
from question_generation.models import GeneratedQuestion

from .models import (
    CourseGroup,
    LearningMaterial,
    LearningObject,
    LearningObjectGroup,
    OutlineNode,
    Question,
    QuestionLearningObjectLink,
)
from .services.object_merge import (
    MergeError,
    merge_learning_objects,
    merge_text,
    split_learning_object,
)


class MergeFixture(TestCase):
    def setUp(self):
        self.course = CourseGroup.objects.create(title="Science")
        self.topic = OutlineNode.objects.create(course=self.course, title="States")
        self.material = LearningMaterial.objects.create(
            course=self.course, outline_node=self.topic, title="First",
            generated_json={
                "learning_objects_confirmed": True,
                "lesson_playlist": [],
            },
        )
        self.other = LearningMaterial.objects.create(
            course=self.course, outline_node=self.topic, title="Second",
            generated_json={"learning_objects_confirmed": True},
        )
        self.intro = self._object(self.material, "Matter", "Matter has mass.", 0, "Matter")
        self.shape = self._object(self.material, "Shape", "Solids keep their shape.", 1, "Comparing")
        self.volume = self._object(self.material, "Volume", "Gases fill space.", 2, "Comparing")
        self.flow = self._object(self.material, "Flow", "Liquids flow.", 3, "Comparing")
        self.after = self._object(self.material, "Examples", "Ice.", 4, "")
        self.comparing = self._object(self.other, "Comparing", "The table compares.", 0, "Comparing")
        self.material.generated_json["lesson_playlist"] = [
            {"learning_object_id": item.id, "narration": item.content, "audio_url": ""}
            for item in (self.shape, self.volume, self.after)
        ]
        self.material.save(update_fields=["generated_json"])

    def _object(self, material, title, content, order, section):
        group = LearningObjectGroup.objects.create(outline_node=self.topic, label=title)
        return LearningObject.objects.create(
            material=material, group=group, title=title, content=content,
            order=order, section_title=section,
        )

    def _question(self, learning_object, *, primary=True):
        question = Question.objects.create(material=self.material, prompt=f"About {learning_object.title}?")
        QuestionLearningObjectLink.objects.create(
            question=question, learning_object=learning_object, is_primary=primary,
        )
        return question

    def _generated(self, learning_object):
        return GeneratedQuestion.objects.create(
            node=learning_object, question_text="Q?", question_format="TF", correct_answer="True",
        )


class MergeTextTests(MergeFixture):
    def test_each_member_keeps_its_title_as_a_lead_in(self):
        self.assertEqual(
            merge_text([self.shape, self.volume]),
            "Shape: Solids keep their shape.\nVolume: Gases fill space.",
        )


class MergeTests(MergeFixture):
    def test_members_become_one_row_titled_by_their_heading(self):
        kept, _ = merge_learning_objects([self.volume, self.shape, self.flow])

        self.assertEqual(kept.id, self.shape.id)
        self.assertEqual(kept.title, "Comparing")
        self.assertEqual(
            kept.content,
            "Shape: Solids keep their shape.\nVolume: Gases fill space.\nFlow: Liquids flow.",
        )
        self.assertEqual(kept.kind, LearningObject.Kind.TEXT)
        self.assertFalse(LearningObject.objects.filter(pk__in=[self.volume.id, self.flow.id]).exists())
        self.assertEqual([entry["title"] for entry in kept.merged_from], ["Shape", "Volume", "Flow"])

    def test_orders_are_renumbered_without_gaps(self):
        merge_learning_objects([self.shape, self.volume, self.flow])

        rows = list(self.material.learning_objects.order_by("order").values_list("title", "order"))
        self.assertEqual(rows, [("Matter", 0), ("Comparing", 1), ("Examples", 2)])

    def test_question_links_and_generated_questions_move_to_the_kept_row(self):
        question = self._question(self.volume)
        generated = self._generated(self.flow)

        kept, _ = merge_learning_objects([self.shape, self.volume, self.flow])

        self.assertEqual(QuestionLearningObjectLink.objects.get(question=question).learning_object_id, kept.id)
        generated.refresh_from_db()
        self.assertEqual(generated.node_id, kept.id)

    def test_a_duplicate_link_keeps_the_primary_flag(self):
        question = Question.objects.create(material=self.material, prompt="Both?")
        QuestionLearningObjectLink.objects.create(question=question, learning_object=self.shape, is_primary=False)
        QuestionLearningObjectLink.objects.create(question=question, learning_object=self.volume, is_primary=True)

        kept, _ = merge_learning_objects([self.shape, self.volume])

        link = QuestionLearningObjectLink.objects.get(question=question)
        self.assertEqual(link.learning_object_id, kept.id)
        self.assertTrue(link.is_primary)

    def test_versions_and_audio_of_members_are_dropped(self):
        LessonVariant.objects.create(learning_object=self.shape, variant="SIMPLIFIED", narration="Short.")

        merge_learning_objects([self.shape, self.volume])

        self.assertFalse(LessonVariant.objects.filter(learning_object=self.shape).exists())
        self.material.refresh_from_db()
        playlist_ids = [entry["learning_object_id"] for entry in self.material.generated_json["lesson_playlist"]]
        self.assertEqual(playlist_ids, [self.after.id])

    def test_the_member_already_connected_elsewhere_is_kept(self):
        self.comparing.group = self.flow.group
        self.comparing.save(update_fields=["group"])

        kept, _ = merge_learning_objects([self.shape, self.volume, self.flow])

        self.assertEqual(kept.id, self.flow.id)
        self.assertEqual(kept.group_id, self.comparing.group_id)

    def test_two_members_connected_elsewhere_are_refused(self):
        self.comparing.group = self.flow.group
        self.comparing.save(update_fields=["group"])
        extra = self._object(self.other, "Shape too", "Shape.", 1, "")
        extra.group = self.shape.group
        extra.save(update_fields=["group"])

        with self.assertRaises(MergeError):
            merge_learning_objects([self.shape, self.flow])

    def test_objects_from_different_pdfs_are_refused(self):
        with self.assertRaises(MergeError):
            merge_learning_objects([self.shape, self.comparing])

    def test_a_single_object_is_refused(self):
        with self.assertRaises(MergeError):
            merge_learning_objects([self.shape])

    def test_the_title_comes_from_the_first_heading_not_the_first_member(self):
        figure = self._object(self.material, "Okay, let's describe this figure", "A diagram.", 0, "")
        LearningObject.objects.filter(pk=self.intro.pk).update(order=1)
        self.intro.refresh_from_db()

        kept, _ = merge_learning_objects([figure, self.intro])

        self.assertEqual(kept.title, "Matter")
        self.assertEqual(kept.section_title, "Matter")

    def test_members_without_any_heading_keep_the_first_member_title(self):
        figure = self._object(self.material, "A figure", "A diagram.", 5, "")
        tail = self._object(self.material, "Another", "More.", 6, "")

        kept, _ = merge_learning_objects([figure, tail])

        self.assertEqual(kept.title, "A figure")
        self.assertEqual(kept.section_title, "")

    def test_an_explicit_title_wins_over_the_heading(self):
        kept, _ = merge_learning_objects([self.shape, self.volume], title="States of matter")

        self.assertEqual(kept.title, "States of matter")

    def test_the_kept_row_stops_being_taught_through_another_object(self):
        self.comparing.group = self.shape.group
        self.comparing.save(update_fields=["group"])
        LearningObject.objects.filter(pk=self.shape.pk).update(represented_by=self.comparing)
        self.shape.refresh_from_db()

        kept, _ = merge_learning_objects([self.shape, self.volume])

        self.assertEqual(kept.id, self.shape.id)
        self.assertIsNone(kept.represented_by_id)
        self.comparing.refresh_from_db()
        self.assertIsNone(self.comparing.represented_by_id)
        self.assertEqual(self.comparing.group_id, kept.group_id)

    def test_an_unlocked_group_label_follows_the_merged_title(self):
        kept, _ = merge_learning_objects([self.shape, self.volume, self.flow])

        kept.group.refresh_from_db()
        self.assertEqual(kept.group.label, "Comparing")
        self.assertEqual(kept.group.version_selection, {})

    def test_a_locked_group_label_and_its_lock_survive_the_merge(self):
        group = self.shape.group
        group.label = "Teacher's name"
        group.version_selection = {"label_locked": True, "representative_id": 999}
        group.save(update_fields=["label", "version_selection"])

        kept, _ = merge_learning_objects([self.shape, self.volume])

        kept.group.refresh_from_db()
        self.assertEqual(kept.group.label, "Teacher's name")
        self.assertEqual(kept.group.version_selection, {"label_locked": True})

    def test_a_published_topic_is_unpublished(self):
        OutlineNode.objects.filter(pk=self.topic.pk).update(published=True)

        _, unpublished = merge_learning_objects([self.shape, self.volume])

        self.topic.refresh_from_db()
        self.assertTrue(unpublished)
        self.assertFalse(self.topic.published)


class SplitTests(MergeFixture):
    def test_split_restores_rows_ids_titles_and_order(self):
        metadata = {item.title: item.metadata_id for item in (self.shape, self.volume, self.flow)}
        kept, _ = merge_learning_objects([self.shape, self.volume, self.flow])

        restored, _ = split_learning_object(kept)

        self.assertEqual([row.title for row in restored], ["Shape", "Volume", "Flow"])
        self.assertEqual({row.title: row.metadata_id for row in restored}, metadata)
        rows = list(self.material.learning_objects.order_by("order").values_list("title", "order"))
        self.assertEqual(
            rows,
            [("Matter", 0), ("Shape", 1), ("Volume", 2), ("Flow", 3), ("Examples", 4)],
        )
        self.assertTrue(all(row.merged_from == [] for row in restored))

    def test_split_moves_questions_back_including_dropped_duplicates(self):
        moved = self._question(self.volume)
        both = Question.objects.create(material=self.material, prompt="Both?")
        QuestionLearningObjectLink.objects.create(question=both, learning_object=self.shape, is_primary=True)
        QuestionLearningObjectLink.objects.create(question=both, learning_object=self.volume, is_primary=False)
        generated = self._generated(self.volume)
        kept, _ = merge_learning_objects([self.shape, self.volume])

        restored, _ = split_learning_object(kept)

        volume = next(row for row in restored if row.title == "Volume")
        shape = next(row for row in restored if row.title == "Shape")
        self.assertEqual(QuestionLearningObjectLink.objects.get(question=moved).learning_object_id, volume.id)
        self.assertEqual(
            set(QuestionLearningObjectLink.objects.filter(question=both).values_list("learning_object_id", "is_primary")),
            {(shape.id, True), (volume.id, False)},
        )
        generated.refresh_from_db()
        self.assertEqual(generated.node_id, volume.id)

    def test_restored_rows_start_ungrouped(self):
        self.comparing.group = self.shape.group
        self.comparing.save(update_fields=["group"])
        kept, _ = merge_learning_objects([self.shape, self.volume])

        restored, _ = split_learning_object(kept)

        self.assertTrue(all(row.group_id is None for row in restored))
        self.comparing.refresh_from_db()
        self.assertIsNotNone(self.comparing.group_id)

    def test_an_unmerged_object_cannot_be_split(self):
        with self.assertRaises(MergeError):
            split_learning_object(self.shape)


from .tests import authenticated_api_client


class MergeApiTests(MergeFixture):
    def _url(self, suffix):
        return f"/api/courses/{self.course.id}/outline-nodes/{self.topic.id}/{suffix}"

    def test_merge_endpoint_merges_and_returns_the_resources(self):
        client = authenticated_api_client()

        response = client.post(
            self._url("merge-learning-objects/"),
            {"learning_object_ids": [self.shape.id, self.volume.id, self.flow.id]},
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertIn("learning_object_groups", response.data)
        merged = LearningObject.objects.get(pk=self.shape.id)
        self.assertEqual(len(merged.merged_from), 3)
        parts = [
            item["merged_parts"]
            for group in response.data["learning_object_groups"]
            for item in group["learning_objects"]
            if item["id"] == self.shape.id
        ][0]
        self.assertEqual([part["title"] for part in parts], ["Shape", "Volume", "Flow"])
        self.assertIs(response.data["unpublished"], False)

    def test_merge_endpoint_reports_an_unpublished_topic(self):
        OutlineNode.objects.filter(pk=self.topic.pk).update(published=True)
        client = authenticated_api_client()

        response = client.post(
            self._url("merge-learning-objects/"),
            {"learning_object_ids": [self.shape.id, self.volume.id]},
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertIs(response.data["unpublished"], True)

    def test_reconfirming_after_a_merge_does_not_recreate_merged_away_rows(self):
        client = authenticated_api_client()
        merged = client.post(
            self._url("merge-learning-objects/"),
            {"learning_object_ids": [self.shape.id, self.volume.id, self.flow.id]},
            format="json",
        )
        self.assertEqual(merged.status_code, 200, merged.data)

        response = client.post(
            f"/api/courses/{self.course.id}/materials/{self.material.id}/confirm-learning-objects/",
            {},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(LearningObject.objects.filter(pk__in=[self.volume.id, self.flow.id]).exists())
        self.assertEqual(
            sorted(self.material.learning_objects.values_list("title", flat=True)),
            ["Comparing", "Examples", "Matter"],
        )
        self.assertEqual(len(LearningObject.objects.get(pk=self.shape.id).merged_from), 3)

    def test_merge_endpoint_rejects_objects_from_two_pdfs(self):
        client = authenticated_api_client()

        response = client.post(
            self._url("merge-learning-objects/"),
            {"learning_object_ids": [self.shape.id, self.comparing.id]},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("same PDF", response.data["detail"])

    def test_merge_endpoint_rejects_a_non_list_body(self):
        client = authenticated_api_client()
        before = sorted(self.material.learning_objects.values_list("title", flat=True))

        response = client.post(
            self._url("merge-learning-objects/"),
            {"learning_object_ids": "12"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            sorted(self.material.learning_objects.values_list("title", flat=True)), before,
        )

    def test_split_endpoint_restores_the_originals(self):
        kept, _ = merge_learning_objects([self.shape, self.volume])
        client = authenticated_api_client()

        response = client.post(self._url(f"learning-objects/{kept.id}/split/"), format="json")

        self.assertEqual(response.status_code, 200, response.data)
        self.assertIs(response.data["unpublished"], False)
        self.assertEqual(
            sorted(self.material.learning_objects.values_list("title", flat=True)),
            ["Examples", "Flow", "Matter", "Shape", "Volume"],
        )
