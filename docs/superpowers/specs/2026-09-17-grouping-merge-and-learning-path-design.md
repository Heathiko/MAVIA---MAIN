# Many-to-one grouping merges and revised learning-path criteria

Date: 2026-09-17 · Status: design approved in brainstorming, not implemented
Supersedes parts of: `2026-09-13-prerequisite-criteria-v3-design.md` (semantic
reference measurement, cross-section cap)

## 1. Problem

Two real lessons were run end to end on 2026-09-17:

| Topic | Materials | Concepts | Accepted edges | Correct edges found |
|---|---|---|---|---|
| 62 Solid, Liquid and Gas | 15 `Lesson-1_Solid-Liquid-and-Gas`, 16 `states-of-matter-accessible` | 23 | 18 (most wrong) | 1 of 10 |
| 79 Reproduction Among Flowering Plants | 13, 14 (near-copy) | 10 | 3 | 1 of 8 |

Observed failures:

1. **Grouping cannot express many-to-one content.** A group admits at most one
   object per PDF (`semantic_grouping.py`, `eligible_groups`). Material 15 teaches
   the comparison as four items (Shape, Volume, Particle arrangement, Flow);
   material 16 as one section plus a table figure. Material 16 splits each state
   into text + diagram + examples; material 15 has one object per state. Result:
   duplicate and fragment concepts (3x "Diagram description", 4x "Everyday
   examples", 2x "Comparing the Three States").
2. **Figure-description boilerplate inflates similarity.** Both figure objects
   open with "Here's a description of the figure for…" / "Okay, let's describe
   this figure…". The particles figure and "6. Changing From One State to
   Another" scored 0.625 and the suggestion was accepted.
3. **Semantic reference measures similarity, not reference.** It compares the
   embedding of a concept's *name* with the other concept's text windows. Seven of
   the eight misses on correct edges were reversed (e.g. Stamen -> Pollination
   0.23 forward vs 0.32 backward). "Comparing the Three States" appeared to be
   referenced by every comparative sentence, producing four reversed accepted
   edges.
4. **Foundationality voted against 12 of the 15 gold edges measured.**
5. **Numbered structural labels escape the structural check.** "7. Everyday
   Examples" received 13 accepted incoming edges.
6. **Long titles leave concepts unnameable** ("Changing From One State to
   Another"), so no content criterion can vote on them.
7. **Uploaded PDFs are never removed from disk.** `media/learning_materials/`
   holds ~390 files for 4 live materials, including ~90 8-byte `states_*.pdf`
   written by tests into the real media folder.

Temporal order was correct on all 15 gold edges measured.

Out of scope (groupmate-owned extraction): titles cut mid-sentence, lost
`section_title` on figure objects, figure-describer preambles stored in content.
They are reported, not fixed; this design only works around them where scoring
depends on them.

## 2. Constraints

- Keep the requirement "Selection of Learning Object – Learning Path (adaptive
  graph traversal and scoring algorithm)": a scored prerequisite graph ordered by
  topological sort.
- Keep the three criteria (temporal order, semantic reference, foundationality)
  and the vote (3/3 accepted, 2/3 pending, otherwise none), each traceable to
  manuscript §2.6: Wang et al. 2016 (position), Liang et al. 2015 RefD
  (reference), Aytekin & Saygin 2024 ACE / all-MiniLM-L6-v2 (embeddings).
  Measurement changes are allowed if documented with before/after results.
- No generative model in the criteria; the same concepts always give the same
  graph.
- Teacher decisions (approved/rejected edges, accepted/rejected suggestions)
  are never overwritten.

## 3. Gold standard (from the teacher)

Topic 62, after merging:

```
Matter (+ particle-energy intro) -> Solid, Liquid, Gas
Solid, Liquid, Gas -> Comparing the Three States
Solid, Liquid, Gas -> Changing From One State to Another
Comparing the Three States -> Changing From One State to Another
Everyday Examples: no edges, last
Solid, Liquid, Gas: no edges among each other
```

Expected order: Matter, Solid, Liquid, Gas, Comparing, Changing, Examples.

Topic 79:

```
Reproduction in Flowering Plants (intro + flower figure) -> Stamen, Pistil, Petals and Sepals
Stamen, Pistil -> Pollination -> Fertilization -> Seed formation -> Fruit formation
Everyday Examples: no edges, last
```

Expected order: Reproduction, Stamen, Pistil, Petals and Sepals, Pollination,
Fertilization, Seed formation, Fruit formation, Examples.

Required edges: 18 in total. Topic 62: 10 (Matter -> 3 states; 3 states ->
Comparing; 3 states -> Changing; Comparing -> Changing). Topic 79: 8
(Reproduction -> Stamen, Pistil, Petals and Sepals; Stamen, Pistil ->
Pollination; Pollination -> Fertilization -> Seed formation -> Fruit formation).
Transitive extras (e.g. Pollination -> Fruit formation) are allowed.

Forbidden: any edge touching an Examples concept; any edge among Solid, Liquid,
Gas; the reverse of any required edge.

## 4. Design

### 4.1 Build order

1. Gold fixtures and failing gold test (§4.6).
2. Many-to-one merges in grouping (§4.2).
3. Boilerplate stripping for scoring (§4.3).
4. Revised learning-path criteria (§4.4, §4.5).
5. Media cleanup (§4.7).
6. Re-run both topics on the live database; before/after report.

### 4.2 Many-to-one merges

**Unit detection** (`lessons/services/semantic_grouping.py`, new helper):

- A *unit* is two or more consecutive objects (by `order`) in one material that
  share a non-empty `section_title`, extended by an immediately following object
  whose title, with leading numbering stripped and case folded, equals that
  heading (recovers object 183, whose heading extraction lost).
- Unit text for scoring = `"<title>: <content>"` per member, joined by newline,
  in document order. Units that exceed the encoder or cross-encoder limit are not
  scored (existing no-silent-truncation rule).
- Units are scored against single objects and units from other materials with
  the existing `rank_groups` models and thresholds.
- **Units never merge automatically.** Any unit match at or above the review
  threshold (0.3) with the required margin becomes a suggestion, regardless of
  score. One-to-one behaviour for single objects is unchanged.
- A unit may mix `text` and `image` members; the merged object is `text`.

**Suggestion model:** `LearningObjectMatchSuggestion` gains
`source_extra_ids` and `candidate_extra_ids` (JSON lists, default empty). The
existing primary FKs point at each unit's first member. Uniqueness and the
different-PDF check still apply to the primaries; the same-kind check is skipped
when either list is non-empty.

**Accept** (`accept_match_suggestion`), one transaction:

1. For each side with extras, merge the unit into its first member (the
   *kept row*):
   - `title` = the shared heading (or the kept row's title if none);
     `content` = unit text as above; `kind` = `text`; `order` = kept row's order.
   - New `LearningObject.merged_from` JSONField (default empty list) stores, per
     original member: `id`, `metadata_id`, `title`, `content`, `kind`, `order`,
     `section_title`, `source_page`, `source_block_id`, `image_url`,
     `image_prompt`, and the ids of questions linked to it.
   - Re-point `QuestionLearningObjectLink` and `question_generation`
     `GeneratedQuestion` rows from the other members to the kept row
     (deduplicating links).
   - Delete `LessonVariant` rows of all unit members (including the kept row);
     versions are re-derived by version assignment.
   - Delete the other members; renumber the material's remaining `order`
     values contiguously; refresh the material's saved learning-object snapshot
     so re-confirmation does not recreate them.
2. Join the two (now single) objects into one group exactly as today.
3. If the topic is published, unpublish it (same rule as regrouping apply).

**Split back** (new endpoint
`outline-nodes/<node_id>/learning-objects/<object_id>/split`): rebuild the
original rows from `merged_from` (restoring `metadata_id`), move each question
link back to its original row, restore orders, remove the restored rows from any
group (each starts ungrouped), clear `merged_from`, delete versions of the kept
row, unpublish if published.

Hidden rows were rejected in favour of the snapshot: ~25 modules query learning
objects and would all need a "skip merged" filter.

**Frontend** (`TopicDetailPage.jsx`): suggestion cards list every member on
each side; merged objects show "Split back".

### 4.3 Boilerplate stripping for scoring

Before embedding or cross-encoding, remove a leading figure-describer preamble
matching sentences such as "Here's a description of the figure for (your|a
blind) student:" and "Okay, let's (describe|explain) (this|what this) figure…".
Scoring input only; stored content is untouched. The pattern list lives next to
`normalized()` with a comment naming it as a workaround for extraction output.

### 4.4 Concept surface (`learning_path/services/`)

- **Text:** criteria read the concatenated text of all concept members, not only
  the representative's.
- **Name:** strip leading numbering ("7. ", "5) ") before resolution. When the
  title is too long to be a name, fall back to the members' `section_title`,
  then to the existing definition-subject rule.
- **Structural concepts:** a concept whose normalized name (numbering stripped)
  is a generic label (`STRUCTURAL_LABELS`, extended to match
  `_GENERIC_INSTRUCTIONAL_LABELS` in grouping) is marked structural.
  `decide_pairs` skips every pair involving it. `order_with_links` places
  structural concepts after all others, keeping their relative document order.

### 4.5 Criteria revisions

- **Temporal order:** unchanged.
- **Semantic reference (RefD-style):**
  - Key terms of concept A = its name plus distinctive terms from its text.
    Term weight = inverse document frequency over the topic's concepts; terms
    below a weight floor are dropped (e.g. "particles" in topic 62).
  - `ref(B -> A)` = weighted share of A's key terms mentioned in B's text,
    using the existing `mentions` plural folding.
  - Multi-word terms that are not matched literally may match a B text window
    by all-MiniLM-L6-v2 cosine at or above a strict cutoff.
  - Vote = 1 when `ref(B -> A) - ref(A -> B)` exceeds a margin.
  - The weight floor, SBERT cutoff and margin are calibrated on the gold
    fixtures and reported with their values.
- **Foundationality:** same inbound/outbound ratio and relative margin,
  computed from `ref` instead of name-window similarity.
- **Contrast veto:** also treats comparative "than" clauses as contrastive
  ("more energy than in a solid").
- **Cross-section cap removed.** `cross_section` is still computed and stored
  for display. If the gold test shows parallel-section leakage, the cap returns
  and this is reported.
- **Evidence:** `evidence` stores `ref_forward`, `ref_backward`, matched key
  terms per direction, and IOL values, replacing `csr_*`.

**Stop condition:** if a required edge cannot be reached by text evidence
without a lesson-specific rule, stop and report to the user rather than add one.

### 4.6 Testing

- **Fixtures:** `backend/learning_path/fixtures/gold_topic_62.json` and
  `gold_topic_79.json`: per concept, id, title, section headings, member texts,
  order, and whether structural; exported after merges by a management command
  (`export_gold_concepts`), plus the required/forbidden edge lists and expected
  orders from §3.
- **Gold test** `learning_path/test_gold_paths.py`: runs the real encoder,
  skipped when models are unavailable. Fails on any missing required edge, any
  forbidden edge, or wrong order; prints extra non-forbidden edges.
- **Unit tests:** unit detection (including lost-heading recovery), units never
  auto-merge, accept merges and re-points questions, split restores
  `metadata_id`s and links, published topic unpublished, boilerplate stripping,
  numbering-stripped names, structural concepts excluded and ordered last,
  RefD reference direction on synthetic text, "than" contrast veto.
- **Existing tests:** the 28 synthetic learning-path tests change only where they
  encode deliberately replaced behaviour (cross-section cap, name-window
  similarity), each with a one-line reason.
- **Report:** per topic, before/after accepted, pending, required hits, forbidden
  hits, and final order, for the manuscript's revision notes beside §2.6.

### 4.7 Media cleanup

- Deleting a `LearningMaterial` (and `CourseOutline`) deletes its file from
  storage after the transaction commits.
- Management command `clean_orphan_media` lists files under `media/` not
  referenced by any row; deletes only with `--delete`.
- Test settings point `MEDIA_ROOT` at a temporary directory.

## 5. Risks

- Two lessons are a small gold standard; thresholds may overfit. Report per
  lesson; add a third lesson when available.
- Matter -> Liquid, Comparing -> Changing and Reproduction -> Petals and Sepals may lack textual reference
  evidence (§4.5 stop condition).
- Merging relies on `section_title`, which extraction sometimes loses; missed
  units stay as separate concepts (no regression).
- Merge deletes rows; correctness of split depends on the snapshot being
  complete. Tested field by field.
