# Generation-Time Grounding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop MAVIA's question generator producing ungrounded questions in the first place, so the strict CRAG gate rejects far fewer of them — without weakening the gate.

**Architecture:** Four independent changes at the generation step, each closing one loophole found by walking the live code against the published topic 276. The CRAG gate (`question_generation/services/grounding.py`) is **not touched**: it stays strict, rejecting on both `contradicted` and `unsupported`. The gate is the specification; this plan makes the generator meet it.

**Tech Stack:** Django 5.1, Ollama (`llama3.2:3b` via `QUESTION_LLM_MODEL`), structured JSON decoding via Ollama's `format` parameter, Django `TestCase` (database) and `SimpleTestCase` (pure functions).

**Spec:** No separate spec document. The requirements were derived in-session by reading the live code and measuring the published bank on outline node 276 (course "Grade 1 Science", topic "Solid, Liquid and Gas"). The measured findings this plan argues from:

- 61 of 76 final questions used content words absent from all three source PDFs.
- Q107 and Q109 marked **`plasma`** as the correct answer where the source says "representing a gas" and "representing a solid". `plasma` appears in **0 of 3 PDFs**.
- Q108 is a `TF` item whose stem is *"...what is the shape of the particles?"* — not a proposition — answered `True`.
- Q111 asked about a solid→liquid change from a passage that only describes particle arrangements (topic drift).
- The prompt receives only the concept's **NORMAL** bundle (32 words for "Solid"), while the learner hears all three tellings (220 words) during remediation.

## Global Constraints

- **Do not modify `question_generation/services/grounding.py`.** The gate stays strict. Any task that seems to need a gate change is mis-scoped — stop and ask.
- **Do not add new Python dependencies.** `requirements.txt` and `requirements-semantic.txt` stay as they are.
- Prompt text is ASCII only. The pipeline reconfigures stdout to UTF-8, but prompts are sent to Ollama over HTTP and the existing templates are ASCII.
- Every task ends with `python manage.py test question_generation` passing in full (88 tests before this plan starts).
- Commit messages end with: `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`
- Work on branch `mavia-latest`. Do not commit `db.sqlite3` or any `db.sqlite3.*` backup.
- Run all commands from `C:\MAVIA\backend`.

## Review Focus

Input classes the generator will meet that no task's tests exercise by default. Each has a test assigned to the task that owns the code.

1. **A concept whose group has only one telling** (most of topic 276 — 10 of 19 concepts are single-PDF). Widening context must return exactly what it returns today, not an empty string or a duplicated one. → Task 1, Step 1.
2. **A concept with no group at all** (`group_id is None`). Must fall back to the object's own content, as today. → already pinned by the existing `test_an_ungrouped_object_uses_its_own_text` (`test_bundle_questions.py:42`); Task 1 must keep it passing, not replace it.
3. **An `EXTRA` bundle** (group 574 on topic 276 has one). It is deliberately excluded from what the learner is served, so it must not silently enter the prompt either. → Task 1, Step 1.
4. **A model reply whose `correct_answer` is a choice's full text rather than its letter.** The current code already recovers this; the rewrite must not lose it. → Task 4, Step 1.
5. **A `TF` item whose stem opens with a wh-word** (Q108's exact shape). Must be rejected before it reaches the bank. → Task 4, Step 1.

---

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `question_generation/services/pipeline.py` | Decides which objects generate and what text they generate from | Modify `concept_source_text` (Task 1) |
| `question_generation/services/question_generator.py` | Prompt text, Ollama call, response parsing, structural validation | Modify `PROMPT_TEMPLATES` (Task 2), `build_response_schema` (Task 3), `_validate_question` (Task 4) |
| `question_generation/test_bundle_questions.py` | Owns the contract for what text a concept generates from | Update + extend (Task 1) |
| `question_generation/test_structured_generation.py` | Owns the schema and parsing contract | Extend (Task 3) |
| `question_generation/test_question_validation.py` | **New.** Owns the structural-validation contract | Create (Task 4) |

Tasks are independent and may be done in any order, but Task 1 changes the question-bank fingerprint, so doing it first means one regeneration rather than two.

---

### Task 1: Generate from every telling of the concept, not only the Normal one

**Why:** A concept holds one bundle per PDF. Questions are written from `NORMAL` alone, but the adaptive engine serves `SIMPLIFIED` and `ELABORATED` from *other* PDFs during remediation — so a learner escalated to the elaborated version is asked questions written from text they were never read. It also starves HOT: a higher-order question must combine two or more stated facts, and with 32 words there often aren't two to combine, so the model supplies the second from its own knowledge.

Measured on topic 276: "Solid" 32 → 220 words, "Liquid" 37 → 246, "Comparing the Three States" 52 → 280.

`EXTRA` is excluded deliberately — `course/services.py::_build_chunk` and `learning_path/services/published.py::_versions` both skip it, so it is not text any learner is served.

**Files:**
- Modify: `question_generation/services/pipeline.py:157-172` (`concept_source_text`)
- Test: `question_generation/test_bundle_questions.py`

**Interfaces:**
- Consumes: `course.version_assignment.version_bundles(group) -> {role: [LearningObject]}` where role is one of `"NORMAL"`, `"SIMPLIFIED"`, `"ELABORATED"`, `"EXTRA"`. `lessons.services.concept_bundles.bundle_text(objects) -> str` (each object's `content`, newline-joined, blanks dropped).
- Produces: `concept_source_text(node) -> str`, unchanged signature. Called by `_draft_questions_for_node` (line 293) and `question_bank_fingerprint` (line 667). Widening the return value changes the fingerprint, which correctly invalidates every existing bank.

- [ ] **Step 1: Write the failing tests**

Add to `question_generation/test_bundle_questions.py`, inside `BundleQuestionSourceTests`:

```python
    def test_every_telling_of_the_concept_reaches_the_prompt(self):
        """A second PDF's telling is text the learner hears on remediation,
        so questions must be written from it too."""
        other = LearningMaterial.objects.create(
            course=self.course, outline_node=self.topic, title="B",
            generated_json={"learning_objects_confirmed": True})
        LearningObject.objects.create(
            material=other, group=self.group, title="Solids", order=0,
            represented_by=self.lead,
            content="Solid particles vibrate in place.")
        text = concept_source_text(self.lead)
        self.assertIn("A solid keeps its shape.", text)
        self.assertIn("Ice cubes and a rock.", text)
        self.assertIn("Solid particles vibrate in place.", text)

    def test_a_single_telling_concept_is_unchanged(self):
        """10 of topic 276's 19 concepts come from one PDF. They must read
        exactly as before, with no blank lines and nothing duplicated."""
        self.assertEqual(
            concept_source_text(self.lead),
            "A solid keeps its shape.\nIce cubes and a rock.",
        )

    def test_an_extra_bundle_is_not_offered_to_the_generator(self):
        """EXTRA is excluded from what a learner is served (published.py
        _versions, course/services.py _build_chunk), so it is not something
        to write questions about either."""
        extra = LearningMaterial.objects.create(
            course=self.course, outline_node=self.topic, title="C",
            generated_json={"learning_objects_confirmed": True})
        LearningObject.objects.create(
            material=extra, group=self.group, title="Aside", order=0,
            represented_by=self.lead, content="An unrelated aside.")
        self.group.version_selection = {
            "normal_material_id": self.material.id,
            "bundle_roles": {str(extra.id): "EXTRA"},
        }
        self.group.save(update_fields=["version_selection"])
        self.assertNotIn("An unrelated aside.", concept_source_text(self.lead))
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
python manage.py test question_generation.test_bundle_questions -v 2
```

Expected: `test_every_telling_of_the_concept_reaches_the_prompt` FAILS on the third `assertIn` — the second PDF's text is absent. The other two PASS already (they pin behavior that must not regress).

- [ ] **Step 3: Widen the context**

Replace `concept_source_text` in `question_generation/services/pipeline.py` (currently lines 157-172) with:

```python
# Roles a learner is actually served. EXTRA is excluded everywhere else that
# builds a version -- learning_path/services/published.py::_versions and
# course/services.py::_build_chunk both skip it -- so it is not text to write
# questions about either.
SERVED_VERSION_ROLES = ("NORMAL", "SIMPLIFIED", "ELABORATED")


def concept_source_text(node):
    """The text a concept's questions are written from: every telling of it.

    A concept holds one bundle per PDF, and the adaptive engine serves those
    bundles as the Normal, Simplified and Elaborated versions of one concept.
    A learner escalated to Elaborated hears another PDF's wording, so a bank
    written from the Normal bundle alone asks about text that learner was
    never read.

    It also starves the higher-order half of the bank. A HOT question has to
    combine two or more stated facts; measured on topic 276, the Normal
    bundle for "Solid" is 32 words and often does not hold two, so the model
    supplied the second from its own knowledge. Every telling together is
    220 words of the same concept -- more facts, no change of subject.
    """
    from course.version_assignment import version_bundles
    from lessons.services.concept_bundles import bundle_text

    if node.group_id is None:
        return node.content or ""

    bundles = version_bundles(node.group)
    if not any(item.id == node.id for item in bundles.get("NORMAL") or []):
        return node.content or ""

    # Deduplicated by object id: one PDF can fill two roles, and the same
    # object must not be read to the model twice.
    seen, objects = set(), []
    for role in SERVED_VERSION_ROLES:
        for item in bundles.get(role) or []:
            if item.id not in seen:
                seen.add(item.id)
                objects.append(item)
    return bundle_text(objects) or (node.content or "")
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
python manage.py test question_generation -v 1
```

Expected: PASS, 91 tests.

- [ ] **Step 5: Confirm the widening on real data**

```bash
python -c "
import os, sys, django
sys.path.insert(0, 'C:/MAVIA/backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings'); django.setup()
from lessons.models import LearningObject
from question_generation.services.pipeline import concept_source_text
for oid in (532, 533, 534, 535):
    lo = LearningObject.objects.get(id=oid)
    print(oid, lo.group.label, len(concept_source_text(lo).split()), 'words')
"
```

Expected: 532 Solid ~220, 533 Liquid ~246, 534 Gas ~211, 535 Comparing ~280. If any still reads 32-52, the role loop is not finding the other bundles — stop and investigate before continuing.

- [ ] **Step 6: Commit**

```bash
git add question_generation/services/pipeline.py question_generation/test_bundle_questions.py
git commit -m "Write a concept's questions from every telling a learner hears

The bank was generated from the Normal bundle alone while the adaptive
engine serves Simplified and Elaborated from other PDFs, so a learner on
a remediation rung was asked about text they were never read. It also
left HOT with too few stated facts to combine: 32 words for Solid, where
every telling together is 220.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 2: Forbid outside knowledge in the prompt

**Why:** The generation prompt has **no prohibition on outside knowledge at all**. Its only grounding instruction is the positive *"Each question must be answerable DIRECTLY from the content"*. The variant generator (`course/variant_generator.py:33-36`) already does this correctly and its wording is the model to follow.

The HOT template is worse than silent — it actively pushes the model off-source:

```python
"Do NOT ask for a fact that is stated word-for-word in the content.\n"
```

With no "only use source facts" rule, that line leaves the model nowhere to go but its own knowledge of states of matter. It is the direct cause of `temperature` (18 occurrences), `pressure` (10) and `intermolecular` (3) in the published bank. The replacement keeps the cognitive demand — the question must still go beyond recall — while pointing the model at the source for its raw material.

**Files:**
- Modify: `question_generation/services/question_generator.py:43-74` (`PROMPT_TEMPLATES`)
- Test: `question_generation/test_structured_generation.py`

**Interfaces:**
- Consumes: nothing new. `_build_prompt(content, thinking_order, format_split, correction="")` already formats these templates and appends the CRAG correction before the JSON contract.
- Produces: no signature change. `{grounding_rule}` is **not** a new format field — the rule is written inline in each template, because `_build_prompt` passes a fixed set of keys and adding one would break any caller that formats a template directly.

- [ ] **Step 1: Write the failing test**

Add to `question_generation/test_structured_generation.py`:

Note the file's existing style: `SimpleTestCase` (these touch no database) and
the module accessor `qg`, both already imported at the top of the file.

```python
class PromptGroundingTests(SimpleTestCase):
    """The prompt must forbid outside knowledge, not merely invite grounding.

    Measured on topic 276 before this: 61 of 76 questions used words absent
    from every source PDF, and two marked "plasma" correct where the source
    says gas and solid.
    """

    def one_line(self, thinking_order):
        prompt = qg._build_prompt(
            "Solids keep their shape.", thinking_order, {"MCQ": 1},
        )
        return " ".join(prompt.split())

    def test_both_orders_forbid_facts_the_content_does_not_state(self):
        for order in ("LOT", "HOT"):
            with self.subTest(order=order):
                prompt = self.one_line(order)
                self.assertIn("ONLY the facts stated in the content", prompt)
                self.assertIn("Do not add facts", prompt)

    def test_both_orders_forbid_options_the_content_does_not_support(self):
        for order in ("LOT", "HOT"):
            with self.subTest(order=order):
                self.assertIn(
                    "Every choice must use words and ideas from the content",
                    self.one_line(order),
                )

    def test_hot_no_longer_steers_the_model_away_from_the_content(self):
        """The old line 'Do NOT ask for a fact that is stated word-for-word'
        left the model nowhere to go but its own knowledge."""
        prompt = self.one_line("HOT")
        self.assertNotIn("stated word-for-word", prompt)
        self.assertIn("combine two or more facts", prompt)

    def test_hot_still_demands_reasoning_beyond_recall(self):
        self.assertIn("BEYOND recall", self.one_line("HOT"))
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
python manage.py test question_generation.test_structured_generation.PromptGroundingTests -v 2
```

Expected: all four FAIL — the phrases are not in the current templates, and `stated word-for-word` is still present.

- [ ] **Step 3: Rewrite the templates**

Replace `PROMPT_TEMPLATES` in `question_generation/services/question_generator.py` (currently lines 43-74) with:

```python
# The grounding rule, shared by both thinking orders. Worded after
# course/variant_generator.py, which has carried the same prohibition since
# the version generator was written and does not drift off-source the way
# this one did. Stated as a prohibition, not an invitation: "answerable from
# the content" told the model what a good question looks like and left it
# free to use anything it knew.
_GROUNDING_RULE = (
    "Use ONLY the facts stated in the content below. Do not add facts, "
    "terms, examples, numbers, causes or categories the content does not "
    "state, even if you know them to be true. If the content does not "
    "settle something, do not ask about it.\n"
    "Every choice must use words and ideas from the content. A wrong choice "
    "must be wrong because the content says otherwise, not because it names "
    "something the lesson never mentions.\n"
)

PROMPT_TEMPLATES = {
    "LOT": (
        "You are a quiz maker. Given the content below, generate {count} questions.\n"
        + _GROUNDING_RULE +
        "Each question must be answerable DIRECTLY from the content. Ask the learner to "
        "recall a stated fact, show they understand what a concept means, or use a stated "
        "rule in a straightforward case.\n"
        "Do NOT ask the learner to compare two things, weigh trade-offs, judge which "
        "option is better, or justify a choice.\n\n"
        "{examples}\n\n"
        "{format_request}\n\n"
        "Content:\n{content}\n\n"
        "{format_instructions}\n\n"
        "Respond ONLY with valid JSON, no other text. Every question object must\n"
        "carry a \"format\" field saying which kind it is. Use this exact structure:\n"
        '{{"questions": [{question_schema}]}}'
    ),
    "HOT": (
        "You are a quiz maker. Given the content below, generate {count} questions.\n"
        + _GROUNDING_RULE +
        "Each question must require reasoning BEYOND recall or direct application. Build "
        "it by asking the learner to combine two or more facts the content states: "
        "compare two things it describes, work out a cause and effect it implies, or "
        "judge which of two stated options fits a situation.\n"
        "The answer must follow from the stated facts. Do not ask about a cause, "
        "comparison or consequence the content gives you no facts for.\n"
        "The question must still have ONE defensible correct answer.\n\n"
        "{examples}\n\n"
        "{format_request}\n\n"
        "Content:\n{content}\n\n"
        "{format_instructions}\n\n"
        "Respond ONLY with valid JSON, no other text. Every question object must\n"
        "carry a \"format\" field saying which kind it is. Use this exact structure:\n"
        '{{"questions": [{question_schema}]}}'
    ),
}
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
python manage.py test question_generation -v 1
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add question_generation/services/question_generator.py question_generation/test_structured_generation.py
git commit -m "Forbid outside knowledge in the question prompt

The prompt had no prohibition at all -- only the positive 'answerable
DIRECTLY from the content' -- while the variant generator has carried a
proper one since it was written. The HOT template was worse than silent:
'Do NOT ask for a fact that is stated word-for-word' pushed the model off
the source with nothing to fall back on but its own knowledge, which is
where temperature, pressure and intermolecular came from.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 3: Constrain `correct_answer` at decode time

**Why:** Ollama constrains the reply against a JSON schema while decoding, and the pipeline already relies on that for shape. But the one field where a wrong value does real harm is typed as *any string*:

```python
"correct_answer": {"type": "string"},
```

An enum makes an out-of-range answer physically impossible to emit rather than something to catch later. The enum is the union of both formats' legal values, because one call can return a mix of MCQ and TF items and Ollama applies one schema to every item in the array.

This does **not** make `plasma` impossible — `D` is a legal letter. It closes the narrower hole where the model answers with free text that `_validate_question` then has to guess at.

**Files:**
- Modify: `question_generation/services/question_generator.py:166-200` (`build_response_schema`)
- Test: `question_generation/test_structured_generation.py`

**Interfaces:**
- Consumes: `SUPPORTED_FORMATS = ("MCQ", "TF")`, already defined at line 122.
- Produces: `build_response_schema(format_split) -> dict`, unchanged signature. The returned dict gains an `enum` on `questions.items.properties.correct_answer`.

- [ ] **Step 1: Write the failing test**

Add to `question_generation/test_structured_generation.py`:

```python
class ResponseSchemaTests(SimpleTestCase):
    def answer_property(self, format_split):
        schema = qg.build_response_schema(format_split)
        return schema["properties"]["questions"]["items"]["properties"]["correct_answer"]

    def test_correct_answer_is_an_enum_not_a_free_string(self):
        """Ollama constrains the decode, so an illegal answer should be
        impossible to emit rather than something to catch afterwards."""
        self.assertIn("enum", self.answer_property({"MCQ": 2, "TF": 1}))

    def test_the_enum_covers_both_formats_in_a_mixed_call(self):
        """One call returns a mix, and Ollama applies one schema to every
        item, so the enum must be the union."""
        values = set(self.answer_property({"MCQ": 2, "TF": 1})["enum"])
        self.assertEqual(values, {"A", "B", "C", "D", "True", "False"})

    def test_a_true_false_only_call_still_allows_letters(self):
        """The format split is a request, not a contract -- a usable MCQ
        arriving in a TF-only call is accepted, so its letter must be legal."""
        values = set(self.answer_property({"TF": 3})["enum"])
        self.assertEqual(values, {"A", "B", "C", "D", "True", "False"})

    def test_explanation_is_required_so_the_model_must_justify_itself(self):
        schema = qg.build_response_schema({"MCQ": 1})
        self.assertIn("explanation", schema["properties"]["questions"]["items"]["required"])
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
python manage.py test question_generation.test_structured_generation.ResponseSchemaTests -v 2
```

Expected: all four FAIL — `correct_answer` has no `enum`, and `required` is `["question", "format", "correct_answer"]`.

- [ ] **Step 3: Constrain the schema**

In `question_generation/services/question_generator.py`, inside `build_response_schema`, replace the body from `formats = [...]` to the end of the return with:

```python
    formats = [fmt for fmt in SUPPORTED_FORMATS if format_split.get(fmt)]
    letter = {"type": "string"}
    # Every legal answer for either format, not just the ones requested: the
    # split is a request, not a contract (see generate_questions), so a usable
    # true/false item arriving in an MCQ-only call is kept -- and its answer
    # has to be legal for the schema to have let it through at all.
    answers = ["A", "B", "C", "D", "True", "False"]
    return {
        "type": "object",
        "properties": {
            "questions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "question": {"type": "string"},
                        "format": {"type": "string", "enum": formats or list(SUPPORTED_FORMATS)},
                        "choices": {
                            "type": "object",
                            "properties": {k: letter for k in ("A", "B", "C", "D")},
                        },
                        # Constrained at decode time so an out-of-range answer
                        # cannot be emitted. It does not stop a wrong letter --
                        # "D" is legal even when D says "plasma" -- which is
                        # what _validate_question and the CRAG gate are for.
                        "correct_answer": {"type": "string", "enum": answers},
                        "explanation": {"type": "string"},
                    },
                    # The explanation is required so the model has to state why
                    # its answer follows from the content. A model that cannot
                    # write one usually could not ground the question either.
                    "required": ["question", "format", "correct_answer", "explanation"],
                },
            },
        },
        "required": ["questions"],
    }
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
python manage.py test question_generation -v 1
```

Expected: PASS.

- [ ] **Step 5: Verify Ollama accepts the schema against the real model**

```bash
python -c "
import os, sys, django
sys.path.insert(0, 'C:/MAVIA/backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings'); django.setup()
from question_generation.services.question_generator import generate_questions
out = generate_questions(
    'A solid keeps its shape. A liquid takes the shape of its container.',
    'LOT', {'MCQ': 2, 'TF': 1})
for q in out:
    print(q['format'], repr(q['correct_answer']), '|', q['question'][:60])
"
```

Expected: 1-3 questions, every `correct_answer` one of `A B C D True False`. If Ollama returns an error mentioning the schema, the enum is malformed — do not proceed.

- [ ] **Step 6: Commit**

```bash
git add question_generation/services/question_generator.py question_generation/test_structured_generation.py
git commit -m "Constrain the answer field at decode time

correct_answer was typed as any string in the schema Ollama decodes
against, on the one field where a wrong value reaches a learner. An enum
of both formats' legal values makes an out-of-range answer impossible to
emit, and requiring the explanation makes the model state why its answer
follows from the content.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 4: Make `_validate_question` validate

**Why:** Its docstring claims it rejects "hallucinated answers," but the whole MCQ check is:

```python
if answer in choices:
    q["correct_answer"] = answer
    return True
```

`"D" in choices` is True, so `D) plasma` was accepted. It never looks at what the option *says*. The TF branch is worse — it accepts any string that reads `true` or `false`, with no check that the stem is a proposition, which is how Q108 (*"...what is the shape of the particles?"* → `True`) reached the bank.

This task cannot check *correctness* — that needs the source, which is CRAG's job. It checks the things that are decidable from the question alone and are currently unchecked:

- an MCQ with fewer than two distinct options is not a choice
- an MCQ whose options repeat is not a choice
- a TF stem that opens with a wh-word is not a statement

**Files:**
- Modify: `question_generation/services/question_generator.py:224-251` (`_validate_question`)
- Create: `question_generation/test_question_validation.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `_validate_question(q, format_type) -> bool`, unchanged signature and unchanged side effect (it normalises `q["correct_answer"]` in place). Called only from `generate_questions` at line 487.

- [ ] **Step 1: Write the failing tests**

Create `question_generation/test_question_validation.py`:

```python
"""Structural validation of a generated question.

What is decidable from the question alone. Whether the answer is *correct*
needs the source text and belongs to the CRAG gate (services/grounding.py);
nothing here consults it.
"""

from django.test import SimpleTestCase

from question_generation.services.question_generator import _validate_question


class MultipleChoiceValidationTests(SimpleTestCase):
    def test_a_letter_present_in_the_choices_is_accepted(self):
        q = {"question": "Which state?", "correct_answer": "C",
             "choices": {"A": "solid", "B": "liquid", "C": "gas"}}
        self.assertTrue(_validate_question(q, "MCQ"))
        self.assertEqual(q["correct_answer"], "C")

    def test_an_answer_given_as_choice_text_is_recovered(self):
        """The model often answers with the option rather than its letter.
        This recovery already existed and must survive the rewrite."""
        q = {"question": "Which state?", "correct_answer": "gas",
             "choices": {"A": "solid", "B": "liquid", "C": "gas"}}
        self.assertTrue(_validate_question(q, "MCQ"))
        self.assertEqual(q["correct_answer"], "C")

    def test_a_letter_absent_from_the_choices_is_rejected(self):
        q = {"question": "Which state?", "correct_answer": "D",
             "choices": {"A": "solid", "B": "liquid", "C": "gas"}}
        self.assertFalse(_validate_question(q, "MCQ"))

    def test_repeated_options_are_rejected(self):
        """Two identical options mean the learner cannot be wrong, or cannot
        be right -- either way it is not a question."""
        q = {"question": "Which state?", "correct_answer": "A",
             "choices": {"A": "gas", "B": "gas", "C": "gas"}}
        self.assertFalse(_validate_question(q, "MCQ"))

    def test_a_single_option_is_rejected(self):
        q = {"question": "Which state?", "correct_answer": "A",
             "choices": {"A": "gas"}}
        self.assertFalse(_validate_question(q, "MCQ"))

    def test_a_blank_option_is_rejected(self):
        q = {"question": "Which state?", "correct_answer": "A",
             "choices": {"A": "gas", "B": "   ", "C": "solid"}}
        self.assertFalse(_validate_question(q, "MCQ"))

    def test_missing_choices_are_rejected(self):
        q = {"question": "Which state?", "correct_answer": "A"}
        self.assertFalse(_validate_question(q, "MCQ"))


class TrueFalseValidationTests(SimpleTestCase):
    def test_a_statement_is_accepted(self):
        q = {"question": "A pencil has a definite shape.", "correct_answer": "true"}
        self.assertTrue(_validate_question(q, "TF"))
        self.assertEqual(q["correct_answer"], "True")

    def test_a_wh_question_is_rejected(self):
        """Q108 on topic 276, verbatim: a true/false item whose stem asks an
        open question. There is no proposition for True to be true of."""
        q = {"question": "In the arrangement that shows particles close "
                         "together but able to move, what is the shape of "
                         "the particles?",
             "correct_answer": "True"}
        self.assertFalse(_validate_question(q, "TF"))

    def test_every_wh_opener_is_rejected(self):
        for opener in ("What", "Which", "How", "Why", "Who", "Where", "When"):
            with self.subTest(opener=opener):
                q = {"question": f"{opener} is the state of matter?",
                     "correct_answer": "True"}
                self.assertFalse(_validate_question(q, "TF"))

    def test_a_statement_merely_containing_a_wh_word_is_kept(self):
        """Only the opener decides. 'Water takes the shape of whatever
        container holds it' is a statement."""
        q = {"question": "Water takes the shape of whatever container holds it.",
             "correct_answer": "True"}
        self.assertTrue(_validate_question(q, "TF"))

    def test_a_non_boolean_answer_is_rejected(self):
        q = {"question": "A pencil has a definite shape.", "correct_answer": "A"}
        self.assertFalse(_validate_question(q, "TF"))


class SharedValidationTests(SimpleTestCase):
    def test_a_question_with_no_text_is_rejected(self):
        q = {"correct_answer": "True"}
        self.assertFalse(_validate_question(q, "TF"))

    def test_a_question_with_no_answer_is_rejected(self):
        q = {"question": "A pencil has a definite shape."}
        self.assertFalse(_validate_question(q, "TF"))
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
python manage.py test question_generation.test_question_validation -v 2
```

Expected: 6 FAIL (repeated options, single option, blank option, the wh-question cases) and the rest PASS. The passing ones pin behavior that must not regress.

- [ ] **Step 3: Rewrite the validator**

Replace `_validate_question` in `question_generation/services/question_generator.py` (currently lines 224-251) with:

```python
# A true/false item is a statement the learner judges. A stem opening with one
# of these is an open question, and "True" answers nothing about it. Measured
# on topic 276: Q108 asked "...what is the shape of the particles?" and was
# answered True. Only the opening word is checked -- "Water takes the shape of
# whatever container holds it" is a perfectly good statement.
_OPEN_QUESTION_OPENERS = (
    "what", "which", "how", "why", "who", "whom", "where", "when",
)


def _validate_question(q, format_type):
    """Reject a question that is structurally unusable, whatever it says.

    Correctness is not decidable here -- that needs the source text, and is
    what services/grounding.py does. This checks only what the question
    itself settles, and normalises ``correct_answer`` in place when it can.
    """
    question_text = str(q.get("question") or "").strip()
    if not question_text or "correct_answer" not in q:
        return False

    answer = str(q["correct_answer"]).strip()
    if not answer:
        return False

    if format_type == "MCQ":
        choices = q.get("choices")
        if not isinstance(choices, dict) or not choices:
            return False

        texts = [str(text).strip() for text in choices.values()]
        # A blank option is unreadable aloud, and a repeated one means the
        # learner either cannot be wrong or cannot be right.
        if any(not text for text in texts):
            return False
        if len({text.casefold() for text in texts}) != len(texts):
            return False
        if len(texts) < 2:
            return False

        if answer in choices:
            q["correct_answer"] = answer
            return True
        # The model often answers with the choice text instead of the letter.
        for letter, text in choices.items():
            if str(text).strip().casefold() == answer.casefold():
                q["correct_answer"] = letter
                return True
        return False

    # TF
    if answer.lower() not in ("true", "false"):
        return False
    first_word = question_text.split()[0].strip("\"'([{").casefold()
    if first_word in _OPEN_QUESTION_OPENERS:
        return False
    q["correct_answer"] = answer.capitalize()
    return True
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
python manage.py test question_generation -v 1
```

Expected: PASS.

- [ ] **Step 5: Confirm against the published bank**

```bash
python -c "
import os, sys, django
sys.path.insert(0, 'C:/MAVIA/backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings'); django.setup()
from question_generation.models import GeneratedQuestion
from question_generation.services.question_generator import _validate_question
q = GeneratedQuestion.objects.filter(id=108).first()
if q:
    payload = {'question': q.question_text, 'correct_answer': q.correct_answer}
    print('Q108 accepted:', _validate_question(payload, 'TF'), '(expected False)')
else:
    print('Q108 no longer present -- regenerated. Skip.')
"
```

Expected: `Q108 accepted: False`, or the skip message if the topic has been regenerated since.

- [ ] **Step 6: Commit**

```bash
git add question_generation/services/question_generator.py question_generation/test_question_validation.py
git commit -m "Make the question validator actually validate

Its docstring claimed it rejected hallucinated answers; the whole MCQ
check was 'is this letter one of the keys', so D) plasma was accepted
without anyone reading what D said. True/false accepted any stem at all,
which is how a question ending 'what is the shape of the particles?' was
answered True. Correctness still belongs to the CRAG gate -- this rejects
what the question alone settles.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 5: Measure the effect

**Why:** Every earlier task is justified by a number measured on topic 276. This task produces the matching after-number, so the effect is reported rather than assumed. It writes no production code.

**Files:**
- Create: `question_generation/management/commands/measure_grounding.py`

**Interfaces:**
- Consumes: `question_generation.services.grounding.build_index(outline_node) -> TopicIndex`, `grounding.ungrounded_terms(question, index) -> [str]`.
- Produces: a management command, no importable API.

- [ ] **Step 1: Write the command**

Create `question_generation/management/commands/measure_grounding.py`:

```python
"""How grounded a topic's current question bank is.

Run before and after a regeneration to report the effect of a change rather
than assume it. Reads only -- it never writes or deletes a question.
"""

from collections import Counter

from django.core.management.base import BaseCommand

from lessons.models import OutlineNode
from question_generation.models import GeneratedQuestion
from question_generation.services import grounding


class Command(BaseCommand):
    help = "Report how much of a topic's question bank is grounded in its PDFs."

    def add_arguments(self, parser):
        parser.add_argument("outline_node_id", type=int)

    def handle(self, *args, **options):
        node = OutlineNode.objects.get(pk=options["outline_node_id"])
        index = grounding.build_index(node)
        questions = list(
            GeneratedQuestion.objects
            .filter(node__material__outline_node=node, status="final")
            .order_by("id")
        )
        if not questions:
            self.stdout.write("No final questions on this topic.")
            return

        novel_by_question = {q.id: grounding.ungrounded_terms(q, index) for q in questions}
        ungrounded = [q for q in questions if novel_by_question[q.id]]
        orders = Counter(q.thinking_order or "unclassified" for q in questions)
        terms = Counter(
            term for novel in novel_by_question.values() for term in novel
        )

        self.stdout.write(f"topic {node.id}: {node.title}")
        self.stdout.write(f"  index: {len(index.chunks)} passages, searchable={index.searchable}")
        self.stdout.write(f"  questions: {len(questions)}  ({dict(orders)})")
        self.stdout.write(
            f"  ungrounded: {len(ungrounded)}/{len(questions)} "
            f"({100 * len(ungrounded) // len(questions)}%)"
        )
        if terms:
            self.stdout.write(f"  most common out-of-corpus terms: {terms.most_common(10)}")
        for q in ungrounded[:15]:
            self.stdout.write(f"    Q{q.id} {novel_by_question[q.id][:5]} | {q.question_text[:70]}")
```

- [ ] **Step 2: Run it and record the number**

```bash
python manage.py measure_grounding 276
```

Expected: it runs without error and prints an ungrounded count. Record the number — it is the "after" figure for this plan.

- [ ] **Step 3: Commit**

```bash
git add question_generation/management/commands/measure_grounding.py
git commit -m "Add a command that measures how grounded a question bank is

Every change in this plan is justified by a number measured on topic 276.
This produces the matching after-number so the effect is reported rather
than assumed.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## After the plan: regenerate and compare

Not a task — a step for the human, because it costs an hour of LLM calls and rewrites live data.

1. Back up: `cp db.sqlite3 db.sqlite3.pre-generation-fix.YYYYMMDD`
2. `python manage.py measure_grounding 276` — record the before figure.
3. Regenerate topic 276 through the teacher UI, or with the session's `regen.py` harness.
4. `python manage.py measure_grounding 276` — record the after figure.
5. Compare against the strict-CRAG baseline already being measured: per-concept yield, LOT/HOT split, and how many concepts end empty.

**Kill regeneration by PID, not by stopping the shell.** A background shell's death does not kill its Python child; during this session that left two runs writing to `db.sqlite3` at once and silently corrupted a measurement. Verify with `Get-CimInstance Win32_Process -Filter "Name='python.exe'"`.

## Deferred — considered and not included

- **A required `supporting_sentence` field**, quoted from the content, verified as a near-match of the source before the question is accepted. The strongest generation-time defence available and cheap to check, but it overlaps Tasks 3 and 4 and changes what the model must produce. Worth doing after this plan's effect is measured, so its contribution can be told apart.
- **Lowering `QUESTION_TEMPERATURE` from 0.7.** Plausible, unmeasured, and one variable at a time.
- **Relaxing the CRAG gate** — explicitly rejected by the user. The gate is the specification.
