# Course-level path, closest match — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A third course-level rule, `"closest"`: each later concept is linked to the earlier-topic concept whose lesson text is closest — accepted on strong evidence, suggested when it stands out, nothing otherwise — scored once on six fresh pairs and made the default only if it passes.

**Architecture:** A new `services/course_closest.py` holds the per-concept search and verdict. `course_criteria.decide_course_pairs` gains `rule="closest"` beside `"strict"` (default) and `"shortlist"` (failed, off). `reasons.link_reason` explains the new rows. Storage, the page, publishing and the adaptive hand-off do not change. Tasks 5-6 are the final check, run by the controller with the user.

**Tech Stack:** Django, `SimpleTestCase`/`TestCase`, the project's MiniLM encoder (fake `word_vectors` encoder in unit tests).

**Spec:** `docs/superpowers/specs/2026-10-03-course-path-closest-match-design.md` (5f87ee0).

## Global Constraints

- `CLOSEST_MARGIN = 0.10`, `MIN_SHARED_TERMS = 2` (existing, `services/clues.py`), name in ≥ 1 sentence. Fixed by the spec; never changed after Task 4's freeze.
- `COURSE_DEFAULT_RULE` stays `STRICT` until Task 6's stop rule passes.
- Final pairs (old ids 340-348, 341-348, 343-347, 357-365, 351-357, 353-357, on the live re-upload) are **never** scored, printed or opened before Task 6; their keys are drafted by a separate agent and never read by the designer or implementers.
- No migration, no new dependency, no word lists, no LLM.
- The shortlist rule's code stays untouched.
- Names: descriptive but short, plain English, like the surrounding code.
- Commits: one plain sentence, ending with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Stage only the files the task names (the working tree holds unrelated user files).
- Backend tests run from `backend/` with `LLM_PROVIDER=ollama` (the Groq `.env` breaks unrelated tests): `LLM_PROVIDER=ollama python manage.py test learning_path.<module>`.

## Review Focus

1. An earlier concept whose title is a sentence (no name) must never be **accepted**, only suggested. (Task 1 test.)
2. An earlier or later topic whose concepts have no full sentence must give no link and no crash. (Task 2 test.)
3. Stored evidence must be JSON-serialisable (no numpy floats) or the row save fails. (Task 2 test.)
4. A teacher's rejection must survive a re-derive under `"closest"`. (Task 2 test.)
5. With the encoder unavailable, `"closest"` must fall back to the strict rule, suggestions only. (Task 2 test.)

---

### Task 1: The closest-match helpers

**Files:**
- Create: `backend/learning_path/services/course_closest.py`
- Modify: `backend/learning_path/services/clues.py:97,108,112` (rename `_owned_words` → `owned_words`)
- Test: `backend/learning_path/test_course_closest.py` (new)

**Interfaces:**
- Consumes: `relatedness(first, second)` (`services/relatedness.py`), `term_use(holder, target, owners, min_terms)`, `MIN_SHARED_TERMS`, `owned_words(holder, owner, owners)` (`services/clues.py`), `ACCEPTED`, `PENDING` (`services/fusion.py`). Inputs are `ConceptText` objects from `concept_text.prepare` (`.sentences`, `.sentence_terms`, `.name`, `.id`, `.concept`).
- Produces:
  - `CLOSEST_MARGIN = 0.10`
  - `closest_earlier(earlier: list[ConceptText], later: ConceptText) -> tuple[ConceptText | None, float]`
  - `own_topic_median(later: ConceptText, topic: list[ConceptText]) -> float | None`
  - `name_sentences(holder: ConceptText, target: ConceptText) -> int`
  - `closest_verdict(closest, later, score: float, own_median: float | None, owners: dict) -> tuple[str | None, dict]` — verdict `ACCEPTED`, `PENDING` or `None` (no link); evidence keys `rule`, `score`, `relatedness`, `own_median`, `margin`, `name_sentences`, `shared_words`, `confirmed`, `contradicts_outline`, `semantic`.

- [ ] **Step 1: Write the failing tests** — `backend/learning_path/test_course_closest.py`:

```python
"""Closest-match course level: the per-concept search and verdict (course spec 2026-10-03, section 3)."""

from django.test import SimpleTestCase

from .services.clues import find_term_owners
from .services.concept_text import prepare
from .services.course_closest import closest_earlier, closest_verdict, own_topic_median
from .services.fusion import ACCEPTED, PENDING
from .testing import concept, word_vectors

NAMED = "Pollen travels from the stamen anther to a stigma."
UNNAMED = "Pollen travels from an anther to a stigma."
ONE_WORD = "The stamen is where the pollen comes from."


def stamen(id=1, title="Stamen"):
    return concept(id, title, "The anther makes pollen grains. " * 8)


def petals():
    return concept(4, "Petals", "Petals attract bees with bright colours. " * 8)


def weather(id=5):
    return concept(id, "Weather", "Clouds bring heavy rain showers today. " * 8)


def pollination(text=NAMED):
    return concept(2, "Pollination", text)


def judge(earlier, later):
    """``{later id: (verdict, closest id, evidence)}``, the earlier and later topic judged together."""
    texts = prepare(earlier + later, embed=word_vectors)
    first, second = texts[:len(earlier)], texts[len(earlier):]
    owners = find_term_owners(texts)
    judged = {}
    for text in second:
        closest, score = closest_earlier(first, text)
        verdict, evidence = closest_verdict(closest, text, score, own_topic_median(text, second), owners)
        judged[text.id] = (verdict, closest.id, evidence)
    return judged


class ClosestEarlierTests(SimpleTestCase):
    def test_the_closest_concept_has_the_most_similar_text(self):
        self.assertEqual(judge([stamen(), petals()], [pollination()])[2][1], 1)

    def test_ties_keep_the_earlier_topics_order(self):
        self.assertEqual(judge([stamen(1, "Stamen"), stamen(8, "Anther")], [pollination()])[2][1], 1)

    def test_no_earlier_concept_with_a_sentence_means_no_closest(self):
        earlier = prepare([concept(1, "Stamen", "Anther.")], embed=word_vectors)
        [later] = prepare([pollination()], embed=word_vectors)

        self.assertEqual(closest_earlier(earlier, later), (None, 0.0))


class ClosestVerdictTests(SimpleTestCase):
    def test_named_and_two_shared_words_is_accepted(self):
        verdict, _, evidence = judge([stamen(), petals()], [pollination()])[2]

        self.assertEqual(verdict, ACCEPTED)
        self.assertEqual(evidence["rule"], "course-closest")
        self.assertEqual(evidence["name_sentences"], 1)
        self.assertEqual(evidence["shared_words"], ["anther", "pollen"])
        self.assertTrue(evidence["confirmed"])
        self.assertFalse(evidence["contradicts_outline"])

    def test_named_with_one_shared_word_is_only_a_suggestion(self):
        verdict, _, evidence = judge([stamen(), petals()], [pollination(ONE_WORD), weather()])[2]

        self.assertEqual(verdict, PENDING)
        self.assertFalse(evidence["confirmed"])
        self.assertGreaterEqual(evidence["margin"], 0.10)

    def test_two_shared_words_without_the_name_is_only_a_suggestion(self):
        verdict, _, _ = judge([stamen(), petals()], [pollination(UNNAMED), weather()])[2]

        self.assertEqual(verdict, PENDING)

    def test_an_earlier_concept_without_a_name_is_never_accepted(self):
        sentence_title = stamen(1, "The anther makes pollen grains for the flower to use later on")

        verdict, closest, evidence = judge([sentence_title, petals()], [pollination(UNNAMED), weather()])[2]

        self.assertEqual((verdict, closest), (PENDING, 1))
        self.assertEqual(evidence["name_sentences"], 0)

    def test_a_concept_no_closer_than_its_own_topic_gets_no_link(self):
        seeds = concept(7, "Seeds", "Pollen on the stigma grows into seeds after an anther drops it.")

        judged = judge([stamen(), petals()], [pollination(UNNAMED), seeds])

        self.assertEqual([judged[2][0], judged[7][0]], [None, None])
        self.assertLess(judged[2][2]["margin"], 0.10)

    def test_an_unrelated_topic_gets_no_link(self):
        wind = concept(6, "Wind", "Strong wind blows across the open fields today.")

        judged = judge([stamen(), petals()], [weather(), wind])

        self.assertEqual([judged[5][0], judged[6][0]], [None, None])

    def test_alone_in_its_topic_only_acceptance_can_link(self):
        verdict, _, evidence = judge([stamen(), petals()], [pollination(UNNAMED)])[2]

        self.assertIsNone(verdict)
        self.assertEqual((evidence["own_median"], evidence["margin"]), (None, None))
```

- [ ] **Step 2: Run them to see them fail**

Run (from `backend/`): `LLM_PROVIDER=ollama python manage.py test learning_path.test_course_closest`
Expected: ERROR, `ModuleNotFoundError: No module named 'learning_path.services.course_closest'`.

- [ ] **Step 3: Make `owned_words` public** — in `backend/learning_path/services/clues.py` rename the function at line 97 and its two callers (lines 108 and 112):

```python
def owned_words(holder, owner, term_owners):
```

```python
    record = {"owned": owned_words(dependent, prerequisite, term_owners),
```

```python
            owned_back=owned_words(prerequisite, dependent, term_owners),
```

Then `grep -rn "_owned_words" backend/learning_path` must print nothing.

- [ ] **Step 4: Write the module** — `backend/learning_path/services/course_closest.py`:

```python
"""The closest-match course level (course spec 2026-10-03, section 3).

For a concept of a later topic, the concept of an earlier topic whose lesson
text is closest. It is accepted when the later concept also names it and
shares two of its distinctive words; it is suggested when it stands out from
the later concept's own topic; otherwise there is no link. Titles never rank.
"""

import statistics

from .clues import MIN_SHARED_TERMS, owned_words, term_use
from .fusion import ACCEPTED, PENDING
from .relatedness import relatedness

# Design pairs, 2026-10-03: a closest match this much closer than the later
# concept's own topic-mates was right 11 times in 17, and never linked two
# unrelated topics (spec section 2).
CLOSEST_MARGIN = 0.10


def closest_earlier(earlier, later):
    """``(text, score)``: the concept of ``earlier`` whose lesson text is closest to ``later``.

    ``(None, 0.0)`` when no earlier concept has a sentence; ties keep the earlier topic's order.
    """
    best, best_score = None, 0.0
    for text in earlier:
        if not text.sentences:
            continue
        score = relatedness(text, later)
        if best is None or score > best_score:
            best, best_score = text, score
    return best, best_score


def own_topic_median(later, topic):
    """How close ``later`` is to the other concepts of its own topic (median), or ``None`` with none."""
    scores = [relatedness(other, later) for other in topic if other is not later and other.sentences]
    return float(statistics.median(scores)) if scores else None


def name_sentences(holder, target):
    """How many of the holder's sentences contain every stem of the target's name."""
    if not target.name:
        return 0
    needed = set(target.name)
    return sum(1 for stems in holder.sentence_terms if needed <= set(stems))


def closest_verdict(closest, later, score, own_median, owners):
    """``(verdict, evidence)`` for ``later`` and its closest earlier concept; ``None`` means no link."""
    named = name_sentences(later, closest)
    shares_words = term_use(later, closest, owners, MIN_SHARED_TERMS) > 0
    margin = None if own_median is None else score - own_median
    if named and shares_words:
        verdict = ACCEPTED
    elif margin is not None and margin >= CLOSEST_MARGIN:
        verdict = PENDING
    else:
        verdict = None
    evidence = {
        "rule": "course-closest",
        "score": round(float(score), 3),
        "relatedness": round(float(score), 3),
        "own_median": None if own_median is None else round(own_median, 3),
        "margin": None if margin is None else round(float(margin), 3),
        "name_sentences": named,
        "shared_words": owned_words(later, closest, owners),
        "confirmed": verdict == ACCEPTED,
        "contradicts_outline": False,
        "semantic": True,
    }
    return verdict, evidence
```

(`confirmed` is not in the spec's evidence list; it lets the reason text tell an accepted link from a suggestion without re-deriving, as the shortlist rule's evidence already does.)

- [ ] **Step 5: Run the tests**

Run: `LLM_PROVIDER=ollama python manage.py test learning_path.test_course_closest learning_path.test_reasons learning_path.test_course_criteria`
Expected: OK (the renamed helper breaks nothing).

- [ ] **Step 6: Commit**

```bash
git add backend/learning_path/services/course_closest.py backend/learning_path/services/clues.py backend/learning_path/test_course_closest.py
git commit -m "Find each later concept's closest earlier concept and judge it by name, shared words and margin

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: `decide_course_pairs(rule="closest")`

**Files:**
- Modify: `backend/learning_path/services/course_criteria.py` (imports, rule constants at lines 24-29, new `_closest`, `decide_course_pairs` at lines 137-186)
- Test: `backend/learning_path/test_course_criteria.py` (append), `backend/learning_path/test_course_links.py` (append)

**Interfaces:**
- Consumes: Task 1's `closest_earlier`, `own_topic_median`, `closest_verdict`.
- Produces: `CLOSEST = "closest"`; `COURSE_RULES = (STRICT, SHORTLIST, CLOSEST)`; `decide_course_pairs(..., rule=CLOSEST)` returns rows `{"prerequisite", "dependent", "verdict", "evidence"}` with `evidence["rule"] == "course-closest"`. `refresh_course_links(course, rule="closest")` and `evaluate_course_paths --rule closest` work through `COURSE_RULES` with no change.

- [ ] **Step 1: Write the failing tests** — append to `backend/learning_path/test_course_criteria.py`, and add `CLOSEST` to its import line (`from .services.course_criteria import CLOSEST, SHORTLIST, course_topics, course_verdict, decide_course_pairs`):

```python
def decide_by_closest(topic_concepts, embed=word_vectors):
    return {
        (row["prerequisite"].id, row["dependent"].id): row
        for row in decide_course_pairs(topic_concepts, calibration=CALIBRATION, embed=embed, rule=CLOSEST)
    }


class ClosestRuleTests(SimpleTestCase):
    def test_a_named_closest_concept_sharing_two_words_is_accepted(self):
        decided = decide_by_closest([[stamen(), petals()], [pollination()]])

        self.assertEqual(set(decided), {(1, 2)})
        self.assertEqual(decided[(1, 2)]["verdict"], ACCEPTED)
        self.assertEqual(decided[(1, 2)]["evidence"]["rule"], "course-closest")

    def test_an_unrelated_later_topic_gets_no_link(self):
        self.assertEqual(decide_by_closest([[stamen(), petals()], [weather()]]), {})

    def test_at_most_one_link_per_later_concept_for_each_earlier_topic(self):
        decided = decide_by_closest([[stamen(), petals()], [weather()], [pollination()]])

        self.assertEqual(set(decided), {(1, 2)})

    def test_concepts_without_a_full_sentence_give_no_link(self):
        no_sentences = [concept(1, "Stamen", "Anther."), concept(4, "Petals", "Bright.")]

        self.assertEqual(decide_by_closest([no_sentences, [pollination()]]), {})
        self.assertEqual(decide_by_closest([[stamen(), petals()], [concept(2, "Pollination", "Pollen.")]]), {})

    def test_without_the_encoder_the_strict_rule_runs(self):
        decided = decide_by_closest([[stamen(), petals()], [pollination()]], embed=no_encoder)

        self.assertTrue(decided)
        self.assertEqual({row["verdict"] for row in decided.values()}, {PENDING})
        self.assertEqual({row["evidence"]["rule"] for row in decided.values()}, {"course"})

    def test_evidence_is_json_serialisable(self):
        import json

        decided = decide_by_closest([[stamen(), petals()], [pollination(names_stamen=False), weather()]])

        self.assertEqual({row["verdict"] for row in decided.values()}, {PENDING})
        json.dumps([row["evidence"] for row in decided.values()])
```

Append to `backend/learning_path/test_course_links.py`:

```python
class ClosestRuleLinksTests(CourseFixture):
    def _refresh_closest(self):
        with patch("learning_path.services.embeddings.embed", word_vectors):
            return refresh_course_links(self.course, rule="closest")

    def test_the_closest_rule_stores_its_link(self):
        self._refresh_closest()

        link = CourseConceptLink.objects.get()
        self.assertEqual((link.prerequisite, link.dependent), (self.groups["Stamen"], self.groups["Pollination"]))
        self.assertEqual((link.status, link.evidence["rule"]), ("accepted", "course-closest"))

    def test_a_teacher_rejection_survives_the_closest_rule(self):
        self._refresh_closest()
        CourseConceptLink.objects.update(status="rejected", source="teacher")

        self._refresh_closest()

        self.assertEqual(CourseConceptLink.objects.get().status, "rejected")
```

- [ ] **Step 2: Run them to see them fail**

Run: `LLM_PROVIDER=ollama python manage.py test learning_path.test_course_criteria learning_path.test_course_links`
Expected: ERROR, `ImportError: cannot import name 'CLOSEST'`.

- [ ] **Step 3: Implement** — in `backend/learning_path/services/course_criteria.py`:

Add the import beside the shortlist import:

```python
from .course_closest import closest_earlier, closest_verdict, own_topic_median
```

Replace the rule constants:

```python
STRICT = "strict"
SHORTLIST = "shortlist"
CLOSEST = "closest"
COURSE_RULES = (STRICT, SHORTLIST, CLOSEST)
# The strict rule until the closest rule passes its final check (course spec 2026-10-03, section 5).
COURSE_DEFAULT_RULE = STRICT
```

Add after `_shortlisted`:

```python
def _closest(earlier, later, owners):
    """Course spec 2026-10-03 section 3: each later concept against its closest earlier concept."""
    rows = []
    for second in later:
        if not second.sentences:
            continue
        first, score = closest_earlier(earlier, second)
        if first is None:
            continue
        verdict, evidence = closest_verdict(first, second, score, own_topic_median(second, later), owners)
        if verdict is not None:
            rows.append({"prerequisite": first.concept, "dependent": second.concept,
                         "verdict": verdict, "evidence": evidence})
    return rows
```

In `decide_course_pairs`, extend the docstring's rule sentence to: ``rule`` is ``STRICT`` (name and terms must agree), ``SHORTLIST`` (outline gate, concept shortlist, strict confirmation) or ``CLOSEST`` (each later concept's closest earlier concept, course spec 2026-10-03); default ``COURSE_DEFAULT_RULE``. Without the encoder both newer rules run the strict rule. Then, after the `use_shortlist` block, add:

```python
    use_closest = rule == CLOSEST and semantic
```

and inside the pair loop, right after `owners = find_term_owners(earlier + later)`:

```python
            if use_closest:
                decisions.extend(_closest(earlier, later, owners))
                continue
```

- [ ] **Step 4: Run the tests**

Run: `LLM_PROVIDER=ollama python manage.py test learning_path`
Expected: OK, every existing test unmodified.

- [ ] **Step 5: Commit**

```bash
git add backend/learning_path/services/course_criteria.py backend/learning_path/test_course_criteria.py backend/learning_path/test_course_links.py
git commit -m "Add the closest-match rule to the course level beside the strict and shortlist rules

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: The teacher's reason for a closest-match link

**Files:**
- Modify: `backend/learning_path/services/reasons.py` (new `_closest_reason`, one branch in `link_reason`)
- Test: `backend/learning_path/test_reasons.py` (append)

**Interfaces:**
- Consumes: evidence from Task 1 (`rule`, `confirmed`, `shared_words`).
- Produces: `link_reason(evidence, prerequisite_title, dependent_title)` for `rule == "course-closest"`.

- [ ] **Step 1: Write the failing tests** — append to `backend/learning_path/test_reasons.py`:

```python
class ClosestReasonTests(SimpleTestCase):
    def test_an_accepted_closest_match_names_its_evidence(self):
        evidence = {"rule": "course-closest", "confirmed": True, "shared_words": ["anther", "pollen"]}

        self.assertEqual(
            link_reason(evidence, "Stamen", "Pollination"),
            "Pollination is closest in meaning to Stamen, names it, and shares anther, pollen.",
        )

    def test_a_suggested_closest_match_asks_the_teacher(self):
        evidence = {"rule": "course-closest", "confirmed": False, "shared_words": ["pollen"]}

        self.assertEqual(
            link_reason(evidence, "Stamen", "Pollination"),
            "Pollination is closest in meaning to Stamen, clearly closer than the concepts of its own "
            "topic. Please confirm or dismiss.",
        )
```

- [ ] **Step 2: Run them to see them fail**

Run: `LLM_PROVIDER=ollama python manage.py test learning_path.test_reasons`
Expected: FAIL (the reason falls through to another branch's text).

- [ ] **Step 3: Implement** — in `backend/learning_path/services/reasons.py`, after `_shortlist_reason`:

```python
def _closest_reason(evidence, a, b):
    if evidence.get("confirmed"):
        return f"{b} is closest in meaning to {a}, names it, and shares {', '.join(evidence.get('shared_words') or [])}."
    return (f"{b} is closest in meaning to {a}, clearly closer than the concepts of its own topic. "
            "Please confirm or dismiss.")
```

and in `link_reason`, after the `course-shortlist` branch:

```python
    if rule == "course-closest":
        return _closest_reason(evidence, a, b)
```

- [ ] **Step 4: Run the tests**

Run: `LLM_PROVIDER=ollama python manage.py test learning_path.test_reasons`
Expected: OK.

- [ ] **Step 5: Commit**

```bash
git add backend/learning_path/services/reasons.py backend/learning_path/test_reasons.py
git commit -m "Explain a closest-match course link in one sentence for the teacher

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Design-pair measurement, real-text guard, freeze

**Files:**
- Create: `docs/course-path-closest-evaluation/design-closest.json`, `docs/course-path-closest-evaluation/spent-closest.json`
- Modify: `backend/learning_path/test_course_gold_paths.py` (one test)

**Interfaces:**
- Consumes: `evaluate_course_paths --rule closest` (Task 2), the frozen fixtures `gold_course_*` already in the repo.
- Produces: the freeze commit hash, recorded in the ledger; nothing in `course_closest.py` or the `CLOSEST` parts of `course_criteria.py` changes after it until Task 6.

- [ ] **Step 1: Real-text guard** — append to `CourseGoldPathTests` in `backend/learning_path/test_course_gold_paths.py`, and add `CLOSEST` to its import (`from .services.course_criteria import CLOSEST, decide_course_pairs`):

```python
    def test_the_closest_rule_accepts_nothing_between_different_subjects(self):
        for first, second in UNRELATED:
            with self.subTest(pair=(first, second)):
                if not (FIXTURES / f"gold_course_{first}_{second}.json").exists():
                    self.skipTest(f"fixture gold_course_{first}_{second}.json missing")
                data, topics = load_course_gold(first, second)
                report = course_gold_report(data, topics, decide_course_pairs(topics, rule=CLOSEST))
                self.assertEqual(report["unrelated_accepted"], 0, json.dumps(report, indent=2))
```

Run: `LLM_PROVIDER=ollama python manage.py test learning_path.test_course_gold_paths` → OK (or skipped without the encoder).

- [ ] **Step 2: Measure** — from `backend/`:

```bash
mkdir -p ../docs/course-path-closest-evaluation
LLM_PROVIDER=ollama python manage.py evaluate_course_paths --rule closest > ../docs/course-path-closest-evaluation/design-closest.json
LLM_PROVIDER=ollama python manage.py evaluate_course_paths --pairs 351-353 341-343 341-347 347-348 351-365 353-365 --final-check --rule closest > ../docs/course-path-closest-evaluation/spent-closest.json
```

(The second set was spent on 2026-10-03; `--final-check` only lifts its old lock.) Summarise over both files:

```bash
python - <<'EOF'
import json
reports = [r for f in ("design", "spent") for r in json.load(open(f"../docs/course-path-closest-evaluation/{f}-closest.json"))["reports"]]
accepted = sum(len(r["accepted"]) for r in reports)
right = sum(round((r["accepted_precision"] or 0) * len(r["accepted"])) for r in reports)
print("accepted", accepted, "right", right, "wrong", accepted - right,
      "unrelated accepted", sum(r["unrelated_accepted"] for r in reports),
      "pending", sum(len(r["pending"]) for r in reports),
      "hit", sum(r["shortlist"]["hit"] for r in reports), "/", sum(r["shortlist"]["dependents"] for r in reports))
EOF
```

Expected, from spec section 2: accepted 3, wrong 0, unrelated accepted 0, hit about 11-12 of 30. **If wrong > 0 or unrelated accepted > 0, stop and report to the user — do not change the rule or its settings.**

- [ ] **Step 3: Full suite** — `LLM_PROVIDER=ollama python manage.py test learning_path` → OK.

- [ ] **Step 4: Freeze** — commit and note the hash:

```bash
git add docs/course-path-closest-evaluation backend/learning_path/test_course_gold_paths.py
git commit -m "Measure the closest-match course level on the design pairs before the final check

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Final pairs — lock, blind keys, user approval, fixtures (controller, with the user)

Not for an implementer subagent. Blocked until the user says the four biology lessons (Human Major Body Organs, The Human Organ System at Work, Reproduction Among Flowering Plants, Living Things Depend on Their Environment) are uploaded and set up.

**Files:**
- Modify: `backend/learning_path/management/commands/evaluate_course_paths.py` (`FINAL_CHECK_PAIRS`), `backend/learning_path/fixtures/course_topic_titles.json`
- Create: `docs/course-path-closest-keys/snapshot_<a>_<b>.md`, `course_map_<a>_<b>.json`, `course_map_<a>_<b>_review.md` (by the key agent), `backend/learning_path/fixtures/gold_course_<a>_<b>.json`, `gold_course_map_<a>_<b>.json`

- [ ] **Step 1: Live ids and outline order** — from `backend/`:

```bash
LLM_PROVIDER=ollama python manage.py shell -c "
from lessons.models import CourseGroup
from learning_path.services.course_criteria import course_topics
for course in CourseGroup.objects.all():
    print(course.id, course.title, [(t.id, t.title) for t in course_topics(course)])
"
```

Map each final pair to live ids by title, `<a>` = the earlier topic in that order. Record the six `<a>-<b>` in the ledger.

- [ ] **Step 2: Lock** — add the six `"<a>-<b>"` strings to `FINAL_CHECK_PAIRS` in `evaluate_course_paths.py`, and the live ids' outline titles to `course_topic_titles.json` (`"titles": {"<id>": "<title>"}`; live ids do not collide with the old 340-365). `LLM_PROVIDER=ollama python manage.py test learning_path.test_course_evaluation` → OK. Commit ("Lock the six closest-match final pairs before their keys are drafted").

- [ ] **Step 3: Snapshots** — for each pair: `LLM_PROVIDER=ollama python manage.py export_course_pairs <a> <b> --snapshot ../docs/course-path-closest-keys/snapshot_<a>_<b>.md`. Print only the "Wrote" line.

- [ ] **Step 4: Blind keys** — dispatch one fresh general-purpose agent with this prompt (fill in the six pairs):

> You are drafting answer keys for a thesis evaluation. For each topic pair below, read `docs/course-path-closest-keys/snapshot_<a>_<b>.md` (both topics' concepts with full lesson text; `<a>` is taught first). Decide, by meaning, which concepts of the later topic a learner could not understand without a concept of the earlier topic. Same subject or shared words are not enough. A pair may have no links at all; then mark it unrelated. Write `docs/course-path-closest-keys/course_map_<a>_<b>.json` in exactly this shape: `{"topics": [<a>, <b>], "_note": "Drafted <date> by a fresh AI agent from the lesson text, deciding by meaning; to be reviewed by the user.", "concept_keys": {"<concept id>": "c<concept id>", ...}, "required": [["c<earlier id>", "c<later id>"], ...], "reasons": {"c<earlier> -> c<later>": "<one sentence>"}, "unrelated": <true|false>, "notes": ["<links you considered and rejected, and why>"]}`. Every concept id of both topics goes in `concept_keys`, except front matter with no lesson content ("What I Need to Know", bare numbers), which you leave out and list in `notes`. Also write `course_map_<a>_<b>_review.md`: the two topics, then each link as "**<earlier title>** (topic <a>, c<id>) -> **<later title>** (topic <b>, c<id>): <reason>", then concepts left out, then notes. Do not run any code in `backend/learning_path`, do not open `docs/course-path-*evaluation*`, any `gold_course_*` fixture, or any other key folder. Reply only "done" and the list of files written — no counts, no relatedness, no links.

Pairs: <the six `<a>-<b>` with their titles>.

The controller does not open the maps or review sheets.

- [ ] **Step 5: User approval (gate)** — ask the user to review the six `_review.md` sheets (how-to: same as "How to approve the keys" in `docs/course-path-open-issues-2026-10-02.md`) and to say "closest keys approved". Corrections go through the user or a separate agent, never the controller.

- [ ] **Step 6: Freeze the fixtures** — for each pair:

```bash
LLM_PROVIDER=ollama python manage.py export_course_pairs <a> <b> --map ../docs/course-path-closest-keys/course_map_<a>_<b>.json --out learning_path/fixtures/gold_course_<a>_<b>.json | tail -1
cp ../docs/course-path-closest-keys/course_map_<a>_<b>.json learning_path/fixtures/gold_course_map_<a>_<b>.json
```

Check without printing contents that every derived concept id is in its map or deliberately left out (compare id sets only). Commit ("Freeze the six user-approved closest-match keys as fixtures before the final check").

---

### Task 6: Score once, stop rule, outcome (controller)

**Files:**
- Create: `docs/course-path-closest-evaluation/final-strict.json`, `final-closest.json`, `docs/course-path-closest-evaluation-<scoring date>.md`
- Modify (only if the stop rule passes): `backend/learning_path/services/course_criteria.py` (`COURSE_DEFAULT_RULE`), `backend/learning_path/test_course_criteria.py`, `backend/learning_path/test_course_links.py`, `backend/learning_path/test_course_gold_paths.py`; always `backend/learning_path/CRITERIA.md`

- [ ] **Step 1: Score once** — from `backend/`, with `P` = the six `<a>-<b>`:

```bash
LLM_PROVIDER=ollama python manage.py evaluate_course_paths --pairs $P --final-check --rule strict > ../docs/course-path-closest-evaluation/final-strict.json
LLM_PROVIDER=ollama python manage.py evaluate_course_paths --pairs $P --final-check --rule closest > ../docs/course-path-closest-evaluation/final-closest.json
```

- [ ] **Step 2: Stop rule** (spec section 5), summed over the six pairs, with the Task 4 summary snippet pointed at the two final files:
  1. `"closest"`: unrelated accepted = 0;
  2. `"closest"` accepted wrong ≤ strict accepted wrong, and ≤ 1;
  3. `"closest"` hit / dependents ≥ 0.30, and `"closest"` hit > strict hit.

- [ ] **Step 3a (passes):** `COURSE_DEFAULT_RULE = CLOSEST` with the comment `# 2026-MM-DD: the closest rule passed its final check (course spec 2026-10-03, section 5).` Keep the old tests on the old rule: `test_course_criteria.decide()` passes `rule=STRICT` (import `STRICT`); `CourseFixture._refresh` in `test_course_links.py` passes `rule="strict"`; `CourseGoldPathTests._report` passes `rule="strict"`. Replace `test_the_strict_rule_is_still_the_default` with:

```python
    def test_the_closest_rule_is_the_default(self):
        decided = decide_course_pairs([[stamen(), petals()], [pollination()]], calibration=CALIBRATION, embed=word_vectors)

        self.assertEqual({row["evidence"]["rule"] for row in decided}, {"course-closest"})
```

`LLM_PROVIDER=ollama python manage.py test learning_path` → OK.

- [ ] **Step 3b (fails):** leave the default and the tests; nothing else changes.

- [ ] **Step 4: Report** — `docs/course-path-closest-evaluation-<scoring date>.md`: what was tested, sets and key provenance (AI-drafted, user-approved, designer saw the materials lessons at topic level), design and final tables for both rules, stop-rule outcome, why, limits. Update the "Course level" section of `backend/learning_path/CRITERIA.md` with the outcome and the report path; the six pairs are now spent. Commit ("Score the closest-match course level once on new pairs and record the outcome").
