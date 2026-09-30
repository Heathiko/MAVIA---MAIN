# Course-level Learning Path Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Derive concept links between topics of one course with the v5 evidence (content family + the teacher's outline order), show them on a new Course path page, and publish confirmed earlier-topic prerequisites for the adaptive engine.

**Architecture:** A new model `CourseConceptLink` beside `ConceptPrerequisite`; `services/course_criteria.py` reuses `concept_text`, `relatedness` and `clues` across topics with the outline order as the structure vote; `services/course_links.py` stores, rolls up and edits links; `published.py` adds `course_prerequisites` per step; a React page draws topics and arrows. The adaptive engine is not touched.

**Tech Stack:** Django 5 / DRF, numpy, the v5 learning-path services; React + @xyflow/react + vitest.

**Spec:** `docs/superpowers/specs/2026-09-30-course-learning-path-design.md`

## Global Constraints

- Branch `learning-path-graph-screen`. Commit per task, staging **explicit paths only** (never `git add -A`, never `git stash`). The user's uncommitted `.gitignore`, `export_live_concepts.py` and untracked `gold_map_308.json` / `.claude/` stay out of every commit. **Do not push or merge.**
- Only these paths change: `backend/learning_path/**`, `web-app/src/pages/CoursePathPage.jsx`, `web-app/src/learning-path/coursePath*`, `web-app/src/api.js`, `web-app/src/App.jsx`, `web-app/src/pages/CourseDetailPage.jsx`, `docs/**`. **Never `backend/adaptive/`** (groupmate's), never `backend/lessons/`.
- No new constants except `MIN_AGREEING_CONTENT = 2` (spec §3). Cutoffs come from `calibration.load_calibration()`.
- Cross-topic verdicts (spec §3): content silent → no link; content against the outline → PENDING, content's direction, `contradicts_outline: true`; ≥ 2 content clues agree, none against, outline agrees → ACCEPTED; otherwise PENDING; no encoder → never ACCEPTED.
- `course_prerequisites` (spec §6): accepted/approved only, earlier topics only, target concept has a saved `LearningPathStep` in a published topic, nearest topic first.
- Naming as v5 spec §11: descriptive names, no single letters or maths names, no `compute_`/`get_`/`helper`/`utils`.
- Backend tests from `backend/`: `python manage.py test learning_path`. Frontend from `web-app/`: `npm test && npm run build`.

## Review Focus

1. **A course with one topic, or none with content** — expected: no links, the page still renders every outline topic. Test in Task 3.
2. **A cross-topic link whose concept was deleted or regrouped** — expected: rows cascade away; `course_path` and `course_prerequisites` never crash on a missing concept title. Test in Task 3.
3. **An approved link from a later topic** (contradicts the outline) — expected: shown red on the page, never in `course_prerequisites`. Test in Task 6.
4. **The prerequisite topic is not published yet** — expected: its concepts never appear in `course_prerequisites`. Test in Task 6.
5. **Course derivation fails during a topic publish** (encoder error, DB error) — expected: the topic still publishes; a warning is logged. Test in Task 7.

---

### Task 1: `CourseConceptLink` model

**Files:**
- Modify: `backend/learning_path/models.py`
- Create: `backend/learning_path/migrations/0009_courseconceptlink.py` (generated)
- Test: `backend/learning_path/test_course_links.py`

**Interfaces:**
- Produces: `learning_path.models.CourseConceptLink` with fields `course`, `prerequisite`, `dependent`, `status`, `source`, `evidence`, `decided_at`, `created_at`, `updated_at`; class attributes `Status`, `Source`, `SHAPES_PATH`, `TEACHER_DECIDED` (same values as `ConceptPrerequisite`); unique (`prerequisite`, `dependent`).

- [ ] **Step 1: Write the failing test** — create `test_course_links.py`:

```python
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
```

- [ ] **Step 2: Run to verify it fails**

Run: `python manage.py test learning_path.test_course_links`
Expected: FAIL — `ImportError: cannot import name 'CourseConceptLink'`.

- [ ] **Step 3: Implement** — append to `models.py` (after `ConceptPrerequisite`; add `CourseGroup` to the `lessons.models` import):

```python
class CourseConceptLink(models.Model):
    """"Learn ``prerequisite`` before ``dependent``", across two topics of one course.

    The course-level counterpart of ``ConceptPrerequisite``, kept apart so a
    topic's path and screen never see a concept from another topic. Same
    statuses and the same rule: re-deriving never overwrites a teacher's
    ``approved`` or ``rejected``.
    """

    Status = ConceptPrerequisite.Status
    Source = ConceptPrerequisite.Source
    SHAPES_PATH = ConceptPrerequisite.SHAPES_PATH
    TEACHER_DECIDED = ConceptPrerequisite.TEACHER_DECIDED

    course = models.ForeignKey(CourseGroup, related_name="course_concept_links", on_delete=models.CASCADE)
    prerequisite = models.ForeignKey(
        LearningObjectGroup, related_name="course_dependent_links", on_delete=models.CASCADE,
    )
    dependent = models.ForeignKey(
        LearningObjectGroup, related_name="course_prerequisite_links", on_delete=models.CASCADE,
    )
    status = models.CharField(max_length=10, choices=ConceptPrerequisite.Status.choices, db_index=True)
    source = models.CharField(
        max_length=10, choices=ConceptPrerequisite.Source.choices, default=ConceptPrerequisite.Source.DERIVED,
    )
    # Votes and scores behind a derived row, plus ``contradicts_outline``.
    evidence = models.JSONField(default=dict, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["prerequisite", "dependent"], name="unique_course_concept_link"),
        ]

    def __str__(self):
        return f"{self.prerequisite_id} -> {self.dependent_id} ({self.status})"
```

Run: `python manage.py makemigrations learning_path --name courseconceptlink`
Expected: `Migrations for 'learning_path': … 0009_courseconceptlink.py`.

- [ ] **Step 4: Run to verify it passes**

Run: `python manage.py test learning_path.test_course_links`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/learning_path/models.py backend/learning_path/migrations/0009_courseconceptlink.py backend/learning_path/test_course_links.py
git commit -m "Add the CourseConceptLink model for cross-topic links"
```

---

### Task 2: Cross-topic criteria

**Files:**
- Create: `backend/learning_path/services/course_criteria.py`
- Test: `backend/learning_path/test_course_criteria.py`

**Interfaces:**
- Consumes: `concept_text.prepare`, `relatedness.relatedness`, `clues.name_vote/term_vote/meaning_vote/find_term_owners/clue_records`, `fusion.ACCEPTED/PENDING/PARALLEL/CONTENT_CLUES/family_direction`, `calibration.load_calibration`, `embeddings.embed/EncoderUnavailable`.
- Produces:
  - `course_topics(course, with_content=True) -> list[OutlineNode]` in outline order (ancestor chain of `(order, id)`).
  - `course_verdict(votes, semantic=True) -> (verdict, direction)`; `votes` has `name`, `terms`, `meaning`, `outline` (+1 when the first concept's topic is earlier).
  - `decide_course_pairs(topic_concepts, calibration=None, embed=None) -> list[dict]` — `topic_concepts` is a list (outline order) of concept lists; each dict has `prerequisite`, `dependent` (concepts), `verdict`, `evidence` (`rule: "course"`, `relatedness`, `confidence`, `votes`, `records`, `contradicts_outline`, `semantic`).

- [ ] **Step 1: Write the failing tests** — `test_course_criteria.py`:

```python
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
    # Name + meaning carry the link: with two concepts G2 cannot make "anther" owned.
    return concept(1, "Stamen", "The anther makes pollen grains. The filament is a thin green stalk. The filament holds the anther up high. Each grain carries a male cell.")


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
    def test_two_content_clues_with_the_outline_are_accepted(self):
        self.assertEqual(course_verdict(votes(name=1, terms=1)), (ACCEPTED, 1))

    def test_one_content_clue_is_only_pending(self):
        self.assertEqual(course_verdict(votes(terms=1)), (PENDING, 1))

    def test_a_clue_against_blocks_acceptance(self):
        self.assertEqual(course_verdict(votes(name=1, terms=1, meaning=-1)), (PENDING, 1))

    def test_content_against_the_outline_is_pending_in_the_contents_direction(self):
        self.assertEqual(course_verdict(votes(name=-1, terms=-1)), (PENDING, -1))

    def test_the_outline_alone_makes_no_link(self):
        self.assertEqual(course_verdict(votes())[0], PARALLEL)

    def test_without_the_encoder_nothing_is_accepted(self):
        self.assertEqual(course_verdict(votes(name=1, terms=1), semantic=False), (PENDING, 1))


class DecideCoursePairsTests(SimpleTestCase):
    def test_a_later_topic_using_an_earlier_topics_concept_is_accepted(self):
        row = decide([[stamen()], [pollination()]])[(1, 2)]

        self.assertEqual(row["verdict"], ACCEPTED)
        self.assertEqual(row["evidence"]["rule"], "course")
        self.assertEqual(row["evidence"]["votes"]["outline"], 1)
        self.assertFalse(row["evidence"]["contradicts_outline"])

    def test_an_earlier_topic_needing_a_later_one_is_flagged(self):
        row = decide([[pollination()], [stamen()]])[(1, 2)]

        self.assertEqual(row["verdict"], PENDING)
        self.assertTrue(row["evidence"]["contradicts_outline"])

    def test_one_clue_across_topics_is_only_pending(self):
        row = decide([[stamen()], [pollination(names_stamen=False)]])[(1, 2)]

        self.assertEqual(row["verdict"], PENDING)

    def test_unrelated_topics_get_no_link(self):
        self.assertEqual(decide([[stamen()], [weather()]]), {})

    def test_concepts_of_one_topic_are_never_paired_here(self):
        self.assertEqual(decide([[stamen(), pollination()]]), {})

    def test_without_the_encoder_links_are_only_pending(self):
        decided = decide([[stamen()], [pollination()]], embed=no_encoder)

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
```

- [ ] **Step 2: Run to verify they fail**

Run: `python manage.py test learning_path.test_course_criteria`
Expected: FAIL — `ModuleNotFoundError: No module named 'learning_path.services.course_criteria'`.

- [ ] **Step 3: Implement** — `services/course_criteria.py`:

```python
"""Prerequisite links between topics of one course (the course-level path).

The topic-level v5 evidence, read across topics: relatedness gates a pair, the
name, terms and meaning clues are the content family, and the teacher's
outline order is the structure -- headings and PDF order cannot compare two
topics. See docs/superpowers/specs/2026-09-30-course-learning-path-design.md.
"""

from lessons.models import OutlineNode

from . import embeddings
from .calibration import load_calibration
from .clues import clue_records, find_term_owners, meaning_vote, name_vote, term_vote
from .concept_text import prepare
from .fusion import ACCEPTED, CONTENT_CLUES, PARALLEL, PENDING, family_direction
from .relatedness import relatedness

# The outline always votes, so one content clue -- the meaning clue is at chance
# on direction -- must not be enough to send a learner to another topic.
MIN_AGREEING_CONTENT = 2


def course_topics(course, with_content=True):
    """The course's topics in the order its outline teaches them (unit order, then topic order)."""
    nodes = {node.id: node for node in OutlineNode.objects.filter(course=course)}
    with_children = {node.parent_id for node in nodes.values() if node.parent_id}
    if with_content:
        topic_ids = set(
            OutlineNode.objects.filter(course=course, learning_object_groups__isnull=False)
            .values_list("id", flat=True)
        )
    else:
        topic_ids = {node_id for node_id in nodes if node_id not in with_children}

    def outline_position(node):
        chain = []
        while node is not None:
            chain.append((node.order, node.id))
            node = nodes.get(node.parent_id)
        return tuple(reversed(chain))

    return sorted((nodes[node_id] for node_id in topic_ids), key=outline_position)


def course_verdict(votes, semantic=True):
    """``(verdict, direction)`` for concepts of two topics; direction +1 means "first before second"."""
    content = family_direction(votes, CONTENT_CLUES)
    if not content:
        return PARALLEL, 0
    if content == -votes["outline"]:
        return PENDING, content
    agreeing = sum(1 for clue in CONTENT_CLUES if votes[clue] == content)
    against = sum(1 for clue in CONTENT_CLUES if votes[clue] == -content)
    if semantic and agreeing >= MIN_AGREEING_CONTENT and not against:
        return ACCEPTED, content
    return PENDING, content


def _decide(first, second, owners, calibration, semantic):
    """The link between ``first`` (earlier topic) and ``second`` (later topic), or ``None``."""
    if not (first.sentences and second.sentences):
        return None
    score = relatedness(first, second) if semantic else None
    if semantic and score < calibration["related_cutoff"]:
        return None
    meaning_cutoff = calibration["meaning_cutoff"]
    votes = {
        "name": name_vote(first, second)[0],
        "terms": term_vote(first, second, owners)[0],
        "meaning": meaning_vote(first, second, meaning_cutoff)[0] if semantic else 0,
        "outline": 1,
    }
    outcome, direction = course_verdict(votes, semantic)
    if outcome not in (ACCEPTED, PENDING):
        return None
    prerequisite, dependent = (first, second) if direction > 0 else (second, first)
    oriented = {clue: vote * direction for clue, vote in votes.items()}
    voting = [clue for clue in oriented if oriented[clue]]
    records = clue_records(prerequisite, dependent, owners, {}, meaning_cutoff, semantic)
    records.pop("heading", None)
    records.pop("order", None)
    return {
        "prerequisite": prerequisite.concept,
        "dependent": dependent.concept,
        "verdict": outcome,
        "evidence": {
            "rule": "course",
            "relatedness": None if score is None else round(score, 3),
            "confidence": round(sum(1 for clue in voting if oriented[clue] == 1) / len(voting), 3),
            "votes": oriented,
            "records": records,
            "contradicts_outline": direction < 0,
            "semantic": semantic,
        },
    }


def decide_course_pairs(topic_concepts, calibration=None, embed=None):
    """Every cross-topic pair the evidence accepts or sends to the teacher.

    ``topic_concepts`` lists each topic's concepts, topics in outline order.
    Term ownership is read over the two topics of a pair together, so a term a
    later topic introduces can point back at an earlier topic's concept.
    """
    calibration = calibration or load_calibration()
    concepts = [concept for topic in topic_concepts for concept in topic]
    semantic = True
    try:
        texts = prepare(concepts, embed=embed or embeddings.embed)
    except embeddings.EncoderUnavailable:
        texts, semantic = prepare(concepts), False
    by_topic, start = [], 0
    for topic in topic_concepts:
        by_topic.append(texts[start:start + len(topic)])
        start += len(topic)

    decisions = []
    for first_index, earlier in enumerate(by_topic):
        for later in by_topic[first_index + 1:]:
            owners = find_term_owners(earlier + later)
            for first in earlier:
                for second in later:
                    row = _decide(first, second, owners, calibration, semantic)
                    if row:
                        decisions.append(row)
    return decisions
```

- [ ] **Step 4: Run to verify they pass**

Run: `python manage.py test learning_path.test_course_criteria`
Expected: PASS (13 tests). If a `DecideCoursePairsTests` case fails because the stub text does not produce the intended clue (e.g. G² below 3.84), fix the **test data** (repeat sentences, as the topic tests do), never the rule, and record the ruling.

- [ ] **Step 5: Commit**

```bash
git add backend/learning_path/services/course_criteria.py backend/learning_path/test_course_criteria.py
git commit -m "Derive cross-topic concept links with the outline as structure"
```

---

### Task 3: Storing and rolling up course links

**Files:**
- Create: `backend/learning_path/services/course_links.py`
- Test: `backend/learning_path/test_course_links.py` (append)

**Interfaces:**
- Consumes: `course_topics`, `decide_course_pairs` (Task 2), `concepts_for_topic`, `CourseConceptLink` (Task 1), `reasons.link_reason`.
- Produces:
  - `refresh_course_links(course, embed=None) -> {"accepted": n, "pending": n, "teacher_decided": n}`
  - `course_path(course) -> {"course": {id, title}, "topics": [{id, title, position, has_content}], "arrows": [{from_topic, to_topic, contradicts_outline, shaping, pending, links: [{id, status, prerequisite: {concept_id, title, topic_id}, dependent: {…}, reason, contradicts_outline}]}]}` — rejected rows omitted.

- [ ] **Step 1: Write the failing tests** — append to `test_course_links.py`:

```python
from unittest.mock import patch

from lessons.models import LearningMaterial, LearningObject

from .services.course_links import course_path, refresh_course_links
from .testing import word_vectors


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
```

- [ ] **Step 2: Run to verify they fail**

Run: `python manage.py test learning_path.test_course_links`
Expected: FAIL — `ModuleNotFoundError: No module named 'learning_path.services.course_links'`.

- [ ] **Step 3: Implement** — `services/course_links.py`:

```python
"""Course-level links: storing what the criteria derive, the page's roll-up, teacher edits.

Mirrors ``publishing.refresh_prerequisites`` and ``teacher_links`` for
``CourseConceptLink``: derived rows are updated in place so ids stay stable,
and a teacher's ``approved`` or ``rejected`` is never overwritten.
"""

from collections import defaultdict

from django.db import transaction
from django.utils import timezone

from ..models import CourseConceptLink
from .concept_units import concepts_for_topic
from .course_criteria import course_topics, decide_course_pairs
from .reasons import link_reason


def refresh_course_links(course, embed=None):
    """Re-derive the course's cross-topic links, keeping every teacher decision."""
    topics = course_topics(course)
    decisions = decide_course_pairs([list(concepts_for_topic(topic)) for topic in topics], embed=embed)
    fresh = {(row["prerequisite"].id, row["dependent"].id): row for row in decisions}

    with transaction.atomic():
        existing = {
            (row.prerequisite_id, row.dependent_id): row
            for row in CourseConceptLink.objects.select_for_update().filter(course=course)
        }
        decided = {pair for pair, row in existing.items() if row.status in CourseConceptLink.TEACHER_DECIDED}
        for pair, decision in fresh.items():
            row = existing.get(pair)
            if row is None:
                row, created = CourseConceptLink.objects.get_or_create(
                    prerequisite_id=pair[0],
                    dependent_id=pair[1],
                    defaults={
                        "course": course,
                        "status": decision["verdict"],
                        "source": CourseConceptLink.Source.DERIVED,
                        "evidence": decision["evidence"],
                    },
                )
                if created:
                    continue
            if row.status in CourseConceptLink.TEACHER_DECIDED:
                row.evidence = decision["evidence"]
                row.save(update_fields=["evidence", "updated_at"])
                continue
            CourseConceptLink.objects.filter(pk=row.pk).exclude(
                status__in=CourseConceptLink.TEACHER_DECIDED,
            ).update(
                status=decision["verdict"],
                source=CourseConceptLink.Source.DERIVED,
                evidence=decision["evidence"],
                updated_at=timezone.now(),
            )
        stale = [
            row.pk for pair, row in existing.items()
            if pair not in fresh and row.status not in CourseConceptLink.TEACHER_DECIDED
        ]
        CourseConceptLink.objects.filter(pk__in=stale).exclude(
            status__in=CourseConceptLink.TEACHER_DECIDED,
        ).delete()

    counts = {"accepted": 0, "pending": 0, "teacher_decided": len(decided)}
    for pair, decision in fresh.items():
        if pair not in decided:
            counts[decision["verdict"]] += 1
    return counts


def _concept_titles(topics):
    return {concept.id: concept.title for topic in topics for concept in concepts_for_topic(topic)}


def course_path(course):
    """The Course path page: outline topics, and one arrow per pair of topics with links."""
    topics = course_topics(course, with_content=False)
    with_content = {topic.id for topic in course_topics(course)}
    position = {topic.id: index for index, topic in enumerate(topics)}
    titles = _concept_titles([topic for topic in topics if topic.id in with_content])

    arrows = defaultdict(list)
    rows = (
        CourseConceptLink.objects.filter(course=course)
        .exclude(status=CourseConceptLink.Status.REJECTED)
        .select_related("prerequisite", "dependent")
    )
    for row in rows:
        from_topic, to_topic = row.prerequisite.outline_node_id, row.dependent.outline_node_id
        if from_topic not in position or to_topic not in position:
            continue
        before = titles.get(row.prerequisite_id) or row.prerequisite.label or "Untitled concept"
        after = titles.get(row.dependent_id) or row.dependent.label or "Untitled concept"
        arrows[(from_topic, to_topic)].append({
            "id": row.id,
            "status": row.status,
            "prerequisite": {"concept_id": row.prerequisite_id, "title": before, "topic_id": from_topic},
            "dependent": {"concept_id": row.dependent_id, "title": after, "topic_id": to_topic},
            "reason": link_reason(row.evidence, before, after),
            "contradicts_outline": position[from_topic] > position[to_topic],
        })

    return {
        "course": {"id": course.id, "title": course.title},
        "topics": [
            {"id": topic.id, "title": topic.title, "position": position[topic.id], "has_content": topic.id in with_content}
            for topic in topics
        ],
        "arrows": [
            {
                "from_topic": from_topic,
                "to_topic": to_topic,
                "contradicts_outline": position[from_topic] > position[to_topic],
                "shaping": sum(1 for link in links if link["status"] in CourseConceptLink.SHAPES_PATH),
                "pending": sum(1 for link in links if link["status"] == CourseConceptLink.Status.PENDING),
                "links": sorted(links, key=lambda link: link["id"]),
            }
            for (from_topic, to_topic), links in sorted(arrows.items(), key=lambda item: (position[item[0][0]], position[item[0][1]]))
        ],
    }
```

- [ ] **Step 4: Run to verify they pass**

Run: `python manage.py test learning_path.test_course_links`
Expected: PASS (10 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/learning_path/services/course_links.py backend/learning_path/test_course_links.py
git commit -m "Store course links and roll them up per pair of topics"
```

---

### Task 4: Teacher decisions and undo for course links

**Files:**
- Modify: `backend/learning_path/services/course_links.py`
- Test: `backend/learning_path/test_course_links.py` (append)

**Interfaces:**
- Produces: `CourseLinkError(ValueError)`; `decide_course_link(course, link_id, status) -> undo list`; `restore_course_links(course, records) -> None`. Undo records: `{"prerequisite_id", "dependent_id", "prior": None | {"status", "source", "decided_at"}}` (same shape as the topic screen).

- [ ] **Step 1: Write the failing tests** — append:

```python
from .services.course_links import CourseLinkError, decide_course_link, restore_course_links


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
```

- [ ] **Step 2: Run to verify they fail**

Run: `python manage.py test learning_path.test_course_links`
Expected: FAIL — `ImportError: cannot import name 'CourseLinkError'`.

- [ ] **Step 3: Implement** — append to `course_links.py` (add `from django.utils.dateparse import parse_datetime` and `from lessons.models import LearningObjectGroup` to the imports):

```python
class CourseLinkError(ValueError):
    """A teacher's change that cannot be applied; the message is shown as is."""


_INVALID_UNDO = "That undo is not valid. Refresh the page."


def _snapshot(course, pairs):
    rows = {
        (row.prerequisite_id, row.dependent_id): row
        for row in CourseConceptLink.objects.filter(course=course)
    }
    records = []
    for prerequisite_id, dependent_id in pairs:
        row = rows.get((prerequisite_id, dependent_id))
        records.append({
            "prerequisite_id": prerequisite_id,
            "dependent_id": dependent_id,
            "prior": None if row is None else {
                "status": row.status,
                "source": row.source,
                "decided_at": row.decided_at.isoformat() if row.decided_at else None,
            },
        })
    return records


def decide_course_link(course, link_id, status):
    """Approve a suggestion, or reject (remove) any link. Returns the undo record."""
    if status not in CourseConceptLink.TEACHER_DECIDED:
        raise CourseLinkError("Choose approve or reject.")
    row = CourseConceptLink.objects.filter(pk=link_id, course=course).first()
    if row is None:
        raise CourseLinkError("That link no longer exists. Refresh the page.")
    undo = _snapshot(course, [(row.prerequisite_id, row.dependent_id)])
    row.status = status
    row.source = CourseConceptLink.Source.TEACHER
    row.decided_at = timezone.now()
    row.save(update_fields=["status", "source", "decided_at", "updated_at"])
    return undo


def _course_group(course, group_id):
    group = LearningObjectGroup.objects.filter(pk=group_id, outline_node__course=course).first()
    if group is None:
        raise CourseLinkError(_INVALID_UNDO)
    return group


@transaction.atomic
def restore_course_links(course, records):
    """Put each pair back exactly as an undo record says it was."""
    if not isinstance(records, list) or not records:
        raise CourseLinkError("Nothing to undo.")
    for record in records:
        try:
            prerequisite = _course_group(course, int(record["prerequisite_id"]))
            dependent = _course_group(course, int(record["dependent_id"]))
            prior = record["prior"]
        except (KeyError, TypeError, ValueError):
            raise CourseLinkError(_INVALID_UNDO)
        if prior is None:
            CourseConceptLink.objects.filter(prerequisite=prerequisite, dependent=dependent).delete()
            continue
        if (
            not isinstance(prior, dict)
            or prior.get("status") not in CourseConceptLink.Status.values
            or prior.get("source") not in CourseConceptLink.Source.values
            or not isinstance(prior.get("decided_at"), (str, type(None)))
        ):
            raise CourseLinkError(_INVALID_UNDO)
        CourseConceptLink.objects.update_or_create(
            prerequisite=prerequisite,
            dependent=dependent,
            defaults={
                "course": course,
                "status": prior["status"],
                "source": prior["source"],
                "decided_at": parse_datetime(prior["decided_at"]) if prior.get("decided_at") else None,
            },
        )
```

Note: `_course_group` raising `CourseLinkError` inside the `try` is fine — it is not caught by the `except (KeyError, TypeError, ValueError)` clause only because `CourseLinkError` *is* a `ValueError`; it is re-raised as the same message either way.

- [ ] **Step 4: Run to verify they pass**

Run: `python manage.py test learning_path.test_course_links`
Expected: PASS (15 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/learning_path/services/course_links.py backend/learning_path/test_course_links.py
git commit -m "Let teachers approve, reject and undo course links"
```

---

### Task 5: Course path endpoints

**Files:**
- Modify: `backend/learning_path/views.py`, `backend/learning_path/urls.py`
- Test: `backend/learning_path/test_course_links.py` (append)

**Interfaces:**
- Consumes: `refresh_course_links`, `course_path`, `decide_course_link`, `restore_course_links`, `CourseLinkError`.
- Produces: `GET /api/learning-path/courses/<course_id>/`, `POST /api/learning-path/courses/<course_id>/links/<link_id>/decision/` (`{"status"}` → `{...course_path, "undo"}`), `POST /api/learning-path/courses/<course_id>/links/restore/` (`{"undo"}` → course_path). Teacher/admin only.

- [ ] **Step 1: Write the failing tests** — append:

```python
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient


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
```

- [ ] **Step 2: Run to verify they fail**

Run: `python manage.py test learning_path.test_course_links.CoursePathApiTests`
Expected: FAIL — 404 on every URL.

- [ ] **Step 3: Implement** — in `views.py` add to the imports `from lessons.models import CourseGroup, OutlineNode` (replacing the `OutlineNode` import) and `from .services.course_links import CourseLinkError, course_path, decide_course_link, refresh_course_links, restore_course_links`, then append:

```python
@api_view(["GET"])
@permission_classes([IsTeacherOrAdmin])
def course_learning_path(request, course_id):
    """The Course path page: topics in outline order and cross-topic arrows, derived on open."""
    course = CourseGroup.objects.filter(pk=course_id).first()
    if course is None:
        return Response({"detail": "Course not found."}, status=status.HTTP_404_NOT_FOUND)
    refresh_course_links(course)
    return Response(course_path(course))


@api_view(["POST"])
@permission_classes([IsTeacherOrAdmin])
def decide_course_path_link(request, course_id, link_id):
    """Approve a suggestion, or reject (remove) a course link. Body: ``{"status": "approved"|"rejected"}``."""
    course = CourseGroup.objects.filter(pk=course_id).first()
    if course is None:
        return Response({"detail": "Course not found."}, status=status.HTTP_404_NOT_FOUND)
    try:
        undo = decide_course_link(course, link_id, request.data.get("status"))
    except CourseLinkError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    return Response({**course_path(course), "undo": undo})


@api_view(["POST"])
@permission_classes([IsTeacherOrAdmin])
def restore_course_path_links(request, course_id):
    """Undo a course link change. Body: ``{"undo": [<record from the change's response>]}``."""
    course = CourseGroup.objects.filter(pk=course_id).first()
    if course is None:
        return Response({"detail": "Course not found."}, status=status.HTTP_404_NOT_FOUND)
    try:
        restore_course_links(course, request.data.get("undo"))
    except CourseLinkError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    return Response(course_path(course))
```

In `urls.py` append to `urlpatterns`:

```python
    path("courses/<int:course_id>/", views.course_learning_path, name="course-learning-path"),
    path("courses/<int:course_id>/links/<int:link_id>/decision/", views.decide_course_path_link, name="decide-course-path-link"),
    path("courses/<int:course_id>/links/restore/", views.restore_course_path_links, name="restore-course-path-links"),
```

- [ ] **Step 4: Run to verify they pass**

Run: `python manage.py test learning_path.test_course_links`
Expected: PASS (19 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/learning_path/views.py backend/learning_path/urls.py backend/learning_path/test_course_links.py
git commit -m "Add the course path endpoints"
```

---

### Task 6: `course_prerequisites` in the published path

**Files:**
- Modify: `backend/learning_path/services/published.py`
- Test: `backend/learning_path/test_course_links.py` (append)

**Interfaces:**
- Consumes: `course_topics`, `CourseConceptLink`, `LearningPathStep`.
- Produces: `published.course_prerequisites(node, concept_ids) -> {concept_id: [{"topic_id", "concept_id", "position", "status"}]}`; each published step gains `"course_prerequisites"` (list, possibly empty).

- [ ] **Step 1: Write the failing tests** — append:

```python
from django.utils import timezone

from .models import LearningPathStep
from .services.published import course_prerequisites


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
```

- [ ] **Step 2: Run to verify they fail**

Run: `python manage.py test learning_path.test_course_links.CoursePrerequisiteTests`
Expected: FAIL — `ImportError: cannot import name 'course_prerequisites'`.

- [ ] **Step 3: Implement** — in `published.py` change the model import to `from ..models import ConceptPrerequisite, CourseConceptLink, LearningPathStep`, add `from .course_criteria import course_topics`, and add above `get_published_path`:

```python
def course_prerequisites(node, concept_ids):
    """Earlier-topic concepts each step needs, for the adaptive engine.

    Only links that shape paths (accepted, approved), only from topics earlier
    in the outline, only to concepts saved in a published topic's path --
    nearest topic first. See docs/handoff-course-prerequisites.md.
    """
    topics = course_topics(node.course)
    rank = {topic.id: index for index, topic in enumerate(topics)}
    published = {topic.id for topic in topics if topic.published}
    if node.id not in rank:
        return {}
    rows = list(
        CourseConceptLink.objects.filter(
            course_id=node.course_id,
            status__in=CourseConceptLink.SHAPES_PATH,
            dependent_id__in=concept_ids,
        ).select_related("prerequisite")
    )
    positions = {
        (step.outline_node_id, step.concept_id): step.position
        for step in LearningPathStep.objects.filter(concept_id__in=[row.prerequisite_id for row in rows])
    }
    found = defaultdict(list)
    for row in rows:
        topic_id = row.prerequisite.outline_node_id
        if topic_id not in published or rank.get(topic_id, len(rank)) >= rank[node.id]:
            continue
        position = positions.get((topic_id, row.prerequisite_id))
        if position is None:
            continue
        found[row.dependent_id].append((rank[topic_id], {
            "topic_id": topic_id,
            "concept_id": row.prerequisite_id,
            "position": position,
            "status": row.status,
        }))
    return {
        concept_id: [entry for _, entry in sorted(entries, key=lambda item: (-item[0], item[1]["position"]))]
        for concept_id, entries in found.items()
    }
```

In `get_published_path`, after `position_of = …` add:

```python
    earlier_topics = course_prerequisites(node, concept_ids)
```

and in each `payload_steps.append({...})` after `"leads_to": …` add:

```python
            "course_prerequisites": earlier_topics.get(group.id, []),
```

- [ ] **Step 4: Run to verify they pass**

Run: `python manage.py test learning_path`
Expected: PASS (whole app; existing published-path tests unaffected apart from the extra key).

- [ ] **Step 5: Commit**

```bash
git add backend/learning_path/services/published.py backend/learning_path/test_course_links.py
git commit -m "Publish earlier-topic prerequisites for the adaptive engine"
```

---

### Task 7: Refresh course links when a topic is published

**Files:**
- Modify: `backend/learning_path/services/publishing.py` (`publish_learning_path`)
- Test: `backend/learning_path/test_publishing.py` (append)

**Interfaces:**
- Produces: `publish_learning_path` result gains `"course_links"` (the counts dict, or `None` when the refresh failed).

- [ ] **Step 1: Write the failing tests** — append to `test_publishing.py`:

```python
class CourseRefreshOnPublishTests(PublishingFixture):
    def test_publishing_a_topic_refreshes_its_course_links(self):
        with self._derive(), patch("learning_path.services.course_links.refresh_course_links", return_value={"accepted": 0, "pending": 0, "teacher_decided": 0}) as refresh:
            summary = publishing.publish_learning_path(self.topic)

        refresh.assert_called_once_with(self.topic.course)
        self.assertEqual(summary["course_links"]["accepted"], 0)

    def test_a_failed_course_refresh_never_fails_the_publish(self):
        with self._derive(), patch("learning_path.services.course_links.refresh_course_links", side_effect=RuntimeError("boom")):
            with self.assertLogs("learning_path.services.publishing", level="WARNING"):
                summary = publishing.publish_learning_path(self.topic)

        self.assertIsNone(summary["course_links"])
        self.assertEqual(summary["steps"], 4)
```

- [ ] **Step 2: Run to verify they fail**

Run: `python manage.py test learning_path.test_publishing.CourseRefreshOnPublishTests`
Expected: FAIL — `AssertionError: Expected 'refresh_course_links' to be called once`.

- [ ] **Step 3: Implement** — in `publish_learning_path`, before `return {**saved, **link_counts}`:

```python
    # Cross-topic links follow the topic's new concepts. A failure here must not
    # undo a publish the teacher already sees as done.
    from . import course_links

    try:
        course_counts = course_links.refresh_course_links(node.course)
    except Exception as exc:  # noqa: BLE001 -- logged; the topic path is already saved
        logger.warning("[Learning path topic %s] course links not refreshed: %s", node.id, exc)
        course_counts = None
```

and return `{**saved, **link_counts, "course_links": course_counts}`.

- [ ] **Step 4: Run to verify they pass**

Run: `python manage.py test learning_path`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/learning_path/services/publishing.py backend/learning_path/test_publishing.py
git commit -m "Refresh a course's cross-topic links when a topic is published"
```

---

### Task 8: Reasons for course links

**Files:**
- Modify: `backend/learning_path/services/reasons.py`
- Test: `backend/learning_path/test_reasons.py` (append)

**Interfaces:**
- Produces: `link_reason` handles `rule == "course"`.

- [ ] **Step 1: Write the failing tests** — append inside `LinkReasonTests`:

```python
    def test_a_course_link_that_follows_the_outline(self):
        evidence = {"rule": "course", "confidence": 1.0, "semantic": True, "contradicts_outline": False,
                    "votes": {"name": 1, "terms": 1, "meaning": 0, "outline": 1},
                    "records": {"terms": {"owned": ["anther"]}}}

        self.assertEqual(
            link_reason(evidence, "Stamen", "Pollination"),
            "Pollination uses terms Stamen explains (anther). Pollination names Stamen. "
            "This follows your outline. Confidence 1.00.",
        )

    def test_a_course_link_against_the_outline_says_so(self):
        evidence = {"rule": "course", "confidence": 0.67, "semantic": True, "contradicts_outline": True,
                    "votes": {"name": 1, "terms": 1, "meaning": 0, "outline": -1}, "records": {}}

        self.assertEqual(
            link_reason(evidence, "Stamen", "Pollination"),
            "Pollination uses terms Stamen explains. Pollination names Stamen. "
            "This contradicts your outline: Stamen's topic comes later. Confidence 0.67.",
        )
```

- [ ] **Step 2: Run to verify they fail**

Run: `python manage.py test learning_path.test_reasons`
Expected: FAIL — both return "Added by you.".

- [ ] **Step 3: Implement** — in `reasons.py` add:

```python
def _course_reason(evidence, a, b):
    votes = evidence.get("votes") or {}
    records = evidence.get("records") or {}
    parts = []
    if votes.get("terms") == 1:
        owned = (records.get("terms") or {}).get("owned") or []
        listed = f" ({', '.join(owned[:3])})" if owned else ""
        parts.append(f"{b} uses terms {a} explains{listed}.")
    if votes.get("meaning") == 1:
        parts.append(f"{b}'s sentences refer to {a}'s ideas.")
    if votes.get("name") == 1:
        parts.append(f"{b} names {a}.")
    if evidence.get("contradicts_outline"):
        parts.append(f"This contradicts your outline: {a}'s topic comes later.")
    else:
        parts.append("This follows your outline.")
    if evidence.get("semantic") is False:
        parts.append("The meaning check was unavailable.")
    if evidence.get("confidence") is not None:
        parts.append(f"Confidence {evidence['confidence']:.2f}.")
    return " ".join(parts)
```

and in `link_reason`, next to the `fusion` branch:

```python
    if rule == "course":
        return _course_reason(evidence, a, b)
```

- [ ] **Step 4: Run to verify they pass**

Run: `python manage.py test learning_path.test_reasons learning_path.test_course_links`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/learning_path/services/reasons.py backend/learning_path/test_reasons.py
git commit -m "Explain course links in plain words"
```

---

### Task 9: Course path page

**Files:**
- Modify: `web-app/src/api.js`, `web-app/src/App.jsx`, `web-app/src/pages/CourseDetailPage.jsx`
- Create: `web-app/src/learning-path/coursePathModel.js`, `web-app/src/learning-path/coursePathModel.test.js`, `web-app/src/learning-path/coursePath.css`, `web-app/src/pages/CoursePathPage.jsx`

**Interfaces:**
- Consumes: Task 5 endpoints and the `course_path` payload (Task 3).
- Produces: `fetchCourseLearningPath(courseId)`, `decideCoursePathLink(courseId, linkId, status)`, `restoreCoursePathLinks(courseId, undo)`; `arrowKind(arrow)`; `buildCourseGraph(path, selectedArrow)`; route `/courses/:courseId/path`.

- [ ] **Step 1: Write the failing test** — `coursePathModel.test.js`:

```javascript
import { describe, expect, it } from "vitest";

import { arrowKind, buildCourseGraph } from "./coursePathModel";

const PATH = {
  course: { id: 1, title: "Grade 1 Science" },
  topics: [
    { id: 10, title: "Solid, Liquid and Gas", position: 0, has_content: true },
    { id: 11, title: "Grouping Materials", position: 1, has_content: true },
    { id: 12, title: "Empty topic", position: 2, has_content: false },
  ],
  arrows: [
    { from_topic: 10, to_topic: 11, contradicts_outline: false, shaping: 2, pending: 1, links: [] },
    { from_topic: 11, to_topic: 10, contradicts_outline: true, shaping: 0, pending: 1, links: [] },
  ],
};

describe("arrowKind", () => {
  it("names an arrow by what the teacher must know first", () => {
    expect(arrowKind(PATH.arrows[0])).toBe("follows");
    expect(arrowKind(PATH.arrows[1])).toBe("contradicts");
    expect(arrowKind({ contradicts_outline: false, shaping: 0, pending: 2 })).toBe("pending");
  });
});

describe("buildCourseGraph", () => {
  it("draws every topic in outline order and greys topics without content", () => {
    const graph = buildCourseGraph(PATH);
    expect(graph.nodes.map((node) => node.id)).toEqual(["10", "11", "12"]);
    expect(graph.nodes[2].data.empty).toBe(true);
    expect(graph.nodes[0].position.x).toBeLessThan(graph.nodes[1].position.x);
  });

  it("labels each arrow with its link count", () => {
    const graph = buildCourseGraph(PATH);
    expect(graph.edges.map((edge) => edge.label)).toEqual(["2 links", "1 suggestion"]);
    expect(graph.edges[1].className).toContain("contradicts");
  });
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd web-app && npx vitest run src/learning-path/coursePathModel.test.js`
Expected: FAIL — cannot resolve `./coursePathModel`.

- [ ] **Step 3: Implement the model** — `coursePathModel.js`:

```javascript
// Pure helpers behind the Course path page: where topics sit and how each
// arrow between them is drawn. Nothing here renders or calls the server.
export const TOPIC_WIDTH = 220;
export const TOPIC_HEIGHT = 60;
const COLUMNS = 4;
const COLUMN_STEP = TOPIC_WIDTH + 80;
const ROW_STEP = TOPIC_HEIGHT + 90;
const MARGIN = 20;

// "contradicts" first: a teacher must see an arrow against the outline even
// when it also carries accepted links.
export function arrowKind(arrow) {
  if (arrow.contradicts_outline) return "contradicts";
  if (!arrow.shaping) return "pending";
  return "follows";
}

function arrowLabel(arrow) {
  if (arrow.shaping) return `${arrow.shaping} link${arrow.shaping === 1 ? "" : "s"}`;
  return `${arrow.pending} suggestion${arrow.pending === 1 ? "" : "s"}`;
}

const COLOURS = { follows: "#2f6f4f", pending: "#b8860b", contradicts: "#b3261e" };

export function buildCourseGraph(path, selectedArrow = null) {
  const topics = [...path.topics].sort((a, b) => a.position - b.position);
  const nodes = topics.map((topic, index) => ({
    id: String(topic.id),
    type: "topic",
    position: { x: MARGIN + (index % COLUMNS) * COLUMN_STEP, y: MARGIN + Math.floor(index / COLUMNS) * ROW_STEP },
    data: { topic, empty: !topic.has_content },
    draggable: false,
  }));
  const edges = path.arrows.map((arrow) => {
    const kind = arrowKind(arrow);
    const id = `${arrow.from_topic}-${arrow.to_topic}`;
    return {
      id,
      source: String(arrow.from_topic),
      target: String(arrow.to_topic),
      label: arrowLabel(arrow),
      className: `cp-arrow ${kind}${selectedArrow === id ? " selected" : ""}`,
      markerEnd: { type: "arrowclosed", width: 18, height: 18, color: COLOURS[kind] },
      style: { stroke: COLOURS[kind], strokeWidth: selectedArrow === id ? 3 : 1.5, strokeDasharray: kind === "follows" ? undefined : "6 4" },
      data: { arrow },
    };
  });
  return { nodes, edges };
}
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd web-app && npx vitest run src/learning-path/coursePathModel.test.js`
Expected: PASS (3 tests).

- [ ] **Step 5: API functions** — append to `api.js`:

```javascript
// The Course path page: outline topics and the cross-topic links between them.
export function fetchCourseLearningPath(courseId) {
  return request(`/learning-path/courses/${courseId}/`);
}

// "approved" accepts a suggestion; "rejected" removes a course link for good.
export function decideCoursePathLink(courseId, linkId, status) {
  return request(`/learning-path/courses/${courseId}/links/${linkId}/decision/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  });
}

export function restoreCoursePathLinks(courseId, undo) {
  return request(`/learning-path/courses/${courseId}/links/restore/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ undo }),
  });
}
```

- [ ] **Step 6: The page** — `pages/CoursePathPage.jsx`:

```javascript
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Background, Controls, Handle, Position, ReactFlow } from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import { decideCoursePathLink, fetchCourseLearningPath, restoreCoursePathLinks } from "../api";
import ConfirmDialog from "../learning-path/ConfirmDialog";
import UndoBar from "../learning-path/UndoBar";
import { buildCourseGraph } from "../learning-path/coursePathModel";
import "../learning-path/pathGraph.css";
import "../learning-path/coursePath.css";

function TopicNode({ data }) {
  const { topic, empty } = data;
  return (
    <div className={`cp-topic${empty ? " empty" : ""}`} title={topic.title}>
      <Handle type="target" position={Position.Left} isConnectable={false} />
      <span className="cp-topic-position">{topic.position + 1}</span>
      <span className="cp-topic-title">{topic.title}</span>
      <Handle type="source" position={Position.Right} isConnectable={false} />
    </div>
  );
}

const NODE_TYPES = { topic: TopicNode };

export default function CoursePathPage() {
  const { courseId } = useParams();
  const [path, setPath] = useState(null);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState(null);
  const [confirm, setConfirm] = useState(null);
  const [busy, setBusy] = useState(false);
  const [undo, setUndo] = useState(null);

  useEffect(() => {
    fetchCourseLearningPath(courseId)
      .then(setPath)
      .catch((err) => setError(err.message || "Could not load the course path."));
  }, [courseId]);

  const graph = useMemo(() => (path ? buildCourseGraph(path, selected) : { nodes: [], edges: [] }), [path, selected]);
  const arrow = path?.arrows.find((item) => `${item.from_topic}-${item.to_topic}` === selected) || null;
  const topicTitle = (id) => path?.topics.find((topic) => topic.id === id)?.title || "";

  const decide = useCallback(async (link, status) => {
    setBusy(true);
    try {
      const result = await decideCoursePathLink(courseId, link.id, status);
      setPath(result);
      setConfirm(null);
      setUndo({
        records: result.undo,
        message: `${status === "approved" ? "Approved" : "Removed"}: ${link.prerequisite.title} → ${link.dependent.title}.`,
      });
    } catch (err) {
      setConfirm((current) => current && { ...current, error: err.message || "Could not save." });
    } finally {
      setBusy(false);
    }
  }, [courseId]);

  const handleUndo = useCallback(async () => {
    if (!undo) return;
    setBusy(true);
    try {
      setPath(await restoreCoursePathLinks(courseId, undo.records));
      setUndo(null);
    } catch (err) {
      setUndo((current) => current && { ...current, error: err.message || "Could not undo." });
    } finally {
      setBusy(false);
    }
  }, [courseId, undo]);
  const closeUndo = useCallback(() => setUndo(null), []);

  const ask = (link, status) => setConfirm({
    title: status === "approved" ? "Approve this link?" : "Remove this link?",
    message: `${link.prerequisite.title} (${topicTitle(link.prerequisite.topic_id)}) before ${link.dependent.title} (${topicTitle(link.dependent.topic_id)}).`,
    actions: [{ label: status === "approved" ? "Approve" : "Remove", primary: true, onClick: () => decide(link, status) }],
  });

  if (error) return <div className="error-banner">{error}</div>;
  if (!path) return <p className="muted-text">Loading the course path…</p>;

  return (
    <>
      <section className="card">
        <Link to={`/courses/${courseId}`} style={{ color: "var(--muted)" }}>Back to course</Link>
        <h2>Course path: {path.course.title}</h2>
        <p className="muted-text">
          Topics in your outline order. An arrow means a concept in one topic builds on a concept in another.
          Green follows your outline, yellow is a suggestion, red contradicts your outline.
        </p>
      </section>
      <div className="cp-layout">
        <div className="pg-canvas">
          <ReactFlow
            nodes={graph.nodes}
            edges={graph.edges}
            nodeTypes={NODE_TYPES}
            nodesDraggable={false}
            onEdgeClick={(_, edge) => setSelected(edge.id)}
            onPaneClick={() => setSelected(null)}
            fitView
          >
            <Background />
            <Controls showInteractive={false} />
          </ReactFlow>
        </div>
        {arrow && (
          <section className="pg-details cp-panel" aria-labelledby="cp-panel-title">
            <h3 id="cp-panel-title">{topicTitle(arrow.from_topic)} → {topicTitle(arrow.to_topic)}</h3>
            {arrow.contradicts_outline && (
              <p className="cp-warning">
                To follow these links, move “{topicTitle(arrow.from_topic)}” before “{topicTitle(arrow.to_topic)}” in the outline.
              </p>
            )}
            <ul className="pg-details-list">
              {arrow.links.map((link) => (
                <li key={link.id} className={`cp-link ${link.status}`}>
                  <strong>{link.prerequisite.title} → {link.dependent.title}</strong>
                  <span className="cp-link-status">{link.status}</span>
                  <p>{link.reason}</p>
                  <div className="action-row">
                    {link.status === "pending" && (
                      <button type="button" className="btn btn-small btn-primary" onClick={() => ask(link, "approved")}>Approve</button>
                    )}
                    <button type="button" className="btn btn-small btn-secondary" onClick={() => ask(link, "rejected")}>
                      {link.status === "pending" ? "Reject" : "Remove"}
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          </section>
        )}
      </div>
      {confirm && (
        <ConfirmDialog
          title={confirm.title}
          message={confirm.message}
          actions={confirm.actions}
          error={confirm.error}
          busy={busy}
          onCancel={() => setConfirm(null)}
        />
      )}
      {undo && <UndoBar message={undo.message} error={undo.error} busy={busy} onUndo={handleUndo} onClose={closeUndo} />}
    </>
  );
}
```

`learning-path/coursePath.css`:

```css
/* Course path page: topic boxes and the side panel. Arrow colours live in coursePathModel.js. */
.cp-layout { display: grid; grid-template-columns: 1fr minmax(260px, 340px); gap: 1rem; margin-top: 1rem; }
.cp-layout > .pg-canvas:only-child { grid-column: 1 / -1; }
.cp-topic {
  width: 220px; min-height: 60px; box-sizing: border-box; display: grid; grid-template-columns: auto 1fr;
  gap: 0.5rem; align-items: center; padding: 0.5rem 0.65rem; border: 2px solid #1f2a37; border-radius: 10px;
  background: #fff; color: #1f2a37; font-size: 0.85rem;
}
.cp-topic.empty { border-style: dashed; color: #8a96a3; border-color: #b8c2cc; background: #f7f9fb; }
.cp-topic-position { font-weight: 700; }
.cp-panel { align-self: start; }
.cp-warning { color: #b3261e; }
.cp-link { margin-bottom: 0.75rem; }
.cp-link-status { margin-left: 0.5rem; font-size: 0.75rem; text-transform: uppercase; color: #5b6b7b; }
@media (max-width: 900px) { .cp-layout { grid-template-columns: 1fr; } }
```

In `App.jsx` add `import CoursePathPage from "./pages/CoursePathPage";` beside `LearningPathPage`, and a route after the topic path route:

```javascript
      <Route
        path="/courses/:courseId/path"
        element={
          <RequireRole allow={[ROLES.TEACHER, ROLES.ADMIN]}>
            <div className="app-shell">
              <CoursePathPage />
            </div>
          </RequireRole>
        }
      />
```

In `CourseDetailPage.jsx`, inside the `course-header-row` div after the title block:

```javascript
          <Link to={`/courses/${id}/path`} className="btn btn-secondary">
            Course path
          </Link>
```

- [ ] **Step 7: Run the frontend suite and build**

Run: `cd web-app && npm test && npm run build`
Expected: all tests PASS, build succeeds.

- [ ] **Step 8: Check it in the browser** — start the dev servers from `.claude/launch.json` (or create entries for `python manage.py runserver` and `npm run dev`), log in as a teacher, open `/courses/<course id of topic 340>/path`: every outline topic shows, topics without content are dashed; no arrows yet (only 340 and 357 have content and they are unrelated). Screenshot for the user.

- [ ] **Step 9: Commit**

```bash
git add web-app/src/api.js web-app/src/App.jsx web-app/src/pages/CourseDetailPage.jsx web-app/src/pages/CoursePathPage.jsx web-app/src/learning-path/coursePathModel.js web-app/src/learning-path/coursePathModel.test.js web-app/src/learning-path/coursePath.css
git commit -m "Add the Course path page"
```

---

### Task 10: Course gold tooling

**Files:**
- Create: `backend/learning_path/management/commands/export_course_pairs.py`
- Modify: `backend/learning_path/services/gold.py` (add `load_course_gold`, `course_gold_report`)
- Test: `backend/learning_path/test_course_gold.py`

**Interfaces:**
- Produces:
  - Command: `python manage.py export_course_pairs <first_topic> <second_topic> --snapshot <md path>` writes both topics' concepts with full text; `… --map <map.json> --out <fixture.json>` freezes concepts with keys from the map.
  - Map format (`fixtures/gold_course_map_<a>_<b>.json`): `{"topics": [a, b], "_note", "concept_keys": {"<group id>": "key"}, "required": [[key, key]], "unrelated": false}`.
  - Fixture format (`fixtures/gold_course_<a>_<b>.json`): the map fields + `"concepts": {"<topic id>": [rows as in export_live_concepts]}`.
  - `gold.load_course_gold(first, second) -> (data, [concepts_of_first, concepts_of_second])` (stubs with `key`, as `load_gold`).
  - `gold.course_gold_report(data, topic_concepts, decisions) -> {accepted, pending, accepted_precision, reachable_count, required_count, unrelated_accepted, outline_flags: {right, wrong}}`.

- [ ] **Step 1: Write the failing tests** — `test_course_gold.py`:

```python
"""Course-level gold report (course spec section 7)."""

from django.test import SimpleTestCase

from .services.gold import course_gold_report
from .testing import concept


def decision(before, after, verdict, contradicts=False):
    return {"prerequisite": before, "dependent": after, "verdict": verdict,
            "evidence": {"contradicts_outline": contradicts}}


class CourseGoldReportTests(SimpleTestCase):
    def setUp(self):
        self.liquid = concept(1, "Liquid", "x", key="liquid")
        self.solid = concept(2, "Solid", "x", key="solid")
        self.evaporation = concept(3, "Evaporation", "x", key="evaporation")
        self.melting = concept(4, "Melting", "x", key="melting")
        self.topics = [[self.liquid, self.solid], [self.evaporation, self.melting]]
        self.data = {"required": [["liquid", "evaporation"], ["solid", "melting"]], "unrelated": False}

    def test_precision_and_reach(self):
        report = course_gold_report(self.data, self.topics, [
            decision(self.liquid, self.evaporation, "accepted"),
            decision(self.liquid, self.melting, "accepted"),
            decision(self.solid, self.melting, "pending"),
        ])

        self.assertEqual(report["accepted_precision"], 0.5)
        self.assertEqual((report["reachable_count"], report["required_count"]), (2, 2))

    def test_an_unrelated_pair_counts_every_accepted_link(self):
        report = course_gold_report({"required": [], "unrelated": True}, self.topics, [
            decision(self.liquid, self.evaporation, "accepted"),
        ])

        self.assertEqual(report["unrelated_accepted"], 1)

    def test_an_outline_flag_is_right_only_when_the_key_agrees(self):
        report = course_gold_report(self.data, self.topics, [
            decision(self.evaporation, self.liquid, "pending", contradicts=True),
        ])

        self.assertEqual(report["outline_flags"], {"right": 0, "wrong": 1})
```

- [ ] **Step 2: Run to verify they fail**

Run: `python manage.py test learning_path.test_course_gold`
Expected: FAIL — `ImportError: cannot import name 'course_gold_report'`.

- [ ] **Step 3: Implement in `gold.py`** — append:

```python
def load_course_gold(first_topic, second_topic):
    """``(map data, [concepts of first, concepts of second])`` from a frozen course fixture."""
    data = json.loads(
        (FIXTURES / f"gold_course_{first_topic}_{second_topic}.json").read_text(encoding="utf-8")
    )
    topics, next_id = [], 1
    for topic_id in data["topics"]:
        concepts = []
        for index, row in enumerate(data["concepts"][str(topic_id)]):
            members = tuple(SimpleNamespace(**member) for member in row["members"])
            text = "\n".join(member.content for member in members)
            concepts.append(SimpleNamespace(
                id=next_id, key=row["key"], title=row["title"], content=text, member_text=text,
                section_title=row["section_title"], kind=row.get("kind", "text"), order=index, members=members,
            ))
            next_id += 1
        topics.append(concepts)
    return data, topics


def course_gold_report(data, topic_concepts, decisions):
    """How cross-topic decisions measure up against a course key (course spec section 7)."""
    key = {concept.id: concept.key for topic in topic_concepts for concept in topic}
    required = {tuple(edge) for edge in data["required"]}

    def keyed(row):
        return key.get(row["prerequisite"].id), key.get(row["dependent"].id)

    accepted = [keyed(row) for row in decisions if row["verdict"] == criteria.ACCEPTED]
    pending = [keyed(row) for row in decisions if row["verdict"] == criteria.PENDING]
    flags = {"right": 0, "wrong": 0}
    for row in decisions:
        if (row.get("evidence") or {}).get("contradicts_outline"):
            flags["right" if keyed(row) in required else "wrong"] += 1
    reachable = required & (set(accepted) | set(pending))
    return {
        "accepted": [list(edge) for edge in accepted],
        "pending": [list(edge) for edge in pending],
        "accepted_precision": (
            sum(1 for edge in accepted if edge in required) / len(accepted) if accepted else None
        ),
        "reachable_count": len(reachable),
        "required_count": len(required),
        "unrelated_accepted": len(accepted) if data.get("unrelated") else 0,
        "outline_flags": flags,
    }
```

- [ ] **Step 4: Implement the command** — `export_course_pairs.py`:

```python
"""Snapshot two topics for a course-level answer key, or freeze them as a fixture.

``--snapshot`` writes both topics' concepts with their full text, the input
given to the AI tool that drafts the key. ``--map`` + ``--out`` freeze the
concepts the pipeline derives today, labelled from the map, so the course gold
report runs without the database (the same idea as ``export_live_concepts``).
"""

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from lessons.models import OutlineNode
from learning_path.services.concept_units import concepts_for_topic


class Command(BaseCommand):
    help = "Snapshot or freeze two topics' concepts for the course-level gold report."

    def add_arguments(self, parser):
        parser.add_argument("first_topic", type=int)
        parser.add_argument("second_topic", type=int)
        parser.add_argument("--snapshot")
        parser.add_argument("--map")
        parser.add_argument("--out")

    def handle(self, *args, first_topic, second_topic, snapshot=None, map=None, out=None, **options):
        if not snapshot and not (map and out):
            raise CommandError("Give --snapshot PATH, or --map MAP --out FIXTURE.")
        topics = []
        for topic_id in (first_topic, second_topic):
            node = OutlineNode.objects.filter(pk=topic_id).first()
            if node is None:
                raise CommandError(f"No outline node {topic_id}.")
            topics.append((node, list(concepts_for_topic(node))))

        if snapshot:
            lines = [f"# Topics {first_topic} and {second_topic}: concepts with full text", ""]
            for node, concepts in topics:
                lines += [f"## {node.title} (topic {node.id})", ""]
                for index, concept in enumerate(concepts, start=1):
                    lines.append(f"{index}. {concept.title}")
                    for member in concept.members:
                        lines.append(f"   - [{member.material.title}] {' '.join((member.content or '').split())}")
                    lines.append("")
            Path(snapshot).write_text("\n".join(lines) + "\n", encoding="utf-8")
            self.stdout.write(self.style.SUCCESS(f"Wrote {snapshot}"))

        if map and out:
            spec = json.loads(Path(map).read_text(encoding="utf-8"))
            keys = {int(concept_id): key for concept_id, key in spec["concept_keys"].items()}
            output = {name: spec[name] for name in ("topics", "required", "unrelated")}
            output["_note"] = spec.get("_note", "")
            output["concepts"] = {
                str(node.id): [
                    {
                        "key": keys.get(concept.id),
                        "concept_id": concept.id,
                        "title": concept.title,
                        "section_title": concept.section_title,
                        "kind": concept.kind,
                        "members": [
                            {"title": member.title, "section_title": member.section_title or "",
                             "content": member.content or "", "material_id": member.material_id, "order": member.order}
                            for member in concept.members
                        ],
                    }
                    for concept in concepts
                ]
                for node, concepts in topics
            }
            Path(out).write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
            self.stdout.write(self.style.SUCCESS(f"Wrote {out}"))
```

- [ ] **Step 5: Run to verify they pass**

Run: `python manage.py test learning_path.test_course_gold`
Expected: PASS (3 tests).

- [ ] **Step 6: Check the command on live data** (read-only)

Run: `python manage.py export_course_pairs 340 357 --snapshot ../docs/course-pair-340-357-2026-09-30.md`
Expected: `Wrote ../docs/course-pair-340-357-2026-09-30.md` listing 15 + 10 concepts.

- [ ] **Step 7: Commit**

```bash
git add backend/learning_path/management/commands/export_course_pairs.py backend/learning_path/services/gold.py backend/learning_path/test_course_gold.py docs/course-pair-340-357-2026-09-30.md
git commit -m "Add course-level gold tooling"
```

---

### Task 11: Hand-off note for the adaptive engine

**Files:**
- Create: `docs/handoff-course-prerequisites.md`

- [ ] **Step 1: Write the note** with these sections (plain prose, no code changes elsewhere):
  1. **What the field is** — `course_prerequisites` on every step of `GET /api/learning-path/topics/<id>/published/` (and `get_published_path`): a list of `{topic_id, concept_id, position, status}`; meaning "this step's concept builds on that concept of an earlier topic, confirmed by the evidence (accepted) or by a teacher (approved)".
  2. **Guarantees** — earlier topics only (outline order); published targets only (a saved step exists at `position` in that topic's published path); never pending or rejected links; nearest topic first; changes only when a topic is published again.
  3. **Suggested use in `_reroute`** — after the in-topic prerequisite detour and before the alternate chunk: detour to the first entry; the remediation-stack frame must also record the topic so `_resume_or_advance` returns the learner to the topic and step they left; keep one detour per step (`remediated_positions`, keyed by topic too) and `MAX_REMEDIATION_DEPTH`; log it as `DETOUR_PREREQUISITE` with the topic in the decision log.
  4. **Example payload** — a real step from topic 357 or 340 (empty list today; replace with a real entry once 341/345 are uploaded and a link is approved).
  5. **Contact** — decisions about using it are the adaptive engine owner's.

- [ ] **Step 2: Commit**

```bash
git add docs/handoff-course-prerequisites.md
git commit -m "Add the course prerequisites hand-off note for the adaptive engine"
```

---

### Task 12: Documentation

**Files:**
- Modify: `backend/learning_path/CRITERIA.md`, `docs/open-issues-2026-09-30.md`, `docs/AGENT_LOG.md`

- [ ] **Step 1:** `CRITERIA.md` — add a section "Course level" (five lines: pairs across topics, outline order as structure, the cross-topic verdict table, `CourseConceptLink`, `course_prerequisites`), linking the course spec.
- [ ] **Step 2:** `open-issues-2026-09-30.md` 1.5 — mark "implemented, evaluation waiting for uploads 341/345" with links to the spec and the hand-off note.
- [ ] **Step 3:** `AGENT_LOG.md` — append a session entry (template at the top of the file): commits, tests, live database untouched, rulings, not done (evaluation).
- [ ] **Step 4: Run everything and commit**

Run: `python manage.py test` (backend) and `cd web-app && npm test && npm run build`
Expected: all PASS.

```bash
git add backend/learning_path/CRITERIA.md docs/open-issues-2026-09-30.md docs/AGENT_LOG.md
git commit -m "Document the course-level learning path"
```

---

### Task 13: Evaluation (blocked until 341 and 345 are uploaded and grouped)

**Files:**
- Create: `docs/course-pair-340-341-2026-*.md`, `docs/course-pair-340-345-*.md`, `docs/course-pair-341-345-*.md`, the maps and fixtures `backend/learning_path/fixtures/gold_course_map_*.json` / `gold_course_*.json`, `backend/learning_path/test_course_gold_paths.py`, `docs/course-path-evaluation-<date>.md`

- [ ] **Step 1:** Confirm 341 and 345 have concepts: `python manage.py shell -c "…concepts_for_topic…"` for each.
- [ ] **Step 2:** Write snapshots for 340↔341, 340↔345, 341↔345 with `export_course_pairs … --snapshot`; the user gets the AI tool's answer for each (same tool and prompt style as 340/357).
- [ ] **Step 3:** Encode each answer as `gold_course_map_<a>_<b>.json` (`_note` says AI-drafted), plus `unrelated: true` maps for 357↔340/341/345 with empty `required`; freeze with `--map … --out gold_course_<a>_<b>.json`.
- [ ] **Step 4:** Design pair 340↔341 only: run `decide_course_pairs` + `course_gold_report`; if `MIN_AGREEING_CONTENT` or a verdict row must change, change it here only and record the ruling.
- [ ] **Step 5:** Test pairs (345 with 340 and 341) and the unrelated controls: measure without changes. `unrelated_accepted` must be 0.
- [ ] **Step 6:** Write `docs/course-path-evaluation-<date>.md` (tables per pair, clue counts, ablation, caveats) and `test_course_gold_paths.py` with measured floors (skip when fixtures are missing); commit.
