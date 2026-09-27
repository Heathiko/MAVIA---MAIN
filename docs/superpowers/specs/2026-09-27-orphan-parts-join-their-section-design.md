# An orphan object joins its section, instead of becoming a concept

**Date:** 2026-09-27
**Status:** Draft, pending review
**Files touched:** `lessons/services/learning_resource_linker.py`,
`lessons/test_orphan_sections.py`

**Follows:** `2026-09-27-peer-heading-absorption-design.md`, which fixed the
extraction defect that fused `changing` into `comparing`. This addresses a
different cause of the same symptom.

## Problem

Topic 276's learning path has 19 steps where the teacher's gold map for this
lesson (`gold_map_62.json`) has 7. Six of the excess are objects that are not
concepts at all — they are parts of a section that became steps of their own:

| step | object | its section | group size |
|---|---|---|---|
| 13 | `Melting` | How Matter Changes State | 1 |
| 14 | `Freezing` | How Matter Changes State | 1 |
| 16 | `Evaporation` | How Matter Changes State | 1 |
| 17 | `Condensation` | How Matter Changes State | 1 |
| 18 | `Everyday examples` | Gases | 1 |

Each is taught as a standalone concept, tracked with its own mastery score, and
handed to question generation as a 37-41 character source text.

## Why cross-PDF matching cannot fix it

Grouping joins a concept's tellings across PDFs. These objects have no telling
in another PDF — PDF 49 writes `Key idea` callouts and bullet terms that PDFs 46
and 48 do not have as separate objects at all. Measured: each orphan's best
match in any other PDF is the **wrong** concept.

| orphan | best match in another PDF | score |
|---|---|---|
| `Key idea` (after Solids) | m48 `Liquids` | 0.629 |
| `Key idea` (after Liquids) | m48 `Example` | 0.617 |
| `Melting` | m48 `Liquids` | 0.579 |
| `Evaporation` | m48 `Everyday examples` | 0.545 |

Two of those sit **above** the 0.60 auto-group threshold while being wrong, so
loosening the threshold would fuse unrelated concepts rather than fix anything.
Everything in one lesson scores 0.5-0.63 against everything else; similarity does
not separate these classes.

## Design

**An object that is alone in its group joins the group of its section head.**

A section head is the object, in the same material, whose own title equals its
`section_title`. The rule runs after grouping settles, so cross-PDF matches are
already in place and only genuine leftovers are considered.

### Why "alone in its group" is the discriminator

It is what separates a part from a concept, and getting this wrong has already
cost this project once.

```
532 Solid    section_title='Matter'   group has 6 members across 3 PDFs
533 Liquid   section_title='Matter'   group has 7 members
534 Gas      section_title='Matter'   group has 4 members
```

`Solid`, `Liquid` and `Gas` sit under a `Matter` heading but are three of the
teacher's seven concepts. A rule that filed every object under its section head
would swallow them — and `docs/PROJECT_CONTEXT.md` records that outcome
happening before: naming them after their heading "gave three concepts the same
name and the learning-path criteria's same-name veto then deleted their edges."

An object with companions in other PDFs has been corroborated as a concept in
its own right. An object alone has not.

### Exclusion: an object that is itself a section head

An object whose own title is a numbered section heading is a head whose section
failed to register, not a part. Object 556 (`6. Changing From One State to
Another`) is alone, and carries `section_title='Comparing the Three States'` —
the *previous* section, mis-assigned by extraction. Folding it would file the
changes-of-state table under `comparing`.

Detected with the existing `_section_heading_title`, which returns a title only
for a numbered heading. Such objects are skipped and logged.

## Measured effect

Simulated against topic 276, writing nothing:

```
WOULD MOVE (5)
  552  Everyday examples   grp 587 -> 569   (head: Gases)
  605  Melting             grp 608 -> 590   (head: How Matter Changes State)
  606  Freezing            grp 609 -> 590
  607  Evaporation         grp 610 -> 590
  608  Condensation        grp 611 -> 590

SKIPPED
  556  its own title is a section heading -- it IS a head, not a part
  530, 542, 597, 600, 602, 603   no section_title

distinct groups: 20 -> 15
```

`Solid`, `Liquid` and `Gas` are untouched.

## Goals

1. An object with no independent corroboration stops being a concept of its own.
2. It remains its own **row**, so a question can still be generated from it and
   remediation can target it. Only its group changes.
3. An object corroborated across PDFs is never moved.
4. A material with no section titles behaves exactly as today.

## Non-goals

- The three `Key idea` objects. They carry `section_title=''` — extraction never
  gave them a parent, so there is no head to join. That is an extraction defect,
  recorded as a known gap in the preceding spec, and is not addressed here.
- Object 556's wrong `section_title`. Excluded above rather than repaired.
- Getting from 14 steps to 7. That additionally needs the `Key idea` objects
  sectioned, the `comparing`/`Shape` duplicate joined, and the `matter` split
  resolved.

## Blast radius

Group membership feeds concept bundles, the learning path's steps and edges,
version assignment, audio playlists and question generation's source text. Moving
five objects removes five concepts from topic 276, so **the published path
changes and prerequisite edges will be recomputed**. That is the intent.

Applying it to live data unpublishes the topic, the way `apply_regrouping`
already does, so a teacher re-reviews before learners see it.

The rule only ever moves an object **into** an existing group and never splits
one, so it cannot separate objects a teacher has joined.

## Verification

New tests:

- an object alone in its group, with a section head elsewhere, joins that head
- an object sharing a group with others is never moved, even with a section head
  elsewhere (the Solid/Liquid/Gas guard)
- an object whose own title is a numbered section heading is not moved
- an object with no `section_title` is not moved
- an object whose section head is in the same group already is not moved
- a material whose objects have no section titles is unchanged

Acceptance on real data: topic 276 falls from 19 steps to 14; `Melting`,
`Freezing`, `Evaporation` and `Condensation` are members of the `changing`
concept and remain four separate rows; `Solid`, `Liquid` and `Gas` are still
three separate concepts with their cross-PDF members intact.

## Not yet verified

The rule is simulated, not run through the real pipeline. Whether the learning
path's edges and order survive the merge is checked by the acceptance run and by
`test_gold_paths`, not asserted here.
