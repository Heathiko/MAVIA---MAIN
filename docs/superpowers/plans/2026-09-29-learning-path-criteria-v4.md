# Learning-Path Criteria v4 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the three-vote prerequisite criteria with typed evidence:
- **R1** definition dependency;
- **R2** section containment;
- **R3** passage reference distance.

Each link carries one named evidence type, and document order is used only to break ties in the
ordering.

**Architecture:**
- `learning_path/services/criteria.py` keeps its public entry point, `decide_pairs(concepts,
  runtime_instance=None)`, but its internals are replaced.
- Each decision now carries an `evidence` dict with a `rule` key instead of the old `votes` dict.
- Two new pure helpers compute R1 and R3.
- R2 is the existing `contained_in`.
- Publishing, ordering (`order_with_links`) and everything in `adaptive/` are untouched, apart from
  a one-word key rename in `publishing.py`.

**Tech Stack:** Python 3.12, Django (tests via `manage.py test`), SQLite locally. No models are
called: the new criteria never touch the sentence encoder.

**Spec:** `docs/superpowers/specs/2026-09-29-learning-path-criteria-v4-design.md`. Read it first.
It carries the research basis (Section 8) and the pre-implementation measurement (Section 10.1)
this plan is built on.

## Global Constraints

- Deterministic: no generative model, no sentence encoder, no randomness. The same concepts always
  give the same decisions.
- Document order never creates, removes or changes a link. It is used only as the tie-breaker in
  `order_with_links`, which stays unchanged.
- Do not modify anything under `backend/adaptive/`, and do not change remediation behaviour.
- Do not modify the `ConceptPrerequisite` model or add migrations. `evidence` is an existing
  JSONField.
- Teacher decisions (`approved`/`rejected`) are never overwritten. `refresh_prerequisites` already
  guarantees this; keep it.
- Status values stay `"accepted"` and `"pending"` (`criteria.ACCEPTED`, `criteria.PENDING`).
- `PRD_THRESHOLD` must lie in Liang et al.'s range, `0.02 ≤ θ ≤ 0.1`, and is chosen on gold topics
  62 and 79 only.
- The topic 308 answer key is drafted from the PDFs and committed **before** v4 is run on topic 308.
- Run commands from `C:\MAVIA\backend` with `../.venv/Scripts/python.exe manage.py ...`. Tests:
  `../.venv/Scripts/python.exe manage.py test learning_path`. The baseline is 159 tests, all
  passing.
- Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

These five conditions are implied by the spec but easy to break without noticing. Each is pinned
by a named test in the task that owns the code.

1. **Moving a concept earlier or later in the document must not change any decision.** Task 4:
   `test_document_order_never_changes_a_decision`.
2. **A prerequisite placed later in the PDF than its dependent must still be accepted, and ordered
   first.** Task 4: `test_a_link_can_point_against_document_order`.
3. **A parent's overview that names its children must not reverse the parent → child link.** R2
   beats R3. Task 4: `test_reference_never_overrides_containment`.
4. **Plural and head-word mentions** ("solids", "the seed" for "Seed formation") **must count, but a
   mention only inside a contrast** ("unlike a solid") **must not.** Task 1:
   `test_plural_and_head_word_mentions_count` and `test_a_contrastive_mention_is_not_plain`. Task 2:
   `test_a_contrastive_passage_does_not_count`.
5. **Evidence must be JSON-serialisable**, because it is stored in a JSONField and a non-serialisable
   value only fails at publish time. Task 4: `test_evidence_is_json_serialisable`.

---

## File Structure

| File | Responsibility | Task |
|---|---|---|
| `backend/learning_path/services/text_signals.py` | + `first_sentence(text)` | 1 |
| `backend/learning_path/services/criteria.py` | + `says`, `says_plainly`, `defining_sentences`, `definition_dependency` (T1); + `passage_reference` (T2); rewrite of `decide_pairs`, removal of v3 code (T4); `PRD_THRESHOLD` value (T6) | 1, 2, 4, 6 |
| `backend/learning_path/test_evidence.py` | **New.** Unit tests for R1 and R3 helpers | 1, 2 |
| `backend/learning_path/services/gold.py` | Explicit `forbidden`, `unreachable`, `reachable_count`, `accepted_precision`, `accepted_by_rule` | 3 |
| `backend/learning_path/management/commands/evaluate_gold_paths.py` | Grid over `PRD_THRESHOLD`, `--topics` | 3 |
| `backend/learning_path/management/commands/export_live_concepts.py` | Copy the optional `forbidden` list | 5 |
| `backend/learning_path/test_criteria.py` | **Rewritten.** Decision table, vetoes, kept helpers | 4 |
| `backend/learning_path/services/publishing.py` | `decision["votes"]` → `decision["evidence"]` | 4 |
| `backend/learning_path/test_publishing.py`, `backend/learning_path/tests.py` | Fixture key `votes` → `evidence` | 4 |
| `backend/learning_path/test_gold_paths.py` | New acceptance assertions; no encoder skip; topic 308 test | 4, 6 |
| `backend/learning_path/fixtures/gold_map_308.json`, `gold_topic_308.json` | **New.** Answer key for hand-grouped topic 308 | 5 |
| `backend/learning_path/CRITERIA.md`, `docs/AGENT_LOG.md` | v4 documentation | 7 |

**Task order and gates:**
- Tasks 1–4 are code and can run straight through.
- **Task 5 is human-gated:** the user hand-groups topic 308, then corrects the drafted answer key.
  It must be finished before Task 6.
- Nothing in Tasks 1–4 runs the criteria on topic 308. Keep it that way, so the answer key stays
  independent of the new criteria.

---

### Task 1: R1 — definition dependency helpers

**Files:**
- Modify: `backend/learning_path/services/text_signals.py` (add after `definition_subject`, end of file)
- Modify: `backend/learning_path/services/criteria.py` (add after `contained_in`, around line 136)
- Create: `backend/learning_path/test_evidence.py`

**Interfaces:**
- Consumes: `text_signals.normalize`, `mentions`, `singular`, `definition_subject`, `_SENTENCE_SPLIT`.
  `criteria.only_contrastive_mentions(name, text)`, `criteria.concept_names(concepts)`,
  `criteria.head_words(names)`.
- Produces:
  - `text_signals.first_sentence(text: str) -> str`
  - `criteria.says(text: str, concept_id: int, names: dict[int, str|None], heads: dict[int, str]) -> bool`
  - `criteria.says_plainly(text: str, concept_id: int, names, heads) -> bool`
  - `criteria.defining_sentences(concept, name: str|None) -> list[str]`: raw sentences, no
    trailing punctuation.
  - `criteria.definition_dependency(a, b, names, heads) -> str | None`: B's defining sentence
    naming A when R1 holds for A→B, else `None`.

- [ ] **Step 1: Write the failing tests**

Create `backend/learning_path/test_evidence.py`:

```python
"""R1 and R3 of the v4 criteria, tested on their own.

The decision table that combines them lives in ``test_criteria.py``. These tests
pin the two measurements, so a failure here says which piece of evidence
changed rather than only that a verdict moved. See
``docs/superpowers/specs/2026-09-29-learning-path-criteria-v4-design.md``.
"""

from django.test import SimpleTestCase

from .services.criteria import (
    concept_names,
    defining_sentences,
    definition_dependency,
    head_words,
    says,
    says_plainly,
)
from .services.text_signals import first_sentence


class Headed:
    """A concept stub whose members carry their own title, content and heading."""

    def __init__(self, id, order, title, contents, sections=None):
        if isinstance(contents, str):
            contents = (contents,)
        sections = sections or ("",) * len(contents)
        self.id = id
        self.order = order
        self.title = title
        self.content = contents[0]
        self.member_text = "\n".join(contents)
        self.section_title = sections[0]
        self.kind = "text"
        self.members = tuple(
            type("Member", (), {"title": title, "content": content, "section_title": section})()
            for content, section in zip(contents, sections)
        )


def names_and_heads(concepts):
    names = concept_names(concepts)
    return names, head_words(names)


class FirstSentenceTests(SimpleTestCase):
    def test_the_text_up_to_the_first_break(self):
        self.assertEqual(
            first_sentence("Melting is when a solid melts. Then it flows."),
            "Melting is when a solid melts",
        )

    def test_empty_text_has_no_sentence(self):
        self.assertEqual(first_sentence(""), "")
        self.assertEqual(first_sentence(None), "")


class SaysTests(SimpleTestCase):
    def test_plural_and_head_word_mentions_count(self):
        solid = Headed(1, 0, "Solid", "A solid keeps its shape.")
        seed = Headed(2, 1, "Seed formation", "The ovule becomes a seed.")
        names, heads = names_and_heads([solid, seed])

        self.assertTrue(says("Solids keep their shape.", 1, names, heads))
        self.assertTrue(says("The fruit protects the seed.", 2, names, heads))
        self.assertFalse(says("Liquids flow.", 1, names, heads))

    def test_an_unnamed_concept_is_never_said(self):
        self.assertFalse(says("anything at all", 1, {1: None}, {}))

    def test_a_contrastive_mention_is_not_plain(self):
        solid = Headed(1, 0, "Solid", "A solid keeps its shape.")
        names, heads = names_and_heads([solid])
        text = "A gas spreads out, unlike a solid."

        self.assertTrue(says(text, 1, names, heads))
        self.assertFalse(says_plainly(text, 1, names, heads))


class DefiningSentenceTests(SimpleTestCase):
    def test_a_sentence_that_defines_the_concept(self):
        melting = Headed(1, 0, "Melting", "Melting is when a solid turns into a liquid. It needs heat.")

        self.assertEqual(
            defining_sentences(melting, "melting"),
            ["Melting is when a solid turns into a liquid"],
        )

    def test_a_plural_subject_still_defines(self):
        solid = Headed(1, 0, "Solid", "Solids are hard and keep their shape.")

        self.assertEqual(defining_sentences(solid, "solid"), ["Solids are hard and keep their shape"])

    def test_a_description_is_not_a_definition(self):
        solid = Headed(1, 0, "Solid", "Solids keep their shape.")

        self.assertEqual(defining_sentences(solid, "solid"), [])

    def test_a_members_title_alone_does_not_make_a_definition(self):
        """Amended 2026-09-29: counting the first sentence of any member
        titled "Matter" made "It comes in three states: solid..." Matter's
        definition, which produced Solid -> Matter on gold topic 62."""
        matter = Headed(1, 0, "Matter", "It comes in three states: solid, liquid and gas.")

        self.assertEqual(defining_sentences(matter, "matter"), [])

    def test_every_members_definition_counts(self):
        melting = Headed(1, 0, "Melting", (
            "Melting is when a solid turns into a liquid.",
            "Melting means heat breaks the solid apart.",
        ))

        self.assertEqual(len(defining_sentences(melting, "melting")), 2)

    def test_no_name_no_definition(self):
        self.assertEqual(defining_sentences(Headed(1, 0, "x", "X is y."), None), [])


class DefinitionDependencyTests(SimpleTestCase):
    def setUp(self):
        self.solid = Headed(1, 0, "Solid", "A solid keeps its shape.")
        self.liquid = Headed(2, 1, "Liquid", "A liquid flows.")
        self.melting = Headed(3, 2, "Melting", "Melting is when a solid turns into a liquid.")
        self.concepts = [self.solid, self.liquid, self.melting]
        self.names, self.heads = names_and_heads(self.concepts)

    def test_a_concept_used_in_anothers_definition_comes_first(self):
        self.assertEqual(
            definition_dependency(self.solid, self.melting, self.names, self.heads),
            "Melting is when a solid turns into a liquid",
        )

    def test_the_reverse_direction_does_not_hold(self):
        self.assertIsNone(definition_dependency(self.melting, self.solid, self.names, self.heads))

    def test_definitions_naming_each_other_decide_nothing(self):
        heat = Headed(1, 0, "Heat", "Heat is energy that causes melting.")
        melting = Headed(2, 1, "Melting", "Melting is what heat does to ice.")
        names, heads = names_and_heads([heat, melting])

        self.assertIsNone(definition_dependency(heat, melting, names, heads))
        self.assertIsNone(definition_dependency(melting, heat, names, heads))

    def test_a_contrastive_mention_in_a_definition_is_not_a_dependency(self):
        gas = Headed(2, 1, "Gas", "A gas is a state that spreads out, unlike a solid.")
        names, heads = names_and_heads([self.solid, gas])

        self.assertIsNone(definition_dependency(self.solid, gas, names, heads))

    def test_a_head_word_in_a_definition_names_the_concept(self):
        seed = Headed(1, 0, "Seed formation", "The ovule becomes a seed.")
        fruit = Headed(2, 1, "Fruit formation", "Fruit formation is when the ovary grows around the seed.")
        names, heads = names_and_heads([seed, fruit])

        self.assertEqual(
            definition_dependency(seed, fruit, names, heads),
            "Fruit formation is when the ovary grows around the seed",
        )

    def test_an_unnamed_concept_takes_no_part(self):
        figure = Headed(4, 3, "The image shows three boxes of dots representing the states", "Dots.")
        names, heads = names_and_heads([self.solid, figure])

        self.assertIsNone(names[4])
        self.assertIsNone(definition_dependency(figure, self.solid, names, heads))
        self.assertIsNone(definition_dependency(self.solid, figure, names, heads))
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `../.venv/Scripts/python.exe manage.py test learning_path.test_evidence -v 2`
Expected: ERROR, `ImportError: cannot import name 'defining_sentences'` (or `first_sentence`).

- [ ] **Step 3: Implement**

Append to `backend/learning_path/services/text_signals.py`:

```python
def first_sentence(text):
    """The text up to its first sentence break, stripped.

    Uses the same split as ``definition_subject``, so the sentence a definition
    is read from is the sentence reported as the definition.
    """
    return _SENTENCE_SPLIT.split(text or "", 1)[0].strip()
```

In `backend/learning_path/services/criteria.py`:
- Change the text_signals import (line 19) to:

```python
from .text_signals import (
    MIN_TERM_LENGTH,
    STOP_WORDS,
    definition_subject,
    first_sentence,
    mentions,
    normalize,
    singular,
)
```

- Add these functions directly after `contained_in` (after line 135):

```python
def says(text, concept_id, names, heads):
    """True when ``text`` names the concept: its full name, or its head word.

    A multi-word name counts through its head word only when that word is
    unambiguous (see ``head_words``): lessons say "the seed", not "seed
    formation".
    """
    name = names.get(concept_id)
    if not name:
        return False
    normalized = normalize(text)
    if mentions(normalized, name):
        return True
    return concept_id in heads and mentions(normalized, heads[concept_id])


def says_plainly(text, concept_id, names, heads):
    """``says``, in at least one clause that is not a contrast.

    "A gas spreads out, unlike a solid" names solid only to say what a gas is
    not. The contrast check reads the full name only, so a head-word mention is
    always plain -- the known limitation recorded on ``_CONTRAST``.
    """
    if not says(text, concept_id, names, heads):
        return False
    return not only_contrastive_mentions(names[concept_id], text)


def _canonical(name):
    """A name compared word by word in singular form: "solids" matches "solid"."""
    return " ".join(singular(word) for word in (name or "").split())


def defining_sentences(concept, name):
    """The sentences that define ``concept``: R1's evidence.

    Wang et al. (2016) take a concept's first sentence as its definition. Here
    that is the first sentence of each member, counted only when it actually
    opens by defining the concept ("Melting is...", "Solids are..."). A member
    merely *titled* with the name is not enough: "Matter" over "It comes in
    three states: solid, liquid and gas" would make Solid a prerequisite of
    Matter (measured on gold topic 62, 2026-09-29).
    """
    if not name:
        return []
    target = _canonical(name)
    found = []
    for member in getattr(concept, "members", None) or (concept,):
        content = getattr(member, "content", "") or ""
        if _canonical(definition_subject(content)) == target:
            found.append(first_sentence(content))
    return found


def definition_dependency(a, b, names, heads):
    """R1: B's defining sentence that names A, when A must come first; else None.

    Wang et al. 2016, *Supportive relationship in concept definition*: "A is
    likely to be B's prerequisite if A is used in B's definition"; Talukdar &
    Cohen 2012 use the same first-sentence signal. Two definitions naming each
    other decide nothing, and a mention only inside a contrast is not a use.
    """
    if not names.get(a.id) or not names.get(b.id):
        return None
    if any(says(sentence, b.id, names, heads) for sentence in defining_sentences(a, names[a.id])):
        return None
    for sentence in defining_sentences(b, names[b.id]):
        if says_plainly(sentence, a.id, names, heads):
            return sentence
    return None
```

`only_contrastive_mentions` is defined further down the module. Python resolves it when
`says_plainly` is called, so the order within the module does not matter.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `../.venv/Scripts/python.exe manage.py test learning_path.test_evidence -v 2`
Expected: all tests in `test_evidence` PASS.

Run: `../.venv/Scripts/python.exe manage.py test learning_path`
Expected: 159 + new tests, all OK. The v3 code is untouched so far.

- [ ] **Step 5: Commit**

```bash
git add backend/learning_path/services/text_signals.py backend/learning_path/services/criteria.py backend/learning_path/test_evidence.py
git commit -m "Add R1 definition-dependency helpers for learning-path criteria v4

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: R3 — passage reference distance

**Files:**
- Modify: `backend/learning_path/services/criteria.py` (add after `definition_dependency`)
- Modify: `backend/learning_path/test_evidence.py` (append a test class)

**Interfaces:**
- Consumes: `criteria.says_plainly` (Task 1), `concept_names`, `head_words`.
- Produces: `criteria.passage_reference(concepts, names, heads) -> dict[tuple[int, int], dict]`.
  - Keys are ordered pairs `(a.id, b.id)`, only for pairs where both concepts have a name.
  - Each value is `{"prw_forward": float, "prw_backward": float, "prd": float}`, each rounded to
    6 places:
    - `prw_forward` = share of B's passages naming A;
    - `prw_backward` = share of A's passages naming B;
    - `prd = prw_forward − prw_backward`.

- [ ] **Step 1: Write the failing tests**

Add `passage_reference` to the import list at the top of `backend/learning_path/test_evidence.py`,
then append:

```python
class PassageReferenceTests(SimpleTestCase):
    def test_passages_naming_another_concept_point_to_it(self):
        solid = Headed(1, 0, "Solid", "It keeps its shape.")
        comparing = Headed(2, 1, "Comparing", "The table puts the solid beside the gas.")
        names, heads = names_and_heads([solid, comparing])

        references = passage_reference([solid, comparing], names, heads)

        self.assertEqual(references[(1, 2)], {"prw_forward": 1.0, "prw_backward": 0.0, "prd": 1.0})
        self.assertEqual(references[(2, 1)]["prd"], -1.0)

    def test_the_share_is_over_the_dependents_passages(self):
        solid = Headed(1, 0, "Solid", "It keeps its shape.")
        changing = Headed(2, 1, "Changing", ("A solid can melt.", "Heat is added."))
        names, heads = names_and_heads([solid, changing])

        self.assertEqual(passage_reference([solid, changing], names, heads)[(1, 2)]["prw_forward"], 0.5)

    def test_a_contrastive_passage_does_not_count(self):
        solid = Headed(1, 0, "Solid", "It keeps its shape.")
        gas = Headed(2, 1, "Gas", "A gas spreads out, unlike a solid.")
        names, heads = names_and_heads([solid, gas])

        self.assertEqual(passage_reference([solid, gas], names, heads)[(1, 2)]["prd"], 0.0)

    def test_an_unnamed_concept_has_no_reference(self):
        figure = Headed(1, 0, "The image shows three boxes of dots representing the states", "A solid.")
        solid = Headed(2, 1, "Solid", "It keeps its shape.")
        names, heads = names_and_heads([figure, solid])

        references = passage_reference([figure, solid], names, heads)

        self.assertNotIn((1, 2), references)
        self.assertNotIn((2, 1), references)

    def test_a_parents_overview_points_the_reference_backwards(self):
        """The known weakness R2 has to overrule (spec Section 11): Matter's
        overview names its children, so the passage score reads Solid -> Matter.
        Measured on gold topic 62 at -1.0 for Matter -> Solid."""
        matter = Headed(1, 0, "Matter", "Matter can be a solid, a liquid or a gas.")
        solid = Headed(2, 1, "Solid", "It keeps its shape.", ("Matter",))
        names, heads = names_and_heads([matter, solid])

        self.assertEqual(passage_reference([matter, solid], names, heads)[(2, 1)]["prd"], 1.0)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `../.venv/Scripts/python.exe manage.py test learning_path.test_evidence -v 2`
Expected: ERROR, `ImportError: cannot import name 'passage_reference'`.

- [ ] **Step 3: Implement**

Add after `definition_dependency` in `backend/learning_path/services/criteria.py`:

```python
def passage_reference(concepts, names, heads):
    """R3: ``{(a id, b id): {prw_forward, prw_backward, prd}}`` for named pairs.

    Pan et al. 2017, Feature 2 (video reference distance), a generalisation of
    RefD (Liang et al. 2015) to course material without Wikipedia links. Pan's
    unit is a video; here it is a learning object, and a concept's units are
    its grouped members -- grouping already decided which passages teach it.

    ``prw_forward`` is the share of b's passages that name a; ``prw_backward``
    the share of a's passages that name b; ``prd`` their difference. A positive
    ``prd`` means b's passages lean on a, so a comes first. Position is never
    read, and no concept owns any word.
    """
    passages = {
        concept.id: [
            getattr(member, "content", "") or ""
            for member in (getattr(concept, "members", None) or (concept,))
        ]
        for concept in concepts
    }

    def share(holder_id, target_id):
        texts = passages[holder_id]
        if not texts:
            return 0.0
        return sum(1 for text in texts if says_plainly(text, target_id, names, heads)) / len(texts)

    named = [concept for concept in concepts if names.get(concept.id)]
    references = {}
    for a in named:
        for b in named:
            if a.id == b.id:
                continue
            forward, backward = share(b.id, a.id), share(a.id, b.id)
            references[(a.id, b.id)] = {
                "prw_forward": round(forward, 6),
                "prw_backward": round(backward, 6),
                "prd": round(forward - backward, 6),
            }
    return references
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `../.venv/Scripts/python.exe manage.py test learning_path.test_evidence -v 2`
Expected: all PASS.

Run: `../.venv/Scripts/python.exe manage.py test learning_path`
Expected: all OK.

- [ ] **Step 5: Commit**

```bash
git add backend/learning_path/services/criteria.py backend/learning_path/test_evidence.py
git commit -m "Add R3 passage reference distance for learning-path criteria v4

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Gold report and evaluation command for v4

**Files:**
- Modify: `backend/learning_path/services/gold.py:71-121` (`gold_report`)
- Modify: `backend/learning_path/management/commands/evaluate_gold_paths.py` (whole file)
- Test: `backend/learning_path/test_gold_report.py` (**new**)

**Interfaces:**
- Consumes: decision dicts with keys `prerequisite`, `dependent`, `verdict` and optionally
  `evidence` (`{"rule": str, ...}`). v3 decisions have no `evidence`; `gold_report` must accept
  both.
- Produces: `gold_report(...)` returns every key it returns today, plus:
  - `unreachable: list[list[str]]`: required edges neither accepted nor pending;
  - `reachable_count: int`: `len(required) - len(unreachable)`;
  - `accepted_precision: float | None`: see below;
  - `accepted_by_rule: dict[str, int]`: counts of `evidence["rule"]` over all accepted
    decisions (`"none"` when a decision has no evidence).
- `accepted_precision` = share of scoreable accepted edges that are in the **transitive closure**
  of the required edges; `None` when nothing scoreable is accepted. Gold maps list only direct
  edges, so "Matter → Comparing" (implied by Matter → Solid → Comparing) counts as correct.
- Map files may now carry an optional `"forbidden": [[before, after], ...]` list, which is added to
  the derived forbidden set.

- [ ] **Step 1: Write the failing tests**

Create `backend/learning_path/test_gold_report.py`:

```python
"""The gold report's v4 measures: reachability, closure precision, rules."""

from types import SimpleNamespace

from django.test import SimpleTestCase

from .services.gold import gold_report


def concept(id, key, order):
    return SimpleNamespace(id=id, key=key, order=order, title=key, kind="text", members=())


def decision(before, after, verdict, rule=None):
    row = {"prerequisite": before, "dependent": after, "verdict": verdict}
    if rule:
        row["evidence"] = {"rule": rule}
    return row


class GoldReportTests(SimpleTestCase):
    def setUp(self):
        self.matter, self.solid, self.comparing, self.figure = (
            concept(1, "matter", 0), concept(2, "solid", 1),
            concept(3, "comparing", 2), concept(4, "figure", 3),
        )
        self.concepts = [self.matter, self.solid, self.comparing, self.figure]
        self.data = {
            "topic_id": 999,
            "required": [["matter", "solid"], ["solid", "comparing"]],
            "parallel": [],
            "structural": [],
            "forbidden": [["figure", "matter"]],
            "expected_order": ["matter", "solid", "comparing", "figure"],
        }

    def test_pending_required_edges_are_reachable(self):
        report = gold_report(self.data, self.concepts, [
            decision(self.matter, self.solid, "accepted", "containment"),
            decision(self.solid, self.comparing, "pending", "reference"),
        ])

        self.assertEqual(report["unreachable"], [])
        self.assertEqual(report["reachable_count"], 2)

    def test_a_required_edge_with_no_decision_is_unreachable(self):
        report = gold_report(self.data, self.concepts, [
            decision(self.matter, self.solid, "accepted", "containment"),
        ])

        self.assertEqual(report["unreachable"], [["solid", "comparing"]])
        self.assertEqual(report["reachable_count"], 1)

    def test_an_edge_implied_by_the_required_chain_is_correct(self):
        report = gold_report(self.data, self.concepts, [
            decision(self.matter, self.solid, "accepted", "containment"),
            decision(self.matter, self.comparing, "accepted", "definition"),
        ])

        self.assertEqual(report["accepted_precision"], 1.0)

    def test_an_explicitly_forbidden_edge_is_reported(self):
        report = gold_report(self.data, self.concepts, [
            decision(self.figure, self.matter, "accepted", "definition"),
        ])

        self.assertEqual(report["forbidden_accepted"], [["figure", "matter"]])
        self.assertEqual(report["accepted_precision"], 0.0)

    def test_accepted_links_are_counted_by_rule(self):
        report = gold_report(self.data, self.concepts, [
            decision(self.matter, self.solid, "accepted", "containment"),
            decision(self.solid, self.comparing, "accepted"),
        ])

        self.assertEqual(report["accepted_by_rule"], {"containment": 1, "none": 1})

    def test_nothing_accepted_has_no_precision(self):
        self.assertIsNone(gold_report(self.data, self.concepts, [])["accepted_precision"])
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `../.venv/Scripts/python.exe manage.py test learning_path.test_gold_report -v 2`
Expected: FAIL / `KeyError: 'unreachable'`.

- [ ] **Step 3: Implement**

In `backend/learning_path/services/gold.py`, add `from collections import Counter` to the imports.
Then change `gold_report` as follows.

Replace the `forbidden` helper and add the closure right after `known_missing = ...`:

```python
    explicit_forbidden = {tuple(edge) for edge in data.get("forbidden", [])}

    def forbidden(edge):
        before, after = edge
        return (
            edge in explicit_forbidden
            or before in structural
            or after in structural
            or any(before in group and after in group for group in parallel)
            or (after, before) in required
        )

    # Gold maps list direct edges only. An accepted edge the required chain
    # implies ("matter -> comparing" through solid) is correct, not an extra.
    implied = set(required)
    changed = True
    while changed:
        changed = False
        for (first, middle) in list(implied):
            for (other, last) in list(implied):
                if middle == other and first != last and (first, last) not in implied:
                    implied.add((first, last))
                    changed = True
```

Replace the lines from `accepted_set = set(accepted)` through the end of the returned dict with:

```python
    accepted_set = set(accepted)
    reachable = accepted_set | set(pending)
    missing_required = [edge for edge in required if edge not in accepted_set]
    unreachable = [edge for edge in required if edge not in reachable]
    rules = Counter(
        (row.get("evidence") or {}).get("rule", "none")
        for row in decisions if row["verdict"] == criteria.ACCEPTED
    )
    return {
        "topic": data["topic_id"],
        "accepted": [list(edge) for edge in accepted],
        "pending": [list(edge) for edge in pending],
        "missing_required": [list(edge) for edge in missing_required],
        "unexpected_missing": [list(edge) for edge in missing_required if edge not in known_missing],
        "gaps_closed": [list(edge) for edge in known_missing if edge in accepted_set],
        "forbidden_accepted": [list(edge) for edge in accepted if forbidden(edge)],
        "extra_accepted": [list(edge) for edge in accepted if edge not in required and not forbidden(edge)],
        "unreachable": [list(edge) for edge in unreachable],
        "reachable_count": len(required) - len(unreachable),
        "accepted_precision": (
            sum(1 for edge in accepted if edge in implied) / len(accepted) if accepted else None
        ),
        "accepted_by_rule": dict(rules),
        "order": order,
        "order_matches": order == data["expected_order"],
        "ignored_links": [[key[before], key[after]] for before, after in ignored],
        "unkeyed_concepts": sum(1 for concept in concepts if concept.key is None),
    }
```

`gold_report` calls `order_with_links(concepts, links)`, which reads `concept.kind` and `title`
through `is_structural`. The test's `SimpleNamespace` concepts carry both, so no stub change is
needed.

Replace `backend/learning_path/management/commands/evaluate_gold_paths.py` with:

```python
"""Print the gold report; ``--grid`` sweeps ``PRD_THRESHOLD``.

v4 has one constant. The spec fixes its range to Liang et al.'s recommended
0.02-0.1 and chooses it on topics 62 and 79 only; 152 and 308 are then read at
that value unchanged (docs/superpowers/specs/2026-09-29-learning-path-criteria-v4-design.md).
"""

import json

from django.core.management.base import BaseCommand

from learning_path.services import criteria
from learning_path.services.gold import gold_report, load_gold

GRID = (0.02, 0.05, 0.1)


class Command(BaseCommand):
    help = "Report derived learning paths against the gold standard."

    def add_arguments(self, parser):
        parser.add_argument("--grid", action="store_true")
        parser.add_argument("--topics", nargs="*", type=int, default=[62, 79])

    def _reports(self, topics):
        reports = []
        for topic_id in topics:
            data, concepts = load_gold(topic_id)
            reports.append(gold_report(data, concepts, criteria.decide_pairs(concepts)))
        return reports

    def handle(self, *args, grid=False, topics=(62, 79), **options):
        if not grid:
            self.stdout.write(json.dumps(self._reports(topics), indent=2))
            return

        default = criteria.PRD_THRESHOLD
        rows = []
        try:
            for value in GRID:
                criteria.PRD_THRESHOLD = value
                reports = self._reports(topics)
                rows.append({
                    "PRD_THRESHOLD": value,
                    "forbidden": sum(len(report["forbidden_accepted"]) for report in reports),
                    "reachable": {report["topic"]: report["reachable_count"] for report in reports},
                    "accepted_precision": {report["topic"]: report["accepted_precision"] for report in reports},
                    "orders_match": all(report["order_matches"] for report in reports),
                })
        finally:
            criteria.PRD_THRESHOLD = default
        self.stdout.write(json.dumps(rows, indent=2))
```

This command reads `criteria.PRD_THRESHOLD`, which only exists after Task 4. Until then, only the
non-grid path is usable. That is fine: the command is first run in Task 6.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `../.venv/Scripts/python.exe manage.py test learning_path.test_gold_report learning_path.test_gold_paths -v 2`
Expected: all PASS. The gold tests still assert their v3 keys, which are all still returned.

- [ ] **Step 5: Commit**

```bash
git add backend/learning_path/services/gold.py backend/learning_path/test_gold_report.py backend/learning_path/management/commands/evaluate_gold_paths.py
git commit -m "Report reachability, closure precision and evidence rules in the gold report

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Replace `decide_pairs` with the v4 decision table

**Files:**
- Modify: `backend/learning_path/services/criteria.py` (module docstring, imports, remove v3 code,
  new `decide_pairs`)
- Rewrite: `backend/learning_path/test_criteria.py`
- Modify: `backend/learning_path/services/publishing.py:61` and `:72`
- Modify: `backend/learning_path/test_publishing.py:32`, `backend/learning_path/tests.py:344`
- Modify: `backend/learning_path/test_gold_paths.py` (whole file)

**Interfaces:**
- Consumes: `definition_dependency`, `passage_reference`, `says_plainly` (Tasks 1–2),
  `contained_in`, `presented_in_parallel`, `crosses_sections`, `concept_names`, `head_words`,
  `is_structural`. `gold_report` keys `reachable_count`, `forbidden_accepted`, `order_matches`
  (Task 3).
- Produces:
  - `criteria.PRD_THRESHOLD = 0.05` (a provisional value; Task 6 confirms or changes it).
  - `criteria.decide_pairs(concepts, runtime_instance=None) -> list[dict]`. Each dict has:
    - `prerequisite`, `dependent`;
    - `verdict`: `"accepted"` or `"pending"`;
    - `evidence`: a dict;
    - `cross_section`: bool.
  - `evidence` shapes:
    - `{"rule": "definition", "definition": {"sentence": str}}`, optionally plus
      `"opposing_reference": {"prd": float}`;
    - `{"rule": "containment", "containment": {"heading": str}}`, optionally plus
      `"opposing_reference": {"prd": float}`;
    - `{"rule": "reference", "reference": {"prw_forward", "prw_backward", "prd", "theta"}}`;
    - `{"rule": "conflict", "forward": {"rule": str, ...detail}, "backward": {"rule": str, ...detail}}`.

- [ ] **Step 1: Rewrite the test file (failing)**

Replace `backend/learning_path/test_criteria.py` entirely with:

```python
"""The v4 decision table, its vetoes, and the helpers it keeps from v3.

R1 and R3 are measured on their own in ``test_evidence.py``; this file pins how
they combine with R2 into a verdict. See
``docs/superpowers/specs/2026-09-29-learning-path-criteria-v4-design.md``.
"""

import json

from django.test import SimpleTestCase, TestCase

from lessons.models import CourseGroup, LearningMaterial, LearningObject, LearningObjectGroup, OutlineNode

from .services.concept_units import concepts_for_topic
from .services.criteria import (
    ACCEPTED,
    PENDING,
    PRD_THRESHOLD,
    concept_names,
    contained_in,
    crosses_sections,
    decide_pairs,
    head_words,
    only_contrastive_mentions,
    presented_in_parallel,
)
from .services.publishing import order_with_links


class Headed:
    """A concept stub whose members carry their own title, content and heading."""

    def __init__(self, id, order, title, contents, sections=None):
        if isinstance(contents, str):
            contents = (contents,)
        sections = sections or ("",) * len(contents)
        self.id = id
        self.order = order
        self.title = title
        self.content = contents[0]
        self.member_text = "\n".join(contents)
        self.section_title = sections[0]
        self.kind = "text"
        self.members = tuple(
            type("Member", (), {"title": title, "content": content, "section_title": section})()
            for content, section in zip(contents, sections)
        )


def rows(concepts):
    return {(row["prerequisite"].id, row["dependent"].id): row for row in decide_pairs(concepts)}


class ConceptNameTests(SimpleTestCase):
    def test_a_structural_label_names_nothing(self):
        self.assertEqual(concept_names([Headed(1, 0, "Everyday Examples", "A rock.")]), {1: None})


class ContrastTests(SimpleTestCase):
    def test_a_mention_only_after_a_contrast_marker_is_contrastive(self):
        self.assertTrue(only_contrastive_mentions("solid", "A gas spreads out, unlike a solid."))

    def test_contrast_is_scoped_to_the_clause_not_the_sentence(self):
        text = "Liquids and gases can flow, while solids normally do not."
        self.assertFalse(only_contrastive_mentions("liquid", text))
        self.assertTrue(only_contrastive_mentions("solid", text))

    def test_a_comparison_with_than_is_contrastive(self):
        self.assertTrue(only_contrastive_mentions("solid", "Gas particles have more energy than in a solid."))

    def test_no_mention_is_not_a_contrast(self):
        self.assertFalse(only_contrastive_mentions("solid", "Gases spread out."))


class SectionTests(SimpleTestCase):
    def test_different_headings_cross_sections(self):
        self.assertTrue(crosses_sections(
            Headed(1, 0, "A", "x", ("Solids",)), Headed(2, 1, "B", "y", ("Gases",)),
        ))

    def test_the_same_heading_does_not(self):
        self.assertFalse(crosses_sections(
            Headed(1, 0, "A", "x", ("Solids",)), Headed(2, 1, "B", "y", (" solids ",)),
        ))

    def test_a_concept_without_a_heading_crosses_nothing(self):
        self.assertFalse(crosses_sections(Headed(1, 0, "A", "x", ("Solids",)), Headed(2, 1, "B", "y")))


class HeadWordTests(SimpleTestCase):
    def test_the_head_word_is_the_first_significant_word(self):
        self.assertEqual(
            head_words({1: "seed formation", 2: "stamen male part", 3: "solid"}),
            {1: "seed", 2: "stamen"},
        )

    def test_a_shared_head_word_is_ambiguous(self):
        self.assertEqual(head_words({1: "seed formation", 2: "seed dispersal"}), {})

    def test_a_single_word_name_makes_its_word_ambiguous(self):
        self.assertEqual(head_words({1: "seed", 2: "seed dispersal"}), {})


class ContainmentTests(SimpleTestCase):
    def test_a_concept_under_anothers_heading_is_contained(self):
        solid = Headed(2, 1, "Solid", ("A solid keeps its shape.", "Solids vibrate."), ("Matter", "Solids"))
        self.assertTrue(contained_in(solid, "matter"))

    def test_no_heading_contains_nothing(self):
        self.assertFalse(contained_in(Headed(2, 1, "Roots", "Roots take in water."), "matter"))
        self.assertFalse(contained_in(Headed(2, 1, "Solid", "x", ("Matter",)), None))


class ParallelPresentationTests(SimpleTestCase):
    def test_two_passages_under_one_heading_are_parallel(self):
        solid = Headed(1, 0, "Solid", "Particles are drawn as evenly spaced dots.", ("Matter",))
        gas = Headed(2, 1, "Gas", "Particles are drawn as widely spaced dots.", ("Matter",))
        self.assertTrue(presented_in_parallel(solid, gas, {1: "solid", 2: "gas"}))

    def test_the_concept_the_heading_names_is_the_parent_not_a_sibling(self):
        matter = Headed(1, 0, "Matter", "Matter has mass.", ("Matter",))
        solid = Headed(2, 1, "Solid", "A solid keeps its shape.", ("Matter",))
        self.assertFalse(presented_in_parallel(matter, solid, {1: "matter", 2: "solid"}))

    def test_passages_under_different_headings_are_not_parallel(self):
        solid = Headed(1, 0, "Solid", "A solid keeps its shape.", ("Matter",))
        comparing = Headed(2, 1, "Comparing", "The table compares them.", ("Comparing the Three States",))
        self.assertFalse(presented_in_parallel(solid, comparing, {1: "solid", 2: "comparing"}))

    def test_a_concept_under_no_heading_is_parallel_to_nothing(self):
        solid = Headed(1, 0, "Solid", "A solid keeps its shape.", ("Matter",))
        changing = Headed(2, 1, "Changing", "Heat changes the state.")
        self.assertFalse(presented_in_parallel(solid, changing, {1: "solid", 2: "changing"}))


class DecisionTableTests(SimpleTestCase):
    """Spec Section 6, row by row."""

    def matter_and_solid(self, matter_order=0, solid_order=1):
        matter = Headed(1, matter_order, "Matter", "Matter is anything that has mass.", ("Matter",))
        solid = Headed(2, solid_order, "Solid", "It keeps its shape.", ("Matter",))
        return matter, solid

    def test_containment_is_accepted(self):
        decided = rows(list(self.matter_and_solid()))

        self.assertEqual(decided[(1, 2)]["verdict"], ACCEPTED)
        self.assertEqual(decided[(1, 2)]["evidence"], {"rule": "containment", "containment": {"heading": "matter"}})

    def test_a_definition_is_accepted(self):
        solid = Headed(1, 0, "Solid", "It keeps its shape.")
        liquid = Headed(2, 1, "Liquid", "It flows.")
        melting = Headed(3, 2, "Melting", "Melting is when a solid turns into a liquid.")

        decided = rows([solid, liquid, melting])

        self.assertEqual(decided[(1, 3)]["verdict"], ACCEPTED)
        self.assertEqual(decided[(1, 3)]["evidence"]["rule"], "definition")
        self.assertEqual(
            decided[(1, 3)]["evidence"]["definition"]["sentence"],
            "Melting is when a solid turns into a liquid",
        )
        self.assertNotIn((3, 1), decided)

    def test_strong_evidence_both_ways_is_a_conflict_for_the_teacher(self):
        matter = Headed(1, 0, "Matter", "Matter is what a solid is made of.")
        solid = Headed(2, 1, "Solid", "It keeps its shape.", ("Matter",))

        decided = rows([matter, solid])

        for pair in ((1, 2), (2, 1)):
            self.assertEqual(decided[pair]["verdict"], PENDING)
            self.assertEqual(decided[pair]["evidence"]["rule"], "conflict")
        self.assertEqual(decided[(1, 2)]["evidence"]["forward"]["rule"], "containment")
        self.assertEqual(decided[(1, 2)]["evidence"]["backward"]["rule"], "definition")

    def test_reference_alone_is_pending(self):
        solid = Headed(1, 0, "Solid", "It keeps its shape.", ("Solids",))
        comparing = Headed(2, 1, "Comparing", "The table puts the solid beside the gas.", ("Comparing the Three States",))

        decided = rows([solid, comparing])

        self.assertEqual(decided[(1, 2)]["verdict"], PENDING)
        self.assertEqual(decided[(1, 2)]["evidence"], {
            "rule": "reference",
            "reference": {"prw_forward": 1.0, "prw_backward": 0.0, "prd": 1.0, "theta": PRD_THRESHOLD},
        })

    def test_reference_at_or_below_the_threshold_decides_nothing(self):
        solid = Headed(1, 0, "Solid", "A solid can become a liquid.")
        liquid = Headed(2, 1, "Liquid", "A liquid can become a solid.")

        self.assertEqual(rows([solid, liquid]), {})

    def test_reference_never_overrides_containment(self):
        """Review Focus 3: Matter's overview names Solid, so R3 alone reads
        Solid -> Matter. Containment keeps Matter -> Solid accepted."""
        matter = Headed(1, 0, "Matter", "Matter can be a solid, a liquid or a gas.")
        solid = Headed(2, 1, "Solid", "It keeps its shape.", ("Matter",))

        decided = rows([matter, solid])

        self.assertEqual(decided[(1, 2)]["verdict"], ACCEPTED)
        self.assertEqual(decided[(1, 2)]["evidence"]["opposing_reference"], {"prd": 1.0})
        self.assertNotIn((2, 1), decided)

    def test_siblings_need_a_definition_not_a_reference(self):
        solid = Headed(1, 0, "Solid", "It keeps its shape.", ("Matter",))
        gas = Headed(2, 1, "Gas", "A gas can become a solid when cooled.", ("Matter",))

        self.assertNotIn((1, 2), rows([solid, gas]))

    def test_a_sibling_defined_through_another_keeps_its_link(self):
        seed = Headed(1, 0, "Seed", "It holds a tiny plant.", ("How Flowering Plants Reproduce",))
        fruit = Headed(2, 1, "Fruit", "A fruit is the ripened ovary that holds the seed.", ("How Flowering Plants Reproduce",))

        decided = rows([seed, fruit])

        self.assertEqual(decided[(1, 2)]["verdict"], ACCEPTED)
        self.assertEqual(decided[(1, 2)]["evidence"]["rule"], "definition")

    def test_a_contrastive_mention_supports_nothing(self):
        solid = Headed(1, 0, "Solid", "It keeps its shape.")
        gas = Headed(2, 1, "Gas", "A gas is a state that spreads out, unlike a solid.")

        self.assertNotIn((1, 2), rows([solid, gas]))

    def test_two_concepts_with_the_same_name_are_never_linked(self):
        first = Headed(1, 0, "Solid", "A solid keeps its shape.")
        second = Headed(2, 1, "Solid", "A solid is rigid because of the solid bonds.")

        self.assertEqual(rows([first, second]), {})

    def test_document_order_never_changes_a_decision(self):
        """Review Focus 1: the whole point of v4 (spec goal 1)."""
        forward = rows(list(self.matter_and_solid(matter_order=0, solid_order=1)))
        reversed_ = rows(list(self.matter_and_solid(matter_order=1, solid_order=0)))

        self.assertEqual(
            {pair: (row["verdict"], row["evidence"]) for pair, row in forward.items()},
            {pair: (row["verdict"], row["evidence"]) for pair, row in reversed_.items()},
        )

    def test_a_link_can_point_against_document_order(self):
        """Review Focus 2: Solid sits first in the PDF, Matter second; the link
        is still Matter -> Solid, and the path teaches Matter first."""
        matter, solid = self.matter_and_solid(matter_order=1, solid_order=0)

        decided = rows([solid, matter])
        ordered, _, _ = order_with_links([solid, matter], [
            pair for pair, row in decided.items() if row["verdict"] == ACCEPTED
        ])

        self.assertEqual(decided[(1, 2)]["verdict"], ACCEPTED)
        self.assertEqual([concept.id for concept in ordered], [1, 2])

    def test_evidence_is_json_serialisable(self):
        """Review Focus 5: evidence goes into a JSONField at publish."""
        matter = Headed(1, 0, "Matter", "Matter can be a solid, a liquid or a gas.")
        solid = Headed(2, 1, "Solid", "It keeps its shape.", ("Matter",))
        melting = Headed(3, 2, "Melting", "Melting is when a solid turns into a liquid.")
        comparing = Headed(4, 3, "Comparing", "The solid is beside the matter.", ("Comparing the Three States",))

        for row in decide_pairs([matter, solid, melting, comparing]):
            json.dumps(row["evidence"])

    def test_crossing_sections_is_recorded(self):
        solid = Headed(1, 0, "Solid", "It keeps its shape.", ("Solids",))
        comparing = Headed(2, 1, "Comparing", "The table puts the solid beside the gas.", ("Comparing the Three States",))

        self.assertTrue(rows([solid, comparing])[(1, 2)]["cross_section"])

    def test_a_concept_is_never_its_own_prerequisite(self):
        for (before, after) in rows(list(self.matter_and_solid())):
            self.assertNotEqual(before, after)

    def test_too_few_concepts_decide_nothing(self):
        self.assertEqual(decide_pairs([Headed(1, 0, "Matter", "Matter has mass.")]), [])

    def test_structural_concepts_take_part_in_no_pair(self):
        matter, solid = self.matter_and_solid()
        examples = Headed(3, 2, "7. Everyday Examples", "Matter, a solid, a liquid and a gas.", ("Matter",))

        decided = rows([matter, solid, examples])

        self.assertFalse(any(3 in pair for pair in decided))


class MemberTextTests(TestCase):
    """Concepts built the way the topic path builds them carry every PDF's text."""

    def test_member_text_joins_every_pdf(self):
        course = CourseGroup.objects.create(title="Grade 1 Science")
        topic = OutlineNode.objects.create(course=course, title="Solid, Liquid and Gas", order=0, depth=0)
        first = LearningMaterial.objects.create(course=course, outline_node=topic, title="A", status="completed")
        second = LearningMaterial.objects.create(course=course, outline_node=topic, title="B", status="completed")
        group = LearningObjectGroup.objects.create(outline_node=topic, label="Solid")
        LearningObject.objects.create(material=first, group=group, title="Solid", content="A solid is matter that keeps its shape.", order=0)
        LearningObject.objects.create(material=second, group=group, title="Solids", content="Solid particles vibrate.", order=0)

        concept = next(c for c in concepts_for_topic(topic) if c.id == group.id)

        self.assertIn("A solid is matter that keeps its shape.", concept.member_text)
        self.assertIn("Solid particles vibrate.", concept.member_text)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `../.venv/Scripts/python.exe manage.py test learning_path.test_criteria -v 2`
Expected: ERROR, `ImportError: cannot import name 'PRD_THRESHOLD'`.

- [ ] **Step 3: Rewrite the criteria module**

In `backend/learning_path/services/criteria.py`:

1. Replace the module docstring (lines 1–10) with:

```python
"""Prerequisite evidence for the learning path (criteria v4).

Three kinds of evidence, each traceable to published work, decide whether one
concept precedes another. None of them reads where a concept sits in the PDF;
document order only breaks ties later, in ``order_with_links``.

* **R1 definition dependency** -- B's defining sentence names A
  (Wang et al. 2016; Talukdar & Cohen 2012).
* **R2 section containment** -- B sits under a heading naming A (Wang et al. 2016).
* **R3 passage reference distance** -- B's passages name A more than A's name B
  (Pan et al. 2017, generalising RefD, Liang et al. 2015).

R1 or R2 accepts a link; R3 alone only proposes one for the teacher. Nothing
here writes to the database or calls a model. See ``learning_path/CRITERIA.md``
and docs/superpowers/specs/2026-09-29-learning-path-criteria-v4-design.md.
"""
```

2. Replace the imports block (lines 12–19) with:

```python
import re
from collections import Counter

from .concepts import heading_name, is_structural, resolve_concept
from .text_signals import (
    MIN_TERM_LENGTH,
    STOP_WORDS,
    definition_subject,
    first_sentence,
    mentions,
    normalize,
    singular,
)
```

3. **Delete** these v3 definitions entirely:
   - constants `WINDOW_SIZE`, `MAX_WINDOWS_PER_CONCEPT`, `MIN_OUTBOUND`, `MAX_IOL`,
     `MIN_IOL_MARGIN`, `REF_MAX_DF_RATIO`, `REF_MARGIN`, `PHRASE_COSINE`, with their comments;
   - functions `_windows`, `_terms`, `key_terms`, `_phrase_hits`, `reference_details`,
     `reference_matrix`, `inbound_outbound_ratios`, `temporal_order`, `semantic_reference`,
     `inbound_outbound`, `cast_votes`, `decide`, `vetoed`, `names_the_target`.

   **Keep:**
   - `concept_names`, `concept_text`, `head_words`, `contained_in`;
   - the Task 1–2 functions;
   - `_CONTRAST`, `_SENTENCE`, `only_contrastive_mentions`;
   - `named_sections`, `presented_in_parallel`, `section_headings`, `crosses_sections`.

4. In `concept_names`'s docstring, replace the sentence referring to `key_terms` with:
   `"A concept with no name cannot be referred to; it can still depend on a concept whose heading it sits under."`

5. Put the constants right after the imports:

```python
# R3 threshold. RefD's authors recommend 0.02-0.1 (Liang et al. 2015, sec. 4.3);
# chosen on gold topics 62 and 79 only (Task 6 of the v4 plan). Measured
# 2026-09-29: results identical across that range on all three gold topics.
PRD_THRESHOLD = 0.05

ACCEPTED = "accepted"
PENDING = "pending"
```

   Also delete the later duplicate `ACCEPTED = ...` / `PENDING = ...` lines, which sat above the
   old `decide`.

6. Replace the old `decide_pairs` with:

```python
def _strong_evidence(a, b, names, heads):
    """R1, else R2, for "a before b": ``(rule, detail)`` or ``None``."""
    sentence = definition_dependency(a, b, names, heads)
    if sentence:
        return "definition", {"sentence": sentence}
    if contained_in(b, names.get(a.id)):
        return "containment", {"heading": names[a.id]}
    return None


def decide_pairs(concepts, runtime_instance=None):
    """Every ordered pair the evidence accepts or sends to the teacher.

    ``runtime_instance`` is kept for callers and ignored: v4 calls no model.

    Rule precedence, not voting (spec Section 6). R1/R2 one way only is
    accepted; R1/R2 both ways is a conflict for the teacher; R3 alone is a
    suggestion, never between coordinate siblings. R3 never overrides R1/R2 --
    a parent's overview names its children, so R3 reads parent/child pairs
    backwards (measured: Matter/Solid on topic 62).
    """
    # Examples and similar furniture present concepts; nothing depends on them
    # and they depend on nothing. They are ordered last by `order_with_links`.
    concepts = [concept for concept in concepts if not is_structural(concept)]
    if len(concepts) < 2:
        return []

    names = concept_names(concepts)
    heads = head_words(names)
    references = passage_reference(concepts, names, heads)

    decisions = []
    for a in concepts:
        for b in concepts:
            if a.id == b.id:
                continue
            if names.get(a.id) and names.get(a.id) == names.get(b.id):
                continue

            forward = _strong_evidence(a, b, names, heads)
            backward = _strong_evidence(b, a, names, heads)
            reference = references.get((a.id, b.id))

            if forward and backward:
                verdict = PENDING
                evidence = {
                    "rule": "conflict",
                    "forward": {"rule": forward[0], **forward[1]},
                    "backward": {"rule": backward[0], **backward[1]},
                }
            elif forward:
                verdict = ACCEPTED
                evidence = {"rule": forward[0], forward[0]: forward[1]}
                opposing = references.get((b.id, a.id))
                if opposing and opposing["prd"] > PRD_THRESHOLD:
                    evidence["opposing_reference"] = {"prd": opposing["prd"]}
            elif backward:
                # The reverse pair records this link.
                continue
            elif (
                reference
                and reference["prd"] > PRD_THRESHOLD
                and not presented_in_parallel(a, b, names)
            ):
                verdict = PENDING
                evidence = {"rule": "reference", "reference": {**reference, "theta": PRD_THRESHOLD}}
            else:
                continue

            decisions.append({
                "prerequisite": a,
                "dependent": b,
                "verdict": verdict,
                "evidence": evidence,
                "cross_section": crosses_sections(a, b),
            })
    return decisions
```

7. Check for leftovers: `Grep` `criteria.py` for `semantic_runtime|math\.|defaultdict|_windows|key_terms|MIN_IOL|REF_|PHRASE_`.
   Expected: no matches. `Counter` is still used by `head_words`. If `MIN_TERM_LENGTH` and
   `STOP_WORDS` are still used by `head_words`, keep them; otherwise remove them from the import.

- [ ] **Step 4: Update publishing and its fixtures**

In `backend/learning_path/services/publishing.py`, change both `decision["votes"]` (lines 61 and 72)
to `decision["evidence"]`.

In `backend/learning_path/test_publishing.py:32`, replace

```python
        "votes": {"temporal_order": 1, "semantic_reference": 1, "inbound_outbound": 1},
```

with

```python
        "evidence": {"rule": "containment", "containment": {"heading": "matter"}},
```

In `backend/learning_path/tests.py:344`, replace `"votes": {},` with `"evidence": {},`.

- [ ] **Step 5: Replace the gold acceptance test**

Replace `backend/learning_path/test_gold_paths.py` entirely with:

```python
"""Acceptance: the v4 criteria on real lesson text, against the teacher's maps.

v4 calls no model, so this runs everywhere. Assertions follow the spec's
acceptance criteria (Section 10): no forbidden link accepted, the expected
order, and at least the measured number of required links reachable
(accepted or pending). Accepted recall is reported, not gated: most links are
teacher suggestions by design. See
docs/superpowers/specs/2026-09-29-learning-path-criteria-v4-design.md, 10.1.
"""

import json

from django.test import SimpleTestCase

from .services import criteria
from .services.gold import gold_report, load_gold

REACHABLE_FLOOR = {62: 9, 79: 3, 152: 8}


class GoldPathTests(SimpleTestCase):
    def _report(self, topic_id):
        data, concepts = load_gold(topic_id)
        return gold_report(data, concepts, criteria.decide_pairs(concepts))

    def _assert_gold(self, report):
        details = f"\nFull report:\n{json.dumps(report, indent=2)}"
        self.assertEqual(report["forbidden_accepted"], [], "forbidden edges accepted" + details)
        self.assertTrue(report["order_matches"], f"order was {report['order']}" + details)
        self.assertGreaterEqual(
            report["reachable_count"], REACHABLE_FLOOR[report["topic"]],
            "fewer required edges reachable than the measured v4 baseline" + details,
        )

    def test_solid_liquid_and_gas(self):
        self._assert_gold(self._report(62))

    def test_reproduction_among_flowering_plants(self):
        self._assert_gold(self._report(79))

    def test_solid_liquid_and_gas_as_the_pipeline_groups_it_today(self):
        """Topic 152 freezes the pipeline's own 14 concepts for the lesson
        topic 62 holds in the teacher's grouping (see export_live_concepts)."""
        self._assert_gold(self._report(152))
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `../.venv/Scripts/python.exe manage.py test learning_path -v 1`
Expected: all OK.

If a gold test fails:
- **Do not change the floor or the rules.** Print the report:
  `../.venv/Scripts/python.exe manage.py evaluate_gold_paths --topics 62 79 152`
- Compare it with spec Section 10.1, which gives the numbers this implementation must reproduce.
- A mismatch means the code differs from the measured rules. Fix the code.
- If the numbers match Section 10.1 but `order_matches` is false, stop and report to the user. The
  spec did not measure order.

- [ ] **Step 7: Commit**

```bash
git add backend/learning_path/services/criteria.py backend/learning_path/services/publishing.py backend/learning_path/test_criteria.py backend/learning_path/test_publishing.py backend/learning_path/tests.py backend/learning_path/test_gold_paths.py
git commit -m "Replace the three-vote criteria with v4 typed evidence

Definition dependency or section containment accepts a link; passage
reference distance alone proposes one for the teacher. Document order no
longer votes, and each link records the evidence rule behind it.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Topic 308 answer key (human-gated)

**Files:**
- Modify: `backend/learning_path/management/commands/export_live_concepts.py:74-75`
- Create: `backend/learning_path/fixtures/gold_map_308.json`
- Create: `backend/learning_path/fixtures/gold_topic_308.json` (generated)

**Interfaces:**
- Consumes: `export_live_concepts <topic_id> <map_path> <out_path>`; `gold_report` reads the
  optional `forbidden` key (Task 3).
- Produces: fixture 308 in the live shape (like 152), with keys at least `matter`, `solid`,
  `liquid`, `gas`, an explicit `forbidden` list, and `known_missing: []`.

- [ ] **Step 1: GATE, the user hand-groups topic 308.** Ask the user to finish grouping topic 308
  in the Course Builder, and wait for confirmation. Do not continue before it.

- [ ] **Step 2: Make the export carry explicit forbidden edges**

In `export_live_concepts.py`, after `output["known_missing"] = spec.get("known_missing", [])`, add:

```python
        output["forbidden"] = spec.get("forbidden", [])
```

- [ ] **Step 3: List the hand-grouped concepts**

Run:

```bash
../.venv/Scripts/python.exe manage.py shell -c "from lessons.models import OutlineNode; from learning_path.services.concept_units import concepts_for_topic; [print(c.id, repr(c.title), '|', sorted({m.section_title for m in c.members}), '|', c.source_material_ids) for c in concepts_for_topic(OutlineNode.objects.get(pk=308))]"
```

- [ ] **Step 4: Draft the answer key from the PDFs, not from the criteria**

Read the three source PDFs:
- `backend/media/learning_materials/Lesson-1_Solid-Liquid-and-Gas-1.pdf`
- `Solid-Liquid-Gas-2.pdf`
- `Solid_Liquid_and_Gas.pdf`

**Do not run `decide_pairs` or `evaluate_gold_paths` on topic 308 before the key is committed.**

Write `backend/learning_path/fixtures/gold_map_308.json` in the `gold_map_152.json` shape, with
these keys:
- `topic_id`, `_note`, `concept_keys` (concept id → key; leave out concepts the key does not
  score);
- `required`: direct edges only;
- `parallel`: at least `["solid", "liquid", "gas"]`;
- `structural`: the examples keys;
- `forbidden`:
  - every figure-description or example-type key → the concept defining its subject;
  - any reverse parent/child edge the teacher would reject;
- `expected_order`, and `known_missing: []`.

- [ ] **Step 5: GATE, the user corrects the draft.** Show the draft to the user as a readable
  list: required edges, forbidden edges, expected order, and which concept ids map to which key.
  Apply their corrections. Continue only after an explicit "approved".

- [ ] **Step 6: Export and commit**

```bash
../.venv/Scripts/python.exe manage.py export_live_concepts 308 learning_path/fixtures/gold_map_308.json learning_path/fixtures/gold_topic_308.json
../.venv/Scripts/python.exe manage.py test learning_path
git add backend/learning_path/management/commands/export_live_concepts.py backend/learning_path/fixtures/gold_map_308.json backend/learning_path/fixtures/gold_topic_308.json
git commit -m "Add the hand-grouped topic 308 answer key as a gold fixture

Drafted from the three source PDFs and corrected by the user before the v4
criteria were run on this topic.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

Expected: the test suite is still all OK. Fixture 308 is not asserted on yet.

---

### Task 6: Confirm θ, then accept topic 308

**Files:**
- Modify: `backend/learning_path/services/criteria.py` (`PRD_THRESHOLD`, only if the grid says so)
- Modify: `backend/learning_path/test_gold_paths.py` (add the 308 test)

**Interfaces:**
- Consumes: `evaluate_gold_paths --grid --topics`, fixture 308 (Task 5), and the
  `gold_report` keys `accepted`, `accepted_precision` (Task 3).
- Produces: the final `PRD_THRESHOLD`, and `test_solid_liquid_and_gas_hand_grouped`.

- [ ] **Step 1: Choose θ on topics 62 and 79 only**

Run: `../.venv/Scripts/python.exe manage.py evaluate_gold_paths --grid --topics 62 79`

Selection rule, applied in order:
1. `forbidden == 0`;
2. highest total `reachable`;
3. `orders_match` true;
4. ties go to **0.05**, Liang et al.'s best value on CrowdComp.

Expected, from spec Section 10.1: all three values identical, so θ stays `0.05`. If the grid
picks another value, set `PRD_THRESHOLD` to it in `criteria.py`.

Save the grid output for Task 7.

- [ ] **Step 2: Read topics 152 and 308 at that θ, unchanged**

Run: `../.venv/Scripts/python.exe manage.py evaluate_gold_paths --topics 152 308`
Save the output for Task 7. Do **not** change θ or any rule in response to it.

- [ ] **Step 3: Write the 308 acceptance test**

Add to `GoldPathTests` in `backend/learning_path/test_gold_paths.py`:

```python
    def test_solid_liquid_and_gas_hand_grouped(self):
        """Topic 308 after hand grouping (spec Section 10, criterion 4).

        The answer key was drafted from the PDFs and corrected by the user
        before v4 ran on this topic. Its explicit `forbidden` list carries
        "no figure or example before the concept defining its subject".
        """
        report = self._report(308)
        details = f"\nFull report:\n{json.dumps(report, indent=2)}"

        self.assertEqual(report["forbidden_accepted"], [], "forbidden edges accepted" + details)
        self.assertTrue(report["order_matches"], f"order was {report['order']}" + details)
        self.assertGreaterEqual(report["accepted_precision"] or 0.0, 0.8, "accepted precision" + details)
        for child in ("solid", "liquid", "gas"):
            self.assertIn(["matter", child], report["accepted"], details)
```

- [ ] **Step 4: Run it**

Run: `../.venv/Scripts/python.exe manage.py test learning_path.test_gold_paths -v 2`
Expected: all PASS.

**If the 308 test fails: stop.** Do not edit the answer key, θ or the rules. Report the full
report to the user, and decide the fallback with them (spec Section 10: "decided with the user
before any tuning").

- [ ] **Step 5: Run the whole suite and commit**

Run: `../.venv/Scripts/python.exe manage.py test learning_path`
Expected: all OK.

```bash
git add backend/learning_path/services/criteria.py backend/learning_path/test_gold_paths.py
git commit -m "Accept v4 on the hand-grouped topic 308 and confirm the R3 threshold

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Document v4

**Files:**
- Modify: `backend/learning_path/CRITERIA.md` (banner at top, new section at end)
- Modify: `docs/AGENT_LOG.md` (new dated entry at the position the file's convention uses)

**Interfaces:**
- Consumes: the Task 6 outputs (grid and reports), and spec Sections 4–10.
- Produces: documentation only.

- [ ] **Step 1: Update `CRITERIA.md`**

Replace the first blockquote line (the "Superseded in part by the 2026-09-17 revision" banner) with:

```markdown
> **Superseded by [v4 (2026-09-29)](#v4-2026-09-29-typed-evidence).** Everything above that section is kept as history.
```

Append a section `## v4 (2026-09-29): typed evidence` containing:
- The three rules (R1, R2, R3), each with its formula or condition and its citation, copied from
  spec Section 4.
- The decision table from spec Section 6, and the vetoes from Section 5. Label the sibling rule as
  MAVIA's own design choice.
- The evidence JSON shapes from Task 4's Interfaces block.
- The measured table from spec Section 10.1, plus the Task 6 grid output and the 152/308 reports
  pasted verbatim.
- What was removed and why: spec Section 4, "Rules considered and excluded".

- [ ] **Step 2: Log the work in `docs/AGENT_LOG.md`**

Add a 2026-09-29 entry. Follow the file's existing entry format: read its last entry first and
mirror its headings. The entry should record:
- the v4 change;
- the spec and plan paths;
- the commits;
- the 308 answer-key provenance: drafted by Claude from the PDFs, corrected by the user;
- the open follow-ups from spec Section 12, including that the manuscript's prerequisite sections
  still describe v3.

- [ ] **Step 3: Commit**

```bash
git add backend/learning_path/CRITERIA.md docs/AGENT_LOG.md
git commit -m "Document learning-path criteria v4

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
