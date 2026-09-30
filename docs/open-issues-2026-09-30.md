# MAVIA open issues — 2026-09-30

A handover for the next session. Read this, then `docs/AGENT_LOG.md` (latest
entries) and `docs/PROJECT_CONTEXT.md`. Everything below was traced on the live
database, not assumed; re-verify anything you rely on — data changes as the user
uploads and edits.

**Owner split.** The user owns **learning path formation** and **question
generation**. A groupmate owns **PDF extraction** (chunking, headings, sections).
Grouping (`lessons/services/…`, concept bundles) — ownership not confirmed; ask.
Version generation (Normal/Simplified/Elaborated) is **on hold** pending a group
decision.

## Where things stand

| Branch | State |
|---|---|
| `learning-path-criteria-v4` | v4 criteria (R1 definition / R2 containment accept, R3 reference pending). Pushed to origin. **Not merged.** |
| `learning-path-graph-screen` | Graph-first review screen + fixes (below), pushed 2026-09-30. Since then, locally: **criteria v5** (relatedness + two evidence families, `backend/learning_path/CRITERIA.md`; results in `docs/learning-path-v5-evaluation-2026-09-30.md`). **Not merged — wait for the user's cue.** |

Live data (SQLite `backend/db.sqlite3`): outline 12 "Outline for Grade 1 Science".
Topic **340** Solid, Liquid and Gas (materials 62, 63, 64 — published).
Topic **357** Reproduction Among Flowering Plants (materials 65, 66).
All other topics are empty.

## Done (branch `learning-path-graph-screen`)

- Learning path review screen: full-width React Flow + dagre graph; drag B onto
  A = "A before B" (add or move); confirm + 10 s undo on every change;
  pending recommendations shown in the dependent concept's card as yellow rows;
  concepts with pending links flagged yellow with a count.
  Spec: `docs/superpowers/specs/2026-09-29-learning-path-graph-screen-design.md`
  (section 10 = latest revision).
- Links are derived when the screen opens (`GET /api/learning-path/topics/<id>/`),
  with stable ids; `links/move/` and `links/restore/` endpoints; plain-words
  `reason` per link.
- "Topic published!" dialog after a successful publish: Normal narration per
  concept in path order, multi-part concepts play back to back, one at a time.
- Fixed: concurrent screen opens → 500 IntegrityError; on PostgreSQL a
  re-derivation could overwrite/delete a concurrent teacher decision.

---

## 1. Learning path formation (user's pipeline)

### 1.1 Automatic rules find few real prerequisites — highest impact
> **2026-09-30, v5:** v4's R1/R2/R3 are gone. On the test topic 340, required links reached 11 → 18 of 23, 0 forbidden, accepted precision 0.92. Topic 357 (AI-drafted key): 8 → 20 of 20 required links, τ 1.00, 0 forbidden, every accepted link correct — but the process chain is reached only as pending suggestions (amendment 2); remediation needs a teacher to approve them. Gold 62 lost reach (9 → 5): heading containment no longer accepts on its own.

Only R2 (section containment) fired on topics 340/357; **R1 never fired**.
- **R1 is blind to the lessons' definition format.** PDFs define terms as a bold
  title + body ("**Pollination:** Pollen is carried from the anther to the
  stigma"). The extractor stores term in `title`, definition in `content`.
  `criteria.defining_sentences` only accepts a body that opens "Pollination
  is…" (`definition_subject(content) == name`). Fix direction: treat a
  title-term/content-definition learning object as a definition of its title.
- **R3 matches names, lessons refer by parts.** Pollination's text says
  "anther"/"stigma", never "stamen"/"pistil". No stemming either:
  "fertilized ovule" ≠ "Fertilization".
- **Consequence:** topic 357's process chain has **no links at all**
  (stamen/pistil → pollination → fertilization → seed → fruit). The adaptive
  engine detours only through accepted/approved prerequisites
  (`backend/adaptive/services.py:739-740`), so a learner missing Fertilization
  cannot be sent back to Pollination.
- Do **not** tune constants to close gaps on the gold topics (they are fitted to
  the same lessons). Measure on unseen lessons (1.6).

### 1.2 Structural list sends lead sections to the end — small, ready
> **2026-09-30, v5:** the label lists and lead/examples/closing tiers are removed; examples and summaries get links from the clues like any concept. Kahn ties now go to PDF order (the build-on-latest tie-break lowered τ on the development set), so examples are not pulled before Changing State unless a link requires it.

`learning_path/services/concepts.py:39` `STRUCTURAL_LABELS` forces every match
to the end of the path with no links. It mixes **lead** sections (Introduction,
Overview, Objectives, Definition, Vocabulary, Glossary → should come first) with
**trail** sections (Summary, Review, Recap, Examples, Activity, Practice
questions → last). Matching is whole-title, so "Summary: what to remember" is
not recognised. Fix: split into lead/trail, match on the title's start; update
`publishing.order_with_links` rank.

### 1.3 Backwards recommendation
> **2026-09-30, v5:** the same overview effect broke the first v5 build (Solid → Matter). Fixed by requiring the content clues to agree with author structure; when they disagree the link is pending in the structure's direction.

`Seed formation → Reproduction in Flowering Plants` (topic 357, pending, R3): the
parent overview says "seeds", so R3 reads it backwards. Known R3 weakness with
parent/child overviews.

### 1.4 Figure rule — designed, awaiting the user's decision
> **2026-09-30, v5:** superseded — figures are read through their descriptions like any passage; no separate rule.

"A figure comes after every concept its caption/description names" (same name
matching as R1–R3, no model). Simulated read-only: topic 340 particle figure
moves from step 2 to after Gas; topic 357 flower-parts figure moves after
Petals and Sepals; nothing else moved. Lives in `criteria.py` (user's code).

### 1.5 Course-level learning path — implemented 2026-09-30, evaluation waiting for uploads 341 and 345
> Spec `docs/superpowers/specs/2026-09-30-course-learning-path-design.md`, plan `docs/superpowers/plans/2026-09-30-course-learning-path.md` (Task 13 blocked on uploads), hand-off `docs/handoff-course-prerequisites.md`. Topic ids changed since this note: 341 Grouping Materials, 345/346 Changes, 343 Mixtures, 348 Separating Mixture, 362 Reproductive Structures.

Today topic→topic order is only the outline order
(`adaptive/services.py:431 _next_topic_with_content`); no cross-topic links.
Agreed direction so far (not designed in detail):
- View it on the **course outline screen**.
- Derive at concept level across topics (R1 carries over: a definition in topic
  B naming topic A's concept), roll up to topic level for display.
- Never reorder the teacher's outline automatically: links that agree confirm
  it; links that contradict it are flagged. Cross-topic R3 → pending only.
- Needs uploads first: **309** Grouping Materials Based on Properties and **313**
  Changes that Materials Undergo (build on Solid, Liquid and Gas), plus **311**
  Mixtures + **316** Separating Mixture. Related later: **330** Reproductive
  Structures ↔ 357.
- Literature to verify before citing: Yang et al. 2015 "Concept Graph Learning
  from Educational Data"; Liang et al. 2017 "Recovering Concept Prerequisite
  Relations from University Course Dependencies".
- Needs a brainstorm → spec → plan cycle.

### 1.6 Unseen-lesson evaluation
Criteria are fitted to the gold lessons (62/79/152). The uploads in 1.5 double
as the unseen test set.

### 1.7 Topic 340's current path is entirely teacher-shaped
All automatic containment links (Matter → Solid/Liquid/Gas, Comparing →
Changing figure) were **rejected**; every path-shaping link is teacher-approved
(some from recommendations, some drag-added). Worth knowing when reporting how
much of the path the system derived.

### 1.8 Topic 340 arrangement findings (verify with the user)
Full path with every learning object's text:
`docs/learning-path-340-snapshot-2026-09-30.md`. Read against the content:
- **Steps 1 and 2 are one concept split by grouping.** PDF 64's "What Is
  Matter? (Part 1)" ("Matter is anything that has mass…") sits in step 2 with
  "Matter usually exists…", not in step 1 "Matter". (See 3.2.)
- **Step 13 "Example (Part 1 of 2)" is a changes-of-state example** (ice cube
  melts, then evaporates) but sits with the examples, unlinked — caused by the
  extraction chunk crossing the "7. Everyday Examples" heading (3.1).
- **Step 12 Summary mentions melting/freezing/evaporating/condensing** yet has no
  link from 10/11 (Changing State); only Matter/Solid/Liquid/Gas → Summary are
  pending. It lands after 10/11 by document order alone.
- **Steps 8 and 9 are the same comparison from different PDFs**; 8 → 9 is a
  teacher link stitching a grouping split, not a real prerequisite. Same for
  10 → 11 (Changing text → its table figure).
- **Step 7 (particle figure) depends only on "As a general rule"**; it
  illustrates Solid/Liquid/Gas — what the figure rule (1.4) would link.
- **Liquid → As a general rule was drag-added by hand**; the text never names
  liquids ("Solids have the least…; gases have the most"). Confirm intended.

### 1.9 Deferred minors from the whole-branch review (graph screen)
- `add_link`/`decide_link`: snapshot + loop check without `atomic`/lock —
  two teachers adding opposite links at once on PostgreSQL could both pass.
- Undo timer keeps running during an in-flight restore; a restore failing
  after the 10 s timeout is never shown.
- UndoBar timer keyed on message text; identical consecutive messages don't
  restart the 10 s.
- Undo bar (z 60) is clickable above the confirm backdrop (z 50).
- One Escape closes both the confirm dialog and the details card.
- A row recreated by restore shows "Added by you." until the next load (restore
  view does not re-derive).
- Crafted undo record with a non-string `decided_at` → 500 instead of 400.
- Old `.cm-*`, `.lf-*`, `.path-step*`, `.ps-*` rules in
  `web-app/src/styles/pipeline.css` are unused.

---

## 2. Question generation (user's pipeline)

Not examined in the 2026-09-29/30 sessions. Items below come from
`docs/AGENT_LOG.md` open threads and were **measured on topic 276, which has
since been deleted** — re-measure on topics 340/357 first. The grounding gate
(`question_generation/services/grounding.py`) is present on this branch.

1. **Students are served the answer key (security).**
   `adaptive.views.LessonDetailView` (`IsStudent`) returns
   `lessons.Question.correct_answer` via
   `lessons/services/lesson_package.py::_lesson_questions`. Path mode is safe
   (`adaptive.services.student_safe_step`); this endpoint is not.
2. **True/False questions dressed as MCQs** (A True / B False + two fillers).
   Decision open: reject, or convert to real TF items.
3. **The grounding gate rejects more than it accepts** (100 vs 76; MCQ hit
   hardest). Cause unmeasured; reasons are in `GenerationEvent`.
4. **Concepts left with no questions** (were: Melting, Freezing, Condensation,
   short concepts) — generated, then rejected by the gate. Path mode skips a
   concept with no question entirely.
5. **Question judge uncalibrated** (`QUESTION_JUDGE_MODEL`): accuracy rests on
   two examples; wants a labelled supported/unsupported set.
6. **Questions can be written from a bundle later marked EXTRA** if generation
   runs before the Versions step.
7. **Category is a fixed lookup** (`BLOOM_TO_CATEGORY`), not a prediction;
   spread lopsided. State it that way in the manuscript.

---

## 3. Not the user's pipeline, but it affects it

### 3.1 Extraction (groupmate)
- "1. What is Matter?" classified as `assessment` (heading ending in "?"), so
  PDF 63's definition of matter never becomes a learning object. **Groupmate is
  fixing this; the user will pull it.**
- A numbered heading does not start a new chunk: "7. Everyday Examples" is
  swallowed into "Example (Part 1/2, 2/2)" with the ice-cube melting example.
- Stale `section_title`: when a heading becomes an object's title its section is
  left blank and the next object inherits the previous section — the
  changes-of-state table (lo792) is filed under "Comparing the Three States",
  creating a false containment link.
- PDF 65's figure gets a phantom section "Flowering Plants".

### 3.2 Grouping (owner unconfirmed)
- Topic 340: Matter split in two concepts ("Matter" / "Matter usually exists…");
  Comparing split in two; Changing split into text + figure; examples over three
  steps. These produce odd path steps such as "Comparing → Comparing".
- Suggestion 315 (Comparing ↔ Comparing) reads `accepted` while its objects sit
  in different groups (g831 vs g832) — accepted at the time, later separated.

### 3.3 Version generation (on hold — group decision)
- Current rule (`course/version_assignment.py::review_gemma_role`): ELABORATED =
  "keeps Normal's facts and adds something", so content only another PDF covers
  is reachable only on remediation (topic 340: the four changes of state were in
  Elaborated; Normal was a dangling intro).
- User's position (not yet group-agreed): consolidate PDFs into a complete
  Normal; LLM generates Simplified/Elaborated; the thesis novelty moves to
  grouping/integration. Claude suggested extractive consolidation.
- The Versions step auto-POSTs `generate-all-versions` (seen on topic 357).

### 3.4 Media
Audio is served without HTTP Range support, so players cannot seek (dev server).

---

## Suggested order
1. Answer-key leak (2.1) — security, small.
2. Structural lead/trail fix (1.2) — small, ready.
3. Upload related topics (1.5) — unblocks course-level design and unseen testing.
4. R1 reads title = term, content = definition (1.1) — biggest gain on links.
5. Course-level learning path design (1.5).
6. Re-measure question generation on current topics; settle TF-in-MCQ (2.2–2.4).

## Useful commands
```bash
cd backend
python manage.py test learning_path            # ~190 tests
python manage.py test                          # full backend, ~1214 tests
python manage.py show_learning_path 340 --preview --links
cd ../web-app && npm test && npm run build     # vitest + build
```
Trace a topic end to end (read-only): `concepts_for_topic(node)` →
`criteria.decide_pairs(concepts)` → `publishing.order_with_links(concepts, links)`.
