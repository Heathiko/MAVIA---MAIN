# Course-level path, top down — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Course-level links found top down (outline titles → concept shortlist → strict confirmation), and a Course path page whose topic graph flows top to bottom with a learning-order list below it.

**Architecture:** A new `services/course_shortlist.py` holds the outline gate and the shortlist ranking. `course_criteria.decide_course_pairs` gains `rule="shortlist"` (new) beside `"strict"` (today, still the default until the final check). `course_links.course_path` adds each topic's steps and each link's rank. The React page swaps its grid layout for a dagre top-to-bottom layout and renders a learning-order list from a pure model function.

**Tech Stack:** Django, `SimpleTestCase`/`TestCase`; React + `@xyflow/react` + `@dagrejs/dagre`; vitest.

**Spec:** `docs/superpowers/specs/2026-10-02-course-path-top-down-design.md` (758e03c).

## Global Constraints

- `TOPIC_TITLE_CUTOFF = 0.30`, `SHORTLIST_SIZE = 3`; changeable only from design pairs, in Task 7.
- Design pairs: 340-341, 340-343, 340-347, 343-348 and controls 340-357, 341-357, 343-357, 347-357, 348-357. Final pairs: 351-353, 341-343, 341-347, 347-348, 351-365, 353-365 — **never** scored, printed or opened before Task 8; their keys (`docs/course-path-new-keys/`) are drafted blind by a separate agent and must not be read by the executor.
- The old rule (`"strict"`) keeps its exact behaviour and stays the default until the stop rule passes; all existing course tests stay green unmodified.
- No new dependency; no word lists. Titles count as "real names" via the existing `ConceptText.name` (`name_terms`).
- Names: descriptive but short, plain English, like the surrounding code.
- Commits: one plain sentence, ending with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Backend tests from `backend/`: `python manage.py test learning_path.<module>`; frontend from `web-app/`: `npx vitest run src/learning-path` and `npm run build`.

## Review Focus

1. A later concept whose title is not a real name ("2", a sentence) must still get a shortlist, ranked by lesson text. (Task 1 test.)
2. With the encoder unavailable, `rule="shortlist"` must fall back to the strict rule (pending only), never crash. (Task 2 test.)
3. A teacher's `rejected` (dismissed) shortlist entry must stay dismissed after the page re-derives. (Task 3 test.)
4. A topic with no saved path must still list its steps, marked not published. (Task 3 test.)
5. A course with no arrows must still lay out every topic (all in the "Not linked yet" strip) and the page must not break. (Task 5 test.)

---

### Task 1: Outline gate and shortlist helpers

**Files:**
- Create: `backend/learning_path/services/course_shortlist.py`
- Test: `backend/learning_path/test_course_shortlist.py`

**Interfaces:**
- Produces: `TOPIC_TITLE_CUTOFF`, `SHORTLIST_SIZE`; `unit_vectors(strings, embed) -> np.ndarray`; `topic_similarities(topic_titles, embed) -> {(i, j): float}` for `i < j`; `title_vectors(texts, embed) -> {text.id: vector}`; `concept_score(first, second, vectors) -> (float, "title"|"content")`; `shortlist(earlier, later_text, vectors, size=SHORTLIST_SIZE) -> [(text, rank, score, ranked_by)]`.

- [ ] **Step 1: Write the failing tests**

```python
"""Top-down course level: the outline gate and the concept shortlist (course spec 2026-10-02, section 3)."""

from django.test import SimpleTestCase

from .services.concept_text import prepare
from .services.course_shortlist import (
    SHORTLIST_SIZE, concept_score, shortlist, title_vectors, topic_similarities,
)
from .testing import concept, word_vectors


def texts(*concepts):
    return prepare(list(concepts), embed=word_vectors)


class TopicSimilarityTests(SimpleTestCase):
    def test_related_titles_score_higher_than_unrelated_ones(self):
        scores = topic_similarities(["Flower parts", "Flower reproduction", "Weather"], word_vectors)

        self.assertGreater(scores[(0, 1)], scores[(0, 2)])
        self.assertEqual(set(scores), {(0, 1), (0, 2), (1, 2)})


class ShortlistTests(SimpleTestCase):
    def test_names_are_ranked_by_title(self):
        earlier = texts(
            concept(1, "Liquid", "A liquid flows and takes the shape of its container."),
            concept(2, "Solid", "A solid keeps its own shape all the time."),
        )
        [later] = texts(concept(3, "Liquid mixtures", "Some mixtures are made by stirring things into water."))
        vectors = title_vectors(earlier + [later], word_vectors)

        ranked = shortlist(earlier, later, vectors)

        self.assertEqual([(text.id, rank, by) for text, rank, _, by in ranked], [(1, 1, "title"), (2, 2, "title")])

    def test_a_title_that_is_not_a_name_is_ranked_by_text(self):
        earlier = texts(concept(1, "Liquid", "A liquid flows and takes the shape of its container."))
        [later] = texts(concept(3, "Pour the water into the cup and watch how the liquid flows away",
                                "Pour the liquid and watch it flow into the container."))
        vectors = title_vectors(earlier + [later], word_vectors)

        _, ranked_by = concept_score(earlier[0], later, vectors)

        self.assertEqual(ranked_by, "content")

    def test_only_the_closest_few_are_kept(self):
        earlier = texts(*[concept(index, f"Topic word {index}", f"Sentence number {index} about matter.")
                          for index in range(1, 6)])
        [later] = texts(concept(9, "Matter", "Matter takes up space in every form."))
        vectors = title_vectors(earlier + [later], word_vectors)

        self.assertEqual(len(shortlist(earlier, later, vectors)), SHORTLIST_SIZE)

    def test_concepts_without_a_full_sentence_are_not_candidates(self):
        earlier = texts(concept(1, "Liquid", "Flows."), concept(2, "Solid", "A solid keeps its own shape."))
        [later] = texts(concept(3, "Liquid mixtures", "Some mixtures are made by stirring things into water."))
        vectors = title_vectors(earlier + [later], word_vectors)

        self.assertEqual([text.id for text, *_ in shortlist(earlier, later, vectors)], [2])
```

- [ ] **Step 2: Run** `python manage.py test learning_path.test_course_shortlist` — Expected: ERROR, `No module named 'learning_path.services.course_shortlist'`.

- [ ] **Step 3: Implement** `backend/learning_path/services/course_shortlist.py`:

```python
"""The top-down course level: which topics to compare, and which concepts to shortlist.

Spec: docs/superpowers/specs/2026-10-02-course-path-top-down-design.md, section 3.
Level 1 compares the outline's topic titles; level 2 ranks an earlier topic's
concepts for each concept of a later topic by concept title, or by lesson text
when a title is not a real name (a page label, a whole sentence).
"""

import numpy as np

from .relatedness import relatedness

# Design pairs, 2026-10-02: linked topic pairs scored 0.34-0.71, the same-subject
# pair with no links 0.22, unrelated pairs 0.00-0.20.
TOPIC_TITLE_CUTOFF = 0.30
SHORTLIST_SIZE = 3


def unit_vectors(strings, embed):
    vectors = np.asarray(embed(list(strings)), dtype="float32")
    if not len(vectors):
        return vectors
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return vectors / norms


def topic_similarities(topic_titles, embed):
    """``{(earlier, later): cosine of the two outline titles}`` for every ordered pair of topics."""
    vectors = unit_vectors(topic_titles, embed)
    return {
        (first, second): round(float(vectors[first] @ vectors[second]), 3)
        for first in range(len(topic_titles))
        for second in range(first + 1, len(topic_titles))
    }


def title_vectors(texts, embed):
    """``{concept id: unit vector of its title}``."""
    vectors = unit_vectors([text.concept.title or "" for text in texts], embed)
    return {text.id: vector for text, vector in zip(texts, vectors)}


def concept_score(first, second, vectors):
    """``(score, ranked_by)``: title cosine when both titles are names, else the lesson-text score."""
    if first.name and second.name:
        return float(vectors[first.id] @ vectors[second.id]), "title"
    return float(relatedness(first, second)), "content"


def shortlist(earlier, later_text, vectors, size=SHORTLIST_SIZE):
    """The ``size`` concepts of ``earlier`` closest to ``later_text``, as ``(text, rank, score, ranked_by)``."""
    scored = []
    for text in earlier:
        if not text.sentences:
            continue
        score, ranked_by = concept_score(text, later_text, vectors)
        scored.append((score, text, ranked_by))
    scored.sort(key=lambda item: -item[0])  # stable: ties keep the earlier topic's order
    return [(text, rank, round(score, 3), ranked_by) for rank, (score, text, ranked_by) in enumerate(scored[:size], start=1)]
```

- [ ] **Step 4: Run** the tests — Expected: OK.
- [ ] **Step 5: Commit** — `git add backend/learning_path/services/course_shortlist.py backend/learning_path/test_course_shortlist.py`; message "Add the outline gate and the concept shortlist for the course-level path".

---

### Task 2: `decide_course_pairs(rule="shortlist")`

**Files:**
- Modify: `backend/learning_path/services/course_criteria.py`, `backend/learning_path/services/course_links.py` (`refresh_course_links`), `backend/learning_path/services/reasons.py`
- Test: `backend/learning_path/test_course_criteria.py` (append), `backend/learning_path/test_reasons.py` (append)

**Interfaces:**
- Consumes: Task 1.
- Produces: `course_criteria.STRICT = "strict"`, `SHORTLIST = "shortlist"`, `COURSE_RULES`, `COURSE_DEFAULT_RULE = STRICT`; `decide_course_pairs(topic_concepts, calibration=None, embed=None, rule=None, topic_titles=None)`. Shortlist rows: `evidence.rule == "course-shortlist"` with `rank`, `ranked_by`, `score`, `topic_similarity`, `confirmed`, plus the old course fields. `refresh_course_links(course, embed=None, rule=None)` passes outline titles.

- [ ] **Step 1: Write the failing tests** (append to `test_course_criteria.py`; add `SHORTLIST` to its `from .services.course_criteria import ...` line)

```python
def decide_by_shortlist(topic_concepts, titles, embed=word_vectors):
    return {
        (row["prerequisite"].id, row["dependent"].id): row
        for row in decide_course_pairs(topic_concepts, calibration=CALIBRATION, embed=embed,
                                       rule=SHORTLIST, topic_titles=titles)
    }


class ShortlistRuleTests(SimpleTestCase):
    """Course spec 2026-10-02, section 3."""

    titles = ["Flower parts", "Flower reproduction"]

    def test_a_shortlisted_link_the_text_confirms_is_accepted(self):
        row = decide_by_shortlist([[stamen(), petals()], [pollination()]], self.titles)[(1, 2)]

        self.assertEqual(row["verdict"], ACCEPTED)
        self.assertEqual(row["evidence"]["rule"], "course-shortlist")
        self.assertTrue(row["evidence"]["confirmed"])
        self.assertEqual(row["evidence"]["rank"], 1)

    def test_other_shortlisted_concepts_go_to_the_teacher(self):
        row = decide_by_shortlist([[stamen(), petals()], [pollination()]], self.titles)[(4, 2)]

        self.assertEqual(row["verdict"], PENDING)
        self.assertFalse(row["evidence"]["confirmed"])
        self.assertEqual(row["evidence"]["rank"], 2)

    def test_topics_with_unrelated_titles_are_never_compared(self):
        self.assertEqual(decide_by_shortlist([[stamen(), petals()], [pollination()]], ["Flower parts", "Weather"]), {})

    def test_without_the_encoder_the_strict_rule_runs(self):
        decided = decide_by_shortlist([[stamen(), petals()], [pollination()]], self.titles, embed=no_encoder)

        self.assertEqual({row["verdict"] for row in decided.values()}, {PENDING})
        self.assertEqual({row["evidence"]["rule"] for row in decided.values()}, {"course"})

    def test_evidence_is_json_serialisable(self):
        import json

        json.dumps([row["evidence"] for row in decide_by_shortlist([[stamen(), petals()], [pollination()]], self.titles).values()])

    def test_the_strict_rule_is_still_the_default(self):
        self.assertEqual({row["evidence"]["rule"] for row in decide([[stamen(), petals()], [pollination()]]).values()}, {"course"})
```

and append to `test_reasons.py`:

```python
class ShortlistReasonTests(SimpleTestCase):
    def test_an_unconfirmed_entry_says_it_is_a_close_match(self):
        evidence = {"rule": "course-shortlist", "confirmed": False, "rank": 2, "votes": {}, "records": {}}

        self.assertEqual(
            link_reason(evidence, "Liquid", "Solutions"),
            "One of the 3 closest matches for Solutions in its earlier topic (rank 2). Please confirm or dismiss.",
        )

    def test_a_confirmed_entry_reads_like_a_course_link(self):
        evidence = {"rule": "course-shortlist", "confirmed": True, "rank": 1,
                    "votes": {"name": 1, "terms": 1}, "records": {"terms": {"owned": ["flow"]}}}

        self.assertEqual(
            link_reason(evidence, "Liquid", "Solutions"),
            "Solutions uses terms Liquid explains (flow). Solutions names Liquid. This follows your outline.",
        )
```

- [ ] **Step 2: Run** `python manage.py test learning_path.test_course_criteria learning_path.test_reasons` — Expected: ImportError on `SHORTLIST`.

- [ ] **Step 3: Implement `course_criteria.py`**

Add imports `from .course_shortlist import SHORTLIST_SIZE, TOPIC_TITLE_CUTOFF, shortlist, title_vectors, topic_similarities`. Add after `COURSE_CLUES`:

```python
STRICT = "strict"
SHORTLIST = "shortlist"
COURSE_RULES = (STRICT, SHORTLIST)
# The strict rule until the shortlist passes the final check (course spec 2026-10-02, section 5).
COURSE_DEFAULT_RULE = STRICT
```

Split `_decide` into the vote part and the row part — replace `_decide` with:

```python
def _votes(first, second, owners, calibration, semantic):
    return {
        "name": name_vote(first, second)[0],
        "terms": term_vote(first, second, owners)[0],
        "meaning": meaning_vote(first, second, calibration["meaning_cutoff"])[0] if semantic else 0,
        "outline": 1,
    }


def _row(first, second, votes, outcome, direction, owners, calibration, semantic, score, extra=None):
    prerequisite, dependent = (first, second) if direction > 0 else (second, first)
    oriented = {clue: vote * direction for clue, vote in votes.items()}
    voting = [clue for clue in oriented if oriented[clue]]
    records = clue_records(prerequisite, dependent, owners, {}, calibration["meaning_cutoff"], semantic)
    records.pop("heading", None)
    records.pop("order", None)
    evidence = {
        "rule": "course",
        "relatedness": None if score is None else round(score, 3),
        "confidence": round(sum(1 for clue in voting if oriented[clue] == 1) / len(voting), 3) if voting else 0.0,
        "votes": oriented,
        "records": records,
        "contradicts_outline": direction < 0,
        "semantic": semantic,
    }
    evidence.update(extra or {})
    return {"prerequisite": prerequisite.concept, "dependent": dependent.concept, "verdict": outcome, "evidence": evidence}


def _decide(first, second, owners, calibration, semantic):
    """The strict rule's link between ``first`` (earlier topic) and ``second`` (later topic), or ``None``."""
    if not (first.sentences and second.sentences):
        return None
    score = relatedness(first, second) if semantic else None
    if semantic and score < calibration["related_cutoff"]:
        return None
    votes = _votes(first, second, owners, calibration, semantic)
    outcome, direction = course_verdict(votes, semantic)
    if outcome not in (ACCEPTED, PENDING):
        return None
    return _row(first, second, votes, outcome, direction, owners, calibration, semantic, score)


def _shortlisted(earlier, later, owners, calibration, vectors, similarity):
    """Course spec 2026-10-02 section 3, levels 2 and 3, for one related pair of topics."""
    rows = []
    for second in later:
        if not second.sentences:
            continue
        for first, rank, score, ranked_by in shortlist(earlier, second, vectors):
            votes = _votes(first, second, owners, calibration, True)
            outcome, direction = course_verdict(votes, True)
            confirmed = outcome == ACCEPTED
            if outcome not in (ACCEPTED, PENDING):
                outcome, direction = PENDING, 1
            extra = {"rule": "course-shortlist", "rank": rank, "ranked_by": ranked_by, "score": score,
                     "topic_similarity": similarity, "confirmed": confirmed}
            rows.append(_row(first, second, votes, outcome, direction, owners, calibration, True,
                             relatedness(first, second), extra))
    return rows
```

Change `decide_course_pairs`'s signature and loop:

```python
def decide_course_pairs(topic_concepts, calibration=None, embed=None, rule=None, topic_titles=None):
    """Every cross-topic pair the evidence accepts or sends to the teacher.

    ``topic_concepts`` lists each topic's concepts, topics in outline order;
    ``topic_titles`` their outline titles. ``rule`` is ``STRICT`` (name and
    terms must agree) or ``SHORTLIST`` (outline gate, concept shortlist, strict
    confirmation); default ``COURSE_DEFAULT_RULE``. The shortlist needs the
    encoder and the titles; without either the strict rule runs.
    Term ownership is read over the two topics of a pair together, so a term a
    later topic introduces can point back at an earlier topic's concept.
    """
    calibration = calibration or load_calibration()
    rule = rule or COURSE_DEFAULT_RULE
    encode = embed or embeddings.embed
    concepts = [concept for topic in topic_concepts for concept in topic]
    semantic = True
    try:
        texts = prepare(concepts, embed=encode)
    except embeddings.EncoderUnavailable:
        texts, semantic = prepare(concepts), False
    by_topic, start = [], 0
    for topic in topic_concepts:
        by_topic.append(texts[start:start + len(topic)])
        start += len(topic)

    use_shortlist = rule == SHORTLIST and semantic and topic_titles is not None
    if use_shortlist:
        similarities = topic_similarities(topic_titles, encode)
        vectors = title_vectors(texts, encode)

    decisions = []
    for first_index, earlier in enumerate(by_topic):
        for second_index in range(first_index + 1, len(by_topic)):
            later = by_topic[second_index]
            owners = find_term_owners(earlier + later)
            if use_shortlist:
                similarity = similarities[(first_index, second_index)]
                if similarity >= TOPIC_TITLE_CUTOFF:
                    decisions.extend(_shortlisted(earlier, later, owners, calibration, vectors, similarity))
                continue
            for first in earlier:
                for second in later:
                    row = _decide(first, second, owners, calibration, semantic)
                    if row:
                        decisions.append(row)
    return decisions
```

(`SHORTLIST_SIZE` need not be imported if unused; import only what is used.)

- [ ] **Step 4: Implement the reason** — in `reasons.py`, before `def link_reason`, add:

```python
def _shortlist_reason(evidence, a, b):
    if evidence.get("confirmed"):
        return _course_reason(evidence, a, b)
    return (f"One of the 3 closest matches for {b} in its earlier topic (rank {evidence.get('rank')}). "
            "Please confirm or dismiss.")
```

and in `link_reason`, after the `rule == "course"` branch:

```python
    if rule == "course-shortlist":
        return _shortlist_reason(evidence, a, b)
```

(`_course_reason` already prints "B uses terms A explains (…). B names A. This follows your outline." for those votes; the test pins that wording.)

- [ ] **Step 5: Pass titles from the live derivation** — in `course_links.refresh_course_links`, change the signature to `def refresh_course_links(course, embed=None, rule=None):` and the decide call to:

```python
    decisions = decide_course_pairs(
        [list(concepts_for_topic(topic)) for topic in topics], embed=embed, rule=rule,
        topic_titles=[topic.title for topic in topics],
    )
```

- [ ] **Step 6: Run** `python manage.py test learning_path.test_course_criteria learning_path.test_reasons learning_path.test_course_links learning_path.test_course_gold learning_path.test_course_gold_paths` — Expected: OK.
- [ ] **Step 7: Commit** — message "Let the course level shortlist concepts under related outline topics when asked".

---

### Task 3: `course_path` lists each topic's steps and each link's rank

**Files:**
- Modify: `backend/learning_path/services/course_links.py` (`course_path`)
- Test: `backend/learning_path/test_course_links.py` (append to the class that builds `CourseFixture`; find it with `grep -n "class .*CourseFixture" test_course_links.py`)

- [ ] **Step 1: Write the failing tests** (append a new class)

```python
class CoursePathStepsTests(CourseFixture):
    def test_an_unpublished_topic_lists_its_concepts_in_order(self):
        topic = next(item for item in course_path(self.course)["topics"] if item["id"] == self.flowers.id)

        self.assertFalse(topic["published"])
        self.assertEqual([step["title"] for step in topic["steps"]], ["Stamen", "Petals"])
        self.assertEqual([step["position"] for step in topic["steps"]], [1, 2])

    def test_a_published_topic_lists_its_saved_order(self):
        LearningPathStep.objects.create(outline_node=self.flowers, concept=self.groups["Petals"], position=1)
        LearningPathStep.objects.create(outline_node=self.flowers, concept=self.groups["Stamen"], position=2)

        topic = next(item for item in course_path(self.course)["topics"] if item["id"] == self.flowers.id)

        self.assertTrue(topic["published"])
        self.assertEqual([step["title"] for step in topic["steps"]], ["Petals", "Stamen"])

    def test_a_topic_without_content_has_no_steps(self):
        topic = next(item for item in course_path(self.course)["topics"] if item["id"] == self.empty.id)

        self.assertEqual(topic["steps"], [])

    def test_each_link_carries_its_shortlist_rank(self):
        CourseConceptLink.objects.create(
            course=self.course, prerequisite=self.groups["Stamen"], dependent=self.groups["Pollination"],
            status="pending", evidence={"rule": "course-shortlist", "rank": 2, "confirmed": False},
        )

        [arrow] = course_path(self.course)["arrows"]

        self.assertEqual(arrow["links"][0]["rank"], 2)

    def test_a_dismissed_entry_stays_dismissed_after_re_deriving(self):
        link = CourseConceptLink.objects.create(
            course=self.course, prerequisite=self.groups["Petals"], dependent=self.groups["Pollination"],
            status="rejected", evidence={"rule": "course-shortlist", "rank": 2, "confirmed": False},
        )

        refresh_course_links(self.course, embed=word_vectors, rule="shortlist")

        link.refresh_from_db()
        self.assertEqual(link.status, "rejected")
```

Check how `CourseFixture.setUp` keys `self.groups` (by title, as above) and whether its concepts list in the order Stamen, Petals (created in that order); if `self.groups` uses another key, adapt the four lookups — a ruling, not a behaviour change.

- [ ] **Step 2: Run** `python manage.py test learning_path.test_course_links` — Expected: FAIL/KeyError (`published`, `steps`, `rank`).

- [ ] **Step 3: Implement** — in `course_links.py` add `from ..models import CourseConceptLink, LearningPathStep` (extend the existing import) and, above `course_path`:

```python
def _topic_steps(topic, titles):
    """``(published, steps)``: the saved path's order, or the topic's current concept order."""
    saved = list(LearningPathStep.objects.filter(outline_node=topic).order_by("position").values_list("concept_id", "position"))
    if saved:
        return True, [{"concept_id": concept_id, "title": titles.get(concept_id, "Untitled concept"), "position": position}
                      for concept_id, position in saved]
    return False, [{"concept_id": concept.id, "title": concept.title or "Untitled concept", "position": index}
                   for index, concept in enumerate(concepts_for_topic(topic), start=1)]
```

In `course_path`, add `"rank": (row.evidence or {}).get("rank"),` to each link dict, and build topics as:

```python
    topic_rows = []
    for topic in topics:
        published, steps = _topic_steps(topic, titles) if topic.id in with_content else (False, [])
        topic_rows.append({
            "id": topic.id, "title": topic.title, "position": position[topic.id],
            "has_content": topic.id in with_content, "published": published, "steps": steps,
        })
```

and return `"topics": topic_rows`.

- [ ] **Step 4: Run** `python manage.py test learning_path.test_course_links` — Expected: OK.
- [ ] **Step 5: Commit** — message "Give the Course path page each topic's steps and each link's shortlist rank".

---

### Task 4: Course evaluation command and its lock

**Files:**
- Create: `backend/learning_path/fixtures/course_topic_titles.json`, `backend/learning_path/management/commands/evaluate_course_paths.py`
- Modify: `backend/learning_path/services/gold.py` (append `course_shortlist_hits`)
- Test: `backend/learning_path/test_course_evaluation.py`

- [ ] **Step 1: Titles fixture** — write it from the database (titles only):

```bash
cd backend && python - <<'EOF'
import json, os, sys, django
sys.path.insert(0, "."); os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings"); django.setup()
from lessons.models import OutlineNode
ids = [340, 341, 343, 347, 348, 351, 353, 357, 365]
titles = {str(node.id): node.title for node in OutlineNode.objects.filter(id__in=ids)}
json.dump({"_note": "Outline titles of the topics in the course gold fixtures (fixtures carry none).", "titles": titles},
          open("learning_path/fixtures/course_topic_titles.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)
print(sorted(titles))
EOF
```

- [ ] **Step 2: Write the failing tests** — `backend/learning_path/test_course_evaluation.py`:

```python
"""Course-level evaluation: shortlist hits and the final-check lock (course spec 2026-10-02, section 5)."""

from types import SimpleNamespace

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase

from .services.criteria import ACCEPTED, PENDING
from .services.gold import course_shortlist_hits


def concept(id, key):
    return SimpleNamespace(id=id, key=key)


class ShortlistHitTests(SimpleTestCase):
    def test_a_dependent_counts_when_any_key_prerequisite_is_offered(self):
        liquid, solid, solutions, air = concept(1, "liquid"), concept(2, "solid"), concept(3, "solutions"), concept(4, "air")
        data = {"required": [["liquid", "solutions"], ["solid", "air"]]}
        decisions = [
            {"prerequisite": liquid, "dependent": solutions, "verdict": PENDING},
            {"prerequisite": liquid, "dependent": air, "verdict": ACCEPTED},
        ]

        hits = course_shortlist_hits(data, [[liquid, solid], [solutions, air]], decisions)

        self.assertEqual(hits, {"dependents": 2, "hit": 1, "offered": 2})


class CourseFinalCheckLockTests(SimpleTestCase):
    def test_a_final_pair_needs_the_flag(self):
        with self.assertRaisesMessage(CommandError, "--final-check"):
            call_command("evaluate_course_paths", pairs=["351-353"])
```

- [ ] **Step 3: Run** `python manage.py test learning_path.test_course_evaluation` — Expected: ImportError `course_shortlist_hits`.

- [ ] **Step 4: Implement** — append to `gold.py`:

```python
def course_shortlist_hits(data, topic_concepts, decisions):
    """Dependents with a key prerequisite, and how many were offered one (accepted or pending)."""
    key = {concept.id: concept.key for topic in topic_concepts for concept in topic}
    required = {tuple(edge) for edge in data["required"]}
    offered = {
        (key.get(row["prerequisite"].id), key.get(row["dependent"].id))
        for row in decisions if row["verdict"] in (criteria.ACCEPTED, criteria.PENDING)
    }
    dependents = {after for _, after in required}
    hit = {after for before, after in required if (before, after) in offered}
    return {"dependents": len(dependents), "hit": len(hit), "offered": len(offered)}
```

`backend/learning_path/management/commands/evaluate_course_paths.py`:

```python
"""Print the course-level gold report for frozen topic pairs (course spec 2026-10-02, section 5).

--pairs A-B ...   topic pairs; default the design pairs
--rule RULE       strict (today) or shortlist (top down); default COURSE_DEFAULT_RULE
--final-check     required to score the final pairs (scored once, after the freeze)
"""

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from learning_path.services import embeddings
from learning_path.services.calibration import load_calibration
from learning_path.services.course_criteria import COURSE_DEFAULT_RULE, COURSE_RULES, decide_course_pairs
from learning_path.services.course_shortlist import TOPIC_TITLE_CUTOFF, topic_similarities
from learning_path.services.gold import FIXTURES, course_gold_report, course_shortlist_hits, load_course_gold

DESIGN_PAIRS = ["340-341", "340-343", "340-347", "343-348", "340-357", "341-357", "343-357", "347-357", "348-357"]
FINAL_CHECK_PAIRS = {"351-353", "341-343", "341-347", "347-348", "351-365", "353-365"}


class Command(BaseCommand):
    help = "Report course-level links against the course answer keys."

    def add_arguments(self, parser):
        parser.add_argument("--pairs", nargs="*", default=DESIGN_PAIRS)
        parser.add_argument("--rule", choices=COURSE_RULES)
        parser.add_argument("--final-check", action="store_true")

    def handle(self, *args, pairs, rule, final_check, **options):
        held_back = sorted(FINAL_CHECK_PAIRS & set(pairs))
        if held_back and not final_check:
            raise CommandError(
                f"{', '.join(held_back)} belong to the final check and are scored once, after the "
                "freeze (course spec 2026-10-02 section 5). Pass --final-check to score them."
            )
        rule = rule or COURSE_DEFAULT_RULE
        calibration = load_calibration()
        titles = json.loads((FIXTURES / "course_topic_titles.json").read_text(encoding="utf-8"))["titles"]
        reports = []
        for pair in pairs:
            first, second = pair.split("-")
            data, topics = load_course_gold(first, second)
            pair_titles = [titles[first], titles[second]]
            decisions = decide_course_pairs(topics, calibration=calibration, rule=rule, topic_titles=pair_titles)
            report = course_gold_report(data, topics, decisions)
            similarity = topic_similarities(pair_titles, embeddings.embed)[(0, 1)]
            report.update(
                pair=pair, unrelated=bool(data.get("unrelated")), topic_similarity=similarity,
                compared=similarity >= TOPIC_TITLE_CUTOFF, shortlist=course_shortlist_hits(data, topics, decisions),
            )
            reports.append(report)
        self.stdout.write(json.dumps({"rule": rule, "reports": reports}, indent=2))
```

(`load_course_gold` builds the fixture path from its two arguments with an f-string, so strings work.)

- [ ] **Step 5: Run** `python manage.py test learning_path.test_course_evaluation` — Expected: OK.
- [ ] **Step 6: Commit** — message "Measure course-level shortlists against the keys and lock the final pairs".

---

### Task 5: Page model — top-to-bottom graph and learning order

**Files:**
- Modify: `web-app/src/learning-path/coursePathModel.js`
- Test: `web-app/src/learning-path/coursePathModel.test.js`

- [ ] **Step 1: Rewrite the tests** — replace the `buildCourseGraph` describe block and add a `learningOrder` block (keep the `arrowKind` block):

```js
const LAYOUT_PATH = {
  topics: [
    { id: 10, title: "Solid, Liquid and Gas", position: 0, has_content: true },
    { id: 11, title: "Mixtures", position: 1, has_content: true },
    { id: 12, title: "Weather", position: 2, has_content: true },
    { id: 13, title: "Empty topic", position: 3, has_content: false },
  ],
  arrows: [{ from_topic: 10, to_topic: 11, contradicts_outline: false, shaping: 1, pending: 0, links: [] }],
};

describe("buildCourseGraph", () => {
  it("flows top to bottom: an earlier topic sits above the topic that builds on it", () => {
    const graph = buildCourseGraph(LAYOUT_PATH);
    const at = (id) => graph.nodes.find((node) => node.id === id).position;
    expect(at("10").y).toBeLessThan(at("11").y);
  });

  it("puts topics without arrows in a strip below, under a label", () => {
    const graph = buildCourseGraph(LAYOUT_PATH);
    const at = (id) => graph.nodes.find((node) => node.id === id).position;
    expect(at("12").y).toBeGreaterThan(at("11").y);
    expect(graph.nodes.find((node) => node.id === "13").data.empty).toBe(true);
    expect(graph.nodes.some((node) => node.type === "label")).toBe(true);
  });

  it("lays out a course with no arrows at all", () => {
    const graph = buildCourseGraph({ ...LAYOUT_PATH, arrows: [] });
    expect(graph.nodes.filter((node) => node.type === "topic")).toHaveLength(4);
    expect(graph.edges).toEqual([]);
  });

  it("labels each arrow with its link count", () => {
    const graph = buildCourseGraph(PATH);
    expect(graph.edges.map((edge) => edge.label)).toEqual(["2 links", "1 suggestion"]);
    expect(graph.edges[1].className).toContain("contradicts");
  });
});

const ORDER_PATH = {
  topics: [
    { id: 11, title: "Mixtures", position: 1, has_content: true, published: false,
      steps: [{ concept_id: 5, title: "Solutions", position: 1 }, { concept_id: 6, title: "Air", position: 2 }] },
    { id: 10, title: "Solid, Liquid and Gas", position: 0, has_content: true, published: true,
      steps: [{ concept_id: 1, title: "Liquid", position: 1 }] },
    { id: 12, title: "Empty", position: 2, has_content: false, published: false, steps: [] },
  ],
  arrows: [{
    from_topic: 10, to_topic: 11, contradicts_outline: false, shaping: 1, pending: 2,
    links: [
      { id: 1, status: "approved", rank: 1, prerequisite: { concept_id: 1, topic_id: 10 }, dependent: { concept_id: 5, topic_id: 11 } },
      { id: 2, status: "pending", rank: 3, prerequisite: { concept_id: 2, topic_id: 10 }, dependent: { concept_id: 6, topic_id: 11 } },
      { id: 3, status: "pending", rank: 1, prerequisite: { concept_id: 1, topic_id: 10 }, dependent: { concept_id: 6, topic_id: 11 } },
    ],
  }],
};

describe("learningOrder", () => {
  it("lists topics with content in outline order", () => {
    expect(learningOrder(ORDER_PATH).map((entry) => entry.topic.id)).toEqual([10, 11]);
  });

  it("puts confirmed links under 'may revisit' and pending ones, by rank, under 'might build on'", () => {
    const mixtures = learningOrder(ORDER_PATH)[1];
    const [solutions, air] = mixtures.steps;
    expect(solutions.revisit.map((link) => link.id)).toEqual([1]);
    expect(air.suggestions.map((link) => link.id)).toEqual([3, 2]);
    expect(mixtures.published).toBe(false);
  });
});
```

and change the import to `import { arrowKind, buildCourseGraph, learningOrder } from "./coursePathModel";`.

- [ ] **Step 2: Run** `npx vitest run src/learning-path/coursePathModel.test.js` (from `web-app/`) — Expected: FAIL (`learningOrder` not exported; layout assertions).

- [ ] **Step 3: Implement** — replace `coursePathModel.js` with:

```js
// Pure helpers behind the Course path page: where topics sit, how each arrow
// between them is drawn, and the learning order listed under the graph.
// Nothing here renders or calls the server.
import dagre from "@dagrejs/dagre";

export const TOPIC_WIDTH = 220;
export const TOPIC_HEIGHT = 60;
const STRIP_GAP = 110;
const STRIP_COLUMNS = 4;
const COLUMN_STEP = TOPIC_WIDTH + 40;
const ROW_STEP = TOPIC_HEIGHT + 30;
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
const byPosition = (topics) => [...topics].sort((a, b) => a.position - b.position);

// Top to bottom like the topic graph: topics the arrows touch are laid out by
// dagre, the rest sit in a "Not linked yet" strip below.
export function buildCourseGraph(path, selectedArrow = null) {
  const topics = byPosition(path.topics);
  const ids = new Set(topics.map((topic) => topic.id));
  const arrows = path.arrows.filter((arrow) => ids.has(arrow.from_topic) && ids.has(arrow.to_topic));
  const touched = new Set(arrows.flatMap((arrow) => [arrow.from_topic, arrow.to_topic]));
  const linked = topics.filter((topic) => touched.has(topic.id));
  const unlinked = topics.filter((topic) => !touched.has(topic.id));

  const positions = new Map();
  let bottom = 0;
  if (linked.length) {
    const graph = new dagre.graphlib.Graph();
    graph.setGraph({ rankdir: "TB", nodesep: 40, ranksep: 70, marginx: MARGIN, marginy: MARGIN });
    graph.setDefaultEdgeLabel(() => ({}));
    for (const topic of linked) graph.setNode(String(topic.id), { width: TOPIC_WIDTH, height: TOPIC_HEIGHT });
    for (const arrow of arrows) graph.setEdge(String(arrow.from_topic), String(arrow.to_topic));
    dagre.layout(graph);
    for (const topic of linked) {
      const { x, y } = graph.node(String(topic.id));
      positions.set(topic.id, { x: x - TOPIC_WIDTH / 2, y: y - TOPIC_HEIGHT / 2 });
      bottom = Math.max(bottom, y + TOPIC_HEIGHT / 2);
    }
  }
  const stripTop = linked.length ? bottom + STRIP_GAP : MARGIN + 34;
  unlinked.forEach((topic, index) => {
    positions.set(topic.id, {
      x: MARGIN + (index % STRIP_COLUMNS) * COLUMN_STEP,
      y: stripTop + Math.floor(index / STRIP_COLUMNS) * ROW_STEP,
    });
  });

  const nodes = topics.map((topic) => ({
    id: String(topic.id),
    type: "topic",
    position: positions.get(topic.id),
    data: { topic, empty: !topic.has_content },
    draggable: false,
  }));
  if (unlinked.length) {
    nodes.push({
      id: "not-linked-label", type: "label", position: { x: MARGIN, y: stripTop - 34 },
      data: { text: "Not linked yet" }, draggable: false, selectable: false,
    });
  }
  const edges = arrows.map((arrow) => {
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

const CONFIRMED = new Set(["accepted", "approved"]);
const byRank = (a, b) => (a.rank ?? Infinity) - (b.rank ?? Infinity) || a.id - b.id;

// The course as a learner goes through it: topics with content in outline
// order, each step with the earlier-topic links into it.
export function learningOrder(path) {
  const links = path.arrows.flatMap((arrow) => arrow.links);
  return byPosition(path.topics)
    .filter((topic) => topic.has_content)
    .map((topic) => ({
      topic,
      published: Boolean(topic.published),
      steps: (topic.steps || []).map((step) => {
        const into = links.filter((link) => link.dependent.concept_id === step.concept_id);
        return {
          ...step,
          revisit: into.filter((link) => CONFIRMED.has(link.status)).sort(byRank),
          suggestions: into.filter((link) => link.status === "pending").sort(byRank),
        };
      }),
    }));
}
```

- [ ] **Step 4: Run** the vitest file — Expected: all pass.
- [ ] **Step 5: Commit** — message "Lay the course graph out top to bottom and model the learning order list".

---

### Task 6: The page

**Files:**
- Modify: `web-app/src/pages/CoursePathPage.jsx`, `web-app/src/learning-path/coursePath.css`

- [ ] **Step 1: Topic boxes flow top to bottom** — in `TopicNode`, `Position.Left` → `Position.Top` and `Position.Right` → `Position.Bottom`; add `function LabelNode({ data }) { return <div className="pg-label">{data.text}</div>; }` and `const NODE_TYPES = { topic: TopicNode, label: LabelNode };`.

- [ ] **Step 2: Learning order list** — import `learningOrder` with `buildCourseGraph`; add `const order = useMemo(() => (path ? learningOrder(path) : []), [path]);`; update the intro paragraph to "Topics flow top to bottom in your outline order. An arrow means a concept in one topic builds on a concept in another. Green follows your outline, yellow is a suggestion, red contradicts your outline. Below, the learning order shows where each step can send a learner back to an earlier topic."; and after the `cp-layout` div add:

```jsx
      <section className="card cp-order" aria-labelledby="cp-order-title">
        <h3 id="cp-order-title">Learning order</h3>
        {order.length === 0 && <p className="muted-text">No topic has lessons yet.</p>}
        <ol className="cp-order-topics">
          {order.map(({ topic, published, steps }) => (
            <li key={topic.id}>
              <h4>
                {topic.title}
                {!published && <span className="cp-unpublished">not published yet</span>}
              </h4>
              <ol className="cp-order-steps">
                {steps.map((step) => (
                  <li key={step.concept_id}>
                    <span className="cp-step-title">{step.title}</span>
                    {step.revisit.length > 0 && (
                      <div className="cp-step-links">
                        <span className="cp-step-label">May revisit:</span>
                        {step.revisit.map((link) => (
                          <span key={link.id} className={`cp-chip ${link.status}`} title={link.reason}>
                            {link.prerequisite.title} — {topicTitle(link.prerequisite.topic_id)}
                            <button type="button" className="btn btn-small btn-secondary" onClick={() => ask(link, "rejected")}>Remove</button>
                          </span>
                        ))}
                      </div>
                    )}
                    {step.suggestions.length > 0 && (
                      <div className="cp-step-links">
                        <span className="cp-step-label">Might build on:</span>
                        {step.suggestions.map((link) => (
                          <span key={link.id} className="cp-chip pending" title={link.reason}>
                            {link.prerequisite.title} — {topicTitle(link.prerequisite.topic_id)}
                            <button type="button" className="btn btn-small btn-primary" onClick={() => ask(link, "approved")}>Approve</button>
                            <button type="button" className="btn btn-small btn-secondary" onClick={() => ask(link, "rejected")}>Dismiss</button>
                          </span>
                        ))}
                      </div>
                    )}
                  </li>
                ))}
              </ol>
            </li>
          ))}
        </ol>
      </section>
```

- [ ] **Step 3: Styles** — append to `coursePath.css`:

```css
.cp-order { margin-top: 1rem; }
.cp-order-topics { padding-left: 1.25rem; }
.cp-order-topics > li { margin-bottom: 1rem; }
.cp-order-topics h4 { margin: 0.5rem 0; }
.cp-unpublished { margin-left: 0.5rem; font-size: 0.75rem; font-weight: 400; color: #5b6b7b; }
.cp-order-steps { padding-left: 1.25rem; }
.cp-order-steps > li { margin-bottom: 0.4rem; }
.cp-step-links { display: flex; flex-wrap: wrap; align-items: center; gap: 0.35rem; margin: 0.25rem 0 0 0.5rem; font-size: 0.85rem; }
.cp-step-label { color: #5b6b7b; }
.cp-chip { display: inline-flex; align-items: center; gap: 0.35rem; padding: 0.15rem 0.4rem; border-radius: 6px; border: 1px solid #c9d2db; }
.cp-chip.accepted, .cp-chip.approved { border-color: #2f6f4f; }
.cp-chip.pending { border-color: #b8860b; border-style: dashed; }
```

- [ ] **Step 4: Verify** — from `web-app/`: `npx vitest run src/learning-path` → pass; `npm run build` → succeeds with no errors.
- [ ] **Step 5: Commit** — message "Show the course graph top to bottom with the learning order and its shortlists below".

---

### Task 7: Design-pair measurement and freeze

- [ ] **Step 1:** `python manage.py test learning_path` → OK.
- [ ] **Step 2:** from `backend/`:

```bash
mkdir -p ../docs/course-path-v2-evaluation
python manage.py evaluate_course_paths --rule strict > ../docs/course-path-v2-evaluation/design-strict.json
python manage.py evaluate_course_paths --rule shortlist > ../docs/course-path-v2-evaluation/design-shortlist.json
```

Summarise per pair: `compared`, `topic_similarity`, accepted (right = in key), `accepted_precision`, `shortlist.hit/dependents`, pending count, and for unrelated controls any accepted/pending. Expected from the spike: 340-341 and the five 357 controls not compared; the three linked pairs compared; hit about 10 of 12.
- [ ] **Step 3:** Keep `TOPIC_TITLE_CUTOFF`/`SHORTLIST_SIZE` unless a design result is plainly caused by them; record the decision.
- [ ] **Step 4: Freeze** — commit `docs/course-path-v2-evaluation` (message "Measure the top-down course level on the design pairs before the final check") and note the hash; `course_shortlist.py` and `course_criteria.py` must not change before Task 8's run.

---

### Task 8: Final check (once), stop rule, write-up

Blocked until the user approves the blind keys in `docs/course-path-new-keys/` (the executor does not open them).

- [ ] **Step 1: Freeze the fixtures** (no printing of contents):

```bash
for pair in 351-353 341-343 341-347 347-348 351-365 353-365; do a=${pair%-*}; b=${pair#*-};
  python manage.py export_course_pairs $a $b --map ../docs/course-path-new-keys/course_map_${a}_${b}.json --out learning_path/fixtures/gold_course_${a}_${b}.json | tail -1; done
```

and add each map as `learning_path/fixtures/gold_course_map_<a>_<b>.json` (copy). Commit.
- [ ] **Step 2: Score once**

```bash
P="351-353 341-343 341-347 347-348 351-365 353-365"
python manage.py evaluate_course_paths --pairs $P --final-check --rule strict > ../docs/course-path-v2-evaluation/final-strict.json
python manage.py evaluate_course_paths --pairs $P --final-check --rule shortlist > ../docs/course-path-v2-evaluation/final-shortlist.json
```

- [ ] **Step 3: Stop rule** (spec section 5), summed over the final pairs: (1) unrelated pairs: shortlist rule has no accepted and no pending; (2) Σhit / Σdependents ≥ 0.6; (3) shortlist accepted wrong ≤ strict accepted wrong.
- [ ] **Step 4a (passes):** `COURSE_DEFAULT_RULE = SHORTLIST` with a dated comment; `refresh_course_links` then uses it by default. Update `test_course_criteria.py`'s `decide()` helper to pass `rule="strict"` so the old tests keep testing the old rule; update `test_course_gold_paths.py` floors if it runs the default rule. `python manage.py test learning_path` → OK.
- [ ] **Step 4b (fails):** leave the default; nothing else changes.
- [ ] **Step 5: Report** `docs/course-path-v2-evaluation-2026-10-02.md` (sets, key provenance, design and final tables for both rules, stop-rule outcome, limits) and update `CRITERIA.md`'s "Course level" section. Commit "Score the top-down course level once on new pairs and record the outcome".
