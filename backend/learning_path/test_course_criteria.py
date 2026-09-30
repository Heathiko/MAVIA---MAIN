"""Cross-topic verdicts and derivation (course spec section 3)."""

from django.test import SimpleTestCase, TestCase

from lessons.models import CourseGroup, LearningObjectGroup, OutlineNode

from .services.course_criteria import course_topics, course_verdict, decide_course_pairs
from .services.embeddings import EncoderUnavailable
from .services.fusion import ACCEPTED, PARALLEL, PENDING
from .testing import concept, word_vectors

CALIBRATION = {
    "weights": {"name": 1.0, "terms": 1.0, "meaning": 1.0, "heading": 1.0, "order": 1.0},
    "related_cutoff": 0.1,
    "meaning_cutoff": 0.3,
    "source": "test",
}


def votes(name=0, terms=0, meaning=0, outline=1):
    return {"name": name, "terms": terms, "meaning": meaning, "outline": outline}


def stamen():
    return concept(1, "Stamen", "The anther makes pollen grains. " * 8)


def petals():
    # Gives the term statistics enough text for "anther" to be significantly Stamen's.
    return concept(4, "Petals", "Petals attract bees with bright colours. " * 8)


def pollination(names_stamen=True):
    text = "Pollen travels from the stamen anther to a stigma." if names_stamen else "Pollen travels from an anther to a stigma."
    return concept(2, "Pollination", text)


def weather():
    return concept(3, "Weather", "Clouds bring heavy rain showers today. " * 8)


def no_encoder(sentences):
    raise EncoderUnavailable("offline")


def decide(topic_concepts, embed=word_vectors):
    return {
        (row["prerequisite"].id, row["dependent"].id): row
        for row in decide_course_pairs(topic_concepts, calibration=CALIBRATION, embed=embed)
    }


class CourseVerdictTests(SimpleTestCase):
    """Across topics only name and terms vote, and they must agree (design pair 340-341:
    every link resting on one clue, or on the meaning clue, was wrong)."""

    def test_name_and_terms_agreeing_with_the_outline_are_accepted(self):
        self.assertEqual(course_verdict(votes(name=1, terms=1)), (ACCEPTED, 1))

    def test_name_and_terms_against_the_outline_are_a_flagged_suggestion(self):
        self.assertEqual(course_verdict(votes(name=-1, terms=-1)), (PENDING, -1))

    def test_one_clue_alone_makes_no_link(self):
        self.assertEqual(course_verdict(votes(terms=1))[0], PARALLEL)
        self.assertEqual(course_verdict(votes(name=-1))[0], PARALLEL)

    def test_the_meaning_clue_does_not_vote(self):
        self.assertEqual(course_verdict(votes(name=1, meaning=1))[0], PARALLEL)
        self.assertEqual(course_verdict(votes(name=1, terms=1, meaning=-1)), (ACCEPTED, 1))

    def test_clues_that_disagree_make_no_link(self):
        self.assertEqual(course_verdict(votes(name=1, terms=-1))[0], PARALLEL)

    def test_the_outline_alone_makes_no_link(self):
        self.assertEqual(course_verdict(votes())[0], PARALLEL)

    def test_without_the_encoder_nothing_is_accepted(self):
        self.assertEqual(course_verdict(votes(name=1, terms=1), semantic=False), (PENDING, 1))


class DecideCoursePairsTests(SimpleTestCase):
    def test_a_later_topic_using_an_earlier_topics_concept_is_accepted(self):
        row = decide([[stamen(), petals()], [pollination()]])[(1, 2)]

        self.assertEqual(row["verdict"], ACCEPTED)
        self.assertEqual(row["evidence"]["rule"], "course")
        self.assertEqual(row["evidence"]["votes"]["outline"], 1)
        self.assertFalse(row["evidence"]["contradicts_outline"])

    def test_an_earlier_topic_needing_a_later_one_is_flagged(self):
        row = decide([[pollination()], [stamen(), petals()]])[(1, 2)]

        self.assertEqual(row["verdict"], PENDING)
        self.assertTrue(row["evidence"]["contradicts_outline"])

    def test_one_clue_across_topics_makes_no_link(self):
        self.assertNotIn((1, 2), decide([[stamen(), petals()], [pollination(names_stamen=False)]]))

    def test_unrelated_topics_get_no_link(self):
        self.assertEqual(decide([[stamen()], [weather()]]), {})

    def test_concepts_of_one_topic_are_never_paired_here(self):
        self.assertEqual(decide([[stamen(), pollination()]]), {})

    def test_without_the_encoder_links_are_only_pending(self):
        decided = decide([[stamen(), petals()], [pollination()]], embed=no_encoder)

        self.assertEqual({row["verdict"] for row in decided.values()}, {PENDING})
        self.assertFalse(decided[(1, 2)]["evidence"]["semantic"])


class CourseTopicsTests(TestCase):
    def test_topics_with_content_in_unit_then_topic_order(self):
        course = CourseGroup.objects.create(title="Grade 1 Science")
        later_unit = OutlineNode.objects.create(course=course, title="Changes", order=1, depth=0)
        first_unit = OutlineNode.objects.create(course=course, title="Matter", order=0, depth=0)
        changes = OutlineNode.objects.create(course=course, parent=later_unit, title="Changes of state", order=0, depth=1)
        grouping = OutlineNode.objects.create(course=course, parent=first_unit, title="Grouping", order=1, depth=1)
        states = OutlineNode.objects.create(course=course, parent=first_unit, title="States", order=0, depth=1)
        empty = OutlineNode.objects.create(course=course, parent=first_unit, title="Empty", order=2, depth=1)
        for topic in (changes, grouping, states):
            LearningObjectGroup.objects.create(outline_node=topic, label=topic.title)

        self.assertEqual([topic.id for topic in course_topics(course)], [states.id, grouping.id, changes.id])
        self.assertEqual(
            [topic.id for topic in course_topics(course, with_content=False)],
            [states.id, grouping.id, empty.id, changes.id],
        )
