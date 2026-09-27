# A peer heading must not be absorbed into its neighbour

**Date:** 2026-09-27
**Status:** Draft, pending review
**Files touched:** `lessons/services/content_generator.py`, `lessons/tests.py`

**Supersedes:** `2026-09-27-heading-levels-from-style-design.md`, which named the
wrong root cause. See "What the superseded spec got wrong".

## Problem

Topic 276's learning path has 19 steps where the teacher's gold map for this
lesson (`gold_map_62.json`) has 7. The largest single contributor: `Melting`,
`Freezing`, `Evaporation` and `Condensation` are four separate concepts of 37-41
characters each, filed under the wrong section, and the concept that should own
them does not exist as an object at all.

Question generation then targets 6 questions per learning object, so it is asked
to write six questions from a 39-character concept.

## Root cause

Verified by running the real pipeline, not by reading it.

`Solid_Liquid_and_Gas.pdf` page 3 is laid out:

```
Comparing the Three States      ← heading, 15.0pt bold #1F3C64
  [property table]              ← rendered as an image; its text rows are
                                   correctly excluded from the text stream
How Matter Changes State        ← heading, 15.0pt bold #1F3C64  (same style)
  Matter can change from one state to another when heat energy is…
  ● Melting — solid to liquid, caused by adding heat.
  ● Freezing — liquid to solid, caused by removing heat.
  ● Evaporation — liquid to gas, caused by adding heat.
  ● Condensation — gas to liquid, caused by removing heat.
```

`exclude_text_blocks_inside_tables` removes the table's six text rows, which is
right — they are served as the table image. But that leaves
`Comparing the Three States` as the open concept with no body of its own.

The next heading then reaches this condition in the block loop:

```python
not _section_heading_title(text)
and _heading_refers_to_current_concept(current, heading_title)
```

`_heading_refers_to_current_concept` matches on lexical overlap after
plural-folding. Both titles contain **state**, so it returns `True`:

```
_heading_refers_to_current_concept({"title": "Comparing the Three States"},
                                   "How Matter Changes State")   ->  True
                                   "Review Questions"            ->  False
                                   "Gases"                       ->  False
```

So `How Matter Changes State` is absorbed as a sub-heading —
`current["parts"].append(f"{heading_title}:")` — instead of opening its own
object. The four bullets that follow then inherit `Comparing the Three States`.

**The evidence is in the stored data.** Learning object 571 is titled
`Comparing the Three States` and its content begins:

```
How Matter Changes State:
Matter can change from one state to another when heat energy is added or removed…
```

That leading `"How Matter Changes State:"` with its trailing colon is exactly
the `f"{heading_title}:"` append.

**Confirmed by differential run.** Building objects from all 49 text blocks
versus the 43 the real pipeline passes:

```
49 blocks (table rows kept)      43 blocks (table rows excluded, real)
How Matter Changes State  ✓      (no such object)
Melting  -> 'How Matter…'  ✓      Melting  -> 'Comparing the Three States'  ✗
```

The only difference is the excluded table rows.

## Why the rule exists

It is not a mistake in general. `lessons/tests.py::
test_numbered_concept_keeps_its_subheadings_and_short_bullet_examples` pins its
purpose: `Particles in a Solid` and `Examples of Solids` must be absorbed into
`1. Solid` rather than becoming concepts of their own. Lexical overlap is a
reasonable signal for that.

The rule is wrong only when the two headings are **peers** — siblings at the
same level that happen to share a word. It has no way to tell a sub-heading from
a sibling, so it treats every overlap as subordination.

## Design

### Change 1: a heading is not absorbed by a heading of its own rank

`extract_pdf_text_blocks` already records `font_size`, `is_bold` and
`text_color` on every block. Form the signature `(round(font_size*2)/2,
is_bold, text_color)`. Absorption is skipped when the incoming heading's
signature equals the signature of the block that opened the current concept.

Measured on the failing document:

| heading | signature | verdict |
|---|---|---|
| `Comparing the Three States` | `(15.0, True, 2046052)` | opens the concept |
| `How Matter Changes State` | `(15.0, True, 2046052)` | **same rank — do not absorb** |
| `Everyday examples` | `(12.5, True, 3036053)` | lower rank — absorb, as today |

**When either signature is unavailable, behaviour is unchanged.** The blocks in
the existing test carry `is_bold` but no `font_size`, so that test keeps passing
untouched — which is the point: the guard only fires where the document supplies
evidence that the two headings are the same rank.

This requires the loop to remember the signature of the block that opened the
current concept, alongside the title it already keeps.

### Change 2: a split definition keeps its term in the delivered text

Carried over unchanged from the superseded spec, where it was Change D. It is
independent of the root cause and still correct.

A version's text is built by `bundle_segments`, which takes
`clip["narration"] or item.content`. A segment is `{text, audio_url}` with no
title field, so a reader cannot render the term even if it wanted to. Today each
term is its own step and its card heading supplies the label; once the four
become parts of one telling, the learner receives four unlabelled definitions.

`_inline_definition_split` matches
`^(?:…)?([A-Z][A-Za-z0-9 /,&()]{1,70})\s*(?::|[-–—])\s+(.+)$` and discards the
separator. Capture it and return content that still opens with the term:

```
title   = "Melting"
content = "Melting — solid to liquid, caused by adding heat."
```

Separator spacing is part of the rule — the regex consumes the surrounding
whitespace, so a naive rejoin gives `Melting— solid`. A dash takes a space on
both sides, a colon only after. Verified against all five real forms in these
PDFs (`Melting`, `Freezing`, `Key idea`, `Everyday examples`,
`Diagram description`); all return exactly as the source wrote them.

Fixing this at extraction rather than at render time is what keeps text,
narration, audio and captions in agreement.
`course/services.py::_version_from_segments` states the invariant: text is
derived from the segments "so a caption can never drift from the wording the
segment actually carries."

## Known defect, deliberately not fixed here

The three `Key idea` callouts still come out with `section_title=''`. A single
inline definition with no sibling run after it never sets `active_section_title`,
so it has no parent to inherit.

**This is not diagnosed to the same standard as Change 1 and must not be fixed
blind.** The superseded spec's failure came from specifying a fix against a
mechanism that was read rather than run. Whoever picks this up should first
reproduce it with the real pipeline, as the Root cause section above does, and
check what the flat-definition-list guard
(`FlatDefinitionListTests::test_a_glossary_term_does_not_become_the_section_of_its_peers`)
is protecting before changing anything.

## What the superseded spec got wrong

It concluded that sections only open on numbered headings, and proposed deriving
heading levels from style signatures so a plain heading could open one. Three
errors:

1. **The heading was already being detected.** `How Matter Changes State` is
   recognised fine; it is absorbed *after* detection. Opening sections
   differently would not have helped.
2. **It reasoned from a partial simulation.** The proof script reimplemented one
   slice of the loop rather than calling the real builder, so it never saw the
   absorption branch. `classify_instructional_blocks` is pure Python with no LLM
   call, so the real function could have been run from the start.
3. **It claimed the stored rows were stale.** Regenerating material 49 produced
   byte-identical objects, groups and path steps. The database always matched the
   code.

The style-signature measurement survives, applied at the right place: it
distinguishes a peer heading from a sub-heading, which is exactly the judgement
`_heading_refers_to_current_concept` cannot make.

## Blast radius

**Change 1** alters object boundaries for any document where two same-rank
headings share a word. On topic 276 that is material 49 only; materials 46 and
48 use numbered headings, which already bypass the absorption branch via
`not _section_heading_title(text)`.

**Change 2** alters stored `content` for every definition-split object in all
three PDFs, so all three re-extract. Narration already recorded for a changed
object must be regenerated or its caption drifts.
`grounding.build_index` builds its vocabulary from `content`, so terms held only
in `title` today become groundable — an improvement, but it moves the question
validation baseline, so any before/after yield figure must be measured after this
lands, not across it.

Re-extraction discards teacher review state on a material's groupings and
deletes its generated questions. Measured on material 49 on 2026-09-27: 9
questions deleted, objects and groups unchanged.

## Verification

**Baseline first.** Record the full suite result before any edit.

New tests for Change 1:

- two headings with the same signature: the second opens its own object
- two headings with the same signature sharing no word: unchanged
- a lower-rank heading sharing a word: still absorbed
- blocks with no `font_size`: unchanged, and
  `test_numbered_concept_keeps_its_subheadings_and_short_bullet_examples`
  passes untouched
- a numbered heading sharing a word: still bypasses absorption as today

New tests for Change 2:

- an inline definition keeps its term and its own separator in `content`
  (`Melting — …`, `Key idea: …`), while `title` holds the term alone
- a definition split that finds no separator is unchanged
- a version built from several definition parts names every term it teaches

**Acceptance, measured on real data.** Re-extract material 49 and show:

1. an object titled `How Matter Changes State` exists
2. `Melting`, `Freezing`, `Evaporation`, `Condensation` carry it as their
   `section_title` and remain four separate objects
3. no object's content begins `"How Matter Changes State:"`
4. topic 276's published path falls from 19 steps
5. materials 46 and 48 keep their current section structure
6. the `changing` step's delivered Normal text names all four changes of state

## Not yet verified

No code has been written. The root cause is proven by differential run and by
the stored evidence in object 571. That the peer guard produces the tree in
"Acceptance" is a prediction, and the first implementation step is to assert it
against the real builder before any production edit.
