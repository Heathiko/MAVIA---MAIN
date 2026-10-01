# Learning-path v7: direction by three votes — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Decide which way each learning-path link points by three equal votes (hierarchy, lesson order, references) instead of by the lesson order alone, and test it on lessons with a deliberately misplaced concept.

**Architecture:** A new module `services/direction_votes.py` builds a block × concept 0/1 matrix and casts the three votes. `criteria.decide_pairs` keeps v6's rule for *whether* a link exists and, with `rule="three-votes"`, hands direction to the votes. v6 stays selectable (`rule="reference-order"`) so both are measured with the same code; the default switches only if the final check passes the stop rule. Evaluation adds "moved" copies of gold topics and a spreadsheet export.

**Tech Stack:** Django 4 management commands, `SimpleTestCase`, Python stdlib (`csv`, `statistics`, `dataclasses`). No new dependency.

**Spec:** `docs/superpowers/specs/2026-10-01-learning-path-v7-direction-votes-design.md` (commit 25a1c4d). Read it first.

## Global Constraints

- No LLM, no black box; every vote and verdict is recomputable in a spreadsheet with `SUM`, `SUMPRODUCT`, `COUNTIF`, `IF`, `AVERAGE`.
- No template / regex phrase hunting. Presence = the concept's own block, its own name's stems, or ≥ `MIN_OWNED_TERMS` of its G²-owned terms.
- Starting values: `MIN_OWNED_TERMS = 2`, `MIN_BLOCKS = 3`, `SUBSUME_HIGH = 0.8`, `SUBSUME_LOW = 0.5`, `REFERENCE_GAP = 0.25`. They may change **only** from design-set (340, 357) results, in Task 8.
- Design set: 340, 357. Final check: 341, 343, 347, 348 — **never** scored before Task 9. Do not run `manage.py test learning_path` without `--exclude-tag final_check` until Task 9. 62/79/152 are not used.
- v6's existence rule, teacher statuses, loop breaking, redundancy and Kahn ordering are unchanged.
- Names: descriptive but short, plain English, like the surrounding code (`hierarchy_vote`, `count_votes`, `blocks_a`); no single letters except loop indexes and `a`/`b` for the pair, no `w_k`-style names.
- Commit messages: one plain sentence in the repo's style, ending with the line `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Run tests from `backend/`: `python manage.py test learning_path.<module>`.

## Review Focus

1. A concept whose title is a sentence (no name) and that owns no terms is present only in its own blocks; every vote must abstain cleanly, never divide by zero. (Task 1 and Task 2 tests.)
2. Concepts taught in different PDFs, or PDFs ordering them differently: the order vote abstains instead of guessing. (Task 2 test.)
3. Running the evaluation on a final-check topic by accident must fail loudly unless `--final-check` is given. (Task 6 test.)
4. A move naming a concept or target that is not in the topic must raise, not silently score an unmoved lesson; a PDF without the target leaves the concept in place. (Task 5 tests.)
5. Stored evidence must be JSON-serialisable (PDF ids as string keys, `None` for unset shares), since it is saved on `ConceptPrerequisite.evidence`. (Task 3 test.)

---

### Task 1: The block × concept matrix

**Files:**
- Create: `backend/learning_path/services/direction_votes.py`
- Test: `backend/learning_path/test_direction_votes.py`

**Interfaces:**
- Consumes: `concept_text.prepare(concepts)` → list of `ConceptText` (`.id`, `.name` tuple of stems, `.passages` list of stem lists, one per member, `.concept`); a `term_owners` dict `{stem: concept id}` (from `clues.find_term_owners`).
- Produces: `Block(owner, material_id, order, stems)`, `BlockMatrix(blocks, present)` with `.count(concept_id) -> int`, `.together(first_id, second_id) -> int`, `.own_blocks(concept_id) -> list[int]`; `build_block_matrix(texts, term_owners) -> BlockMatrix`; constants `MIN_OWNED_TERMS`, `MIN_BLOCKS`, `SUBSUME_HIGH`, `SUBSUME_LOW`, `REFERENCE_GAP`.

- [ ] **Step 1: Write the failing tests**

`backend/learning_path/test_direction_votes.py`:

```python
"""v7: the block x concept matrix and the three direction votes (v7 spec sections 4-6)."""

from django.test import SimpleTestCase

from .services.concept_text import prepare
from .services.direction_votes import build_block_matrix
from .testing import concept, member


def three_states():
    """Solid is taught before Matter (the wrong way round); Liquid comes last."""
    return [
        concept(1, "Solid",
                member("A solid is matter with a fixed shape.", order=0),
                member("Solid matter keeps its own volume.", order=1),
                member("Ice is solid matter when it is frozen.", order=2)),
        concept(2, "Matter", member("Matter is everything that takes up space.", order=3)),
        concept(3, "Liquid",
                member("A liquid is matter that flows freely.", order=4),
                member("Liquid matter fills the bottom of a cup.", order=5)),
    ]


class BlockMatrixTests(SimpleTestCase):
    def test_a_concept_is_present_in_its_own_blocks_and_where_its_name_appears(self):
        matrix = build_block_matrix(prepare(three_states()), {})

        self.assertEqual(len(matrix.blocks), 6)
        self.assertEqual(matrix.present[1], (True, True, True, False, False, False))
        self.assertEqual(matrix.present[2], (True,) * 6)
        self.assertEqual(matrix.present[3], (False, False, False, False, True, True))

    def test_two_owned_terms_make_a_concept_present_without_its_name(self):
        lesson = [concept(1, "Stamen", member("The anther makes pollen.", order=0)),
                  concept(2, "Pollination", member("Pollen moves from the anther to the stigma.", order=1))]

        matrix = build_block_matrix(prepare(lesson), {"anther": 1, "pollen": 1})

        self.assertEqual(matrix.present[1], (True, True))

    def test_one_owned_term_is_not_enough(self):
        lesson = [concept(1, "Stamen", member("The anther makes pollen.", order=0)),
                  concept(2, "Pollination", member("Pollen moves from the anther to the stigma.", order=1))]

        matrix = build_block_matrix(prepare(lesson), {"anther": 1})

        self.assertEqual(matrix.present[1], (True, False))

    def test_a_title_that_is_a_sentence_names_nothing(self):
        lesson = [concept(1, "Picking is the simplest method of all the ways to separate things by hand",
                          member("Picking removes big pieces by hand.", order=0)),
                  concept(2, "Sieving", member("Sieving keeps big pieces and picking is slower.", order=1))]

        matrix = build_block_matrix(prepare(lesson), {})

        self.assertEqual(matrix.present[1], (True, False))

    def test_counts_shared_blocks_and_own_blocks(self):
        matrix = build_block_matrix(prepare(three_states()), {})

        self.assertEqual(matrix.count(2), 6)
        self.assertEqual(matrix.together(1, 2), 3)
        self.assertEqual(matrix.own_blocks(3), [4, 5])
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `python manage.py test learning_path.test_direction_votes`
Expected: ERROR, `ModuleNotFoundError: No module named 'learning_path.services.direction_votes'`.

- [ ] **Step 3: Write the matrix**

`backend/learning_path/services/direction_votes.py`:

```python
"""Which way a prerequisite link points: three votes (criteria v7).

Spec: docs/superpowers/specs/2026-10-01-learning-path-v7-direction-votes-design.md,
sections 4-6. The lesson's order is one vote; the hierarchy and the references
are the other two. Every number here can be recomputed in a spreadsheet from the
block x concept matrix (``export_direction_sheet``).
"""

from dataclasses import dataclass

MIN_OWNED_TERMS = 2
MIN_BLOCKS = 3
SUBSUME_HIGH = 0.8
SUBSUME_LOW = 0.5
REFERENCE_GAP = 0.25


@dataclass(frozen=True)
class Block:
    """One extracted chunk: the concept it belongs to, its PDF, its place there, its stems."""

    owner: int
    material_id: object
    order: float
    stems: frozenset


@dataclass(frozen=True)
class BlockMatrix:
    """Which concepts appear in which blocks; ``present[concept id][i]`` is block i."""

    blocks: tuple
    present: dict

    def count(self, concept_id):
        return sum(self.present[concept_id])

    def together(self, first_id, second_id):
        return sum(1 for a, b in zip(self.present[first_id], self.present[second_id]) if a and b)

    def own_blocks(self, concept_id):
        return [index for index, block in enumerate(self.blocks) if block.owner == concept_id]


def _chunks(concept):
    # Same fallback as concept_text.prepare, so chunks line up with ``passages``.
    return getattr(concept, "members", None) or (concept,)


def build_block_matrix(texts, term_owners):
    """The 0/1 matrix of spec section 4, from ``prepare``'s texts and ``find_term_owners``."""
    blocks = tuple(
        Block(text.id, getattr(chunk, "material_id", None), getattr(chunk, "order", 0), frozenset(stems))
        for text in texts
        for chunk, stems in zip(_chunks(text.concept), text.passages)
    )
    owned = {text.id: set() for text in texts}
    for stem, owner in term_owners.items():
        if owner in owned:
            owned[owner].add(stem)
    present = {}
    for text in texts:
        name = set(text.name)
        present[text.id] = tuple(
            block.owner == text.id
            or (bool(name) and name <= block.stems)
            or len(owned[text.id] & block.stems) >= MIN_OWNED_TERMS
            for block in blocks
        )
    return BlockMatrix(blocks, present)
```

- [ ] **Step 4: Run the tests to see them pass**

Run: `python manage.py test learning_path.test_direction_votes`
Expected: `Ran 5 tests ... OK`.

- [ ] **Step 5: Commit**

```bash
git add backend/learning_path/services/direction_votes.py backend/learning_path/test_direction_votes.py
git commit -m "Build the block-by-concept matrix the v7 direction votes read

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: The three votes and the verdict

**Files:**
- Modify: `backend/learning_path/services/direction_votes.py` (append)
- Test: `backend/learning_path/test_direction_votes.py` (append)

**Interfaces:**
- Consumes: Task 1's `BlockMatrix`; `clues.heading_vote(prerequisite, dependent) -> (vote, record)`; `fusion.Decision(verdict, direction, direction_from, contradictions=())`, `fusion.ACCEPTED`, `fusion.PENDING`.
- Produces (all with `a`, `b` = `ConceptText`, vote +1 meaning "`a` before `b`"):
  - `VOTES = ("hierarchy", "order", "reference")`
  - `hierarchy_vote(a, b, matrix) -> (int, dict)` record keys `from`, `blocks_a`, `blocks_b`, `both`, `p_a_given_b`, `p_b_given_a`
  - `teaching_centres(concept_id, matrix) -> {material_id: float}`
  - `centre_order_vote(a, b, matrix) -> (int, dict)` record key `centres` `{str(material): [centre_a, centre_b]}`
  - `reference_vote(a, b, matrix) -> (int, dict)` record keys `a_refers_b`, `b_refers_a`
  - `cast_votes(a, b, matrix) -> (votes, records)`, both dicts keyed by `VOTES`
  - `count_votes(votes) -> Decision`; `direction_from` ∈ `votes_agree`, `outvoted_order`, `majority`, `order_only`, `hierarchy`, `reference`, `contested`, `merged_order`

- [ ] **Step 1: Write the failing tests** (append to `test_direction_votes.py`)

Extend the imports at the top of the file to:

```python
from .services.concept_text import prepare
from .services.direction_votes import (
    build_block_matrix, cast_votes, centre_order_vote, count_votes, hierarchy_vote, reference_vote,
)
from .services.fusion import ACCEPTED, PENDING
from .testing import concept, member
```

and append:

```python
def matrix_and_texts(lesson, owners=None):
    texts = prepare(lesson)
    return build_block_matrix(texts, owners or {}), texts


class VoteTests(SimpleTestCase):
    def test_the_broader_concept_wins_the_hierarchy_vote(self):
        matrix, (solid, matter, _) = matrix_and_texts(three_states())

        vote, record = hierarchy_vote(matter, solid, matrix)

        self.assertEqual(vote, 1)
        self.assertEqual(record["from"], "subsumption")
        self.assertEqual((record["p_a_given_b"], record["p_b_given_a"]), (1.0, 0.5))

    def test_the_hierarchy_vote_abstains_below_three_blocks(self):
        matrix, (_, matter, liquid) = matrix_and_texts(three_states())

        vote, record = hierarchy_vote(matter, liquid, matrix)

        self.assertEqual(vote, 0)
        self.assertIsNone(record["p_a_given_b"])

    def test_a_heading_naming_the_other_decides_the_hierarchy_vote(self):
        lesson = [concept(1, "Seeds", member("Seeds grow into plants.", order=0)),
                  concept(2, "Germination", member("A seed sprouts when it is wet.", order=1, section_title="Seeds"))]
        matrix, (seeds, germination) = matrix_and_texts(lesson)

        vote, record = hierarchy_vote(seeds, germination, matrix)

        self.assertEqual((vote, record["from"]), (1, "heading"))

    def test_the_order_vote_reads_each_concepts_teaching_centre(self):
        matrix, (solid, matter, _) = matrix_and_texts(three_states())

        vote, record = centre_order_vote(solid, matter, matrix)

        self.assertEqual(vote, 1)
        self.assertEqual(record["centres"], {"1": [1, 3]})

    def test_the_order_vote_abstains_when_the_pdfs_disagree(self):
        lesson = [concept(1, "Solid", member("A solid keeps its shape.", material_id=1, order=0),
                          member("A solid keeps its shape.", material_id=2, order=5)),
                  concept(2, "Liquid", member("A liquid flows.", material_id=1, order=1),
                          member("A liquid flows.", material_id=2, order=2))]
        matrix, (solid, liquid) = matrix_and_texts(lesson)

        self.assertEqual(centre_order_vote(solid, liquid, matrix)[0], 0)

    def test_the_order_vote_abstains_without_a_shared_pdf(self):
        lesson = [concept(1, "Solid", member("A solid keeps its shape.", material_id=1, order=0)),
                  concept(2, "Liquid", member("A liquid flows.", material_id=2, order=0))]
        matrix, (solid, liquid) = matrix_and_texts(lesson)

        self.assertEqual(centre_order_vote(solid, liquid, matrix), (0, {"centres": {}}))

    def test_the_concept_the_other_refers_to_wins_the_reference_vote(self):
        matrix, (solid, matter, _) = matrix_and_texts(three_states())

        vote, record = reference_vote(matter, solid, matrix)

        self.assertEqual(vote, 1)
        self.assertEqual(record, {"a_refers_b": 0.0, "b_refers_a": 1.0})

    def test_a_concept_mentioning_nothing_makes_every_vote_abstain(self):
        lesson = [concept(1, "Picking is the simplest method of all the ways to separate things by hand",
                          member("Picking removes big pieces by hand.", order=0)),
                  concept(2, "Evaporation leaves the dissolved salt behind when the water dries up",
                          member("Heat the salty water until it is gone.", order=0, material_id=2))]
        matrix, (picking, evaporation) = matrix_and_texts(lesson)

        votes, _ = cast_votes(picking, evaporation, matrix)

        self.assertEqual(votes, {"hierarchy": 0, "order": 0, "reference": 0})


class CountVotesTests(SimpleTestCase):
    """The verdict table, spec section 6."""

    def test_votes_that_agree_are_accepted(self):
        decision = count_votes({"hierarchy": 0, "order": 1, "reference": 1})

        self.assertEqual((decision.verdict, decision.direction, decision.direction_from), (ACCEPTED, 1, "votes_agree"))

    def test_two_votes_outvote_the_order(self):
        decision = count_votes({"hierarchy": -1, "order": 1, "reference": -1})

        self.assertEqual((decision.verdict, decision.direction, decision.direction_from), (ACCEPTED, -1, "outvoted_order"))

    def test_the_order_and_one_vote_outvote_the_third(self):
        decision = count_votes({"hierarchy": 1, "order": 1, "reference": -1})

        self.assertEqual((decision.verdict, decision.direction_from), (ACCEPTED, "majority"))

    def test_the_order_alone_accepts_when_nothing_disagrees(self):
        decision = count_votes({"hierarchy": 0, "order": -1, "reference": 0})

        self.assertEqual((decision.verdict, decision.direction, decision.direction_from), (ACCEPTED, -1, "order_only"))

    def test_another_vote_alone_is_only_a_suggestion(self):
        decision = count_votes({"hierarchy": 0, "order": 0, "reference": -1})

        self.assertEqual((decision.verdict, decision.direction, decision.direction_from), (PENDING, -1, "reference"))

    def test_two_votes_that_disagree_go_to_the_teacher_in_the_lessons_order(self):
        decision = count_votes({"hierarchy": 1, "order": -1, "reference": 0})

        self.assertEqual((decision.verdict, decision.direction, decision.direction_from), (PENDING, -1, "contested"))

    def test_no_votes_go_to_the_teacher_in_the_topics_order(self):
        decision = count_votes({"hierarchy": 0, "order": 0, "reference": 0})

        self.assertEqual((decision.verdict, decision.direction, decision.direction_from), (PENDING, 1, "merged_order"))
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `python manage.py test learning_path.test_direction_votes`
Expected: ERROR, `ImportError: cannot import name 'cast_votes'`.

- [ ] **Step 3: Write the votes and the verdict**

Change the top of `direction_votes.py` to:

```python
from dataclasses import dataclass
from statistics import mean

from .clues import heading_vote
from .fusion import ACCEPTED, PENDING, Decision

MIN_OWNED_TERMS = 2
MIN_BLOCKS = 3
SUBSUME_HIGH = 0.8
SUBSUME_LOW = 0.5
REFERENCE_GAP = 0.25

VOTES = ("hierarchy", "order", "reference")
```

and append:

```python
def hierarchy_vote(a, b, matrix):
    """+1 when ``a`` is the broader idea: a heading naming it, else coverage subsumption
    (Sanderson & Croft 1999)."""
    blocks_a, blocks_b = matrix.count(a.id), matrix.count(b.id)
    both = matrix.together(a.id, b.id)
    record = {"from": "", "blocks_a": blocks_a, "blocks_b": blocks_b, "both": both,
              "p_a_given_b": None, "p_b_given_a": None}
    heading, _ = heading_vote(a, b)
    if heading:
        record["from"] = "heading"
        return heading, record
    if blocks_a < MIN_BLOCKS or blocks_b < MIN_BLOCKS:
        return 0, record
    a_given_b, b_given_a = both / blocks_b, both / blocks_a
    record.update(p_a_given_b=round(a_given_b, 3), p_b_given_a=round(b_given_a, 3))
    vote = 0
    if a_given_b >= SUBSUME_HIGH and b_given_a <= SUBSUME_LOW:
        vote = 1
    elif b_given_a >= SUBSUME_HIGH and a_given_b <= SUBSUME_LOW:
        vote = -1
    if vote:
        record["from"] = "subsumption"
    return vote, record


def teaching_centres(concept_id, matrix):
    """``{pdf: average position of the concept's own blocks there}``."""
    positions = {}
    for index in matrix.own_blocks(concept_id):
        block = matrix.blocks[index]
        positions.setdefault(block.material_id, []).append(block.order)
    return {material: mean(orders) for material, orders in positions.items()}


def centre_order_vote(a, b, matrix):
    """+1 when every PDF teaching both puts ``a``'s centre earlier; 0 when they disagree or none does."""
    centres_a, centres_b = teaching_centres(a.id, matrix), teaching_centres(b.id, matrix)
    shared = [material for material in centres_a if material in centres_b]
    record = {"centres": {str(material): [centres_a[material], centres_b[material]] for material in shared}}
    directions = {(centres_a[m] < centres_b[m]) - (centres_a[m] > centres_b[m]) for m in shared}
    if len(directions) == 1:
        return directions.pop(), record
    return 0, record


def _share_mentioning(holder_id, mentioned_id, matrix):
    own = matrix.own_blocks(holder_id)
    if not own:
        return 0.0
    return sum(1 for index in own if matrix.present[mentioned_id][index]) / len(own)


def reference_vote(a, b, matrix):
    """+1 when ``b``'s own blocks mention ``a`` clearly more than the reverse (RefD, Liang et al. 2015)."""
    b_refers_a = _share_mentioning(b.id, a.id, matrix)
    a_refers_b = _share_mentioning(a.id, b.id, matrix)
    record = {"a_refers_b": round(a_refers_b, 3), "b_refers_a": round(b_refers_a, 3)}
    gap = b_refers_a - a_refers_b
    if gap >= REFERENCE_GAP:
        return 1, record
    if gap <= -REFERENCE_GAP:
        return -1, record
    return 0, record


def cast_votes(a, b, matrix):
    """``(votes, records)`` for "``a`` before ``b``", each vote +1, -1 or 0."""
    hierarchy, hierarchy_record = hierarchy_vote(a, b, matrix)
    order, order_record = centre_order_vote(a, b, matrix)
    reference, reference_record = reference_vote(a, b, matrix)
    votes = {"hierarchy": hierarchy, "order": order, "reference": reference}
    records = {"hierarchy": hierarchy_record, "order": order_record, "reference": reference_record}
    return votes, records


def count_votes(votes):
    """The verdict table of spec section 6; ``direction`` +1 means ``a`` first.

    Silence is not disagreement: the order alone may accept (user decision A,
    2026-10-01), any other vote alone only suggests.
    """
    cast = {name: vote for name, vote in votes.items() if vote}
    if not cast:
        return Decision(PENDING, 1, "merged_order")
    if len(cast) == 1:
        (name, vote), = cast.items()
        if name == "order":
            return Decision(ACCEPTED, vote, "order_only")
        return Decision(PENDING, vote, name)
    total = sum(cast.values())
    if total == 0:
        return Decision(PENDING, votes["order"] or 1, "contested")
    direction = 1 if total > 0 else -1
    if all(vote == direction for vote in cast.values()):
        return Decision(ACCEPTED, direction, "votes_agree")
    if votes["order"] == -direction:
        return Decision(ACCEPTED, direction, "outvoted_order")
    return Decision(ACCEPTED, direction, "majority")
```

- [ ] **Step 4: Run the tests to see them pass**

Run: `python manage.py test learning_path.test_direction_votes`
Expected: `Ran 20 tests ... OK`.

- [ ] **Step 5: Commit**

```bash
git add backend/learning_path/services/direction_votes.py backend/learning_path/test_direction_votes.py
git commit -m "Cast the hierarchy, order and reference votes and count them into a verdict

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: `decide_pairs` with the three-vote rule

**Files:**
- Modify: `backend/learning_path/services/criteria.py` (imports, constants, `decide_pairs`, new `_three_vote_row`)
- Test: `backend/learning_path/test_criteria.py` (append a class)

**Interfaces:**
- Consumes: Task 2's `build_block_matrix`, `cast_votes`, `count_votes`; existing `reference_verdict`, `term_vote`, `relatedness`.
- Produces: `criteria.THREE_VOTES = "three-votes"`, `criteria.REFERENCE_ORDER = "reference-order"`, `criteria.RULES`, `criteria.DEFAULT_RULE` (= `REFERENCE_ORDER` until Task 9); `decide_pairs(concepts, runtime_instance=None, calibration=None, embed=None, without=(), rule=None)`. A three-vote row's `evidence` has keys `rule`, `direction_from`, `votes` (`hierarchy`/`order`/`reference`, oriented prerequisite-first), `records` (the three vote records plus `terms` from `term_vote`), `relatedness`, `confidence`, `semantic`.

- [ ] **Step 1: Write the failing tests** (append to `test_criteria.py`)

Add to the imports:

```python
from .services.criteria import THREE_VOTES
from .test_direction_votes import three_states
```

and append:

```python
def decide_by_votes(concepts):
    return {
        (row["prerequisite"].id, row["dependent"].id): row
        for row in decide_pairs(concepts, calibration=CALIBRATION, embed=word_vectors, rule=THREE_VOTES)
    }


class ThreeVoteTests(SimpleTestCase):
    """v7 spec section 6: the order is one vote of three."""

    def test_the_hierarchy_and_the_references_outvote_a_misplaced_concept(self):
        """Solid is taught before Matter; Matter is broader and Solid refers to it."""
        row = decide_by_votes(three_states())[(2, 1)]

        self.assertEqual(row["verdict"], ACCEPTED)
        self.assertEqual(row["evidence"]["rule"], "three-votes")
        self.assertEqual(row["evidence"]["direction_from"], "outvoted_order")
        self.assertEqual(row["evidence"]["votes"], {"hierarchy": 1, "order": -1, "reference": 1})
        self.assertAlmostEqual(row["evidence"]["confidence"], 2 / 3, places=3)

    def test_votes_and_records_read_prerequisite_first(self):
        row = decide_by_votes(three_states())[(2, 1)]

        hierarchy = row["evidence"]["records"]["hierarchy"]
        self.assertEqual((hierarchy["blocks_a"], hierarchy["blocks_b"]), (6, 3))
        self.assertEqual(row["evidence"]["records"]["reference"], {"a_refers_b": 0.0, "b_refers_a": 1.0})

    def test_the_existence_rule_is_v6s(self):
        """Siblings under one heading naming neither still get no link."""
        lesson = [concept(1, "Solid", member("A solid keeps its shape.", section_title="States", order=0)),
                  concept(2, "Liquid", member("A liquid is not a solid.", section_title="States", order=1))]

        self.assertEqual(decide_by_votes(lesson), {})

    def test_files_agreeing_while_the_text_is_silent_stays_a_v6_suggestion(self):
        lesson = [
            concept(1, "Stamen", member("The anther makes pollen grains.", material_id=1, order=0),
                    member("The anther makes pollen grains.", material_id=2, order=0)),
            concept(2, "Fruit", member("A ripe fruit protects the seeds.", material_id=1, order=1),
                    member("A ripe fruit protects the seeds.", material_id=2, order=1)),
        ]

        row = decide_by_votes(lesson)[(1, 2)]

        self.assertEqual(row["verdict"], PENDING)
        self.assertEqual(row["evidence"]["rule"], "reference-order")

    def test_three_vote_evidence_is_json_serialisable(self):
        rows = decide_pairs(three_states(), calibration=CALIBRATION, embed=word_vectors, rule=THREE_VOTES)

        self.assertTrue(rows)
        json.dumps([row["evidence"] for row in rows])

    def test_the_default_rule_is_still_v6_until_the_final_check(self):
        rows = decide_pairs(three_states(), calibration=CALIBRATION, embed=word_vectors)

        self.assertTrue(all(row["evidence"]["rule"] == "reference-order" for row in rows))
```

`member` is not yet imported in `test_criteria.py`; change its import line to `from .testing import concept, member, word_vectors`.

- [ ] **Step 2: Run the tests to see them fail**

Run: `python manage.py test learning_path.test_criteria`
Expected: ERROR, `ImportError: cannot import name 'THREE_VOTES'`.

- [ ] **Step 3: Implement the rule switch**

In `criteria.py`, replace the module docstring's first paragraph with:

```python
"""Prerequisite links for the learning path (criteria v6 and v7).

For each pair of concepts in a topic the text decides whether a link exists (a
name, terms one concept explains, or a heading); v6 (``reference-order``) lets
the lesson's order decide which way, v7 (``three-votes``) lets three votes
decide: hierarchy, order and references. Relatedness and meaning are recorded,
not counted. Nothing here writes to the database. See
docs/superpowers/specs/2026-09-30-learning-path-v6-reference-order-design.md and
docs/superpowers/specs/2026-10-01-learning-path-v7-direction-votes-design.md.
"""
```

Add to the imports:

```python
from .direction_votes import build_block_matrix, cast_votes, count_votes
```

After `__all__`, add (and extend `__all__` with `"RULES", "THREE_VOTES", "REFERENCE_ORDER", "DEFAULT_RULE"`):

```python
THREE_VOTES = "three-votes"
REFERENCE_ORDER = "reference-order"
RULES = (THREE_VOTES, REFERENCE_ORDER)
# v6 until v7 passes the final check (v7 spec section 8, stop rule).
DEFAULT_RULE = REFERENCE_ORDER
```

Add above `decide_pairs`:

```python
def _three_vote_row(first, second, matrix, owners, semantic):
    """One v7 row; ``first`` precedes ``second`` in the topic's merged order."""
    votes, _ = cast_votes(first, second, matrix)
    decision = count_votes(votes)
    prerequisite, dependent = (first, second) if decision.direction > 0 else (second, first)
    votes, records = cast_votes(prerequisite, dependent, matrix)
    records["terms"] = term_vote(prerequisite, dependent, owners)[1]
    voting = [vote for vote in votes.values() if vote]
    return {
        "prerequisite": prerequisite.concept,
        "dependent": dependent.concept,
        "verdict": decision.verdict,
        "evidence": {
            "rule": THREE_VOTES,
            "direction_from": decision.direction_from,
            "votes": votes,
            "records": records,
            "relatedness": round(relatedness(first, second), 3) if semantic else None,
            "confidence": round(sum(1 for vote in voting if vote == 1) / len(voting), 3) if voting else 0.0,
            "semantic": semantic,
        },
        "cross_section": crosses_sections(prerequisite.concept, dependent.concept),
    }
```

In `decide_pairs`: add the parameter `rule=None` after `without=()`; extend the docstring with
"``rule`` is ``THREE_VOTES`` or ``REFERENCE_ORDER`` (default ``DEFAULT_RULE``); either way v6 decides whether a link exists."; after `meaning_cutoff = ...` add

```python
    rule = rule or DEFAULT_RULE
    matrix = build_block_matrix(texts, owners) if rule == THREE_VOTES else None
```

and right after the `if decision.verdict not in (ACCEPTED, PENDING): continue` lines add

```python
            # v6's text-silent suggestion stays as it is: no text, nothing for the votes to read.
            if rule == THREE_VOTES and decision.direction_from != "pdf_agreement":
                decisions.append(_three_vote_row(first, second, matrix, owners, semantic))
                continue
```

- [ ] **Step 4: Run the tests to see them pass**

Run: `python manage.py test learning_path.test_criteria learning_path.test_direction_votes learning_path.test_fusion`
Expected: all OK (the existing v6 tests are unchanged because the default is still v6).

- [ ] **Step 5: Commit**

```bash
git add backend/learning_path/services/criteria.py backend/learning_path/test_criteria.py
git commit -m "Let decide_pairs take its link direction from the three votes when asked

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: The review-screen sentence

**Files:**
- Modify: `backend/learning_path/services/reasons.py`
- Test: `backend/learning_path/test_reasons.py` (append a class)

**Interfaces:**
- Consumes: Task 3's evidence shape.
- Produces: `link_reason(evidence, prerequisite_title, dependent_title)` handles `rule == "three-votes"`.

- [ ] **Step 1: Write the failing tests** (append to `test_reasons.py`; `link_reason` is already imported there)

```python
def three_vote_evidence(direction_from, hierarchy=0, order=0, reference=0, hierarchy_from=""):
    return {"rule": "three-votes", "direction_from": direction_from,
            "votes": {"hierarchy": hierarchy, "order": order, "reference": reference},
            "records": {"hierarchy": {"from": hierarchy_from}, "order": {"centres": {}}, "reference": {}}}


class ThreeVoteReasonTests(SimpleTestCase):
    def test_an_outvoted_order_is_said_plainly(self):
        evidence = three_vote_evidence("outvoted_order", hierarchy=1, order=-1, reference=1, hierarchy_from="subsumption")

        self.assertEqual(
            link_reason(evidence, "Matter", "Solid"),
            "Matter is the broader idea: almost everywhere Solid appears, Matter does too. "
            "Solid refers to Matter more than the reverse. "
            "This outvoted the lesson order, which teaches Solid first.",
        )

    def test_votes_that_agree(self):
        evidence = three_vote_evidence("votes_agree", hierarchy=1, order=1, hierarchy_from="heading")

        self.assertEqual(
            link_reason(evidence, "Seeds", "Germination"),
            "Germination sits under a heading naming Seeds. The lesson teaches Seeds first.",
        )

    def test_order_only_says_how_weak_it_is(self):
        self.assertEqual(
            link_reason(three_vote_evidence("order_only", order=1), "Pollination", "Fertilization"),
            "The lesson teaches Pollination first. "
            "Direction from the lesson order only; the text gives nothing else to go on.",
        )

    def test_a_contested_suggestion_names_what_stands_against_it(self):
        evidence = three_vote_evidence("contested", hierarchy=-1, order=1)

        self.assertEqual(
            link_reason(evidence, "Stamen", "Pollination"),
            "The lesson teaches Stamen first. Against it: the hierarchy. "
            "The evidence disagrees; choose the direction.",
        )
```

Check that `SimpleTestCase` is imported in `test_reasons.py`; if it imports `TestCase` only, add `from django.test import SimpleTestCase`.

- [ ] **Step 2: Run the tests to see them fail**

Run: `python manage.py test learning_path.test_reasons`
Expected: FAIL, the reason is `"Added by you."`.

- [ ] **Step 3: Write the sentence builder** (in `reasons.py`, above `link_reason`)

```python
_VOTE_NAMES = {"hierarchy": "the hierarchy", "order": "the lesson order", "reference": "the references"}

_SOURCE_SENTENCES = {
    "outvoted_order": "This outvoted the lesson order, which teaches {b} first.",
    "order_only": "Direction from the lesson order only; the text gives nothing else to go on.",
    "contested": "The evidence disagrees; choose the direction.",
    "merged_order": "Nothing settles the direction; it follows the topic's combined order.",
    "hierarchy": "Only the hierarchy points this way; please confirm.",
    "reference": "Only the references point this way; please confirm.",
}


def _three_vote_reason(evidence, a, b):
    """v7: one sentence per vote for the link, what stands against it, how it was settled."""
    votes = evidence.get("votes") or {}
    records = evidence.get("records") or {}
    parts = []
    if votes.get("hierarchy") == 1:
        if (records.get("hierarchy") or {}).get("from") == "heading":
            parts.append(f"{b} sits under a heading naming {a}.")
        else:
            parts.append(f"{a} is the broader idea: almost everywhere {b} appears, {a} does too.")
    if votes.get("reference") == 1:
        parts.append(f"{b} refers to {a} more than the reverse.")
    if votes.get("order") == 1:
        parts.append(f"The lesson teaches {a} first.")
    source = evidence.get("direction_from")
    against = [_VOTE_NAMES[vote] for vote in _VOTE_NAMES if votes.get(vote) == -1]
    if against and source != "outvoted_order":
        parts.append(f"Against it: {', '.join(against)}.")
    if source in _SOURCE_SENTENCES:
        parts.append(_SOURCE_SENTENCES[source].format(a=a, b=b))
    return " ".join(parts)
```

In `link_reason`, before `if rule == "reference-order":` add:

```python
    if rule == "three-votes":
        return _three_vote_reason(evidence, a, b)
```

Update the module docstring's first line to mention v7: `Built from the evidence ``criteria.decide_pairs`` stores on each derived row (v6 or v7);`.

- [ ] **Step 4: Run the tests to see them pass**

Run: `python manage.py test learning_path.test_reasons`
Expected: OK.

- [ ] **Step 5: Commit**

```bash
git add backend/learning_path/services/reasons.py backend/learning_path/test_reasons.py
git commit -m "Explain a three-vote link in one plain sentence on the review screen

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Moved lessons, and scoring them

**Files:**
- Create: `backend/learning_path/fixtures/direction_moves.json`
- Create: `backend/learning_path/services/moves.py`
- Modify: `backend/learning_path/services/gold.py` (append `move_report`, `vote_accuracy`)
- Test: `backend/learning_path/test_moves.py`

**Interfaces:**
- Consumes: `gold._edges(decisions, key, verdict)`, `gold.FIXTURES`, `criteria.ACCEPTED/PENDING`; Task 2's `cast_votes`, `VOTES`; Task 1's `build_block_matrix`.
- Produces:
  - `moves.load_moves(topic_id=None) -> list[dict]`; a move is `{"number", "set", "topic", "concepts": [keys], "place": "start"|"end"|"before"|"after", "target": key|None}`
  - `moves.apply_move(concepts, move) -> list` (new concept objects; the input is untouched)
  - `gold.move_report(data, concepts, decisions, move) -> dict` keys `move`, `topic`, `links`, `right_way`, `wrong_way`, `pending`, `missing`, `wrong_way_elsewhere`
  - `gold.vote_accuracy(data, concepts) -> {vote: {"right", "wrong", "silent"}}`

- [ ] **Step 1: Write the moves fixture** (approved by the user 2026-10-01; spec section 8)

`backend/learning_path/fixtures/direction_moves.json`:

```json
{
  "_note": "Misplaced-concept copies for the v7 direction test (v7 spec section 8). Approved by the user 2026-10-01, written before any v7 code. A move relocates every block of the listed concepts; the answer key is unchanged. Final-check moves are scored once, after the freeze.",
  "moves": [
    {"number": 1, "set": "design", "topic": 340, "concepts": ["summary"], "place": "start", "target": null},
    {"number": 2, "set": "design", "topic": 340, "concepts": ["comparing", "comparing_detail"], "place": "before", "target": "solid"},
    {"number": 3, "set": "design", "topic": 357, "concepts": ["fertilization"], "place": "before", "target": "pollination"},
    {"number": 4, "set": "design", "topic": 357, "concepts": ["reproduction"], "place": "after", "target": "petals"},
    {"number": 5, "set": "final", "topic": 341, "concepts": ["properties"], "place": "end", "target": null},
    {"number": 6, "set": "final", "topic": 343, "concepts": ["activity"], "place": "start", "target": null},
    {"number": 7, "set": "final", "topic": 347, "concepts": ["reversible"], "place": "start", "target": null},
    {"number": 8, "set": "final", "topic": 348, "concepts": ["choosing_text", "choosing_table"], "place": "after", "target": "why_separable"},
    {"number": 9, "set": "final", "topic": 348, "concepts": ["filtering"], "place": "before", "target": "decantation"}
  ]
}
```

- [ ] **Step 2: Write the failing tests**

`backend/learning_path/test_moves.py`:

```python
"""Moved lessons for the v7 direction test (v7 spec section 8)."""

from django.test import SimpleTestCase

from .services.criteria import ACCEPTED, PENDING
from .services.gold import move_report
from .services.moves import apply_move, load_moves
from .testing import concept, member


def lesson():
    return [
        concept(1, "Matter", member("Matter takes up space.", order=0), key="matter"),
        concept(2, "Solid", member("A solid keeps its shape.", order=1),
                member("A solid is hard.", material_id=2, order=0), key="solid"),
        concept(3, "Summary", member("Matter can be solid.", order=2), key="summary"),
    ]


def orders(concepts):
    return {item.key: [(chunk.material_id, chunk.order) for chunk in item.members] for item in concepts}


class ApplyMoveTests(SimpleTestCase):
    def test_a_concept_moved_to_the_start_comes_first_everywhere(self):
        moved = apply_move(lesson(), {"concepts": ["summary"], "place": "start", "target": None})

        self.assertEqual([item.key for item in moved], ["summary", "matter", "solid"])
        self.assertEqual([item.order for item in moved], [0, 1, 2])
        self.assertLess(orders(moved)["summary"][0][1], 0)

    def test_a_concept_moved_before_a_target_lands_just_before_it(self):
        moved = apply_move(lesson(), {"concepts": ["summary"], "place": "before", "target": "solid"})

        self.assertEqual([item.key for item in moved], ["matter", "summary", "solid"])
        summary_order = orders(moved)["summary"][0][1]
        self.assertTrue(0 < summary_order < 1)

    def test_a_concept_moved_after_a_target_lands_just_after_it(self):
        moved = apply_move(lesson(), {"concepts": ["matter"], "place": "after", "target": "solid"})

        self.assertEqual([item.key for item in moved], ["solid", "matter", "summary"])
        self.assertTrue(1 < orders(moved)["matter"][0][1] < 2)

    def test_a_pdf_without_the_target_leaves_the_concept_in_place(self):
        moved = apply_move(lesson(), {"concepts": ["solid"], "place": "before", "target": "matter"})

        self.assertIn((2, 0), orders(moved)["solid"])

    def test_the_original_lesson_is_untouched(self):
        original = lesson()

        apply_move(original, {"concepts": ["summary"], "place": "start", "target": None})

        self.assertEqual(orders(original)["summary"], [(1, 2)])

    def test_an_unknown_concept_or_target_is_refused(self):
        with self.assertRaises(ValueError):
            apply_move(lesson(), {"concepts": ["gas"], "place": "start", "target": None})
        with self.assertRaises(ValueError):
            apply_move(lesson(), {"concepts": ["summary"], "place": "before", "target": "gas"})

    def test_the_fixture_holds_the_nine_approved_moves(self):
        moves = load_moves()

        self.assertEqual([move["number"] for move in moves], list(range(1, 10)))
        self.assertEqual({move["topic"] for move in moves if move["set"] == "design"}, {340, 357})
        self.assertEqual([move["number"] for move in load_moves(348)], [8, 9])


class MoveReportTests(SimpleTestCase):
    def test_it_scores_the_moved_concepts_links_and_wrong_links_elsewhere(self):
        concepts = lesson()
        matter, solid, summary = concepts
        data = {"topic_id": 1, "required": [["matter", "summary"], ["solid", "summary"], ["matter", "solid"]]}
        decisions = [
            {"prerequisite": matter, "dependent": summary, "verdict": ACCEPTED},
            {"prerequisite": summary, "dependent": solid, "verdict": ACCEPTED},
            {"prerequisite": solid, "dependent": matter, "verdict": ACCEPTED},
        ]

        report = move_report(data, concepts, decisions, {"number": 1, "topic": 1, "concepts": ["summary"]})

        self.assertEqual(report["links"], 2)
        self.assertEqual(report["right_way"], [["matter", "summary"]])
        self.assertEqual(report["wrong_way"], [["solid", "summary"]])
        self.assertEqual(report["wrong_way_elsewhere"], [["solid", "matter"]])

    def test_a_suggested_link_counts_as_pending(self):
        concepts = lesson()
        matter, _, summary = concepts
        data = {"topic_id": 1, "required": [["matter", "summary"]]}
        decisions = [{"prerequisite": matter, "dependent": summary, "verdict": PENDING}]

        report = move_report(data, concepts, decisions, {"number": 1, "topic": 1, "concepts": ["summary"]})

        self.assertEqual(report["pending"], [["matter", "summary"]])
        self.assertEqual(report["missing"], [])
```

- [ ] **Step 3: Run the tests to see them fail**

Run: `python manage.py test learning_path.test_moves`
Expected: ERROR, `ImportError: cannot import name 'move_report'`.

- [ ] **Step 4: Write `moves.py`**

`backend/learning_path/services/moves.py`:

```python
"""Misplaced-concept copies of gold topics, for the v7 direction test.

Spec: docs/superpowers/specs/2026-10-01-learning-path-v7-direction-votes-design.md,
section 8. A move takes every block of some concepts and puts it where the
lesson clearly should not have it; the answer key stays the same, so a rule
that reads more than the order can put the concept back.
"""

import json
from types import SimpleNamespace

from .gold import FIXTURES

MOVES_FILE = FIXTURES / "direction_moves.json"


def load_moves(topic_id=None):
    moves = json.loads(MOVES_FILE.read_text(encoding="utf-8"))["moves"]
    if topic_id is None:
        return moves
    return [move for move in moves if str(move["topic"]) == str(topic_id)]


def _new_spots(anchor, count):
    """``count`` positions strictly between ``anchor`` and ``anchor + 1``, in order."""
    return [anchor + (index + 1) / (count + 1) for index in range(count)]


def apply_move(concepts, move):
    """A copy of ``concepts`` with the move applied, in the merged order and in every PDF."""
    keys = {item.key for item in concepts}
    moving_keys = set(move["concepts"])
    target = move.get("target")
    if not moving_keys <= keys or (move["place"] in ("before", "after") and target not in keys):
        raise ValueError(f"move {move.get('number')}: {sorted(moving_keys - keys) or target} is not in this topic")

    moving = [item for item in concepts if item.key in moving_keys]
    staying = [item for item in concepts if item.key not in moving_keys]
    if move["place"] == "start":
        merged = moving + staying
    elif move["place"] == "end":
        merged = staying + moving
    else:
        spots = [index for index, item in enumerate(staying) if item.key == target]
        cut = spots[0] if move["place"] == "before" else spots[-1] + 1
        merged = staying[:cut] + moving + staying[cut:]

    new_order = {}
    materials = {chunk.material_id for item in concepts for chunk in item.members}
    for material in materials:
        chunks = [chunk for item in moving for chunk in item.members if chunk.material_id == material]
        others = [chunk for item in staying for chunk in item.members if chunk.material_id == material]
        targets = [chunk.order for item in staying if item.key == target
                   for chunk in item.members if chunk.material_id == material]
        if not chunks or not others:
            continue
        if move["place"] == "start":
            anchor = min(chunk.order for chunk in others) - 1
        elif move["place"] == "end":
            anchor = max(chunk.order for chunk in others)
        elif not targets:
            continue  # this PDF does not teach the target: leave the concept where it is
        elif move["place"] == "before":
            anchor = min(targets) - 1
        else:
            anchor = max(targets)
        for chunk, spot in zip(chunks, _new_spots(anchor, len(chunks))):
            new_order[id(chunk)] = spot

    return [
        SimpleNamespace(**{
            **vars(item),
            "order": position,
            "members": tuple(
                SimpleNamespace(**{**vars(chunk), "order": new_order.get(id(chunk), chunk.order)})
                for chunk in item.members
            ),
        })
        for position, item in enumerate(merged)
    ]
```

- [ ] **Step 5: Append `move_report` and `vote_accuracy` to `gold.py`**

Add to `gold.py`'s imports (keep the existing ones):

```python
from .clues import find_term_owners
from .concept_text import prepare
from .direction_votes import VOTES, build_block_matrix, cast_votes
```

(If `prepare` or `find_term_owners` is already imported there, do not import it twice.)

Append:

```python
def move_report(data, concepts, decisions, move):
    """How a moved lesson's links came out (v7 spec section 8).

    The moved concepts' key links are right, wrong (accepted reversed), pending
    or missing; ``wrong_way_elsewhere`` is any other key link accepted reversed.
    """
    moved = set(move["concepts"])
    key = {concept.id: concept.key for concept in concepts}
    accepted = set(_edges(decisions, key, criteria.ACCEPTED))
    pending = set(_edges(decisions, key, criteria.PENDING))
    required = [tuple(edge) for edge in data["required"]]
    links = [edge for edge in required if edge[0] in moved or edge[1] in moved]
    right = [edge for edge in links if edge in accepted]
    wrong = [edge for edge in links if (edge[1], edge[0]) in accepted]
    waiting = [edge for edge in links if edge not in right and edge not in wrong
               and (edge in pending or (edge[1], edge[0]) in pending)]
    missing = [edge for edge in links if edge not in right and edge not in wrong and edge not in waiting]
    elsewhere = [edge for edge in required if edge not in links and (edge[1], edge[0]) in accepted]
    return {
        "move": move["number"],
        "topic": move["topic"],
        "links": len(links),
        "right_way": [list(edge) for edge in right],
        "wrong_way": [list(edge) for edge in wrong],
        "pending": [list(edge) for edge in waiting],
        "missing": [list(edge) for edge in missing],
        "wrong_way_elsewhere": [[after, before] for before, after in elsewhere],
    }


def vote_accuracy(data, concepts):
    """For each v7 vote, how many of the key's links it points the right way, the wrong way, or not at all."""
    texts = prepare(concepts)
    matrix = build_block_matrix(texts, find_term_owners(texts))
    first_of_key = {}
    for text in texts:
        if getattr(text.concept, "key", None):
            first_of_key.setdefault(text.concept.key, text)
    counts = {vote: {"right": 0, "wrong": 0, "silent": 0} for vote in VOTES}
    for before, after in data["required"]:
        votes, _ = cast_votes(first_of_key[before], first_of_key[after], matrix)
        for vote, value in votes.items():
            counts[vote]["right" if value == 1 else "wrong" if value == -1 else "silent"] += 1
    return counts
```

- [ ] **Step 6: Run the tests to see them pass**

Run: `python manage.py test learning_path.test_moves learning_path.test_gold_report`
Expected: OK.

- [ ] **Step 7: Commit**

```bash
git add backend/learning_path/fixtures/direction_moves.json backend/learning_path/services/moves.py backend/learning_path/services/gold.py backend/learning_path/test_moves.py
git commit -m "Add the nine approved moves and score lessons with a misplaced concept

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: The evaluation command, and fencing off the final check

**Files:**
- Modify: `backend/learning_path/management/commands/evaluate_gold_paths.py`
- Modify: `backend/learning_path/test_gold_paths.py` (tag the four final-check tests)
- Test: `backend/learning_path/test_evaluate_command.py` (create)

**Interfaces:**
- Consumes: `criteria.RULES`, `criteria.DEFAULT_RULE`; `moves.load_moves`, `moves.apply_move`; `gold.move_report`, `gold.vote_accuracy`.
- Produces: `python manage.py evaluate_gold_paths [--topics ...] [--rule three-votes|reference-order] [--moves] [--by-vote] [--final-check]`; default topics `340 357`; output JSON adds `"rule"` and, per report, `"moves"` and `"vote_accuracy"` when asked.

- [ ] **Step 1: Write the failing tests**

`backend/learning_path/test_evaluate_command.py`:

```python
"""The evaluation command's guard around the final check (v7 spec section 8)."""

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase


class FinalCheckGuardTests(SimpleTestCase):
    def test_a_final_check_topic_needs_the_flag(self):
        with self.assertRaisesMessage(CommandError, "--final-check"):
            call_command("evaluate_gold_paths", topics=["341"])

    def test_the_default_topics_are_the_design_set(self):
        from learning_path.management.commands.evaluate_gold_paths import DESIGN_TOPICS

        self.assertEqual(DESIGN_TOPICS, ["340", "357"])
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `python manage.py test learning_path.test_evaluate_command`
Expected: FAIL / ERROR (no guard, no `DESIGN_TOPICS`).

- [ ] **Step 3: Update the command**

Replace the docstring's switch list and add the new switches; the full file becomes:

```python
"""Print the gold report for frozen topics, with the switches the evaluation needs.

--rule RULE          three-votes (v7) or reference-order (v6); default criteria.DEFAULT_RULE
--moves              also score each approved move of the topic (fixtures/direction_moves.json)
--by-vote            add each v7 vote's right/wrong/silent count on the key's links
--final-check        required to score 341, 343, 347 or 348 (scored once, after the freeze)
--without CLUE       silence one clue (v6 ablation)
--build-on-latest    Kahn ties prefer the concept building on the latest step (off by default)
--meaning-matches N  average the N best matches in the meaning clue (size check)
--by-clue            add each v6 clue's right/wrong count on the key's links
--baseline order     link each concept to the one before it (no text read)
"""

import json

from django.core.management.base import BaseCommand, CommandError

from learning_path.services import clues, criteria
from learning_path.services.calibration import load_calibration
from learning_path.services.fusion import CLUES
from learning_path.services.gold import (
    clue_accuracy, gate_loss, gold_report, load_gold, move_report, order_only_decisions, vote_accuracy,
)
from learning_path.services.moves import apply_move, load_moves

DESIGN_TOPICS = ["340", "357"]
FINAL_CHECK_TOPICS = {"341", "343", "347", "348"}


class Command(BaseCommand):
    help = "Report derived learning paths against the gold standard."

    def add_arguments(self, parser):
        parser.add_argument("--topics", nargs="*", default=DESIGN_TOPICS)
        parser.add_argument("--rule", choices=criteria.RULES)
        parser.add_argument("--moves", action="store_true")
        parser.add_argument("--by-vote", action="store_true")
        parser.add_argument("--final-check", action="store_true")
        parser.add_argument("--baseline", choices=["order"])
        parser.add_argument("--without", choices=CLUES)
        parser.add_argument("--build-on-latest", action="store_true")
        parser.add_argument("--meaning-matches", type=int, default=1)
        parser.add_argument("--by-clue", action="store_true")

    def handle(self, *args, topics, rule, moves, by_vote, final_check, without, build_on_latest,
               meaning_matches, by_clue, baseline, **options):
        held_back = sorted(FINAL_CHECK_TOPICS & {str(topic) for topic in topics})
        if held_back and not final_check:
            raise CommandError(
                f"{', '.join(held_back)} belong to the final check and are scored once, after the "
                "freeze (v7 spec section 8). Pass --final-check to score them."
            )
        rule = rule or criteria.DEFAULT_RULE
        calibration = load_calibration()
        previous_matches = clues.MEANING_MATCHES
        clues.MEANING_MATCHES = meaning_matches

        def decide(concepts):
            if baseline == "order":
                return order_only_decisions(concepts)
            return criteria.decide_pairs(
                concepts, calibration=calibration, without=(without,) if without else (), rule=rule,
            )

        try:
            reports = []
            for topic_id in topics:
                data, concepts = load_gold(topic_id)
                report = gold_report(data, concepts, decide(concepts), build_on_latest=build_on_latest)
                report["gate_loss"] = gate_loss(data, concepts, calibration)
                if by_clue:
                    report["clue_accuracy"] = clue_accuracy(data, concepts, calibration)
                if by_vote:
                    report["vote_accuracy"] = vote_accuracy(data, concepts)
                if moves:
                    report["moves"] = []
                    for move in load_moves(topic_id):
                        moved = apply_move(concepts, move)
                        report["moves"].append(move_report(data, moved, decide(moved), move))
                reports.append(report)
        finally:
            clues.MEANING_MATCHES = previous_matches
        self.stdout.write(json.dumps({
            "calibration": calibration["source"],
            "rule": rule,
            "without": without,
            "baseline": baseline,
            "build_on_latest": build_on_latest,
            "meaning_matches": meaning_matches,
            "reports": reports,
        }, indent=2))
```

- [ ] **Step 4: Tag the final-check gold tests**

In `test_gold_paths.py`, add `from django.test import SimpleTestCase, tag` (replacing the plain `SimpleTestCase` import) and put `@tag("final_check")` on the four methods `test_topic_341_grouping_materials`, `test_topic_343_mixtures`, `test_topic_347_changes_in_materials`, `test_topic_348_separating_mixtures`. Add this line to the module docstring: "The four test-set topics are tagged ``final_check``: run with ``--exclude-tag final_check`` until the v7 freeze."

- [ ] **Step 5: Run the tests to see them pass**

Run: `python manage.py test learning_path.test_evaluate_command`
Expected: OK.
Run: `python manage.py test learning_path --exclude-tag final_check`
Expected: OK (v6 is still the default, so the design gold tests keep their v6 floors).

- [ ] **Step 6: Commit**

```bash
git add backend/learning_path/management/commands/evaluate_gold_paths.py backend/learning_path/test_gold_paths.py backend/learning_path/test_evaluate_command.py
git commit -m "Score moves and votes in the evaluation, and keep the final check locked

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: The spreadsheet export

**Files:**
- Create: `backend/learning_path/services/direction_sheet.py`
- Create: `backend/learning_path/management/commands/export_direction_sheet.py`
- Test: `backend/learning_path/test_direction_sheet.py`

**Interfaces:**
- Consumes: `criteria.decide_pairs(..., rule=THREE_VOTES)`, `criteria.THREE_VOTES`; `direction_votes` constants, `build_block_matrix`, `centre_order_vote`; `clues.heading_vote`, `clues.find_term_owners`; `concept_text.prepare`; `embeddings.EncoderUnavailable`; `gold.load_gold`; `concept_units.concepts_for_topic(node)`.
- Produces: `direction_sheet.direction_sheet_rows(concepts) -> list[list]`, `direction_sheet.column(number) -> str`; command `python manage.py export_direction_sheet [topic_id] [--gold ID] --output PATH`.

Sheet layout (1-based rows): row 1 settings (`C1` MIN_BLOCKS, `E1` SUBSUME_HIGH, `G1` SUBSUME_LOW, `I1` REFERENCE_GAP); row 3 block owners; row 4 PDFs; row 5 positions; rows 6.. the 0/1 matrix, one concept per row; a blank row; a header; one row per three-vote pair. Pair columns: `A` A, `B` B, `C` Heading (value), `D` Centres (text), `E` Blocks A, `F` Blocks B, `G` Both, `H` P(A|B), `I` P(B|A), `J` A refers to B, `K` B refers to A, `L` Hierarchy, `M` Order (value), `N` Reference, `O` Voters, `P` Total, `Q` Verdict, `R` Direction, `S` Python verdict, `T` Python direction. A is the pair's concept earlier in the topic's merged order.

- [ ] **Step 1: Write the failing tests**

`backend/learning_path/test_direction_sheet.py`:

```python
"""The direction votes as a spreadsheet (v7 spec section 7)."""

import csv
import tempfile
from pathlib import Path

from django.core.management import call_command
from django.test import SimpleTestCase

from .services.direction_sheet import column, direction_sheet_rows
from .test_direction_votes import three_states


class DirectionSheetTests(SimpleTestCase):
    def setUp(self):
        self.rows = direction_sheet_rows(three_states())
        self.header = next(index for index, row in enumerate(self.rows) if row[:2] == ["A", "B"])
        self.pairs = {tuple(row[:2]): row for row in self.rows[self.header + 1:]}

    def test_column_letters(self):
        self.assertEqual([column(1), column(26), column(27)], ["A", "Z", "AA"])

    def test_the_matrix_rows_hold_zeros_and_ones(self):
        self.assertEqual(self.rows[5], ["Solid [1]", 1, 1, 1, 0, 0, 0])
        self.assertEqual(self.rows[6], ["Matter [2]", 1, 1, 1, 1, 1, 1])

    def test_counts_are_formulas_over_the_matrix(self):
        row = self.pairs[("Solid [1]", "Matter [2]")]

        self.assertEqual(row[4], "=SUM($B$6:$G$6)")
        self.assertEqual(row[6], "=SUMPRODUCT($B$6:$G$6,$B$7:$G$7)")
        self.assertIn("$C$1", row[11])

    def test_the_python_columns_match_decide_pairs(self):
        row = self.pairs[("Solid [1]", "Matter [2]")]

        self.assertEqual((row[12], row[18], row[19]), (1, "accepted", "B first"))

    def test_the_command_writes_a_csv_excel_can_open(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "sheet.csv"
            call_command("export_direction_sheet", gold="357", output=str(output))

            with output.open(encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.reader(handle))

        self.assertEqual(rows[0][:3], ["Settings", "MIN_BLOCKS", "3"])
        self.assertTrue(any(row[:2] == ["A", "B"] for row in rows))
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `python manage.py test learning_path.test_direction_sheet`
Expected: ERROR, `ModuleNotFoundError: No module named 'learning_path.services.direction_sheet'`.

- [ ] **Step 3: Write the sheet builder**

`backend/learning_path/services/direction_sheet.py`:

```python
"""The v7 direction votes as a spreadsheet (spec section 7).

One CSV: the settings, the block x concept matrix, then one row per pair whose
counts, shares, votes and verdict are Excel formulas over the matrix, so a
teacher can change a 0/1 cell or a setting and watch the verdict move. Heading,
order and the teaching centres are values: they come from the lesson's
structure, not from the matrix. The two "Python" columns are what the code
decided, for checking the formulas against.
"""

from . import criteria
from .clues import find_term_owners, heading_vote
from .concept_text import prepare
from .direction_votes import (
    MIN_BLOCKS, REFERENCE_GAP, SUBSUME_HIGH, SUBSUME_LOW, build_block_matrix, centre_order_vote,
)
from .embeddings import EncoderUnavailable

HEADER = [
    "A", "B", "Heading", "Centres", "Blocks A", "Blocks B", "Both", "P(A|B)", "P(B|A)",
    "A refers to B", "B refers to A", "Hierarchy", "Order", "Reference", "Voters", "Total",
    "Verdict", "Direction", "Python verdict", "Python direction",
]


def column(number):
    """Spreadsheet column letters: 1 -> A, 27 -> AA."""
    letters = ""
    while number:
        number, rest = divmod(number - 1, 26)
        letters = chr(65 + rest) + letters
    return letters


def _no_encoder(sentences):
    # The verdicts do not need the encoder (criteria docstring); skip loading it.
    raise EncoderUnavailable("not needed for the sheet")


def direction_sheet_rows(concepts):
    concepts = list(concepts)
    texts = prepare(concepts)
    by_id = {text.id: text for text in texts}
    matrix = build_block_matrix(texts, find_term_owners(texts))
    labels = {text.id: f"{text.concept.title} [{text.id}]" for text in texts}
    last = column(len(matrix.blocks) + 1)
    owners = f"$B$3:${last}$3"

    rows = [
        ["Settings", "MIN_BLOCKS", MIN_BLOCKS, "SUBSUME_HIGH", SUBSUME_HIGH,
         "SUBSUME_LOW", SUBSUME_LOW, "REFERENCE_GAP", REFERENCE_GAP],
        [],
        ["Owner"] + [labels[block.owner] for block in matrix.blocks],
        ["PDF"] + [block.material_id for block in matrix.blocks],
        ["Position"] + [block.order for block in matrix.blocks],
    ]
    matrix_row = {}
    for text in texts:
        matrix_row[text.id] = len(rows) + 1
        rows.append([labels[text.id]] + [int(cell) for cell in matrix.present[text.id]])
    rows += [[], HEADER]

    position = {text.id: index for index, text in enumerate(texts)}
    decisions = criteria.decide_pairs(concepts, embed=_no_encoder, rule=criteria.THREE_VOTES)
    for decision in decisions:
        if decision["evidence"]["rule"] != criteria.THREE_VOTES:
            continue
        a, b = sorted((decision["prerequisite"].id, decision["dependent"].id), key=position.get)
        r = len(rows) + 1
        span_a = f"$B${matrix_row[a]}:${last}${matrix_row[a]}"
        span_b = f"$B${matrix_row[b]}:${last}${matrix_row[b]}"
        order, order_record = centre_order_vote(by_id[a], by_id[b], matrix)
        rows.append([
            labels[a], labels[b],
            heading_vote(by_id[a], by_id[b])[0],
            "; ".join(f"PDF {pdf}: {first} vs {second}" for pdf, (first, second) in order_record["centres"].items()),
            f"=SUM({span_a})",
            f"=SUM({span_b})",
            f"=SUMPRODUCT({span_a},{span_b})",
            f"=IF(F{r}=0,0,G{r}/F{r})",
            f"=IF(E{r}=0,0,G{r}/E{r})",
            f"=SUMPRODUCT(({owners}=A{r})*({span_b}))/COUNTIF({owners},A{r})",
            f"=SUMPRODUCT(({owners}=B{r})*({span_a}))/COUNTIF({owners},B{r})",
            f"=IF(C{r}<>0,C{r},IF(AND(E{r}>=$C$1,F{r}>=$C$1),"
            f"IF(AND(H{r}>=$E$1,I{r}<=$G$1),1,IF(AND(I{r}>=$E$1,H{r}<=$G$1),-1,0)),0))",
            order,
            f"=IF(K{r}-J{r}>=$I$1,1,IF(K{r}-J{r}<=-$I$1,-1,0))",
            f'=COUNTIF(L{r}:N{r},"<>0")',
            f"=SUM(L{r}:N{r})",
            f'=IF(O{r}=0,"pending",IF(AND(O{r}=1,M{r}=0),"pending",'
            f'IF(ABS(P{r})>=O{r}-(O{r}=3)*2,"accepted","pending")))',
            f'=IF(P{r}>0,"A first",IF(P{r}<0,"B first",IF(M{r}<0,"B first","A first")))',
            decision["verdict"],
            "A first" if decision["prerequisite"].id == a else "B first",
        ])
    return rows
```

- [ ] **Step 4: Write the command**

`backend/learning_path/management/commands/export_direction_sheet.py`:

```python
"""Write a topic's v7 direction votes as a CSV that Excel recalculates.

    python manage.py export_direction_sheet 12 --output topic12.csv     # a live topic
    python manage.py export_direction_sheet --gold 340 --output 340.csv # a frozen gold topic
"""

import csv

from django.core.management.base import BaseCommand, CommandError

from learning_path.services.concept_units import concepts_for_topic
from learning_path.services.direction_sheet import direction_sheet_rows
from learning_path.services.gold import load_gold
from lessons.models import OutlineNode


class Command(BaseCommand):
    help = "Write a topic's direction votes as a spreadsheet with live formulas."

    def add_arguments(self, parser):
        parser.add_argument("topic_id", nargs="?", type=int, help="Outline topic.")
        parser.add_argument("--gold", help="A frozen gold topic instead, e.g. 340.")
        parser.add_argument("--output", required=True, help="Where to write the CSV.")

    def handle(self, *args, topic_id=None, gold=None, output, **options):
        if gold:
            _, concepts = load_gold(gold)
        elif topic_id is not None:
            node = OutlineNode.objects.filter(pk=topic_id).first()
            if node is None:
                raise CommandError(f"Topic {topic_id} does not exist.")
            concepts = concepts_for_topic(node)
        else:
            raise CommandError("Give a topic id or --gold.")
        # utf-8-sig so Excel reads the titles' accents correctly.
        with open(output, "w", newline="", encoding="utf-8-sig") as handle:
            csv.writer(handle).writerows(direction_sheet_rows(concepts))
        self.stdout.write(f"Wrote {output}")
```

- [ ] **Step 5: Run the tests to see them pass**

Run: `python manage.py test learning_path.test_direction_sheet`
Expected: OK. (357 is a design topic, so exporting it is allowed.)

- [ ] **Step 6: Commit**

```bash
git add backend/learning_path/services/direction_sheet.py backend/learning_path/management/commands/export_direction_sheet.py backend/learning_path/test_direction_sheet.py
git commit -m "Export the direction votes as a spreadsheet that recalculates in Excel

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Measure on the design set, then freeze

No new code unless a cut-off changes. Everything here uses 340 and 357 only.

**Files:**
- Create: `docs/learning-path-v7-evaluation/` (raw JSON outputs)
- Possibly modify: `backend/learning_path/services/direction_votes.py` (cut-offs only)

- [ ] **Step 1: Run v6 and v7 on the design set, unmoved and moved**

From `backend/`:

```bash
mkdir -p ../docs/learning-path-v7-evaluation
python manage.py evaluate_gold_paths --rule reference-order --moves > ../docs/learning-path-v7-evaluation/design-v6.json
python manage.py evaluate_gold_paths --rule three-votes --moves --by-vote > ../docs/learning-path-v7-evaluation/design-v7.json
```

- [ ] **Step 2: Summarise**

For each rule and topic, read off: `covered_count`, `accepted_precision`, `forbidden_accepted`, number of `accepted` and `pending`, and for each of moves 1–4 the counts of `right_way`, `wrong_way`, `pending`, `missing`, `wrong_way_elsewhere`; for v7 also `vote_accuracy`. Put them in a table in the report draft (Task 9, section "Design set").

- [ ] **Step 3: Decide on cut-offs (design set only)**

Change a cut-off only if a v7 result on 340/357 is plainly caused by it (e.g. a wrong-way link the subsumption cut-off lets through). Record every change and its reason in the report. Prefer the starting values: two AI-keyed topics are a thin base for five numbers. If nothing changes, write "starting values kept".

- [ ] **Step 4: Freeze**

```bash
git add ../docs/learning-path-v7-evaluation backend/learning_path/services/direction_votes.py
git commit -m "Measure v7 on the design set and freeze its rules for the final check

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git rev-parse --short HEAD
```

Write the printed hash into the report as the frozen rule version. From here `services/direction_votes.py` and `services/criteria.py` must not change before the final run.

---

### Task 9: The final check (once), the stop rule, and the write-up

**Files:**
- Create: `docs/learning-path-v7-evaluation-2026-10-01.md`
- Create: `docs/learning-path-v7-evaluation/final-v6.json`, `final-v7.json`
- Modify: `backend/learning_path/services/criteria.py` (`DEFAULT_RULE`, only if v7 passes)
- Modify: `backend/learning_path/test_gold_paths.py`, `backend/learning_path/test_criteria.py` (only if v7 passes)
- Modify: `backend/learning_path/CRITERIA.md`

- [ ] **Step 1: Score the final check once**

```bash
python manage.py evaluate_gold_paths --topics 341 343 347 348 --final-check --rule reference-order --moves > ../docs/learning-path-v7-evaluation/final-v6.json
python manage.py evaluate_gold_paths --topics 341 343 347 348 --final-check --rule three-votes --moves --by-vote > ../docs/learning-path-v7-evaluation/final-v7.json
```

Do not rerun with different settings after reading these.

- [ ] **Step 2: Apply the stop rule (spec section 8)**

v7 passes only if all three hold on the final check:
1. `forbidden_accepted` is empty for all four unmoved topics;
2. accepted precision over the four unmoved topics (sum of accepted links in `implied` ÷ sum of accepted) ≥ 0.63 (v6's 0.68 − 0.05);
3. over moves 5–9, v7's total `right_way` > v6's total `right_way`.

- [ ] **Step 3a (v7 passes): switch the default**

In `criteria.py` set `DEFAULT_RULE = THREE_VOTES` and change its comment to `# v7 since the final check of <date> (docs/learning-path-v7-evaluation-2026-10-01.md).`
In `test_criteria.py`, make the v6 helper explicit so v6's tests keep testing v6: in `decide`, pass `rule="reference-order"` to `decide_pairs`; change `test_the_default_rule_is_still_v6_until_the_final_check` to assert `"three-votes"` for rows that are not `pdf_agreement` suggestions and rename it `test_the_default_rule_is_v7`.
In `test_gold_paths.py`: replace the v6 floors for 340, 357, 341, 343, 347, 348 with the v7 values just measured (design values from Task 8, test values from this single run), set `KNOWN_FORBIDDEN` to what v7 accepted against the key on 340/357 with a one-line reason each, remove the `final_check` tags, delete the three tests for 62/79/152 (not in the v7 sets, user decision 2026-10-01), and update the docstring to say "v7".
Run: `python manage.py test learning_path` → OK.

- [ ] **Step 3b (v7 fails): keep v6**

Leave `DEFAULT_RULE = REFERENCE_ORDER`. Remove the `final_check` tags (the final check is spent). Run `python manage.py test learning_path` → OK.

- [ ] **Step 4: Write the report**

`docs/learning-path-v7-evaluation-2026-10-01.md`, in the shape of `docs/learning-path-v6-evaluation-2026-09-30.md`: frozen commit; sets; how to read the numbers; design-set table (v6 vs v7, unmoved and moves 1–4, cut-off decisions); final-check table (same, moves 5–9); vote accuracy; the stop-rule outcome with the three numbers; where v7 fails (expected: 347/348, one block per concept); limits (AI-drafted keys leaning to PDF order, two design topics, presence by names and owned terms only).

- [ ] **Step 5: Update `CRITERIA.md`**

If v7 passed: retitle to "(v7)", replace "The idea", "The steps" step 2, "The evidence" and "The verdict" sections with v7's (spec sections 4–6), keep v6's verdict table under a "v6 (still selectable: `rule="reference-order"`)" heading, and add the export command. If v7 failed: add a short "v7 (tried 2026-10-01, not adopted)" section linking the report.

- [ ] **Step 6: Commit**

```bash
git add ../docs/learning-path-v7-evaluation ../docs/learning-path-v7-evaluation-2026-10-01.md backend/learning_path
git commit -m "Score v7 once on the final check and record whether it replaces v6

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
