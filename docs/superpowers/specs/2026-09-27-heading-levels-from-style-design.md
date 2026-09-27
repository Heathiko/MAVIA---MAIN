# Heading levels from style signatures

**Date:** 2026-09-27
**Status:** Draft, pending review
**Files touched:** `lessons/services/content_generator.py`,
`lessons/services/instructional_content_classifier.py` (read-only use),
`lessons/test_section_parents.py`

**Extends:** `2026-09-12-grouping-and-parent-headings-design.md`. That design is
not wrong; it is incomplete for a document class it did not have in hand.

## Problem

A PDF whose headings are not numbered is extracted completely flat. Every
learning object it produces carries `section_title=''`, so nothing records which
section any object belongs to, and each object becomes a concept of its own.

Topic 276 holds three PDFs of the same Grade 4 lesson. Two number their
headings; one does not.

| material | document | headings | `section_title` populated |
|---|---|---|---|
| 48 | `Solid-Liquid-Gas-2` | `1. What is Matter?`, `2. Solids` | yes |
| 49 | `Solid_Liquid_and_Gas` | `What Is Matter?`, `Solids` | **no — all 10 rows empty** |

### Root cause

`build_learning_objects_from_pdf_blocks` opens a section in exactly one place:

```python
if _section_heading_title(text):
    section_parent_title = (
        heading_title if _qualifies_as_section_parent(block) else ""
    )
```

`_section_heading_title` matches only a leading number:
`\s*\d+(?:\.\d+)*\.?\s+(.+?)\s*`. A heading that carries no number never enters
the branch, so `section_parent_title` is never assigned and stays empty for the
whole document.

This is the 2026-09-12 design working as specified. That spec chose the numbered
form deliberately, to keep assessment items (`1. ______ condense`, `9. Answer
Key`) from being promoted into sections. It assumed authored instructional
headings are numbered. Material 49 is a word-processor export that uses heading
*styles* instead, and the assumption does not hold for it.

### Consequences observed on topic 276

The teacher's gold map for this lesson (`gold_map_62.json`) has 7 concepts. The
published path has **19 steps**. Material 49 contributes most of the excess:
three separate `Key idea` concepts, and `Melting` / `Freezing` / `Evaporation` /
`Condensation` as four concepts of 37-41 characters each.

Question generation targets 6 questions per learning object, so it is asked to
write six questions from a 39-character concept. Of 240 questions targeted for
this topic, 41 survive validation and 22 can ever be served to a learner.

## The information is already extracted

`extract_pdf_text_blocks` records `font_size`, `is_bold` and `text_color` on
every block. Applying steps 1-4 above to all three of topic 276's PDFs gives a
top heading signature that is exactly the set of section headings in each:

| material | top signature | n | what it selects |
|---|---|---|---|
| 49 | `(15.0, bold, 2046052)` | 7 | What Is Matter? · Solids · Liquids · Gases · Comparing the Three States · How Matter Changes State · Review Questions |
| 48 | `(19.0, bold, 1192271)` | 9 | 1. What is Matter? · 2. Solids · 3. Liquids · … |
| 46 | `(16.0, bold, 0)` | 3 | Matter · Comparing the Three States · Everyday Examples |

Each document's title is the single largest signature and occurs exactly once
(17.0pt, 26.0pt and 22.0pt respectively), so step 3 discards it without any rule
about titles.

Material 48's top signature selects **9** headings where the document has 7
authored sections; the extra two are `8. Quick Check Questions` and `9. Answer
Key`. The 2026-09-12 category guard is what keeps them out, which is why Change
B retains it rather than replacing it.

These are word-processor exports, so the levels are real styles rather than
visual coincidence.

**Measurement caveat.** `_learning_object_heading_title` consults `category` and
`include_in_narration`, which are assigned by `classify_instructional_blocks` and
require the LLM. The figures above were produced with the structural half of that
test only (`_section_heading_title` or `_looks_like_plain_subtopic_heading`). The
category guard can only remove headings from the set, never add them, so the top
signature cannot change — but the counts may fall once classification runs.

`font_size` is already read by the block loop — but only to *close* a section
("a larger plain heading has returned to a higher visual level"), never to open
one. The mechanism for reasoning about visual level exists and is half-used.

## Goals

1. A document whose headings are not numbered produces the same section
   structure as one whose headings are.
2. Sub-headings and callouts become **parts of** their section, not peers of it.
3. Every learning object remains its own row. Nothing is merged away.
4. Material 48's current section structure does not change.
5. A learner never receives a definition stripped of the term it defines.

## Non-goals

- Merging learning objects. `Melting` and `Freezing` stay distinct objects, so a
  question can be generated from one and remediation can target one. Concept
  grouping is what joins them; this spec only stops them being *sections*.
- Fixing the block classifier's category assignment (see Risks).
- Changing question generation, grouping thresholds, or the learning-path
  criteria. Those consume `section_title`; none is edited here.

## Design

### Change A: derive a heading-level map per document

Before the block loop, scan the document once and identify its **top heading
signature**:

1. Take every block for which `_learning_object_heading_title(block)` returns a
   title. This spec introduces no new definition of "heading"; it reuses the
   existing one, so the only behaviour changed is which of those headings may
   *open a section*.
2. Round each one's `font_size` to the nearest 0.5pt and form the signature
   `(rounded_size, is_bold, text_color)`.
3. Discard any signature occurring exactly once. This drops the document title
   without needing a rule about titles — see the measurements below.
4. The largest surviving signature is the top heading signature.

Only the top signature is used. An earlier draft of this design ranked every
signature into a full level map; measuring it showed the lower ranks are noise
(review-question stems and table rows tie with real sub-headings), and nothing
in the design needs them. A heading either carries the top signature or it does
not.

The signature is computed per document and used only for that document. Nothing
is compared across documents and no absolute size threshold is introduced.

**A heading whose signature was dropped as a singleton does not open a section**
— it inherits the open one, exactly as a plain heading does today. Material 46's
`Learning Objectives:` is the observed case.

A document with no surviving signature has no top signature, and the numbered
rule applies unchanged.

### Change B: open a section by level, not by numbering

A heading opens a section when it carries the document's top heading signature.
Any other heading does not open one and inherits the open section, which is what
the code already does for plain headings.

**The 2026-09-12 guards are retained unchanged.** A heading may open a section
only when it is `category=lesson_content` and `include_in_narration=True`. The
numbered form stops being *required*; it does not stop being *sufficient*, so
material 48 behaves exactly as it does today.

### Why opening the section is the whole fix

The sub-headings are not headings, and do not need to be. Checked directly:

```
_looks_like_plain_subtopic_heading("Solids")                   -> 'Solids'
_looks_like_plain_subtopic_heading("How Matter Changes State") -> 'How Matter Changes State'
_looks_like_plain_subtopic_heading("Everyday examples")        -> None
_looks_like_plain_subtopic_heading("Key idea:")                -> None
_looks_like_plain_subtopic_heading("Key properties of solids") -> None
```

`Everyday examples`, `Key idea:` and the four change-of-state bullets reach the
object path as `Label: value` inline definitions, not as headings. The
2026-09-12 spec already routed that path to fall back to the section parent when
it has no sibling-run title of its own.

So that machinery is built and correct; it has simply never had a section parent
to fall back to in this document. Setting `section_parent_title` is therefore the
entire change — no new nesting mechanism is required, and the sub-headings cannot
disturb the top signature because they are not in the candidate set at all.

### Change D: a split definition keeps its term in the delivered text

Restoring nesting is necessary but not sufficient, and without this change it
makes delivery **worse**.

A version's text is built by `bundle_segments`, which takes
`clip["narration"] or item.content` — the object's `content` alone. A segment is
`{text, audio_url}`; there is no title field, so no reader can render the term
even if it wanted to. Today each change-of-state term is its own step and its
card heading supplies the label. Once the four become parts of one telling, only
`parts[0].title` survives as the step title and the learner receives:

```
Matter can change from one state to another when heat energy is added or removed...

solid to liquid, caused by adding heat.
liquid to solid, caused by removing heat.
liquid to gas, caused by adding heat.
gas to liquid, caused by removing heat.
```

Four unlabelled definitions with nothing saying which is melting.

This defect is **already live** wherever the extractor split a `Label: value`
pair — material 48's `Everyday examples` delivers `"ice cubes, a wooden chair, a
rock, a coin, and a book."` with no label today. Nesting only makes it obvious by
putting four in a row.

**The fix.** `_inline_definition_split` matches
`^(?:...)?([A-Z][A-Za-z0-9 /,&()]{1,70})\s*(?::|[-–—])\s+(.+)$` and returns
`(title, content)`, discarding the separator. Capture the separator and return
content that still opens with the term:

```
title   = "Melting"
content = "Melting — solid to liquid, caused by adding heat."
```

The term stays in `title` for display; the content becomes self-contained. This
reconstructs the source faithfully — `Key idea: solid particles are held in
place…` and `Everyday examples: ice cubes…` both return exactly as the PDF wrote
them, each keeping its own separator.

Fixing it here rather than at render time is what keeps text, narration, audio
and captions in agreement. `course/services.py::_version_from_segments` states
the invariant: text is derived from the segments "so a caption can never drift
from the wording the segment actually carries." Prefixing the title while joining
would break it — the audio clip would say one thing and the screen another.

**Open on real data.** `_multiline_definition_split` (two-column vocabulary rows)
has a line break where the inline form has a separator. Reconstructing those as
`term — definition` is the proposed default, but a newline inside one segment
reads as a paragraph break downstream, so this case must be checked against real
rows before it is settled rather than assumed.

### Change C: `_qualifies_as_section_parent` gains document context

This is an API change, and the main cost of the design.

The function currently decides from one block's `text`, `category` and
`include_in_narration`. Heading level cannot be derived from a single block — it
is a fact about that block's relationship to every other heading in the
document. The function therefore needs the level map passed in.

`lessons/test_section_parents.py::test_plain_heading_without_a_number_never_opens_a_section`
asserts today that `"Key properties"` does not qualify. That assertion is correct
in intent and must keep passing in substance: `Key properties of solids` is
14.5pt in material 48, below its 19.0pt level 1, so it is a sub-heading and must
not open a section. The test is rewritten to supply a level map rather than
deleted, and its name becomes `test_a_sub_level_heading_never_opens_a_section`.

`FlatDefinitionListTests` is unaffected by construction: peer glossary terms
share one signature, so they share one level, and none can parent the others.

## Blast radius

`section_title` feeds narration wording, M4 section-progression edges in
`learning_path/services/evidence.py`, the path-builder tie-break, linker
structure similarity, and grouping. Populating it on material 49, where it is
currently empty, **will change prerequisite edges and the published path.** That
is the intended outcome, not a side effect.

Changes A-C require re-extracting material 49, which rebuilds its objects, groups
and suggestions and discards teacher review state on them.

**Change D widens this to every material.** It alters stored `content` for every
object built by a definition split, in all three PDFs, so all three re-extract
and all lose teacher review state. It also reaches further than the path:

- **Narration and audio.** Narration is generated from `content`, so any clip
  already recorded for a changed object no longer matches its text and must be
  regenerated. Material 49's change-of-state objects have no narration yet, so
  nothing is invalidated there; objects that already have clips must be
  re-recorded or their captions will drift.
- **Question grounding.** `grounding.build_index` builds its vocabulary from
  `LearningObject.content`, so terms currently held only in `title` enter the
  allowed vocabulary. This is a strict improvement — `melting` and `freezing`
  become groundable — but it moves the validation baseline, and any before/after
  question-yield figure must be measured after this lands, not across it.
- **Question generation source text.** Prompts read `content`, so a generated
  question can finally name the term it is about.

Both changes together mean the 41 surviving questions on topic 276 are rebuilt.
That is expected; the current bank was generated from concepts this spec argues
should not exist.

## Verification

**Baseline first.** Record the full test suite result before any edit. The
2026-09-12 spec recorded 143 passing; that number is stale and must be
re-measured rather than assumed.

New tests:

- a document with plain styled headings opens sections at level 1
- a lower-level heading in the same document inherits rather than opens
- a numbered document is unchanged (the existing numbered tests pass untouched)
- a document with one heading level produces no spurious nesting
- the assessment and narration guards still block promotion
- a document with no font metrics falls back to today's numbered rule
- an inline definition keeps its term and its own separator in `content`
  (`Melting — …`, `Key idea: …`), while `title` still holds the term alone
- a definition split that finds no separator is unchanged
- a version built from several definition parts names every term it teaches

**Acceptance, measured on real data.** Re-extract material 49 and show:

1. every object carries a non-empty `section_title`
2. the three `Key idea` objects carry `Solids` / `Liquids` / `Gases`
3. `Melting`, `Freezing`, `Evaporation`, `Condensation` carry
   `How Matter Changes State` and remain four separate objects
4. topic 276's published path falls from 19 steps
5. materials 46 and 48 re-extract to the same **section structure** they have
   today (their `content` changes under Change D, so the comparison is on
   `section_title` and object boundaries, not on text)
6. the `changing` step's delivered Normal text names all four changes of state —
   the concrete check that Change D did its job

## Risks

**The block classifier may mislabel a heading.** The 2026-09-12 spec records that
`1. What is Matter?` is classified `assessment` and so never becomes a parent —
an accepted cost there. Material 49's `What Is Matter?` has the same
interrogative form and may hit the same path, in which case the first section of
the document still fails to open. This is a pre-existing defect that this change
neither fixes nor worsens, but it may become visible for the first time. If it
fires, the correct response is to fix the classifier in a separate change, not to
weaken the guard here.

**A PDF with inconsistent styling.** Both documents in hand have exact
signatures. A hand-formatted PDF where one heading is 15.0pt and the next 15.5pt
would split one level in two. Mitigated by rounding signatures to the nearest
0.5pt, consistent with the tolerance the existing close-a-section comparison
already uses.

**A PDF with no font metrics** (a scanned document routed through transcription)
has no signatures at all. The level map is then empty and the numbered rule
applies unchanged, which is today's behaviour.

## Ownership

`content_generator.py` is PDF extraction, which belongs to a groupmate under the
project's division of work. The user has chosen to make this change directly. It
should be communicated before it lands, since re-extraction discards teacher
review state and changes the published path for a shared topic.

## Not yet verified

The design has not been run. The root cause, the style signatures and the empty
`section_title` rows are measured facts; that relaxing the condition produces the
tree in "Acceptance" is a prediction. The first implementation step is a
throwaway script that prints the tree both documents would produce, before any
production code is edited.
