# Learning-path criteria v6 (reference + order) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the v5 topic-level verdict so the text decides whether a prerequisite link exists and the lesson's order decides its direction, accepting uncontradicted links and suggesting the rest.

**Architecture:** A pure rule (`fusion.reference_verdict`) takes the facts of one pair, read as "earlier, later" in the lesson order, and returns a verdict, a direction, where the direction came from, and the contradictions found. `criteria.decide_pairs` builds those facts from the existing clue functions (`clues.py`) plus two new helpers, and stores the evidence. Evaluation gains a "covered" number and an order-only baseline. Everything downstream (clean-up, Kahn, publishing, review screen, adaptive engine) is untouched.

**Tech Stack:** Python 3.12, Django 5 (`SimpleTestCase`), NumPy, NLTK Porter stemmer, the pinned `all-MiniLM-L6-v2` encoder (recorded numbers only).

**Spec:** `docs/superpowers/specs/2026-09-30-learning-path-v6-reference-order-design.md` (read §3 before any task).

## Global Constraints

- No generative model. Outside parts stay limited to the pinned sentence encoder and the Porter stemmer.
- Unchanged: Kahn's sort (`publishing.order_with_links`), `break_cycles`, the adaptive engine, the database schema, the review screen, teacher-decision handling.
- Course level unchanged: do not edit `services/course_criteria.py`; keep `ACCEPTED`, `PENDING`, `PARALLEL`, `CLUES`, `CONTENT_CLUES`, `STRUCTURE_CLUES`, `confidence`, `learn_weights` importable from `services/fusion.py`.
- Order never creates a link, except the suggestion when the text is silent and 2+ PDFs agree (v5 amendment 2).
- Tune only on the development set: topics **62, 79, 152, 340, 357**. The test set **341, 343, 347, 348** is scored **once**, in Task 7, after the rules are frozen. Do not run `evaluate_gold_paths` or `test_gold_paths` on test topics before Task 7.
- No keyword or label lists fitted to the lessons; descriptive names (no single letters, no `w_k`-style names).
- Do not merge or push; the user decides.
- Commits end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Run commands from `backend/`: `python manage.py test learning_path.<module>`.

## Review Focus

1. **A concept with no full sentence** (a heading fragment, a one-word figure description) — takes part in no link and does not crash. Test in Task 3 (`test_a_concept_with_no_full_sentence_takes_part_in_no_link`, both with and without the encoder).
2. **Both concepts are figures** — a suggestion in the lesson's order with the `figure` contradiction, never accepted. Test in Task 1 (`test_two_figures_are_suggested_in_order`).
3. **A grouping split: two concepts with one title** — neither names the other (no `reverse_name` from the shared title); owned terms can still link them. Test in Task 2 (`test_two_concepts_with_one_title_do_not_name_each_other`).
4. **Encoder offline** — the same verdicts as with it; `relatedness` is `None`; evidence is JSON-serialisable. Test in Task 3 (`test_without_the_encoder_the_verdicts_are_the_same`).
5. **Rows stored by v5 (`rule: "fusion"`)** — still explained on the review screen until re-derived. Test in Task 4 (existing fused-reason tests stay and must pass).

---

### Task 1: The v6 rule (`fusion.reference_verdict`)

**Files:**
- Modify: `backend/learning_path/services/fusion.py`
- Test: `backend/learning_path/test_fusion.py`
- Modify: `docs/superpowers/specs/2026-09-30-learning-path-v6-reference-order-design.md` (§4: add `name` to the `direction_from` values)

**Interfaces:**
- Produces:
  - `PairFacts` (frozen dataclass): `later_names_earlier: float`, `earlier_names_later: float`, `later_uses_earlier_terms: float`, `earlier_uses_later_terms: float`, `heading: int` (+1 later sits under a heading naming earlier, −1 the reverse), `pdf_agreement: int` (v5 `order_vote` oriented earlier-first), `parallel: bool`, `earlier_is_figure: bool`, `later_is_figure: bool`, `pdf_order: str` (`SHARED`, `NONE_SHARED` or `DISAGREE`); all default to 0 / False / `SHARED`.
  - `Decision` (frozen dataclass): `verdict: str`, `direction: int` (+1 earlier first, −1 later first, 0 none), `direction_from: str`, `contradictions: tuple`.
  - `reference_verdict(facts: PairFacts) -> Decision`.
  - Constants `SHARED = "shared"`, `NONE_SHARED = "none_shared"`, `DISAGREE = "disagree"`, `DECIDING_CLUES = ("name", "terms", "heading", "order")`.
  - `confidence(votes, direction, clues=CLUES)` — gains the `clues` parameter; default keeps v5 behaviour.
  - `verdict` and `family_direction` (v5) are removed.

- [ ] **Step 1: Replace `VerdictTests` in `test_fusion.py` with the v6 rule tests**

Change the import line to:

```python
from .services.fusion import (
    ACCEPTED, DECIDING_CLUES, DISAGREE, NONE_SHARED, PARALLEL, PENDING,
    Decision, PairFacts, confidence, learn_weights, reference_verdict,
)
```

Delete the whole `class VerdictTests` and add:

```python
class ReferenceVerdictTests(SimpleTestCase):
    """Spec section 3: the text decides whether a link exists, the order which way."""

    def test_the_later_concept_referring_to_the_earlier_is_accepted_in_order(self):
        decision = reference_verdict(PairFacts(later_uses_earlier_terms=0.5))

        self.assertEqual(decision, Decision(ACCEPTED, 1, "pdf_order", ()))

    def test_a_name_reference_alone_is_enough(self):
        self.assertEqual(reference_verdict(PairFacts(later_names_earlier=0.2)).verdict, ACCEPTED)

    def test_siblings_get_no_link_even_when_they_refer_to_each_other(self):
        facts = PairFacts(later_names_earlier=0.5, later_uses_earlier_terms=1.0, parallel=True)

        self.assertEqual(reference_verdict(facts).verdict, PARALLEL)

    def test_silent_text_makes_no_link(self):
        self.assertEqual(reference_verdict(PairFacts()).verdict, PARALLEL)

    def test_silent_text_with_files_agreeing_is_only_a_suggestion(self):
        """v5 amendment 2: a process told by the files' order, not by shared words."""
        self.assertEqual(reference_verdict(PairFacts(pdf_agreement=1)), Decision(PENDING, 1, "pdf_agreement", ()))

    def test_siblings_get_no_suggestion_from_the_files_either(self):
        self.assertEqual(reference_verdict(PairFacts(pdf_agreement=1, parallel=True)).verdict, PARALLEL)

    def test_a_heading_decides_the_direction_even_against_the_order(self):
        facts = PairFacts(earlier_names_later=0.5, heading=-1)

        self.assertEqual(reference_verdict(facts), Decision(ACCEPTED, -1, "heading", ()))

    def test_the_earlier_naming_the_later_more_is_a_suggestion_in_order(self):
        """An overview names its parts; the order was right 14 times to 4 (spec section 1)."""
        facts = PairFacts(later_uses_earlier_terms=0.5, earlier_names_later=0.4, later_names_earlier=0.1)

        self.assertEqual(reference_verdict(facts), Decision(PENDING, 1, "pdf_order", ("reverse_name",)))

    def test_only_the_earlier_referring_is_a_suggestion_in_order(self):
        facts = PairFacts(earlier_uses_later_terms=0.5)

        self.assertEqual(reference_verdict(facts), Decision(PENDING, 1, "pdf_order", ("backward_only",)))

    def test_a_figure_follows_the_text_its_description_refers_to(self):
        """Extraction puts a page's figure first, so its position means nothing."""
        facts = PairFacts(earlier_uses_later_terms=0.6, earlier_is_figure=True)

        self.assertEqual(
            reference_verdict(facts),
            Decision(PENDING, -1, "figure", ("figure", "backward_only")),
        )

    def test_a_figure_placed_later_that_refers_back_is_still_only_suggested(self):
        facts = PairFacts(later_uses_earlier_terms=0.6, later_is_figure=True)

        self.assertEqual(reference_verdict(facts), Decision(PENDING, 1, "figure", ("figure",)))

    def test_a_figure_whose_description_refers_to_nothing_follows_the_order(self):
        facts = PairFacts(later_uses_earlier_terms=0.6, earlier_is_figure=True)

        self.assertEqual(reference_verdict(facts), Decision(PENDING, 1, "pdf_order", ("figure",)))

    def test_two_figures_are_suggested_in_order(self):
        facts = PairFacts(later_uses_earlier_terms=0.6, earlier_is_figure=True, later_is_figure=True)

        self.assertEqual(reference_verdict(facts), Decision(PENDING, 1, "pdf_order", ("figure",)))

    def test_concepts_from_different_files_follow_the_name_when_it_points(self):
        facts = PairFacts(later_uses_earlier_terms=0.5, earlier_names_later=0.3, pdf_order=NONE_SHARED)

        self.assertEqual(
            reference_verdict(facts),
            Decision(PENDING, -1, "name", ("reverse_name", "no_shared_pdf")),
        )

    def test_concepts_from_different_files_otherwise_follow_the_merged_order(self):
        facts = PairFacts(later_uses_earlier_terms=0.5, pdf_order=NONE_SHARED)

        self.assertEqual(reference_verdict(facts), Decision(PENDING, 1, "merged_order", ("no_shared_pdf",)))

    def test_files_disagreeing_on_the_order_is_a_suggestion(self):
        facts = PairFacts(later_uses_earlier_terms=0.5, pdf_order=DISAGREE)

        self.assertEqual(reference_verdict(facts), Decision(PENDING, 1, "merged_order", ("pdfs_disagree",)))

    def test_confidence_can_count_only_the_deciding_clues(self):
        votes = {"name": 1, "terms": 1, "meaning": -1, "heading": 0, "order": 0}

        self.assertAlmostEqual(confidence(votes, 1), 2 / 3)
        self.assertAlmostEqual(confidence(votes, 1, DECIDING_CLUES), 1.0)
```

Keep `LearnWeightTests` and any calibration tests in the file unchanged. If another test in `test_fusion.py` calls `verdict(`, delete that test (the v5 rule is gone).

- [ ] **Step 2: Run the tests to see them fail**

Run: `python manage.py test learning_path.test_fusion`
Expected: ImportError / FAIL — `PairFacts`, `reference_verdict` do not exist.

- [ ] **Step 3: Write the rule in `fusion.py`**

Replace the module docstring and everything from `def family_direction` through the end of `def verdict` (keep `confidence`, `_log_odds`, `learn_weights` and the constants) so the top of the file reads:

```python
"""Deciding a link: the text says whether, the lesson's order says which way (v6).

Spec: docs/superpowers/specs/2026-09-30-learning-path-v6-reference-order-design.md,
section 3. Inside one topic almost every pair looks related, and PDF order agreed
with the key's direction on 145 of 156 linked pairs, so the two questions are
answered by different evidence. A link the text makes and nothing contradicts is
accepted; anything contradicted goes to the teacher.
"""

import math
from dataclasses import dataclass

CONTENT_CLUES = ("name", "terms", "meaning")
STRUCTURE_CLUES = ("heading", "order")
CLUES = CONTENT_CLUES + STRUCTURE_CLUES
# The clues v6 decides with; meaning is recorded, not counted.
DECIDING_CLUES = ("name", "terms", "heading", "order")

ACCEPTED = "accepted"
PENDING = "pending"
# No link. The name is v5's and the course level imports it.
PARALLEL = "parallel"

SHARED = "shared"
NONE_SHARED = "none_shared"
DISAGREE = "disagree"

MAX_AGREEMENT = 0.95


@dataclass(frozen=True)
class PairFacts:
    """One pair of concepts, read as ``earlier`` then ``later`` in the lesson's order."""

    later_names_earlier: float = 0.0
    earlier_names_later: float = 0.0
    later_uses_earlier_terms: float = 0.0
    earlier_uses_later_terms: float = 0.0
    heading: int = 0
    pdf_agreement: int = 0
    parallel: bool = False
    earlier_is_figure: bool = False
    later_is_figure: bool = False
    pdf_order: str = SHARED


@dataclass(frozen=True)
class Decision:
    verdict: str
    direction: int
    direction_from: str = ""
    contradictions: tuple = ()


NO_LINK = Decision(PARALLEL, 0)


def _sign(difference):
    return (difference > 0) - (difference < 0)


def _suggested_direction(facts):
    """``(direction, source)`` for a contradicted link (spec section 3)."""
    if facts.earlier_is_figure != facts.later_is_figure:
        if facts.later_is_figure:
            figure_refers = facts.later_names_earlier > 0 or facts.later_uses_earlier_terms > 0
            if figure_refers:
                return 1, "figure"
        else:
            figure_refers = facts.earlier_names_later > 0 or facts.earlier_uses_later_terms > 0
            if figure_refers:
                return -1, "figure"
    elif facts.pdf_order != SHARED:
        name_direction = _sign(facts.later_names_earlier - facts.earlier_names_later)
        if name_direction:
            return name_direction, "name"
    return 1, "pdf_order" if facts.pdf_order == SHARED else "merged_order"


def reference_verdict(facts):
    """The v6 decision for one pair; direction +1 means earlier before later."""
    if facts.parallel:
        return NO_LINK
    later_refers = facts.later_names_earlier > 0 or facts.later_uses_earlier_terms > 0
    earlier_refers = facts.earlier_names_later > 0 or facts.earlier_uses_later_terms > 0
    if not (later_refers or earlier_refers or facts.heading):
        if facts.pdf_agreement:
            return Decision(PENDING, facts.pdf_agreement, "pdf_agreement")
        return NO_LINK
    if facts.heading:
        return Decision(ACCEPTED, facts.heading, "heading")
    contradictions = tuple(name for name, present in (
        ("reverse_name", facts.earlier_names_later > facts.later_names_earlier),
        ("figure", facts.earlier_is_figure or facts.later_is_figure),
        ("no_shared_pdf", facts.pdf_order == NONE_SHARED),
        ("pdfs_disagree", facts.pdf_order == DISAGREE),
        ("backward_only", earlier_refers and not later_refers),
    ) if present)
    if not contradictions:
        return Decision(ACCEPTED, 1, "pdf_order")
    direction, source = _suggested_direction(facts)
    return Decision(PENDING, direction, source, contradictions)


def confidence(votes, direction, clues=CLUES):
    """Share of the given clues that voted and agree with ``direction``."""
    voting = [clue for clue in clues if votes.get(clue)]
    if not voting or not direction:
        return 0.0
    return sum(1 for clue in voting if votes[clue] == direction) / len(voting)
```

(`_log_odds` and `learn_weights` follow unchanged.)

- [ ] **Step 4: Amend the spec's `direction_from` list**

In the spec, §4, change `` `direction_from` (`heading`, `pdf_order`, `figure`, `merged_order`, `pdf_agreement`) `` to `` `direction_from` (`heading`, `pdf_order`, `figure`, `name`, `merged_order`, `pdf_agreement`) ``.

- [ ] **Step 5: Run the tests to see them pass**

Run: `python manage.py test learning_path.test_fusion`
Expected: OK. (`test_criteria` now fails on import of `verdict` from `criteria.py`; Task 3 fixes it.)

- [ ] **Step 6: Commit**

```bash
git add backend/learning_path/services/fusion.py backend/learning_path/test_fusion.py docs/superpowers/specs/2026-09-30-learning-path-v6-reference-order-design.md
git commit -m "Decide a learning-path link from the text and its direction from the order"
```

---

### Task 2: Pair helpers in `clues.py`

**Files:**
- Modify: `backend/learning_path/services/clues.py`
- Test: `backend/learning_path/test_clues.py`

**Interfaces:**
- Consumes: `name_use(holder, target)`, `term_use(holder, target, term_owners)` (existing).
- Produces:
  - `shared_pdf_order(first, second, positions) -> tuple[int | None, int]`: `(direction, pdfs)`; direction +1 when every PDF teaching both puts `first` earlier, −1 when every one puts `second` earlier, 0 when they disagree, `None` when no PDF teaches both; `pdfs` = how many PDFs teach both. `first`/`second` need only `.id`.
  - `reference_uses(earlier, later, term_owners) -> dict` with exactly the keys `later_names_earlier`, `earlier_names_later`, `later_uses_earlier_terms`, `earlier_uses_later_terms` (floats), ready for `PairFacts(**uses)`.

- [ ] **Step 1: Write the failing tests** — append to `test_clues.py` and add `reference_uses, shared_pdf_order` to the `from .services.clues import (...)` list:

```python
class SharedPdfOrderTests(SimpleTestCase):
    first, second = SimpleNamespace(id=1), SimpleNamespace(id=2)

    def test_one_pdf_teaching_both_gives_its_order(self):
        self.assertEqual(shared_pdf_order(self.first, self.second, {10: {1: 0, 2: 1}}), (1, 1))
        self.assertEqual(shared_pdf_order(self.second, self.first, {10: {1: 0, 2: 1}}), (-1, 1))

    def test_no_pdf_teaching_both_gives_no_order(self):
        self.assertEqual(shared_pdf_order(self.first, self.second, {10: {1: 0}, 11: {2: 0}}), (None, 0))

    def test_pdfs_that_disagree_give_zero(self):
        positions = {10: {1: 0, 2: 1}, 11: {1: 1, 2: 0}}

        self.assertEqual(shared_pdf_order(self.first, self.second, positions), (0, 2))


class ReferenceUseTests(SimpleTestCase):
    def test_uses_are_read_each_way(self):
        stamen, pollination = prepare([
            concept(1, "Stamen", "The stamen makes pollen grains."),
            concept(2, "Pollination", "Pollen leaves the stamen on the wind."),
        ])

        uses = reference_uses(stamen, pollination, {})

        self.assertEqual(uses["later_names_earlier"], 1.0)
        self.assertEqual(uses["earlier_names_later"], 0.0)
        self.assertEqual(set(uses), {
            "later_names_earlier", "earlier_names_later",
            "later_uses_earlier_terms", "earlier_uses_later_terms",
        })

    def test_two_concepts_with_one_title_do_not_name_each_other(self):
        """A grouping split: the shared title must not read as a reference either way."""
        first, second = prepare([
            concept(1, "Comparing the Three States", "Comparing the three states shows shape. Comparing the three states shows flow."),
            concept(2, "Comparing the Three States", "Comparing the three states shows volume. The table lists each property."),
        ])

        uses = reference_uses(first, second, {})

        self.assertEqual((uses["later_names_earlier"], uses["earlier_names_later"]), (0.0, 0.0))

    def test_owned_terms_count_as_a_reference(self):
        texts = prepare([
            concept(1, "Stamen", "The anther makes pollen grains. " * 8),
            concept(2, "Pollination", "Pollen travels from an anther to a stigma."),
        ])

        uses = reference_uses(texts[0], texts[1], find_term_owners(texts))

        self.assertGreater(uses["later_uses_earlier_terms"], 0)
        self.assertEqual(uses["earlier_uses_later_terms"], 0.0)
```

- [ ] **Step 2: Run them to see them fail**

Run: `python manage.py test learning_path.test_clues`
Expected: ImportError — `reference_uses`, `shared_pdf_order` not defined.

- [ ] **Step 3: Add the helpers to `clues.py`** (after `order_vote`):

```python
def shared_pdf_order(first, second, positions):
    """``(direction, pdfs)`` from every PDF teaching both concepts.

    +1 when all of them put ``first`` earlier, -1 when all put ``second``
    earlier, 0 when they disagree, ``None`` when no PDF teaches both.
    Unlike ``order_vote``, one PDF is enough: v6 takes direction from the
    lesson's own order (spec section 3).
    """
    shared = [spots for spots in positions.values() if first.id in spots and second.id in spots]
    if not shared:
        return None, 0
    first_count = sum(1 for spots in shared if spots[first.id] < spots[second.id])
    if first_count == len(shared):
        return 1, len(shared)
    if first_count == 0:
        return -1, len(shared)
    return 0, len(shared)


def reference_uses(earlier, later, term_owners):
    """How much each concept refers to the other, by name and by owned terms."""
    same_name = bool(earlier.name) and set(earlier.name) == set(later.name)
    return {
        # One title on two concepts (a split the grouping made) names neither.
        "later_names_earlier": 0.0 if same_name else name_use(later, earlier),
        "earlier_names_later": 0.0 if same_name else name_use(earlier, later),
        "later_uses_earlier_terms": term_use(later, earlier, term_owners),
        "earlier_uses_later_terms": term_use(earlier, later, term_owners),
    }
```

- [ ] **Step 4: Run the tests to see them pass**

Run: `python manage.py test learning_path.test_clues`
Expected: OK. If `test_owned_terms_count_as_a_reference` fails because no term is owned, lengthen the Stamen repetition (e.g. `* 12`); do not change `find_term_owners`.

- [ ] **Step 5: Commit**

```bash
git add backend/learning_path/services/clues.py backend/learning_path/test_clues.py
git commit -m "Read a pair's shared-PDF order and references each way"
```

---

### Task 3: `criteria.decide_pairs` on the v6 rule

**Files:**
- Modify: `backend/learning_path/services/criteria.py`
- Test: `backend/learning_path/test_criteria.py`

**Interfaces:**
- Consumes: `PairFacts`, `reference_verdict`, `SHARED`, `NONE_SHARED`, `DISAGREE`, `DECIDING_CLUES`, `confidence` (Task 1); `shared_pdf_order`, `reference_uses` (Task 2); existing `find_term_owners`, `heading_vote`, `order_vote`, `presented_in_parallel`, `name_vote`, `term_vote`, `meaning_vote`, `clue_records` (`clues.py`), `relatedness` (`relatedness.py`), `prepare`, `material_positions` (`concept_text.py`).
- Produces: `decide_pairs(concepts, runtime_instance=None, calibration=None, embed=None, without=())` with the **same signature and row shape** as v5: `{"prerequisite", "dependent", "verdict", "evidence", "cross_section"}`. Evidence keys: `rule` (`"reference-order"`), `direction_from`, `contradictions` (list), `votes` (name, terms, meaning, heading, order; +1 = supports prerequisite first), `records`, `relatedness` (float or `None`), `confidence`, `semantic`.

- [ ] **Step 1: Rewrite `DecisionTests` in `test_criteria.py`**

Keep the imports, `CALIBRATION`, `flower()`, `decide()`, `no_encoder()`, `SectionTests` and `MemberTextTests`. Replace the whole `class DecisionTests` with:

```python
class DecisionTests(SimpleTestCase):
    def test_a_later_concept_using_terms_an_earlier_one_explains_is_accepted(self):
        row = decide(flower())[(1, 2)]

        self.assertEqual(row["verdict"], ACCEPTED)
        self.assertEqual(row["evidence"]["rule"], "reference-order")
        self.assertEqual(row["evidence"]["direction_from"], "pdf_order")
        self.assertEqual(row["evidence"]["contradictions"], [])
        self.assertEqual(row["evidence"]["votes"]["terms"], 1)
        self.assertGreater(row["evidence"]["confidence"], 0)

    def test_only_the_earlier_referring_is_a_suggestion_in_order(self):
        """Pollination (earlier) uses the stigma Pistil explains; Pistil never refers back."""
        row = decide(flower())[(2, 3)]

        self.assertEqual(row["verdict"], PENDING)
        self.assertIn("backward_only", row["evidence"]["contradictions"])

    def test_unrelated_concepts_get_no_link(self):
        decided = decide([concept(1, "Stamen", "The anther makes pollen grains."),
                          concept(2, "Weather", "Clouds bring heavy rain showers.")])

        self.assertEqual(decided, {})

    def test_files_agreeing_while_the_text_is_silent_is_only_a_suggestion(self):
        first = concept(1, "Pollination", member("Pollen moves to the flower top.", material_id=10, order=0),
                        member("Pollen moves to the flower top.", material_id=11, order=0))
        second = concept(2, "Fertilization", member("Egg cells join sperm cells inside.", material_id=10, order=1),
                         member("Egg cells join sperm cells inside.", material_id=11, order=1))

        decided = decide([first, second])

        self.assertEqual({pair: row["verdict"] for pair, row in decided.items()}, {(1, 2): PENDING})
        self.assertEqual(decided[(1, 2)]["evidence"]["direction_from"], "pdf_agreement")

    def test_a_figure_is_suggested_after_the_text_its_description_refers_to(self):
        figure = concept(1, "Particles in a solid", "The picture shows solid particles packed tightly.", kind="image")
        solid = concept(2, "Solid", "A solid has particles packed tightly in rows. " * 4)

        row = decide([figure, solid])[(2, 1)]

        self.assertEqual(row["verdict"], PENDING)
        self.assertEqual(row["evidence"]["direction_from"], "figure")
        self.assertIn("figure", row["evidence"]["contradictions"])

    def test_concepts_from_different_files_are_only_suggested(self):
        stamen = concept(1, "Stamen", member("The anther makes pollen grains. " * 8, material_id=10))
        pollination = concept(2, "Pollination", member("Pollen travels from an anther to a stigma.", material_id=11))

        row = decide([stamen, pollination])[(1, 2)]

        self.assertEqual(row["verdict"], PENDING)
        self.assertEqual(row["evidence"]["contradictions"], ["no_shared_pdf"])
        self.assertEqual(row["evidence"]["direction_from"], "merged_order")

    def test_files_disagreeing_on_the_order_is_only_suggested(self):
        stamen = concept(1, "Stamen", member("The anther makes pollen grains. " * 8, material_id=10, order=0),
                         member("The anther makes pollen grains. " * 8, material_id=11, order=1))
        pollination = concept(2, "Pollination", member("Pollen travels from an anther to a stigma.", material_id=10, order=1),
                              member("Pollen travels from an anther to a stigma.", material_id=11, order=0))

        row = decide([stamen, pollination])[(1, 2)]

        self.assertEqual(row["verdict"], PENDING)
        self.assertIn("pdfs_disagree", row["evidence"]["contradictions"])

    def test_an_overview_naming_its_part_is_a_suggestion_in_order(self):
        matter = concept(1, "Matter", "Matter comes as a solid or a liquid in daily life.")
        solid = concept(2, "Solid", "A solid keeps its own shape well.")

        row = decide([matter, solid])[(1, 2)]

        self.assertEqual(row["verdict"], PENDING)
        self.assertIn("reverse_name", row["evidence"]["contradictions"])

    def test_a_heading_naming_the_other_accepts_even_against_the_order(self):
        solid = concept(1, "Solid", member("A solid keeps its own shape well.", section_title="Matter"))
        matter = concept(2, "Matter", "Matter comes as a solid or a liquid in daily life.")

        row = decide([solid, matter])[(2, 1)]

        self.assertEqual(row["verdict"], ACCEPTED)
        self.assertEqual(row["evidence"]["direction_from"], "heading")

    def test_siblings_under_one_heading_get_no_link(self):
        solid = concept(1, "Solid", member("A solid keeps its own shape well.", section_title="States"))
        gas = concept(2, "Gas", member("A gas spreads out more than a solid does.", section_title="States"))

        self.assertEqual(decide([solid, gas]), {})

    def test_without_the_encoder_the_verdicts_are_the_same(self):
        with_encoder = {pair: row["verdict"] for pair, row in decide(flower()).items()}
        offline = decide(flower(), embed=no_encoder)

        self.assertEqual({pair: row["verdict"] for pair, row in offline.items()}, with_encoder)
        self.assertFalse(offline[(1, 2)]["evidence"]["semantic"])
        self.assertIsNone(offline[(1, 2)]["evidence"]["relatedness"])
        for row in offline.values():
            json.dumps(row["evidence"])

    def test_a_concept_with_no_full_sentence_takes_part_in_no_link(self):
        concepts = flower() + [concept(4, "Figure", "Stamen")]

        self.assertFalse(any(4 in pair for pair in decide(concepts)))
        self.assertFalse(any(4 in pair for pair in decide(concepts, embed=no_encoder)))

    def test_a_clue_can_be_left_out_for_an_ablation(self):
        matter = concept(1, "Matter", "Matter is anything with mass and volume.")
        solid = concept(2, "Solid", member("A solid is matter with a fixed shape.", section_title="Matter"))

        rows = decide_pairs([matter, solid], calibration=CALIBRATION, embed=word_vectors, without=("heading",))

        self.assertEqual(rows[0]["evidence"]["votes"]["heading"], 0)
        self.assertEqual(rows[0]["evidence"]["direction_from"], "pdf_order")

    def test_evidence_is_json_serialisable(self):
        for row in decide(flower()).values():
            json.dumps(row["evidence"])

    def test_too_few_concepts_decide_nothing(self):
        self.assertEqual(decide([concept(1, "Matter", "Matter has mass and takes up space.")]), {})
```

Remove `EncoderUnavailable` from the imports only if nothing else uses it (it is used by `no_encoder`; keep it).

- [ ] **Step 2: Run them to see them fail**

Run: `python manage.py test learning_path.test_criteria`
Expected: ImportError (`verdict` / `family_direction` no longer in `fusion`) or FAILs on the new evidence keys.

- [ ] **Step 3: Rewrite `criteria.py`**

Replace the module docstring, the imports and `decide_pairs` (keep `section_headings` and `crosses_sections` exactly as they are):

```python
"""Prerequisite links for the learning path (criteria v6).

For each pair of concepts in a topic: the text decides whether a link exists (a
name, terms one concept explains, or a heading), the lesson's order decides which
way, and a link nothing contradicts is accepted. Relatedness and meaning are
recorded, not counted. Nothing here writes to the database. See
docs/superpowers/specs/2026-09-30-learning-path-v6-reference-order-design.md.
"""

from . import embeddings
from .calibration import load_calibration
from .clues import (
    clue_records, find_term_owners, heading_vote, meaning_vote, name_vote, order_vote,
    presented_in_parallel, reference_uses, shared_pdf_order, term_vote,
)
from .concept_text import material_positions, prepare
from .fusion import (
    ACCEPTED, DECIDING_CLUES, DISAGREE, NONE_SHARED, PENDING, SHARED,
    PairFacts, confidence, reference_verdict,
)
from .relatedness import relatedness

__all__ = ["ACCEPTED", "PENDING", "crosses_sections", "decide_pairs"]

_PDF_ORDER = {1: SHARED, -1: SHARED, 0: DISAGREE, None: NONE_SHARED}
_NAME_FIELDS = ("later_names_earlier", "earlier_names_later")
_TERM_FIELDS = ("later_uses_earlier_terms", "earlier_uses_later_terms")
```

then, after `crosses_sections`:

```python
def _is_figure(text):
    return getattr(text.concept, "kind", "text") == "image"


def _facts(first, second, owners, positions, without):
    """``(facts, earlier, later)``; ``first`` precedes ``second`` in the topic's merged order."""
    order, _ = shared_pdf_order(first, second, positions)
    earlier, later = (second, first) if order == -1 else (first, second)
    uses = reference_uses(earlier, later, owners)
    for clue, fields in (("name", _NAME_FIELDS), ("terms", _TERM_FIELDS)):
        if clue in without:
            uses.update({field: 0.0 for field in fields})
    facts = PairFacts(
        **uses,
        heading=0 if "heading" in without else heading_vote(earlier, later)[0],
        pdf_agreement=0 if "order" in without else order_vote(earlier, later, positions)[0],
        parallel=presented_in_parallel(first, second),
        earlier_is_figure=_is_figure(earlier),
        later_is_figure=_is_figure(later),
        pdf_order=_PDF_ORDER[order],
    )
    return facts, earlier, later


def _votes(prerequisite, dependent, owners, positions, meaning_cutoff, semantic, without):
    """Each clue's vote, +1 when it supports ``prerequisite`` first."""
    votes = {
        "name": name_vote(prerequisite, dependent)[0],
        "terms": term_vote(prerequisite, dependent, owners)[0],
        "meaning": meaning_vote(prerequisite, dependent, meaning_cutoff)[0] if semantic else 0,
        "heading": heading_vote(prerequisite, dependent)[0],
        "order": order_vote(prerequisite, dependent, positions)[0],
    }
    return {clue: 0 if clue in without else vote for clue, vote in votes.items()}


def decide_pairs(concepts, runtime_instance=None, calibration=None, embed=None, without=()):
    """Every pair the text links: accepted when nothing contradicts it, pending otherwise.

    ``concepts`` arrive in the topic's merged order (``concepts_for_topic``).
    ``runtime_instance`` is kept for callers and ignored. Without the encoder
    the verdicts are the same; only relatedness and meaning are not recorded.
    ``without`` silences clues, for the evaluation's ablations.
    """
    concepts = list(concepts)
    if len(concepts) < 2:
        return []
    calibration = calibration or load_calibration()
    semantic = True
    try:
        texts = prepare(concepts, embed=embed or embeddings.embed)
    except embeddings.EncoderUnavailable:
        texts, semantic = prepare(concepts), False
    owners = find_term_owners(texts)
    positions = material_positions(concepts)
    meaning_cutoff = calibration["meaning_cutoff"]

    decisions = []
    for index, first in enumerate(texts):
        for second in texts[index + 1:]:
            # A concept with no full sentence has nothing to compare (kept from v5).
            if not (first.sentences and second.sentences):
                continue
            facts, earlier, later = _facts(first, second, owners, positions, without)
            decision = reference_verdict(facts)
            if decision.verdict not in (ACCEPTED, PENDING):
                continue
            prerequisite, dependent = (earlier, later) if decision.direction > 0 else (later, earlier)
            votes = _votes(prerequisite, dependent, owners, positions, meaning_cutoff, semantic, without)
            decisions.append({
                "prerequisite": prerequisite.concept,
                "dependent": dependent.concept,
                "verdict": decision.verdict,
                "evidence": {
                    "rule": "reference-order",
                    "direction_from": decision.direction_from,
                    "contradictions": list(decision.contradictions),
                    "votes": votes,
                    "records": clue_records(prerequisite, dependent, owners, positions, meaning_cutoff, semantic),
                    "relatedness": round(relatedness(first, second), 3) if semantic else None,
                    "confidence": round(confidence(votes, 1, DECIDING_CLUES), 3),
                    "semantic": semantic,
                },
                "cross_section": crosses_sections(prerequisite.concept, dependent.concept),
            })
    return decisions
```

- [ ] **Step 4: Run the criteria tests**

Run: `python manage.py test learning_path.test_criteria`
Expected: OK. If a stub does not produce the clue a test names (e.g. no term is owned), change the stub text (longer repetition, clearer shared word) — never the rule. Record any such change in the commit message.

- [ ] **Step 5: Run the whole learning-path suite except the gold paths**

Run: `python manage.py test learning_path`
Expected: everything passes except possibly `learning_path.test_gold_paths` (v5 floors; Task 6 resets them). The v5 `fusion` tests in `learning_path.test_reasons` must still pass. If anything else fails, it is a caller relying on v5 evidence keys (`disagreement`, `parallel`, `rule: "fusion"`): fix that caller to read the v6 keys, and list it in the commit.

- [ ] **Step 6: Commit**

```bash
git add backend/learning_path/services/criteria.py backend/learning_path/test_criteria.py
git commit -m "Derive topic links with the v6 reference-and-order rule"
```

---

### Task 4: Reason sentences for v6 links

**Files:**
- Modify: `backend/learning_path/services/reasons.py`
- Test: `backend/learning_path/test_reasons.py`

**Interfaces:**
- Consumes: evidence produced in Task 3.
- Produces: `link_reason(evidence, prerequisite_title, dependent_title)` handles `rule == "reference-order"`; every other rule unchanged.

- [ ] **Step 1: Write the failing tests** (append to `LinkReasonTests`; keep every existing test):

```python
    def test_an_accepted_v6_link_names_its_words_and_the_order(self):
        evidence = {"rule": "reference-order", "direction_from": "pdf_order", "contradictions": [],
                    "votes": {"name": 0, "terms": 1, "meaning": 1, "heading": 0, "order": 0},
                    "records": {"terms": {"owned": ["particle", "vibrate"]}}}

        self.assertEqual(
            link_reason(evidence, "Solid", "Gas"),
            "Gas uses terms Solid explains (particle, vibrate). Solid comes first in the lesson.",
        )

    def test_a_v6_link_by_heading_and_name(self):
        evidence = {"rule": "reference-order", "direction_from": "heading", "contradictions": [],
                    "votes": {"name": 1, "terms": 0, "heading": 1}, "records": {}}

        self.assertEqual(
            link_reason(evidence, "Matter", "Solid"),
            "Solid sits under a heading naming Matter. Solid names Matter.",
        )

    def test_a_v6_suggestion_says_what_stands_against_it(self):
        evidence = {"rule": "reference-order", "direction_from": "pdf_order",
                    "contradictions": ["reverse_name", "backward_only"],
                    "votes": {"name": -1, "terms": 0, "heading": 0}, "records": {}}

        self.assertEqual(
            link_reason(evidence, "Matter", "Solid"),
            "Matter comes first in the lesson. But Matter's text names Solid more than the reverse. "
            "But only Matter's text refers to Solid.",
        )

    def test_a_v6_figure_suggestion(self):
        evidence = {"rule": "reference-order", "direction_from": "figure", "contradictions": ["figure"],
                    "votes": {"name": 0, "terms": 1, "heading": 0},
                    "records": {"terms": {"owned": ["particle"]}}}

        self.assertEqual(
            link_reason(evidence, "Solid", "Particles in a solid"),
            "Particles in a solid uses terms Solid explains (particle). "
            "The figure's description refers to Solid. "
            "One of them is a figure, so its place in the file does not give the order.",
        )

    def test_v6_suggestions_from_different_or_disagreeing_files(self):
        evidence = {"rule": "reference-order", "direction_from": "merged_order",
                    "contradictions": ["no_shared_pdf"], "votes": {"terms": 1},
                    "records": {"terms": {"owned": []}}}

        self.assertEqual(
            link_reason(evidence, "Stamen", "Pollination"),
            "Pollination uses terms Stamen explains. Stamen comes first in the topic's combined order. "
            "They come from different files, so their order is a guess.",
        )
        evidence["contradictions"] = ["pdfs_disagree"]
        self.assertTrue(link_reason(evidence, "Stamen", "Pollination").endswith("The files put them in different orders."))

    def test_a_v6_suggestion_from_the_files_alone(self):
        evidence = {"rule": "reference-order", "direction_from": "pdf_agreement", "contradictions": [],
                    "votes": {"order": 1}, "records": {"order": {"pdfs": 2, "agree": 2}}}

        self.assertEqual(
            link_reason(evidence, "Pollination", "Fertilization"),
            "2 of 2 files teach Pollination first; the text says nothing either way.",
        )
```

- [ ] **Step 2: Run them to see them fail**

Run: `python manage.py test learning_path.test_reasons`
Expected: the six new tests FAIL (they fall through to "Added by you.").

- [ ] **Step 3: Add the v6 wording to `reasons.py`** (above `link_reason`):

```python
_CONTRADICTION_SENTENCES = {
    "figure": "One of them is a figure, so its place in the file does not give the order.",
    "no_shared_pdf": "They come from different files, so their order is a guess.",
    "pdfs_disagree": "The files put them in different orders.",
}


def _reference_order_reason(evidence, a, b):
    votes = evidence.get("votes") or {}
    records = evidence.get("records") or {}
    contradictions = evidence.get("contradictions") or []
    parts = []
    if votes.get("heading") == 1:
        parts.append(f"{b} sits under a heading naming {a}.")
    if votes.get("name") == 1:
        parts.append(f"{b} names {a}.")
    if votes.get("terms") == 1:
        owned = (records.get("terms") or {}).get("owned") or []
        listed = f" ({', '.join(owned[:3])})" if owned else ""
        parts.append(f"{b} uses terms {a} explains{listed}.")
    source = evidence.get("direction_from")
    if source == "pdf_order":
        parts.append(f"{a} comes first in the lesson.")
    elif source == "merged_order":
        parts.append(f"{a} comes first in the topic's combined order.")
    elif source == "figure":
        parts.append(f"The figure's description refers to {a}.")
    elif source == "pdf_agreement":
        order = records.get("order") or {}
        parts.append(f"{order.get('agree')} of {order.get('pdfs')} files teach {a} first; the text says nothing either way.")
    if "reverse_name" in contradictions:
        parts.append(f"But {a}'s text names {b} more than the reverse.")
    if "backward_only" in contradictions:
        parts.append(f"But only {a}'s text refers to {b}.")
    parts.extend(_CONTRADICTION_SENTENCES[key] for key in _CONTRADICTION_SENTENCES if key in contradictions)
    return " ".join(parts)
```

and in `link_reason`, directly after the `rule == "course"` branch:

```python
    if rule == "reference-order":
        return _reference_order_reason(evidence, a, b)
```

Update the module docstring's second sentence to: "Built from the evidence ``criteria.decide_pairs`` stores on each derived row; rows from older versions (v4, v5) keep their wording until re-derived."

- [ ] **Step 4: Run the tests to see them pass**

Run: `python manage.py test learning_path.test_reasons`
Expected: OK, including every older (`fusion`, `course`, v4) test.

- [ ] **Step 5: Commit**

```bash
git add backend/learning_path/services/reasons.py backend/learning_path/test_reasons.py
git commit -m "Explain v6 learning-path links in one sentence"
```

---

### Task 5: "Covered" metric and the order-only baseline

**Files:**
- Modify: `backend/learning_path/services/gold.py`
- Modify: `backend/learning_path/management/commands/evaluate_gold_paths.py`
- Test: `backend/learning_path/test_gold_report.py`

**Interfaces:**
- Produces:
  - `covered_links(data, concepts, decisions) -> list[list[str]]`: required links reached by accepted links, directly or through a chain, at concept level (chains may pass through unkeyed concepts or either half of a split concept).
  - `gold_report(...)` adds `"covered"` (that list) and `"covered_count"`.
  - `order_only_decisions(concepts) -> list[dict]`: each concept accepted after the one just before it; row shape as `decide_pairs`, evidence `{"rule": "order-only", "confidence": 1.0}`.
  - `load_gold(topic_id)` accepts an int or a string (e.g. `"348alt"` for a second key).
  - `evaluate_gold_paths --baseline order` uses the baseline; `--topics` takes strings.

- [ ] **Step 1: Write the failing tests** (append to `test_gold_report.py`; add `covered_links, order_only_decisions` to the `gold` import):

```python
class CoveredTests(SimpleTestCase):
    def setUp(self):
        self.matter, self.solid, self.comparing, self.unkeyed = (
            concept(1, "matter", 0), concept(2, "solid", 1),
            concept(3, "comparing", 2), concept(4, None, 3),
        )
        self.concepts = [self.matter, self.solid, self.comparing, self.unkeyed]
        self.data = {"topic_id": 999, "required": [["matter", "solid"], ["matter", "comparing"]],
                     "parallel": [], "structural": [], "forbidden": [],
                     "expected_order": ["matter", "solid", "comparing"]}

    def test_a_chain_of_accepted_links_covers_a_required_link(self):
        decisions = [decision(self.matter, self.solid, "accepted"), decision(self.solid, self.comparing, "accepted")]

        self.assertEqual(covered_links(self.data, self.concepts, decisions), [["matter", "solid"], ["matter", "comparing"]])

    def test_a_chain_through_an_unkeyed_concept_still_covers(self):
        decisions = [decision(self.matter, self.unkeyed, "accepted"), decision(self.unkeyed, self.comparing, "accepted")]

        self.assertEqual(covered_links(self.data, self.concepts, decisions), [["matter", "comparing"]])

    def test_pending_links_cover_nothing(self):
        decisions = [decision(self.matter, self.solid, "pending")]

        self.assertEqual(covered_links(self.data, self.concepts, decisions), [])

    def test_the_report_carries_the_covered_count(self):
        report = gold_report(self.data, self.concepts, [decision(self.matter, self.solid, "accepted")])

        self.assertEqual(report["covered_count"], 1)

    def test_the_order_only_baseline_links_each_concept_to_the_one_before(self):
        rows = order_only_decisions(self.concepts)

        self.assertEqual([(row["prerequisite"].id, row["dependent"].id) for row in rows], [(1, 2), (2, 3), (3, 4)])
        self.assertEqual({row["verdict"] for row in rows}, {"accepted"})
```

- [ ] **Step 2: Run them to see them fail**

Run: `python manage.py test learning_path.test_gold_report`
Expected: ImportError — `covered_links` not defined.

- [ ] **Step 3: Implement in `gold.py`**

Add after `kendall_tau`:

```python
def covered_links(data, concepts, decisions):
    """The key's required links a learner can be sent back through.

    A required link is covered when accepted links lead from a concept carrying
    its first key to one carrying its second, directly or through a chain --
    the adaptive engine walks chains, so a direct link is not needed. Chains may
    pass through unkeyed concepts and either half of a split concept.
    """
    successors = defaultdict(set)
    for row in decisions:
        if row["verdict"] == criteria.ACCEPTED:
            successors[row["prerequisite"].id].add(row["dependent"].id)
    key = {concept.id: concept.key for concept in concepts}

    def reached_from(start):
        seen, waiting = set(), [start]
        while waiting:
            for following in successors[waiting.pop()]:
                if following not in seen:
                    seen.add(following)
                    waiting.append(following)
        return seen

    reach = {concept.id: reached_from(concept.id) for concept in concepts}
    return [
        [before, after] for before, after in data["required"]
        if any(key[reached] == after
               for concept in concepts if concept.key == before
               for reached in reach[concept.id])
    ]


def order_only_decisions(concepts):
    """Baseline: each concept after the one just before it in the topic's order; no text read."""
    return [
        {"prerequisite": before, "dependent": after, "verdict": criteria.ACCEPTED,
         "evidence": {"rule": "order-only", "confidence": 1.0}, "cross_section": False}
        for before, after in zip(concepts, concepts[1:])
    ]
```

In `gold_report`, after `accepted_set = set(accepted)`, add `covered = covered_links(data, concepts, decisions)` and add to the returned dict (after `"reachable_count"`):

```python
        "covered": covered,
        "covered_count": len(covered),
```

`load_gold` needs no code change for strings (it formats `topic_id` into the file name); update its docstring's first line to "``(map data, concepts)`` for a fixture (``gold_topic_<topic_id>.json``; ``topic_id`` may be a string such as ``"348alt"``)".

- [ ] **Step 4: Update `evaluate_gold_paths.py`**

Change the docstring's switch list to add `--baseline order  link each concept to the one before it (no text read)`, and in `add_arguments`:

```python
        parser.add_argument("--topics", nargs="*", default=["62", "79", "152"])
        parser.add_argument("--baseline", choices=["order"])
```

Change `handle`'s signature to include `baseline` and the decision line to:

```python
                if baseline == "order":
                    decisions = order_only_decisions(concepts)
                else:
                    decisions = criteria.decide_pairs(
                        concepts, calibration=calibration, without=(without,) if without else (),
                    )
```

import `order_only_decisions` from `learning_path.services.gold`, and add `"baseline": baseline,` to the printed JSON beside `"without"`.

- [ ] **Step 5: Run the tests to see them pass**

Run: `python manage.py test learning_path.test_gold_report`
Expected: OK.

- [ ] **Step 6: Smoke-run the command on one development topic**

Run: `python manage.py evaluate_gold_paths --topics 62 --baseline order`
Expected: JSON with `"baseline": "order"` and a `covered_count` for topic 62. Development topic only.

- [ ] **Step 7: Commit**

```bash
git add backend/learning_path/services/gold.py backend/learning_path/management/commands/evaluate_gold_paths.py backend/learning_path/test_gold_report.py
git commit -m "Measure covered links and an order-only baseline"
```

---

### Task 6: Measure on the development set, settle the two open choices, reset the floors

**Files:**
- Create: `docs/learning-path-v6-evaluation/eval-v6-dev.json`, `eval-order-dev.json`, `eval-v5-dev.json`, `eval-v6-dev-figure-order.json`
- Modify: `backend/learning_path/test_gold_paths.py`
- Modify (only if a choice changes): `backend/learning_path/services/fusion.py`, spec §3

**Interfaces:**
- Consumes: Tasks 1–5.
- Produces: `test_gold_paths.py` with v6 floors for 62, 79, 152, 340, 357 (`REACHABLE_FLOOR`, `COVERED_FLOOR`, `TAU_FLOOR`, `KNOWN_FORBIDDEN`).

- [ ] **Step 1: Run v6 and the baseline on the development set**

```bash
cd backend
mkdir -p ../docs/learning-path-v6-evaluation
python manage.py evaluate_gold_paths --topics 62 79 152 340 357 --by-clue > ../docs/learning-path-v6-evaluation/eval-v6-dev.json
python manage.py evaluate_gold_paths --topics 62 79 152 340 357 --baseline order > ../docs/learning-path-v6-evaluation/eval-order-dev.json
```

- [ ] **Step 2: Run v5 with the same measuring code, from a temporary worktree**

```bash
cd /c/MAVIA
git worktree add ../MAVIA-v5-eval 3ae921d
cp backend/learning_path/services/gold.py ../MAVIA-v5-eval/backend/learning_path/services/gold.py
cp backend/learning_path/management/commands/evaluate_gold_paths.py ../MAVIA-v5-eval/backend/learning_path/management/commands/evaluate_gold_paths.py
cd ../MAVIA-v5-eval/backend
python manage.py evaluate_gold_paths --topics 62 79 152 340 357 > /c/MAVIA/docs/learning-path-v6-evaluation/eval-v5-dev.json
cd /c/MAVIA
```

Keep the worktree for Task 7. (`3ae921d` is the last commit with the v5 rule; the copied files only measure.)

- [ ] **Step 3: Check the forbidden links**

Read `forbidden_accepted` for each topic in `eval-v6-dev.json`. Expected: empty everywhere except topic 340, where only links whose prerequisite key is `energy_rule` may appear (spec §3: "As a general rule → Liquid / Gas").
**Stop rule:** if any other forbidden link is accepted, stop and report it to the user with the pair and its evidence; do not change the rule to remove it.

- [ ] **Step 4: Settle the figure-suggestion direction (spec §3, last paragraph)**

Measure the alternative (figure pairs follow the order) without editing code:

```bash
cd backend
python manage.py shell -c "
from learning_path.services import fusion
original = fusion._suggested_direction
def order_only(facts):
    if facts.earlier_is_figure or facts.later_is_figure:
        return 1, 'pdf_order' if facts.pdf_order == fusion.SHARED else 'merged_order'
    return original(facts)
fusion._suggested_direction = order_only
from django.core.management import call_command
with open('../docs/learning-path-v6-evaluation/eval-v6-dev-figure-order.json', 'w', encoding='utf-8') as out:
    call_command('evaluate_gold_paths', '--topics', '62', '79', '152', '340', '357', stdout=out)
"
```

Compare total `reachable_count` (accepted + pending reach) over the five topics between `eval-v6-dev.json` and `eval-v6-dev-figure-order.json`. Keep the spec's choice unless the alternative reaches **more** required links **and** adds no forbidden link to `pending` in the wrong direction; if it wins, change `_suggested_direction` to the alternative, update the Task 1 figure tests to expect `pdf_order`, amend spec §3, and re-run Step 1. Write the two totals into the commit message either way.

- [ ] **Step 5: Reset the development floors in `test_gold_paths.py`**

Replace the two floor dictionaries and `_assert_gold` with the measured v6 values from `eval-v6-dev.json` (use the exact numbers, rounded down to two decimals for τ):

```python
# Measured v6 values from docs/learning-path-v6-evaluation/eval-v6-dev.json.
REACHABLE_FLOOR = {62: <reachable_count>, 79: <...>, 152: <...>, 340: <...>, 357: <...>}
COVERED_FLOOR = {62: <covered_count>, 79: <...>, 152: <...>, 340: <...>, 357: <...>}
TAU_FLOOR = {62: <kendall_tau>, 79: <...>, 152: <...>, 340: <...>, 357: <...>}
# Accepted against the key, explained in the v6 evaluation report: the PDF puts
# "As a general rule" before the states; only the AI-drafted key disagrees.
KNOWN_FORBIDDEN = {340: [<the exact pairs from Step 3>]}
```

```python
    def _assert_gold(self, topic_id):
        report = self._report(topic_id)
        shown = json.dumps(report, indent=2)
        self.assertEqual(
            sorted(map(tuple, report["forbidden_accepted"])),
            sorted(map(tuple, KNOWN_FORBIDDEN.get(topic_id, []))),
            shown,
        )
        self.assertGreaterEqual(report["reachable_count"], REACHABLE_FLOOR[topic_id], shown)
        self.assertGreaterEqual(report["covered_count"], COVERED_FLOOR[topic_id], shown)
        self.assertGreaterEqual(report["kendall_tau"], TAU_FLOOR[topic_id], shown)
```

(The `<...>` markers are filled with the numbers just measured in Step 1 — this step's whole purpose is copying them in; leave none unfilled.) Update the module docstring: "Acceptance: v6 on real lesson text, against the answer keys (development set only; the test set is added in Task 7 of the plan, after one run)."

- [ ] **Step 6: Run the gold tests and the whole learning-path suite**

Run: `python manage.py test learning_path`
Expected: OK (the gold tests skip only if the encoder cannot load — say so if they skip).

- [ ] **Step 7: Commit**

```bash
git add docs/learning-path-v6-evaluation backend/learning_path/test_gold_paths.py
git commit -m "Measure v6 on the development set and reset its floors"
```

---

### Task 7: Docs, freeze, and the single test-set run

**Files:**
- Modify: `backend/learning_path/CRITERIA.md`, `docs/open-issues-2026-09-30.md`, `docs/AGENT_LOG.md`
- Create: `docs/learning-path-v6-evaluation/eval-v6-test.json`, `eval-order-test.json`, `eval-v5-test.json`, `docs/learning-path-v6-evaluation-2026-09-30.md` (use the actual date of the run in the file name)
- Modify: `backend/learning_path/test_gold_paths.py` (test-set floors from the one run)

**Interfaces:**
- Consumes: everything above; the worktree `../MAVIA-v5-eval` from Task 6.

- [ ] **Step 1: Rewrite `CRITERIA.md` for v6**

Keep its structure (status, scope, steps table, clues, verdict, edge status, course level, measuring, history). Changes:
- Status: v6, spec path, evaluation path.
- Steps: 0 Prepare (unchanged); 1 "Relatedness — recorded only"; 2 Clues: name, terms, heading, PDF order (single PDF included), parallel flag, figure kind; meaning recorded only; 3 Verdict = the spec §3 table and contradictions list, copied; 4–5 unchanged.
- "Without the encoder the verdicts are the same."
- Measuring: the commands with `--baseline order`; sets: development 62, 79, 152, 340, 357; test 341, 343, 347, 348.
- History: add "v5 (two evidence families, 2026-09-30): retired because text-only links stayed pending and the meaning clue was at chance on direction."
Course-level section: unchanged.

- [ ] **Step 2: Freeze the rules**

```bash
git add backend/learning_path/CRITERIA.md
git commit -m "Document the v6 learning-path criteria"
git log -1 --format=%H
git status --short backend/learning_path/services
```

Expected: `git status` prints nothing for `services/`. Write the printed hash down: it is the frozen rule version quoted in the report. From here on, no change to `services/fusion.py`, `services/criteria.py` or `services/clues.py`.

- [ ] **Step 3: Ask the user whether the extra lesson or a second key exists**

If the user has supplied an extra topic or a second key, its fixture must already be committed (`gold_topic_<id>.json`, or `gold_topic_348alt.json` for a second key on 348), exported with `export_live_concepts` before this step. Add its id to the `--topics` lists below. If not, continue without it and say so in the report.

- [ ] **Step 4: The single test run**

```bash
cd /c/MAVIA/backend
python manage.py evaluate_gold_paths --topics 341 343 347 348 --by-clue > ../docs/learning-path-v6-evaluation/eval-v6-test.json
python manage.py evaluate_gold_paths --topics 341 343 347 348 --baseline order > ../docs/learning-path-v6-evaluation/eval-order-test.json
cd ../../MAVIA-v5-eval/backend
python manage.py evaluate_gold_paths --topics 341 343 347 348 > /c/MAVIA/docs/learning-path-v6-evaluation/eval-v5-test.json
cd /c/MAVIA
git worktree remove ../MAVIA-v5-eval --force
```

Run each command **once**. Do not re-run after reading the results.

- [ ] **Step 5: Write the evaluation report**

`docs/learning-path-v6-evaluation-<date>.md`, in the style of `docs/learning-path-v5-evaluation-2026-09-30.md`:
1. Frozen rule version (hash from Step 2); sets and key sources.
2. Development table: per topic, v5 / order-only / v6 — required, reachable, covered, τ, forbidden accepted, accepted, accepted precision, pending. From the three `*-dev.json` files.
3. Test table: the same columns from the three `*-test.json` files.
4. Reading it: does v6 clearly beat the order-only baseline on covered and forbidden? If not, say that the text rules add nothing measurable. Any forbidden link on the test set, listed with its evidence.
5. The Task 6 figure-direction decision and its two totals.
6. Stated scope (spec §5): grade-school science lessons from one course, one lesson template, AI-drafted keys; test text was read before design (spec §7); the rules found on 340 (spec §7).
7. If a second key exists: agreement between the two keys (shared required links / union) and v6's numbers against each.

- [ ] **Step 6: Add the test topics to `test_gold_paths.py`**

Add the four test topics (and any extra) to `REACHABLE_FLOOR`, `COVERED_FLOOR`, `TAU_FLOOR` with the values just measured, add their forbidden links (if any) to `KNOWN_FORBIDDEN` with a comment pointing to the report, and add one test method per topic, e.g.:

```python
    def test_topic_341_grouping_materials(self):
        self._assert_gold(341)

    def test_topic_343_mixtures(self):
        self._assert_gold(343)

    def test_topic_347_changes_in_materials(self):
        self._assert_gold(347)

    def test_topic_348_separating_mixtures(self):
        self._assert_gold(348)
```

Comment above the floors: "Test-set floors are the single frozen run's values (report section 3); they guard against regressions and were not tuned."

- [ ] **Step 7: Update the handover docs**

`docs/open-issues-2026-09-30.md`: in "Known defects", mark items 2–5 with the v6 result (one line each, numbers from the report) and add the v6 spec/report paths to "Where things stand". `docs/AGENT_LOG.md`: one dated entry (what changed, frozen hash, headline test numbers, not merged).

- [ ] **Step 8: Run everything and commit**

Run: `python manage.py test learning_path` then `python manage.py test`
Expected: OK (report the counts, and any skip).

```bash
git add docs/learning-path-v6-evaluation docs/learning-path-v6-evaluation-*.md backend/learning_path/test_gold_paths.py docs/open-issues-2026-09-30.md docs/AGENT_LOG.md
git commit -m "Score v6 once on the test topics and record the results"
```

Do not merge or push; report the results to the user.
