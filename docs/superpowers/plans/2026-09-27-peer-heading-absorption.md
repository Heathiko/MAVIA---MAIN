# Peer Heading Absorption Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop a heading being absorbed into the concept above it when the two are visual peers, and keep a split definition's term in the text a learner receives.

**Architecture:** Two independent changes inside `lessons/services/content_generator.py`. The first adds a rank guard to the existing lexical-overlap absorption test, using the `(font_size, is_bold, text_color)` signature already recorded on every block: two headings a document styles identically are siblings, so a shared word between them is coincidence, not subordination. The second makes `_inline_definition_split` return content that still opens with its term. Neither adds a new subsystem; both narrow existing behaviour.

**Tech Stack:** Python 3.12, Django, `python manage.py test` (Django test runner — there is no pytest in this project), PyMuPDF for block extraction.

**Spec:** `docs/superpowers/specs/2026-09-27-peer-heading-absorption-design.md`

## Global Constraints

- Test runner is `python manage.py test` from `backend/`. Never `pytest`.
- Behaviour must be **unchanged when font metrics are absent**. Blocks in existing tests carry `is_bold` but no `font_size`; every one of those tests must pass untouched.
- A numbered heading already bypasses absorption via `not _section_heading_title(text)`. Do not alter that path.
- Working keys on the `current` dict must be removed in `_finalize_current_learning_object` before the object is appended, alongside `parts`, `has_supporting_components`, `expected_enumerated_item` and `from_inline_definition`.
- Font sizes round to the nearest 0.5pt, matching the tolerance the existing section-close comparison already uses (`+ 0.5`).
- Do not fix the three `Key idea` objects with empty `section_title`. The spec records it as a known defect and forbids fixing it blind.

## Review Focus

1. **A block with `font_size: None`** (scanned PDF routed through transcription) — the signature is `None`, the guard must not fire, and absorption behaves exactly as today. Covered in Task 1, Step 9.
2. **The new working key leaking into the saved object** — `heading_signature` must not survive into the learning-object payload, or it reaches `LearningObject` creation as an unexpected field. Covered in Task 1, Step 11.
3. **Two peers that share no word** — the guard must not change them; they were never absorbed in the first place and must still each open an object. Covered in Task 1, Step 7.
4. **Fractional font differences** (15.0 versus 15.04 from PDF rounding) — must read as the same rank, not two. Covered in Task 1, Step 13.
5. **A definition whose content is empty or whose separator is absent** — `_inline_definition_split` already returns `None` for these; Change 2 must not make it return a title-only string. Covered in Task 2, Step 7.

## Fixtures verified before this plan was written

Every block fixture below was run through the real
`build_learning_objects_from_pdf_blocks` on 2026-09-27, against unmodified code:

```
defect (expect 1 object, absorbed)         -> ['Comparing the Three States']
                                                content contains "How Matter Changes State:"
peers, no shared word (expect 2)           -> ['Solids', 'Liquids']
true sub-heading (expect 1, absorbed)      -> ['Solids']
no font metrics (expect 1, absorbed)       -> ['Comparing the Three States']
```

So Task 1's first test genuinely reproduces the production defect from synthetic
blocks, and the three tests that must *not* change already behave as asserted.
The predicted failures in this plan are measured, not guessed.

## File Structure

| File | Responsibility |
|---|---|
| `backend/lessons/services/content_generator.py` | Modify. Add `_heading_style_signature` and `_same_heading_rank`; guard the absorption branch; record the signature on `current`; pop it on finalize; change `_inline_definition_split`. |
| `backend/lessons/test_peer_headings.py` | Create. Everything about rank-guarded absorption. |
| `backend/lessons/test_definition_terms.py` | Create. Everything about a definition keeping its term. |

Two new focused test files rather than growing `lessons/tests.py` (4900+ lines), matching the project's existing pattern of `test_label_corroboration.py`, `test_mutual_match.py`, `test_section_parents.py`.

---

### Task 1: Rank-guarded heading absorption

**Files:**
- Modify: `backend/lessons/services/content_generator.py` (add helpers near `_heading_refers_to_current_concept`; guard at line 2463-2474; `current` dict at 2501-2512; `_finalize_current_learning_object`)
- Test: `backend/lessons/test_peer_headings.py` (create)

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces: `_heading_style_signature(block: dict) -> tuple[float, bool, object] | None` and `_same_heading_rank(current: dict, block: dict) -> bool`. Task 2 does not use them.

- [ ] **Step 1: Record the baseline**

Run and write the number into the commit message later:

```bash
cd backend && python manage.py test lessons 2>&1 | tail -5
```

Expected: a passing run. Record the test count. If anything already fails, stop and report it rather than proceeding — you need a clean baseline to attribute later failures.

- [ ] **Step 2: Write the failing test for the real defect**

Create `backend/lessons/test_peer_headings.py`:

```python
"""A heading styled like its neighbour is a sibling, not a sub-heading.

`_heading_refers_to_current_concept` reads a shared word as subordination, so
"Particles in a Solid" folds into "1. Solid". That is right. It is wrong between
peers: "Comparing the Three States" swallowed "How Matter Changes State" because
both contain "state", and the four change-of-state terms below it inherited the
wrong section.
"""

from django.test import SimpleTestCase

from .services.content_generator import build_learning_objects_from_pdf_blocks

H2 = {"font_size": 15.0, "is_bold": True, "text_color": 2046052}
H3 = {"font_size": 12.5, "is_bold": True, "text_color": 3036053}
BODY = {"font_size": 11.0, "is_bold": False, "text_color": 0}


def block(block_id, text, style, line_count=1):
    return {"block_id": block_id, "page": 1, "text": text, "line_count": line_count, **style}


class PeerHeadingTests(SimpleTestCase):
    def titles(self, objects):
        return [item["title"] for item in objects]

    def test_a_peer_heading_sharing_a_word_opens_its_own_object(self):
        blocks = [
            block(1, "Comparing the Three States", H2),
            block(2, "The table below sets the three states side by side.", BODY),
            block(3, "How Matter Changes State", H2),
            block(4, "Matter can change from one state to another when heat is added.", BODY),
        ]

        objects = build_learning_objects_from_pdf_blocks(blocks, [])

        self.assertEqual(
            self.titles(objects),
            ["Comparing the Three States", "How Matter Changes State"],
        )
```

- [ ] **Step 3: Run it and watch it fail**

```bash
cd backend && python manage.py test lessons.test_peer_headings.PeerHeadingTests.test_a_peer_heading_sharing_a_word_opens_its_own_object -v 2
```

Expected: FAIL. The list is `['Comparing the Three States']` — the second heading was absorbed, and its text appended as a part.

- [ ] **Step 4: Add the two helpers**

In `content_generator.py`, directly above `def _heading_refers_to_current_concept`:

```python
def _heading_style_signature(block: dict) -> tuple | None:
    """A heading's visual rank, as the document itself styles it.

    ``None`` when the PDF carries no font metrics -- a transcribed scan, or a
    synthetic block in a test -- which is what keeps this inert wherever the
    evidence for it does not exist.
    """
    size = block.get("font_size")
    if not size:
        return None
    return (round(float(size) * 2) / 2, bool(block.get("is_bold")), block.get("text_color"))


def _same_heading_rank(current: dict, block: dict) -> bool:
    """Whether an incoming heading is the visual peer of the open concept's.

    Absorption reads a shared word as subordination, which is right for
    "Particles in a Solid" under "1. Solid". Two headings a document styles
    identically are siblings, so a word they happen to share is a coincidence of
    vocabulary rather than a parent-child relationship -- "Comparing the Three
    States" and "How Matter Changes State" both contain "state". Unknown rank on
    either side means today's behaviour, unchanged.
    """
    incoming = _heading_style_signature(block)
    return incoming is not None and incoming == current.get("heading_signature")
```

- [ ] **Step 5: Guard the absorption branch and record the signature**

At line 2463, add the guard as the second condition:

```python
        if heading_title:
            if current is not None and not _same_heading_rank(current, block) and (
                _current_concept_accepts_supporting_component(current, heading_title)
                or (
                    not _section_heading_title(text)
                    and _heading_refers_to_current_concept(current, heading_title)
                )
            ):
```

At the `current = {` dict built from a heading (line 2501), add one key after `"title"`:

```python
            current = {
                "order": len(learning_objects),
                "section_title": section_parent_title,
                "title": heading_title,
                # Working key: what rank the document gave this heading, so the
                # next one can tell subordination from coincidence. Popped in
                # _finalize_current_learning_object.
                "heading_signature": _heading_style_signature(block),
                "type": "lesson_content",
                "content": "",
                "source": "teacher_pdf",
                "source_page": block.get("page"),
                "source_block_id": block.get("block_id"),
                "source_excerpt": "",
```

- [ ] **Step 6: Run the test to verify it passes**

```bash
cd backend && python manage.py test lessons.test_peer_headings -v 2
```

Expected: PASS.

- [ ] **Step 7: Add the peers-sharing-no-word test**

Append to `PeerHeadingTests`:

```python
    def test_two_peers_sharing_no_word_are_unaffected(self):
        blocks = [
            block(1, "Solids", H2),
            block(2, "In a solid, particles are packed tightly together.", BODY),
            block(3, "Liquids", H2),
            block(4, "In a liquid, particles slide past one another freely.", BODY),
        ]

        objects = build_learning_objects_from_pdf_blocks(blocks, [])

        self.assertEqual(self.titles(objects), ["Solids", "Liquids"])
```

- [ ] **Step 8: Add the genuine sub-heading test**

```python
    def test_a_lower_rank_heading_sharing_a_word_is_still_absorbed(self):
        blocks = [
            block(1, "Solids", H2),
            block(2, "In a solid, particles are packed tightly together.", BODY),
            block(3, "Examples of Solids", H3),
            block(4, "An ice cube, a wooden block, and a rock are all solids.", BODY),
        ]

        objects = build_learning_objects_from_pdf_blocks(blocks, [])

        self.assertEqual(self.titles(objects), ["Solids"])
        self.assertIn("Examples of Solids:", objects[0]["content"])
```

- [ ] **Step 9: Add the no-font-metrics test (Review Focus 1)**

```python
    def test_absorption_is_unchanged_when_the_pdf_carries_no_font_metrics(self):
        # A transcribed scan has no sizes at all. The guard must not fire, so a
        # shared word still means subordination, exactly as before this change.
        plain = {"is_bold": True}
        blocks = [
            block(1, "Comparing the Three States", plain),
            block(2, "The table below sets the three states side by side.", {}),
            block(3, "How Matter Changes State", plain),
            block(4, "Matter can change from one state to another when heat is added.", {}),
        ]

        objects = build_learning_objects_from_pdf_blocks(blocks, [])

        self.assertEqual(self.titles(objects), ["Comparing the Three States"])
        self.assertIn("How Matter Changes State:", objects[0]["content"])
```

- [ ] **Step 10: Run all four and verify they pass**

```bash
cd backend && python manage.py test lessons.test_peer_headings -v 2
```

Expected: 4 tests, all PASS.

- [ ] **Step 11: Add the key-leak test (Review Focus 2)**

```python
    def test_the_rank_working_key_never_reaches_the_saved_object(self):
        blocks = [
            block(1, "Solids", H2),
            block(2, "In a solid, particles are packed tightly together.", BODY),
        ]

        objects = build_learning_objects_from_pdf_blocks(blocks, [])

        self.assertNotIn("heading_signature", objects[0])
```

- [ ] **Step 12: Run it, watch it fail, then pop the key**

```bash
cd backend && python manage.py test lessons.test_peer_headings.PeerHeadingTests.test_the_rank_working_key_never_reaches_the_saved_object -v 2
```

Expected: FAIL — `'heading_signature' unexpectedly found`.

Then in `_finalize_current_learning_object`, add one line beside the other working-key pops:

```python
    parts = current.pop("parts", [])
    current.pop("has_supporting_components", None)
    current.pop("expected_enumerated_item", None)
    current.pop("from_inline_definition", None)
    current.pop("heading_signature", None)
```

Re-run: expected PASS.

- [ ] **Step 13: Add the fractional-size test (Review Focus 4)**

```python
    def test_a_fractional_font_difference_still_reads_as_one_rank(self):
        # PyMuPDF averages span sizes, so the same authored style can arrive as
        # 15.0 on one heading and 15.04 on the next.
        blocks = [
            block(1, "Comparing the Three States", {**H2, "font_size": 15.04}),
            block(2, "The table below sets the three states side by side.", BODY),
            block(3, "How Matter Changes State", H2),
            block(4, "Matter can change from one state to another when heat is added.", BODY),
        ]

        objects = build_learning_objects_from_pdf_blocks(blocks, [])

        self.assertEqual(
            self.titles(objects),
            ["Comparing the Three States", "How Matter Changes State"],
        )
```

- [ ] **Step 14: Run the whole lessons suite**

```bash
cd backend && python manage.py test lessons 2>&1 | tail -5
```

Expected: the Step 1 baseline count plus 6, all passing. `lessons.tests.…test_numbered_concept_keeps_its_subheadings_and_short_bullet_examples` must still pass — its blocks have no `font_size`, so the guard is inert there.

- [ ] **Step 15: Commit**

```bash
cd backend && git add lessons/services/content_generator.py lessons/test_peer_headings.py
git commit -m "Stop a peer heading being absorbed by its neighbour

_heading_refers_to_current_concept reads a shared word as subordination,
which is right for \"Particles in a Solid\" under \"1. Solid\" and wrong
between siblings. On page 3 of Solid_Liquid_and_Gas.pdf the comparison
table's text rows are excluded, leaving \"Comparing the Three States\"
bodyless, and \"How Matter Changes State\" is then swallowed because both
titles contain \"state\" -- so Melting, Freezing, Evaporation and
Condensation inherited the wrong section.

Two headings a document styles identically are peers. The guard compares
the (font_size, is_bold, text_color) signature already recorded on every
block, and is inert when either side has no metrics, so tests built from
synthetic blocks are untouched.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
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

Expected: 5 tests, all PASS.

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
