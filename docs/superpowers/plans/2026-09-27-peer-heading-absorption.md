# Peer Heading Absorption Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop a heading being absorbed into the concept above it when it merely shares a word rather than naming it, and keep a split definition's term in the text a learner receives.

**Architecture:** Two independent changes inside `lessons/services/content_generator.py`. The first narrows the heading-absorption test from "shares any word with the open concept" to "contains the whole of its title" — a sub-heading names its parent, a sibling merely brushes against it. The second makes `_inline_definition_split` return content that still opens with its term. Neither adds a new subsystem, both narrow existing behaviour, and neither reads font metrics.

**Tech Stack:** Python 3.12, Django, `python manage.py test` (Django test runner — there is no pytest in this project), PyMuPDF for block extraction.

**Spec:** `docs/superpowers/specs/2026-09-27-peer-heading-absorption-design.md`

## Global Constraints

- Test runner is `python manage.py test` from `backend/`. Never `pytest`.
- The decision must rest on the titles alone, so it behaves identically whether or not a PDF carries font metrics. Blocks in existing tests carry `is_bold` but no `font_size`; every one of those tests must pass untouched.
- A numbered heading already bypasses absorption via `not _section_heading_title(text)`. Do not alter that path.
- Do not use `font_size`, `is_bold` or `text_color` to decide heading rank. That approach was tried and rejected — Task 1 Step 7 holds the case that kills it.
- Leave the `len(title_words) <= 3` limit in `_heading_refers_to_current_concept` alone. It is what stops a long section heading absorbing the rest of the document.
- Do not fix the three `Key idea` objects with empty `section_title`. The spec records it as a known defect and forbids fixing it blind.

## Review Focus

1. **A PDF with flat styling** — every heading one size and weight, no colour. Nothing visual separates parent from child, so a genuine sub-heading must still be absorbed on the strength of its title alone. This is the case that rejected the earlier font-signature design. Covered in Task 1, Step 7.
2. **Two headings sharing no word** — must be unaffected; they were never absorbed and must still each open an object. Covered in Task 1, Step 6.
3. **A parent title of four or more content words** — the `<= 3` limit still applies, so such a parent absorbs nothing regardless of containment. Unchanged by this task and deliberately left alone; that limit is what keeps a long section heading from swallowing the document.
4. **A plural parent naming a singular child** — `Solids` folds to `solid`, so `Particles in a Solid` must still contain it. Covered in Task 1, Step 8.
5. **A definition whose body is empty or whose separator is absent** — `_inline_definition_split` already returns `None` for these; Change 2 must not make it return a title-only string. Covered in Task 2, Step 7.

## Fixtures verified before this plan was written

Every block fixture below was run through the real
`build_learning_objects_from_pdf_blocks` on 2026-09-27, against unmodified code:

```
defect (expect 1 object, absorbed)         -> ['Comparing the Three States']
                                                content contains "How Matter Changes State:"
headings sharing no word (expect 2)        -> ['Solids', 'Liquids']
true sub-heading (expect 1, absorbed)      -> ['Solids']
flat-styled sub-heading (expect 1)         -> ['Solids']
```

So Task 1's first test genuinely reproduces the production defect from synthetic
blocks, and the tests that must *not* change already behave as asserted.

The containment rule was then run end to end against material 49's real PDF,
with `_heading_refers_to_current_concept` patched in memory:

```
BEFORE  Melting / Freezing / Evaporation / Condensation -> 'Comparing the Three States'
        (and no "How Matter Changes State" object at all)
AFTER   How Matter Changes State -> its own object
        Melting / Freezing / Evaporation / Condensation -> 'How Matter Changes State'
        flat-styled sub-heading still absorbs correctly
```

The predicted failures in this plan are measured, not guessed.

## File Structure

| File | Responsibility |
|---|---|
| `backend/lessons/services/content_generator.py` | Modify. One operator in `_heading_refers_to_current_concept`; the separator capture in `_inline_definition_split`. |
| `backend/lessons/test_peer_headings.py` | Create. Everything about rank-guarded absorption. |
| `backend/lessons/test_definition_terms.py` | Create. Everything about a definition keeping its term. |

Two new focused test files rather than growing `lessons/tests.py` (4900+ lines), matching the project's existing pattern of `test_label_corroboration.py`, `test_mutual_match.py`, `test_section_parents.py`.

---

### Task 1: A sub-heading must name its parent

**Files:**
- Modify: `backend/lessons/services/content_generator.py` — the return line of `_heading_refers_to_current_concept`, one operator
- Test: `backend/lessons/test_peer_headings.py` (create)

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces: nothing other tasks use. `_heading_refers_to_current_concept(current: dict, heading: str) -> bool` keeps its signature; only its verdict narrows.

- [ ] **Step 1: Record the baseline**

```bash
cd backend && python manage.py test lessons 2>&1 | tail -5
```

Expected: a passing run. Record the test count. If anything already fails, stop and report rather than proceeding — you need a clean baseline to attribute later failures.

- [ ] **Step 2: Write the failing test**

Create `backend/lessons/test_peer_headings.py`:

```python
"""A sub-heading names its parent; a sibling merely brushes against it.

`_heading_refers_to_current_concept` absorbs a heading that shares ANY word with
the open concept. That is right for "Examples of Solids" under "Solids", which
contains the whole parent title. It is wrong for "How Matter Changes State"
under "Comparing the Three States", which shares only "state" -- and that is why
Melting, Freezing, Evaporation and Condensation inherited the wrong section.
"""

from django.test import SimpleTestCase

from .services.content_generator import build_learning_objects_from_pdf_blocks


def block(block_id, text, line_count=1, **extra):
    return {"block_id": block_id, "page": 1, "text": text, "line_count": line_count, **extra}


class PeerHeadingTests(SimpleTestCase):
    def titles(self, objects):
        return [item["title"] for item in objects]

    def test_a_heading_sharing_one_word_is_not_a_sub_heading(self):
        blocks = [
            block(1, "Comparing the Three States", is_bold=True),
            block(2, "The table below sets the three states side by side."),
            block(3, "How Matter Changes State", is_bold=True),
            block(4, "Matter can change from one state to another when heat is added."),
        ]

        objects = build_learning_objects_from_pdf_blocks(blocks, [])

        self.assertEqual(
            self.titles(objects),
            ["Comparing the Three States", "How Matter Changes State"],
        )
```

- [ ] **Step 3: Run it and watch it fail**

```bash
cd backend && python manage.py test lessons.test_peer_headings.PeerHeadingTests.test_a_heading_sharing_one_word_is_not_a_sub_heading -v 2
```

Expected: FAIL. The list is `['Comparing the Three States']` — the second heading was absorbed and its text appended as a part.

- [ ] **Step 4: Change the operator**

In `_heading_refers_to_current_concept`, the final line. Replace:

```python
    return bool(title_words and len(title_words) <= 3 and set(title_words) & heading_words)
```

with:

```python
    # Containment, not overlap. A sub-heading names its parent -- "Examples of
    # Solids" holds the whole of "Solids" -- where a sibling only brushes
    # against it: "How Matter Changes State" shares one word of "Comparing the
    # Three States", which reduces to exactly three and so slipped under the
    # limit below, letting "state" alone carry the decision.
    return bool(title_words and len(title_words) <= 3 and set(title_words) <= heading_words)
```

Also change the docstring's first line from `"""Use lexical overlap to keep concept-specific subheadings with a concept."""` to `"""Keep a subheading with the concept whose title it names."""`

- [ ] **Step 5: Run the test to verify it passes**

```bash
cd backend && python manage.py test lessons.test_peer_headings -v 2
```

Expected: PASS.

- [ ] **Step 6: Add the genuine sub-heading tests**

Append to `PeerHeadingTests`:

```python
    def test_a_sub_heading_naming_its_parent_is_still_absorbed(self):
        blocks = [
            block(1, "Solids", is_bold=True),
            block(2, "In a solid, particles are packed tightly together."),
            block(3, "Examples of Solids", is_bold=True),
            block(4, "An ice cube, a wooden block, and a rock are all solids."),
        ]

        objects = build_learning_objects_from_pdf_blocks(blocks, [])

        self.assertEqual(self.titles(objects), ["Solids"])
        self.assertIn("Examples of Solids:", objects[0]["content"])

    def test_two_headings_sharing_no_word_are_unaffected(self):
        blocks = [
            block(1, "Solids", is_bold=True),
            block(2, "In a solid, particles are packed tightly together."),
            block(3, "Liquids", is_bold=True),
            block(4, "In a liquid, particles slide past one another freely."),
        ]

        objects = build_learning_objects_from_pdf_blocks(blocks, [])

        self.assertEqual(self.titles(objects), ["Solids", "Liquids"])
```

- [ ] **Step 7: Add the flat-styling test (Review Focus 1)**

This is the case that rejected the earlier font-signature design. It must keep working.

```python
    def test_a_sub_heading_styled_exactly_like_its_parent_is_still_absorbed(self):
        # A plainly-formatted PDF renders every heading at one size and weight,
        # with no colour. Nothing visual distinguishes parent from child, so the
        # decision has to come from the titles themselves.
        flat = {"font_size": 14.0, "is_bold": True, "text_color": 0}
        body = {"font_size": 11.0, "is_bold": False, "text_color": 0}
        blocks = [
            block(1, "Solids", **flat),
            block(2, "In a solid, particles are packed tightly together.", **body),
            block(3, "Examples of Solids", **flat),
            block(4, "An ice cube, a wooden block, and a rock are all solids.", **body),
        ]

        objects = build_learning_objects_from_pdf_blocks(blocks, [])

        self.assertEqual(self.titles(objects), ["Solids"])
```

- [ ] **Step 8: Add the plural-folding test (Review Focus 4)**

```python
    def test_containment_survives_a_plural_parent(self):
        # "Solids" folds to "solid", so a child naming "Solid" still contains it.
        blocks = [
            block(1, "Solids", is_bold=True),
            block(2, "In a solid, particles are packed tightly together."),
            block(3, "Particles in a Solid", is_bold=True),
            block(4, "Particles in a solid vibrate in place but do not move past each other."),
        ]

        objects = build_learning_objects_from_pdf_blocks(blocks, [])

        self.assertEqual(self.titles(objects), ["Solids"])
```

- [ ] **Step 8b: Pin the known soft spot (Review Focus 3)**

Containment is easy to satisfy when the parent's title is one word. This test
records the behaviour rather than claiming it is ideal, so that if it is ever
judged wrong there is a named test to change.

```python
    def test_a_one_word_parent_absorbs_a_heading_that_names_it(self):
        # Soft spot, pinned deliberately: a single-word parent is contained by
        # anything mentioning it, so "States of Matter" folds into "Matter".
        # Arguably they are siblings. If that is ever judged wrong, this is the
        # test to change -- the rule is doing exactly what it says.
        blocks = [
            block(1, "Matter", is_bold=True),
            block(2, "Matter is anything that has mass and takes up space."),
            block(3, "States of Matter", is_bold=True),
            block(4, "Matter is found as a solid, a liquid, or a gas in everyday life."),
        ]

        objects = build_learning_objects_from_pdf_blocks(blocks, [])

        self.assertEqual(self.titles(objects), ["Matter"])
```

- [ ] **Step 9: Run all six and verify they pass**

```bash
cd backend && python manage.py test lessons.test_peer_headings -v 2
```

Expected: 6 tests, all PASS.

- [ ] **Step 10: Run the whole lessons suite**

```bash
cd backend && python manage.py test lessons 2>&1 | tail -5
```

Expected: the Step 1 baseline count plus 6, all passing. The existing `lessons.tests` test named `test_numbered_concept_keeps_its_subheadings_and_short_bullet_examples` must still pass — `Particles in a Solid` and `Examples of Solids` both contain their parent `Solid`.

If any other test fails, read it before changing it. A test asserting that a heading sharing *one* word gets absorbed is asserting the behaviour this task removes; anything else is a real regression — stop and report.

- [ ] **Step 11: Commit**

```bash
cd backend && git add lessons/services/content_generator.py lessons/test_peer_headings.py
git commit -F - <<'COMMITMSG'
Absorb a sub-heading only when it names its parent

_heading_refers_to_current_concept absorbed any heading sharing one word
with the open concept. "Comparing the Three States" reduces to exactly
three content words, so it slipped under the <= 3 limit, and "state"
alone was enough to swallow "How Matter Changes State" -- leaving
Melting, Freezing, Evaporation and Condensation under the wrong section
and the concept that owns them with no object at all.

A real sub-heading names its parent: "Examples of Solids" contains the
whole of "Solids". Requiring containment rather than overlap is wrong on
0 of the 8 real pairs, where overlap is wrong on 1.

Deliberately uses no font metrics. Comparing style signatures was tried
first and rejected: a plainly-styled PDF with one heading size and no
colour would have had its genuine sub-headings split out, breaking the
case this rule exists for.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
COMMITMSG
```

---

### Task 2: A split definition keeps its term

**Files:**
- Modify: `backend/lessons/services/content_generator.py` (`_inline_definition_split`, lines 1158-1179)
- Test: `backend/lessons/test_definition_terms.py` (create)

**Interfaces:**
- Consumes: nothing from Task 1.
- Produces: `_inline_definition_split(text: str) -> tuple[str, str] | None` — unchanged signature, changed second element. `_definition_split` and every caller are unaffected.

- [ ] **Step 1: Write the failing test**

Create `backend/lessons/test_definition_terms.py`:

```python
"""A learner must never receive a definition stripped of the term it defines.

A version's text is built from each object's `content` alone -- `bundle_segments`
takes `clip["narration"] or item.content`, and a segment is {text, audio_url}
with no title field. So a term left behind in `title` is never delivered:
"Melting" reaches the learner as "solid to liquid, caused by adding heat."
"""

from django.test import SimpleTestCase

from .services.content_generator import _inline_definition_split


class DefinitionTermTests(SimpleTestCase):
    def test_a_dash_definition_keeps_its_term_and_spacing(self):
        title, content = _inline_definition_split(
            "● Melting — solid to liquid, caused by adding heat."
        )

        self.assertEqual(title, "Melting")
        self.assertEqual(content, "Melting — solid to liquid, caused by adding heat.")
```

- [ ] **Step 2: Run it and watch it fail**

```bash
cd backend && python manage.py test lessons.test_definition_terms -v 2
```

Expected: FAIL. `content` is `'solid to liquid, caused by adding heat.'`.

- [ ] **Step 3: Capture the separator and rejoin**

In `_inline_definition_split`, capture the separator group and build the content from it. The whole function after the change:

```python
def _inline_definition_split(text: str) -> tuple[str, str] | None:
    text = _strip_leading_bullet_marker_lines(text)
    text = re.sub(r"\s+", " ", text or "").strip()
    first_token, separator, remainder = text.partition(" ")
    if separator and _is_standalone_bullet_marker(first_token):
        text = remainder.strip()
    if not text or len(text) > 700:
        return None
    match = re.match(
        r"^(?:(?:\d+[\.\)]|[\-\*•●])\s*)?([A-Z][A-Za-z0-9 /,&()]{1,70})\s*([:\-–—])\s+(.+)$",
        text,
    )
    if not match:
        return None
    title = match.group(1).strip(" .:-–—")
    content = match.group(3).strip()
    if not title or not content or len(content.split()) < 3:
        return None
    if _is_admin_or_system_support_text(title):
        return None
    # The term travels with its definition. A version's text is built from
    # `content` alone, so a term left only in `title` never reaches a learner.
    # The regex ate the whitespace around the separator; a dash takes a space on
    # both sides, a colon only after.
    mark = match.group(2)
    joined = f"{title}{mark} {content}" if mark == ":" else f"{title} {mark} {content}"
    return title[:255], joined
```

Note the capture group renumbering: the definition body is now group **3**, not group 2.

- [ ] **Step 4: Run the test to verify it passes**

```bash
cd backend && python manage.py test lessons.test_definition_terms -v 2
```

Expected: PASS.

- [ ] **Step 5: Add the colon form**

```python
    def test_a_colon_definition_keeps_its_term_without_an_extra_space(self):
        title, content = _inline_definition_split(
            "Everyday examples: ice cubes, a wooden chair, a rock, a coin, and a book."
        )

        self.assertEqual(title, "Everyday examples")
        self.assertEqual(
            content,
            "Everyday examples: ice cubes, a wooden chair, a rock, a coin, and a book.",
        )
```

- [ ] **Step 6: Add the callout form**

```python
    def test_a_key_idea_callout_keeps_its_label(self):
        title, content = _inline_definition_split(
            "Key idea: cooling a gas slows its particles down until they form a liquid."
        )

        self.assertEqual(title, "Key idea")
        self.assertTrue(content.startswith("Key idea: cooling a gas"))
```

- [ ] **Step 7: Add the rejection tests (Review Focus 5)**

```python
    def test_text_with_no_separator_is_still_not_a_definition(self):
        self.assertIsNone(
            _inline_definition_split("A solid has a definite shape and a definite volume.")
        )

    def test_a_definition_with_too_short_a_body_is_still_rejected(self):
        self.assertIsNone(_inline_definition_split("Melting — heat"))
```

- [ ] **Step 8: Run all five and verify they pass**

```bash
cd backend && python manage.py test lessons.test_definition_terms -v 2
```

Expected: 6 tests, all PASS.

- [ ] **Step 9: Run the whole lessons suite**

```bash
cd backend && python manage.py test lessons 2>&1 | tail -5
```

Expected: all passing. Pay attention to any test asserting on a definition object's `content` — `lessons/tests.py` has several. If one fails because the content now opens with its term, that is this change working; update the expectation and say so in the commit. If one fails for any other reason, stop and report.

- [ ] **Step 10: Commit**

```bash
cd backend && git add lessons/services/content_generator.py lessons/test_definition_terms.py
git commit -m "Keep a definition's term in the text a learner receives

A version's text is built by bundle_segments from content alone, and a
segment is {text, audio_url} with no title field, so a term split into
`title` is never delivered: \"Melting\" reaches a learner as \"solid to
liquid, caused by adding heat.\" Already true today for every Label:
value pair; it becomes obvious once several sit in one telling.

_inline_definition_split now captures its separator and returns content
that still opens with the term. Fixed here rather than at render time so
text, narration, audio and captions stay in agreement -- the invariant
_version_from_segments states.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 3: Acceptance on the real PDFs

**Files:**
- Create: a throwaway script in the scratchpad directory. **Nothing in this task is committed to the repo.**

**Interfaces:**
- Consumes: both changes from Tasks 1 and 2.
- Produces: a pass/fail report for the human partner. No code.

- [ ] **Step 1: Assert the real builder against the real PDF**

Write to the scratchpad (not the repo):

```python
import sys; sys.path.insert(0, 'C:/MAVIA/backend')
import os, django, io
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from lessons.models import LearningMaterial
from lessons.services.instructional_content_classifier import extract_pdf_text_blocks
from lessons.services.content_generator import (
    extract_instructional_pdf_tables, exclude_text_blocks_inside_tables,
    build_learning_objects_from_pdf_blocks,
)

m = LearningMaterial.objects.get(id=49)
imgs = (m.generated_json or {}).get("image_descriptions") or []
blocks = extract_pdf_text_blocks(m.pdf_file.path)
kept = exclude_text_blocks_inside_tables(blocks, extract_instructional_pdf_tables(m.pdf_file.path))
objs = build_learning_objects_from_pdf_blocks(kept, imgs)

titles = [o["title"] for o in objs]
by_title = {o["title"]: o for o in objs}
print("objects:", len(objs))

assert "How Matter Changes State" in titles, "the heading still is not its own object"
for term in ("Melting", "Freezing", "Evaporation", "Condensation"):
    assert term in titles, f"{term} is missing"
    got = by_title[term]["section_title"]
    assert got == "How Matter Changes State", f"{term} has section {got!r}"
    assert by_title[term]["content"].startswith(term), f"{term} content lost its term"
for o in objs:
    assert not o["content"].startswith("How Matter Changes State:"), \
        f"{o['title']!r} still swallowed the heading"
print("ALL ACCEPTANCE CHECKS PASSED")
```

- [ ] **Step 2: Run it**

Expected: `ALL ACCEPTANCE CHECKS PASSED`. If any assertion fires, **stop and report to the human partner** — do not adjust the assertions to make them pass. They are the spec's acceptance criteria 1, 2, 3 and 6.

- [ ] **Step 3: Check materials 46 and 48 for regression**

Run the same build for materials 46 and 48 and print each object's title and `section_title`. Compare against what is in the database today:

```bash
cd backend && python manage.py shell -c "
from lessons.models import LearningObject
for mid in (46, 48):
    print('=== material', mid)
    for lo in LearningObject.objects.filter(material_id=mid).order_by('order'):
        print('  %-38s %r' % (lo.title[:38], lo.section_title))
"
```

Expected: section structure and object boundaries match. Their `content` will differ — Task 2 changes it — which is spec acceptance criterion 5. Report any section-structure difference rather than accepting it.

- [ ] **Step 4: Report and stop**

Report to the human partner:
- the acceptance result,
- how many objects material 49 now produces versus 16 today,
- any difference in materials 46 and 48.

**Do not regenerate any material.** Re-extraction rewrites objects, discards teacher review state and deletes that material's generated questions — measured on 2026-09-27, regenerating material 49 deleted 9. That is the human partner's decision, and the spec's acceptance criteria 4 (the path falling from 19 steps) cannot be checked until they take it.
