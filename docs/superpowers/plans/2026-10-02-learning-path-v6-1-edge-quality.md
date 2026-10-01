# Learning-path v6.1: cleaner edges — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make v6's automatic prerequisite edges cleaner: figures and different PDFs no longer block a link, and a link resting on a single shared word becomes a teacher suggestion.

**Architecture:** The three changes live inside v6's existing code path (`clues.term_use`/`reference_uses`, `fusion.reference_verdict`, `criteria.decide_pairs`) behind a new rule name, `rule="cleaner-edges"`. v6 (`"reference-order"`) stays the default and is untouched, so both are measured by the same code; the default switches only if the final check passes the spec's stop rule.

**Tech Stack:** Django management commands, `SimpleTestCase`, Python stdlib. No new dependency.

**Spec:** `docs/superpowers/specs/2026-10-02-learning-path-v6-1-edge-quality-design.md` (commit bd1ac23). Read it first.

## Global Constraints

- `MIN_SHARED_TERMS = 2` is the only number; it may change only from design-set (340, 357) results, in Task 6.
- Design set: 340, 357. Final check: 351, 353, 365 — **never** scored, printed or opened before Task 7 (fixtures committed in 445655e, keys approved by the user). 341–348 are a secondary, already-seen set, also scored only in Task 7.
- The designer/executor must not print or read `fixtures/gold_topic_351.json`, `_353`, `_365` or `docs/learning-path-new-topic-keys/*` before Task 7.
- v6 behaviour with the default rule must not change in Tasks 1–6 (all existing tests stay green unmodified).
- Course-level criteria (`course_criteria.py`) and v7 (`three-votes`) are not changed: every new parameter defaults to v6's behaviour.
- Names: descriptive but short, plain English, like the surrounding code.
- Commit messages: one plain sentence, ending with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Run tests from `backend/`: `python manage.py test learning_path.<module>`; the whole app with `python manage.py test learning_path --exclude-tag final_check` until Task 7.

## Review Focus

1. A pair linked by a single word **and** under a shared heading naming neither (`parallel`) must still get no link, not a suggestion. (Task 2 test.)
2. A pair linked by single words while its PDFs disagree on the order: the suggestion's direction follows the merged order, not a PDF. (Task 2 test.)
3. Ablation `--without terms` must silence the single-word fields too, or "without terms" would still produce `weak_terms` suggestions. (Task 3 test.)
4. Scoring 351/353/365 by accident must fail loudly without `--final-check`. (Task 5 test.)
5. The review-screen sentence for a single-word suggestion must name the word even when it is the *prerequisite's* text that uses the dependent's word. (Task 4 test.)

---

### Task 1: The owned-terms clue can require two words

**Files:**
- Modify: `backend/learning_path/services/clues.py` (`term_use`, `term_vote`, `reference_uses`, `clue_records`, new constant)
- Test: `backend/learning_path/test_clues.py` (append a class)

**Interfaces:**
- Produces: `clues.MIN_SHARED_TERMS = 2`; `term_use(holder, target, term_owners, min_terms=1) -> float`; `term_vote(prerequisite, dependent, term_owners, min_terms=1) -> (int, dict)` — with `min_terms > 1` the record also has `owned_back`, `single_word_use`, `single_word_use_back`; `reference_uses(earlier, later, term_owners, min_terms=1) -> dict` with keys `later_names_earlier`, `earlier_names_later`, `later_uses_earlier_terms`, `earlier_uses_later_terms`, `later_uses_earlier_word`, `earlier_uses_later_word`; `clue_records(..., semantic=True, min_terms=1)`.

- [ ] **Step 1: Write the failing tests** (append to `test_clues.py`; `prepare`, `concept`, `find_term_owners`, `reference_uses`, `term_vote` — add `term_use`, `term_vote` and `MIN_SHARED_TERMS` to the existing `from .services.clues import (...)` block if missing)

```python
class TwoWordTermTests(SimpleTestCase):
    """v6.1 spec section 3, C4: a chunk uses another concept's terms only with two of them."""

    def lesson(self):
        return prepare([
            concept(1, "Stamen", "The anther makes pollen grains. " * 8),
            concept(2, "Pollination", "Pollen travels from an anther to a stigma."),
            concept(3, "Pistil", "The stigma is sticky and holds the style. " * 8),
        ])

    def test_one_owned_word_counts_by_default(self):
        stamen, pollination, pistil = self.lesson()
        owners = find_term_owners([stamen, pollination, pistil])

        self.assertEqual(term_use(pollination, pistil, owners), 1.0)

    def test_one_owned_word_is_not_enough_with_two_required(self):
        stamen, pollination, pistil = self.lesson()
        owners = find_term_owners([stamen, pollination, pistil])

        self.assertEqual(term_use(pollination, pistil, owners, MIN_SHARED_TERMS), 0.0)
        self.assertEqual(term_use(pollination, stamen, owners, MIN_SHARED_TERMS), 1.0)

    def test_reference_uses_keeps_the_single_word_shares(self):
        stamen, pollination, pistil = self.lesson()
        owners = find_term_owners([stamen, pollination, pistil])

        uses = reference_uses(pollination, pistil, owners, MIN_SHARED_TERMS)

        self.assertEqual(uses["earlier_uses_later_terms"], 0.0)
        self.assertEqual(uses["earlier_uses_later_word"], 1.0)

    def test_the_record_names_the_word_used_either_way(self):
        stamen, pollination, pistil = self.lesson()
        owners = find_term_owners([stamen, pollination, pistil])

        _, record = term_vote(pollination, pistil, owners, MIN_SHARED_TERMS)

        self.assertEqual(record["owned_back"], ["stigma"])
        self.assertEqual((record["single_word_use"], record["single_word_use_back"]), (0.0, 1.0))

    def test_the_default_record_is_unchanged(self):
        stamen, pollination, pistil = self.lesson()
        owners = find_term_owners([stamen, pollination, pistil])

        _, record = term_vote(stamen, pollination, owners)

        self.assertEqual(set(record), {"owned", "use", "use_back"})
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `python manage.py test learning_path.test_clues`
Expected: ERROR, `ImportError: cannot import name 'MIN_SHARED_TERMS'`.

- [ ] **Step 3: Implement**

In `clues.py`, after `MEANING_MATCHES = 1` add:

```python
# v6.1: a chunk uses another concept's terms only when it has two of them (spec 2026-10-02, C4).
MIN_SHARED_TERMS = 2
```

Replace `term_use` and `term_vote` with:

```python
def term_use(holder, target, term_owners, min_terms=1):
    """Share of the holder's passages using at least ``min_terms`` distinct terms the target owns."""
    passages = [passage for passage in holder.passages if passage]
    if not passages:
        return 0.0
    return sum(
        1 for passage in passages
        if len({term for term in passage if term_owners.get(term) == target.id}) >= min_terms
    ) / len(passages)


def _owned_words(holder, owner, term_owners):
    return sorted({
        holder.spelling.get(term, term)
        for passage in holder.passages for term in passage
        if term_owners.get(term) == owner.id
    })


def term_vote(prerequisite, dependent, term_owners, min_terms=1):
    use = term_use(dependent, prerequisite, term_owners, min_terms)
    use_back = term_use(prerequisite, dependent, term_owners, min_terms)
    record = {"owned": _owned_words(dependent, prerequisite, term_owners),
              "use": round(use, 3), "use_back": round(use_back, 3)}
    if min_terms > 1:
        record.update(
            owned_back=_owned_words(prerequisite, dependent, term_owners),
            single_word_use=round(term_use(dependent, prerequisite, term_owners), 3),
            single_word_use_back=round(term_use(prerequisite, dependent, term_owners), 3),
        )
    return _sign(use - use_back), record
```

Replace `reference_uses` with:

```python
def reference_uses(earlier, later, term_owners, min_terms=1):
    """How much each concept refers to the other, by name and by owned terms.

    ``*_word`` are the single-word shares v6.1 keeps to tell a weak link from none.
    """
    same_name = bool(earlier.name) and set(earlier.name) == set(later.name)
    return {
        # One title on two concepts (a split the grouping made) names neither.
        "later_names_earlier": 0.0 if same_name else name_use(later, earlier),
        "earlier_names_later": 0.0 if same_name else name_use(earlier, later),
        "later_uses_earlier_terms": term_use(later, earlier, term_owners, min_terms),
        "earlier_uses_later_terms": term_use(earlier, later, term_owners, min_terms),
        "later_uses_earlier_word": term_use(later, earlier, term_owners),
        "earlier_uses_later_word": term_use(earlier, later, term_owners),
    }
```

In `clue_records`, change the signature to `def clue_records(prerequisite, dependent, term_owners, positions, meaning_cutoff, semantic=True, min_terms=1):` and its terms line to `"terms": term_vote(prerequisite, dependent, term_owners, min_terms)[1],`.

- [ ] **Step 4: Fix the one constructor that now gets two unknown keys**

`criteria._facts` builds `PairFacts(**uses, ...)`; the two new keys need fields. Add to `PairFacts` in `fusion.py`, after `earlier_uses_later_terms`:

```python
    later_uses_earlier_word: float = 0.0
    earlier_uses_later_word: float = 0.0
```

- [ ] **Step 5: Run the tests to see them pass**

Run: `python manage.py test learning_path.test_clues learning_path.test_criteria learning_path.test_fusion learning_path.test_course_criteria`
Expected: all OK (default behaviour unchanged).

- [ ] **Step 6: Commit**

```bash
git add backend/learning_path/services/clues.py backend/learning_path/services/fusion.py backend/learning_path/test_clues.py
git commit -m "Let the owned-terms clue require two shared words and keep the single-word shares

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: The v6.1 verdict

**Files:**
- Modify: `backend/learning_path/services/fusion.py` (`reference_verdict`, new constant)
- Test: `backend/learning_path/test_fusion.py` (append a class)

**Interfaces:**
- Consumes: Task 1's `PairFacts.later_uses_earlier_word` / `earlier_uses_later_word`.
- Produces: `fusion.CLEARED_IN_6_1 = ("figure", "no_shared_pdf")`; `reference_verdict(facts, cleaner_edges=False) -> Decision`; new contradiction name `"weak_terms"`.

- [ ] **Step 1: Write the failing tests** (append to `test_fusion.py`; the needed names — `ACCEPTED`, `PENDING`, `PARALLEL`, `DISAGREE`, `NONE_SHARED`, `Decision`, `PairFacts`, `reference_verdict` — are already imported)

```python
class CleanerEdgeVerdictTests(SimpleTestCase):
    """v6.1 spec section 3."""

    def test_a_figure_no_longer_blocks_a_link(self):
        facts = PairFacts(later_uses_earlier_terms=0.6, later_is_figure=True)

        self.assertEqual(reference_verdict(facts, cleaner_edges=True), Decision(ACCEPTED, 1, "pdf_order", ()))

    def test_different_pdfs_no_longer_block_a_link(self):
        facts = PairFacts(later_uses_earlier_terms=0.5, pdf_order=NONE_SHARED)

        self.assertEqual(reference_verdict(facts, cleaner_edges=True), Decision(ACCEPTED, 1, "merged_order", ()))

    def test_a_single_shared_word_is_only_a_suggestion(self):
        facts = PairFacts(later_uses_earlier_word=0.5)

        self.assertEqual(
            reference_verdict(facts, cleaner_edges=True),
            Decision(PENDING, 1, "pdf_order", ("weak_terms",)),
        )

    def test_a_single_word_across_disagreeing_pdfs_follows_the_merged_order(self):
        facts = PairFacts(earlier_uses_later_word=0.5, pdf_order=DISAGREE)

        self.assertEqual(
            reference_verdict(facts, cleaner_edges=True),
            Decision(PENDING, 1, "merged_order", ("weak_terms",)),
        )

    def test_siblings_still_get_no_link_even_with_a_shared_word(self):
        facts = PairFacts(later_uses_earlier_word=0.5, parallel=True)

        self.assertEqual(reference_verdict(facts, cleaner_edges=True).verdict, PARALLEL)

    def test_the_other_contradictions_still_hold(self):
        facts = PairFacts(later_uses_earlier_terms=0.5, pdf_order=DISAGREE)

        self.assertEqual(
            reference_verdict(facts, cleaner_edges=True),
            Decision(PENDING, 1, "merged_order", ("pdfs_disagree",)),
        )

    def test_v6_ignores_single_words(self):
        self.assertEqual(reference_verdict(PairFacts(later_uses_earlier_word=0.5)).verdict, PARALLEL)
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `python manage.py test learning_path.test_fusion`
Expected: ERROR/FAIL, `TypeError: reference_verdict() got an unexpected keyword argument 'cleaner_edges'`.

- [ ] **Step 3: Implement**

In `fusion.py`, after `MAX_AGREEMENT = 0.95` add:

```python
# v6.1 (spec 2026-10-02, C2 and C3): these no longer block a link.
CLEARED_IN_6_1 = ("figure", "no_shared_pdf")
```

Replace `reference_verdict` with:

```python
def reference_verdict(facts, cleaner_edges=False):
    """The v6 decision for one pair; direction +1 means earlier before later.

    ``cleaner_edges`` is v6.1: figures and different PDFs no longer block a link,
    and a pair linked only by single shared words is a suggestion (``weak_terms``).
    """
    if facts.parallel:
        return NO_LINK
    later_refers = facts.later_names_earlier > 0 or facts.later_uses_earlier_terms > 0
    earlier_refers = facts.earlier_names_later > 0 or facts.earlier_uses_later_terms > 0
    in_order = "pdf_order" if facts.pdf_order == SHARED else "merged_order"
    if not (later_refers or earlier_refers or facts.heading):
        if cleaner_edges and (facts.later_uses_earlier_word or facts.earlier_uses_later_word):
            return Decision(PENDING, 1, in_order, ("weak_terms",))
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
    ) if present and not (cleaner_edges and name in CLEARED_IN_6_1))
    if not contradictions:
        # v6 only gets here with a shared PDF, so its rows still read "pdf_order".
        return Decision(ACCEPTED, 1, in_order)
    direction, source = _suggested_direction(facts)
    return Decision(PENDING, direction, source, contradictions)
```

- [ ] **Step 4: Run the tests to see them pass**

Run: `python manage.py test learning_path.test_fusion learning_path.test_criteria`
Expected: OK (v6's existing verdict tests unchanged).

- [ ] **Step 5: Commit**

```bash
git add backend/learning_path/services/fusion.py backend/learning_path/test_fusion.py
git commit -m "Add the v6.1 verdict: figures and different files no longer block, single words only suggest

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: `decide_pairs` with `rule="cleaner-edges"`

**Files:**
- Modify: `backend/learning_path/services/criteria.py`
- Test: `backend/learning_path/test_criteria.py` (append a class)

**Interfaces:**
- Consumes: Task 1 (`MIN_SHARED_TERMS`, `min_terms` parameters), Task 2 (`reference_verdict(facts, cleaner_edges=...)`).
- Produces: `criteria.CLEANER_EDGES = "cleaner-edges"` in `RULES`; v6.1 rows have `evidence["rule"] == "reference-order"` and `evidence["version"] == "6.1"`.

- [ ] **Step 1: Write the failing tests** (append to `test_criteria.py`; add `CLEANER_EDGES` to the `from .services.criteria import ...` line)

```python
def decide_cleanly(concepts, without=()):
    return {
        (row["prerequisite"].id, row["dependent"].id): row
        for row in decide_pairs(concepts, calibration=CALIBRATION, embed=word_vectors,
                                rule=CLEANER_EDGES, without=without)
    }


class CleanerEdgeTests(SimpleTestCase):
    """v6.1 spec section 3, end to end."""

    def test_two_shared_words_still_link(self):
        row = decide_cleanly(flower())[(1, 2)]

        self.assertEqual(row["verdict"], ACCEPTED)
        self.assertEqual(row["evidence"]["version"], "6.1")
        self.assertEqual(row["evidence"]["records"]["terms"]["use"], 1.0)

    def test_a_single_shared_word_is_only_a_suggestion(self):
        """Pollination uses only "stigma" from Pistil."""
        row = decide_cleanly(flower())[(2, 3)]

        self.assertEqual(row["verdict"], PENDING)
        self.assertEqual(row["evidence"]["contradictions"], ["weak_terms"])
        self.assertEqual(row["evidence"]["records"]["terms"]["owned_back"], ["stigma"])

    def test_a_figure_no_longer_blocks_a_link(self):
        figure = concept(1, "Particles in a solid", "The picture shows solid particles packed tightly.", kind="image")
        solid = concept(2, "Solid", "A solid has particles packed tightly in rows. " * 4)

        row = decide_cleanly([figure, solid])[(1, 2)]

        self.assertEqual((row["verdict"], row["evidence"]["direction_from"]), (ACCEPTED, "pdf_order"))

    def test_different_files_no_longer_block_a_link(self):
        stamen = concept(1, "Stamen", member("The anther makes pollen grains. " * 8, material_id=10))
        pollination = concept(2, "Pollination", member("Pollen travels from an anther to a stigma.", material_id=11))
        pistil = concept(3, "Pistil", member("The stigma is sticky and holds the style. " * 8, material_id=12))

        row = decide_cleanly([stamen, pollination, pistil])[(1, 2)]

        self.assertEqual((row["verdict"], row["evidence"]["direction_from"]), (ACCEPTED, "merged_order"))

    def test_leaving_out_terms_leaves_out_single_words_too(self):
        self.assertNotIn((2, 3), decide_cleanly(flower(), without=("terms",)))

    def test_v6_is_still_the_default(self):
        row = decide(flower())[(2, 3)]

        self.assertIn("backward_only", row["evidence"]["contradictions"])
        self.assertNotIn("version", row["evidence"])
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `python manage.py test learning_path.test_criteria`
Expected: ERROR, `ImportError: cannot import name 'CLEANER_EDGES'`.

- [ ] **Step 3: Implement** (all in `criteria.py`)

1. Imports: add `MIN_SHARED_TERMS` to the `from .clues import (...)` list.
2. Constants: replace the rule block with

```python
THREE_VOTES = "three-votes"
REFERENCE_ORDER = "reference-order"
CLEANER_EDGES = "cleaner-edges"
RULES = (THREE_VOTES, REFERENCE_ORDER, CLEANER_EDGES)
# v6 until v6.1 passes the final check (v6.1 spec section 6, stop rule).
DEFAULT_RULE = REFERENCE_ORDER
```

and add `"CLEANER_EDGES"` to `__all__`.
3. Change `_TERM_FIELDS` to

```python
_TERM_FIELDS = ("later_uses_earlier_terms", "earlier_uses_later_terms",
                "later_uses_earlier_word", "earlier_uses_later_word")
```

4. `_facts`: change the signature to `def _facts(first, second, owners, positions, without, min_terms=1):` and its `uses = reference_uses(earlier, later, owners)` line to `uses = reference_uses(earlier, later, owners, min_terms)`.
5. `_votes`: change the signature to `def _votes(prerequisite, dependent, owners, positions, meaning_cutoff, semantic, without, min_terms=1):` and its terms line to `"terms": term_vote(prerequisite, dependent, owners, min_terms)[0],`.
6. `decide_pairs`: after `rule = rule or DEFAULT_RULE` add

```python
    cleaner = rule == CLEANER_EDGES
    min_terms = MIN_SHARED_TERMS if cleaner else 1
```

then change
- `facts, earlier, later = _facts(first, second, owners, positions, without)` → `facts, earlier, later = _facts(first, second, owners, positions, without, min_terms)`
- `decision = reference_verdict(facts)` → `decision = reference_verdict(facts, cleaner_edges=cleaner)`
- `votes = _votes(prerequisite, dependent, owners, positions, meaning_cutoff, semantic, without)` → `votes = _votes(prerequisite, dependent, owners, positions, meaning_cutoff, semantic, without, min_terms)`
- `"records": clue_records(prerequisite, dependent, owners, positions, meaning_cutoff, semantic),` → `"records": clue_records(prerequisite, dependent, owners, positions, meaning_cutoff, semantic, min_terms=min_terms),`

and right after the `decisions.append({...})` of the v6 path add

```python
            if cleaner:
                decisions[-1]["evidence"]["version"] = "6.1"
```

7. Update the docstring of `decide_pairs`: "``rule`` is ``REFERENCE_ORDER`` (v6), ``CLEANER_EDGES`` (v6.1) or ``THREE_VOTES`` (v7, not adopted); default ``DEFAULT_RULE``."

- [ ] **Step 4: Run the tests to see them pass**

Run: `python manage.py test learning_path.test_criteria learning_path.test_fusion learning_path.test_clues learning_path.test_direction_votes`
Expected: OK.

- [ ] **Step 5: Commit**

```bash
git add backend/learning_path/services/criteria.py backend/learning_path/test_criteria.py
git commit -m "Derive links with the v6.1 cleaner-edges rule when asked

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: The review-screen sentence for a single-word suggestion

**Files:**
- Modify: `backend/learning_path/services/reasons.py` (`_reference_order_reason`)
- Test: `backend/learning_path/test_reasons.py` (append a class)

- [ ] **Step 1: Write the failing tests** (append)

```python
class SingleWordReasonTests(SimpleTestCase):
    def evidence(self, owned=(), owned_back=()):
        return {"rule": "reference-order", "version": "6.1", "direction_from": "pdf_order",
                "contradictions": ["weak_terms"], "votes": {"name": 0, "terms": 0, "heading": 0},
                "records": {"name": {"use": 0.0, "use_back": 0.0},
                            "terms": {"owned": list(owned), "owned_back": list(owned_back),
                                      "use": 0.0, "use_back": 0.0}}}

    def test_it_names_the_word(self):
        self.assertEqual(
            link_reason(self.evidence(owned=["table"]), "Comparing the Three States", "Everyday Example"),
            "Comparing the Three States comes first in the lesson. "
            "Only one shared word links them (table); please confirm.",
        )

    def test_it_names_the_word_when_the_prerequisite_uses_it(self):
        self.assertEqual(
            link_reason(self.evidence(owned_back=["stigma"]), "Pollination", "Pistil"),
            "Pollination comes first in the lesson. Only one shared word links them (stigma); please confirm.",
        )
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `python manage.py test learning_path.test_reasons`
Expected: FAIL (the sentence is missing).

- [ ] **Step 3: Implement**

In `_reference_order_reason`, just before the line `parts.extend(_CONTRADICTION_SENTENCES[key] ...)`, add:

```python
    if "weak_terms" in contradictions:
        words = (terms.get("owned") or []) + (terms.get("owned_back") or [])
        listed = f" ({', '.join(words[:3])})" if words else ""
        parts.append(f"Only one shared word links them{listed}; please confirm.")
```

- [ ] **Step 4: Run the tests to see them pass**

Run: `python manage.py test learning_path.test_reasons`
Expected: OK.

- [ ] **Step 5: Commit**

```bash
git add backend/learning_path/services/reasons.py backend/learning_path/test_reasons.py
git commit -m "Tell the teacher when a suggested link rests on one shared word

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Lock the new topics in the evaluation command

**Files:**
- Modify: `backend/learning_path/management/commands/evaluate_gold_paths.py` (`FINAL_CHECK_TOPICS`, docstring)
- Test: `backend/learning_path/test_evaluate_command.py` (append)

- [ ] **Step 1: Write the failing test** (append inside `FinalCheckGuardTests`)

```python
    def test_the_new_topics_are_locked_too(self):
        for topic in ("351", "353", "365"):
            with self.assertRaisesMessage(CommandError, "--final-check"):
                call_command("evaluate_gold_paths", topics=[topic])
```

- [ ] **Step 2: Run it to see it fail**

Run: `python manage.py test learning_path.test_evaluate_command`
Expected: FAIL, `CommandError not raised`. **Watch out:** a failing run executes the command on 351 with v6 and prints the report to the test output. Run it with `> NUL 2>&1`-style redirection to a file in the scratchpad and read only the last lines (`Ran`, `FAILED`), never the JSON.

Run instead: `python manage.py test learning_path.test_evaluate_command > "$SCRATCH/t5-red.log" 2>&1; grep -E "^Ran|^OK|^FAILED|^FAIL:" "$SCRATCH/t5-red.log"` (with `$SCRATCH` the session scratchpad), then delete the log.

- [ ] **Step 3: Implement**

```python
FINAL_CHECK_TOPICS = {"341", "343", "347", "348", "351", "353", "365"}
```

and in the docstring: `--final-check        required to score 341-348 (v7 lock) or 351/353/365 (v6.1 final check)`.

- [ ] **Step 4: Run the tests to see them pass**

Run: `python manage.py test learning_path.test_evaluate_command`
Expected: OK.

- [ ] **Step 5: Commit**

```bash
git add backend/learning_path/management/commands/evaluate_gold_paths.py backend/learning_path/test_evaluate_command.py
git commit -m "Lock topics 351, 353 and 365 until the v6.1 final check

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: v7 wrap-up, design-set measurement, freeze

**Files:**
- Commit: `docs/learning-path-v7-evaluation/design-v6.json`, `design-v7.json` (already on disk)
- Create: `docs/learning-path-v6-1-evaluation/` (raw outputs)
- Modify: `backend/learning_path/CRITERIA.md` (v7 note)

- [ ] **Step 1: Run the full suite** — `python manage.py test learning_path --exclude-tag final_check` → OK.

- [ ] **Step 2: Measure the design set** (from `backend/`)

```bash
mkdir -p ../docs/learning-path-v6-1-evaluation
python manage.py evaluate_gold_paths --rule reference-order --moves > ../docs/learning-path-v6-1-evaluation/design-v6.json
python manage.py evaluate_gold_paths --rule cleaner-edges --moves > ../docs/learning-path-v6-1-evaluation/design-v6-1.json
python manage.py evaluate_gold_paths --baseline order > ../docs/learning-path-v6-1-evaluation/design-order-only.json
```

Compare with the spec's section 5 prototype table (340: 13/23 · 0.85 · 0 wrong-way; 357: 11/20 · 1.00 · 0; moves 7 repaired / 0 wrong). A difference is a finding to explain before freezing (a ruling in the ledger), not something to tune away.

- [ ] **Step 3: Decide `MIN_SHARED_TERMS`** — keep 2 unless a design-set result is plainly caused by it; record the decision.

- [ ] **Step 4: v7 note in `CRITERIA.md`** — add after the "Course level" section:

```markdown
## v7 (tried 2026-10-01, not adopted)

Three equal direction votes (hierarchy, order, references) on a block x concept matrix
(`services/direction_votes.py`, `rule="three-votes"`, spreadsheet export
`export_direction_sheet`). On the design set it repaired fewer moved links than v6 (3 vs 7):
the reference and subsumption votes both read overviews backwards and outvoted correct orders
and headings. Spec `docs/superpowers/specs/2026-10-01-learning-path-v7-direction-votes-design.md`;
outputs `docs/learning-path-v7-evaluation/`. Its final check (moves 5-9 on 341-348) is unspent.
```

- [ ] **Step 5: Freeze**

```bash
git add ../docs/learning-path-v7-evaluation ../docs/learning-path-v6-1-evaluation backend/learning_path/CRITERIA.md backend/learning_path/services/clues.py
git commit -m "Record v7 as not adopted and measure v6.1 on the design set before the final check

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git rev-parse --short HEAD
```

The printed hash is the frozen rule version. `clues.py`, `fusion.py` and `criteria.py` must not change before Task 7's run.

---

### Task 7: Final check (once), stop rule, switch, write-up

**Files:**
- Create: `docs/learning-path-v6-1-evaluation/final-*.json`, `docs/learning-path-v6-1-evaluation-2026-10-02.md`
- Modify: `criteria.py` (`DEFAULT_RULE`, only if v6.1 passes), `test_criteria.py`, `test_gold_paths.py`, `CRITERIA.md`

- [ ] **Step 1: Score the final check once** (from `backend/`)

```bash
python manage.py evaluate_gold_paths --topics 351 353 365 --final-check --rule reference-order > ../docs/learning-path-v6-1-evaluation/final-v6.json
python manage.py evaluate_gold_paths --topics 351 353 365 --final-check --rule cleaner-edges > ../docs/learning-path-v6-1-evaluation/final-v6-1.json
python manage.py evaluate_gold_paths --topics 351 353 365 --final-check --baseline order > ../docs/learning-path-v6-1-evaluation/final-order-only.json
python manage.py evaluate_gold_paths --topics 341 343 347 348 --final-check --rule cleaner-edges > ../docs/learning-path-v6-1-evaluation/seen-v6-1.json
```

(`seen-v6-1.json` is the secondary, already-seen set; v6's numbers for it are `docs/learning-path-v6-evaluation/eval-v6-test.json`.) Do not rerun with other settings after reading these.

- [ ] **Step 2: Apply the stop rule** (spec section 6), summed over 351/353/365:
1. `forbidden_accepted` count of v6.1 ≤ v6's;
2. accepted precision (Σ accepted in the key's implied set ÷ Σ accepted) of v6.1 ≥ v6's + 0.05;
3. `covered_count` of v6.1 ≥ v6's − 3.

- [ ] **Step 3a (passes): switch the default**

`criteria.py`: `DEFAULT_RULE = CLEANER_EDGES`, comment `# v6.1 since the final check of 2026-10-02 (docs/learning-path-v6-1-evaluation-2026-10-02.md).`
`test_criteria.py`: make `decide()` pass `rule="reference-order"` so v6's tests keep testing v6; rename `test_v6_is_still_the_default` to `test_v6_1_is_the_default` asserting every row of `decide_pairs(flower(), calibration=CALIBRATION, embed=word_vectors)` carries `"version": "6.1"`. (v7's `test_the_default_rule_is_still_v6_until_the_final_check` keeps passing unchanged: v6.1 rows still have `rule == "reference-order"`.)
Measure the retired topics the same way for their floors: `python manage.py evaluate_gold_paths --topics 62 79 152 --rule cleaner-edges > ../docs/learning-path-v6-1-evaluation/retired-v6-1.json`.
`test_gold_paths.py`: replace every floor (`REACHABLE_FLOOR`, `COVERED_FLOOR`, `TAU_FLOOR`, `KNOWN_FORBIDDEN`) with the v6.1 values from Task 6 (340, 357), `retired-v6-1.json` (62, 79, 152) and Step 1 (351/353/365, 341–348); add three test methods for 351, 353, 365; remove the `final_check` tags; docstring "v6.1".
Run: `python manage.py test learning_path` → OK.

- [ ] **Step 3b (fails): keep v6** — leave `DEFAULT_RULE`; add the three new topics to `test_gold_paths.py` with v6's measured floors; remove the `final_check` tags (341–348 already scored with v6). Run: `python manage.py test learning_path` → OK.

- [ ] **Step 4: Report** — `docs/learning-path-v6-1-evaluation-2026-10-02.md`, in the shape of `docs/learning-path-v6-evaluation-2026-09-30.md`: frozen commit; sets and how the keys were made (blind agent, shuffled list, user-approved; designer saw concept titles only); design table; final-check table (v6, v6.1, order-only, per topic and summed); stop-rule outcome with the three numbers; secondary set; where v6.1 fails; limits.

- [ ] **Step 5: `CRITERIA.md`** — if v6.1 passed: retitle "(v6.1)", amend "The verdict" (figure and `no_shared_pdf` removed from contradictions; `weak_terms` row: text only single shared words → pending), "The evidence" (terms: two owned words per chunk), and add the evaluation link. If it failed: a short "v6.1 (tried 2026-10-02, not adopted)" section.

- [ ] **Step 6: Commit**

```bash
git add ../docs/learning-path-v6-1-evaluation ../docs/learning-path-v6-1-evaluation-2026-10-02.md backend/learning_path
git commit -m "Score v6.1 once on the new topics and record whether it replaces v6

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
