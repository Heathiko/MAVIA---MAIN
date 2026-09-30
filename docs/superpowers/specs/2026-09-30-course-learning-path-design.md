# Course-level learning path: cross-topic concept links

**Date:** 2026-09-30
**Status:** Design, awaiting review
**Builds on:** criteria v5 — `docs/superpowers/specs/2026-09-30-learning-path-evidence-fusion-design.md`
(§14 and §15 describe the topic-level rules this reuses) and `backend/learning_path/CRITERIA.md`.
**Scope:** the learning-path pipeline (`backend/learning_path/`) and one new teacher page. The
adaptive engine (`backend/adaptive/`) belongs to a groupmate: it receives data and a hand-off
note, never code changes from this work. Extraction and grouping (`lessons/`) are read only.

---

## 1. Why

Today topic-to-topic order is only the teacher's outline order
(`adaptive/services.py::_next_topic_with_content`). There are no cross-topic links, so:

- a teacher cannot see which topics build on which, or whether the outline order is supported by
  the content;
- a learner who fails a concept whose foundation was taught in an earlier topic cannot be sent
  back to it.

Open-issues 1.5 recorded the agreed direction: view it on the course, derive at concept level,
roll up to topics, never reorder the outline automatically.

## 2. Goals and non-goals

**Goals**
1. Derive concept-to-concept links **between topics** of one course with the same evidence as v5.
2. A teacher page that shows the topic roll-up, confirms or flags the outline order, and lets the
   teacher approve, reject or remove cross-topic links.
3. Publish confirmed earlier-topic prerequisites in the path data, for the adaptive engine to use.
4. Measure it on topics not used to design it.

**Non-goals**
- Changing the adaptive engine (groupmate's code) — data + hand-off note only.
- Reordering the outline, automatically or from the new page.
- Adding cross-topic links by drag on the new page (possible later).
- Learning from many courses' orderings (Liang et al. 2017) — MAVIA has one outline.

## 3. Deriving cross-topic links (`services/course_criteria.py`)

**Pairs.** Every concept of a topic with every concept of the **other topics of the same course
that have content**. Pairs inside one topic stay with the topic-level criteria.

**Evidence.** Reused from v5, prepared over the two topics' concepts together:

- **Relatedness gate** — `relatedness.relatedness` with the calibrated `related_cutoff`. Across
  topics this is the main filter: unrelated subjects (340 vs 357) must produce nothing.
- **Content family** — `clues.name_vote`, `clues.term_vote` (term ownership by Dunning G²
  computed over both topics' concepts together), `clues.meaning_vote`.
- **Structure family** — **outline order**: +1 when the first concept's topic comes before the
  second's in the course outline — computed in `learning_path` from the course's `OutlineNode`s
  (units by `order`, topics by `order` within their unit), the order the course page shows. Not
  imported from `adaptive/`, so the two pipelines stay independent.
  Headings and PDF order do not apply across topics (each topic has its own PDFs).

**Verdicts across topics.**

| Situation | Verdict, direction |
|---|---|
| content has no direction | no link (outline order alone says nothing about concepts) |
| content agrees with the outline, ≥ 2 content clues agree and none against | **accepted**, outline direction |
| content agrees with the outline otherwise | pending |
| content points against the outline | pending, content's direction, `contradicts_outline: true` |
| encoder unavailable | nothing accepted (as at topic level) |

The accept bar is higher than inside a topic because the outline always votes: a single noisy
clue (meaning is at chance on direction) must not create a link a learner can be detoured along.
This rule is fixed before seeing data; it may change only on the design pair (§7) and any change
is recorded.

## 4. Storage (`models.CourseConceptLink`)

Fields: `course` (FK `CourseGroup`), `prerequisite`, `dependent` (FK `LearningObjectGroup`),
`status` (`accepted` / `pending` / `approved` / `rejected`, same meanings as
`ConceptPrerequisite`), `source` (`derived` / `teacher`), `evidence` (JSON, as at topic level
plus `contradicts_outline`), `decided_at`, `created_at`, `updated_at`; unique
(`prerequisite`, `dependent`).

A separate model, so the topic path, its screen and their tests are untouched.
`course_links.refresh_course_links(course)` re-derives like `publishing.refresh_prerequisites`:
derived rows are updated in place (stable ids), teacher decisions (`approved`, `rejected`) are
never overwritten, derived rows the criteria no longer produce are deleted, all inside one
transaction with the same concurrency guards.

**When.** When the course path page opens (`GET courses/<id>/path/`) and after a topic is
published (`publishing.publish_learning_path`, already the learning path's publish entry, calls
`refresh_course_links` for the topic's course).

## 5. The teacher page (`/courses/:courseId/path`)

- Opened from a **Course path** button on `CourseDetailPage.jsx`.
- **Topics as boxes** in outline order (topics without content greyed); React Flow + dagre as on
  the topic screen.
- **Arrow A → B** when at least one concept of B has an accepted or approved link from a concept
  of A, labelled with the count. Solid when it follows the outline; **red dashed** when it
  contradicts it; **yellow dashed** when only pending links exist.
- **Clicking an arrow** lists its concept links ("Liquid (340) → Evaporation (345)") with the
  plain-words reason (`reasons.link_reason`, extended with "follows your outline" /
  "contradicts your outline") and **Approve / Reject** (pending) or **Remove** (accepted,
  approved). Every change: confirm dialog + 10-second undo, as on the topic screen.
- Approving a link that contradicts the outline is stored but not offered to the adaptive engine
  (§6); the page says "to follow this link, move topic B before topic A in the outline".

Endpoints (teacher/admin only, like the topic endpoints): `GET courses/<id>/path/`,
`POST courses/<id>/links/<link_id>/decision/`, `POST courses/<id>/links/restore/`.

## 6. Data for the adaptive engine

`services/published.py` adds a per-step field **`course_prerequisites`**: a list of
`{topic_id, concept_id, position, status}` — the concept's position in its own topic's published
path — for accepted or approved `CourseConceptLink` rows whose prerequisite is in an **earlier**
topic, whose target concept is in that topic's **published** path, nearest topic first. It is
read live, like the in-topic `prerequisites` (a teacher's change on the Course path page shows at
once); if the links cannot be read it is empty. Pending and rejected links never appear.
(Corrected after the final review: an earlier draft said it changed only on re-publish.)

**Hand-off note** `docs/handoff-course-prerequisites.md` for the adaptive engine's owner: what
the field means, the guarantees above, a suggested use (after the in-topic prerequisite detour
and before the alternate chunk; the remediation-stack frame must carry the topic so the learner
returns where they were; one detour per step and `MAX_REMEDIATION_DEPTH` still apply), and
example payloads from real data. Until it is used, nothing changes for learners.

## 7. Evaluation

| Role | Topics | Use |
|---|---|---|
| Design | 340 ↔ 341 | the only place rules may be adjusted |
| Test | 345 ↔ 340, 345 ↔ 341 | final numbers; nothing tuned |
| Unrelated control | 357 ↔ 340 / 341 / 345 | no link should appear |

**Keys.** After 341 and 345 are uploaded, `export_course_pairs` writes a snapshot per topic pair
(both topics' concepts with full text); the user asks the same AI tool as for 340/357 which
concepts of the later topic need which of the earlier; answers are encoded as
`fixtures/gold_course_<a>_<b>.json`, labelled AI-drafted. The same command freezes the concept
pairs as fixtures.

**Metrics** (`gold.course_gold_report`): accepted links in the unrelated control — **must be 0**
(hard gate); pending links there reported as noise; accepted precision; reachable recall; outline
flags checked against the key; clue-by-clue counts; ablation of each clue.

**Constants.** None new: cutoffs come from the existing calibration (unrelated subjects).

**Caveats** stated in the report: one course, one subject chain (matter); AI-drafted keys.

## 8. Code changes

**New** (`backend/learning_path/`): `models.CourseConceptLink` + migration;
`services/course_criteria.py` (`decide_course_pairs(course)`), `services/course_links.py`
(`refresh_course_links`, `course_path`, `decide_course_link`, `restore_course_links`);
`management/commands/export_course_pairs.py`; views + urls for the three endpoints;
`gold.course_gold_report`.
**New** (`web-app/src/`): `pages/CoursePathPage.jsx`, route `/courses/:courseId/path`,
`learning-path/coursePathModel.js` (+ vitest), a button on `CourseDetailPage.jsx`.
**Changed:** `services/published.py` (`course_prerequisites`), `publishing.publish_learning_path` (call
`refresh_course_links`), `reasons.link_reason` (outline wording).
**Untouched:** `adaptive/`, `lessons/` (grouping, extraction), the topic path and its screen.

Naming follows the v5 spec §11 (descriptive names, no single letters or maths-style names).

## 9. Testing

Service tests test-first with stub concepts (as `test_criteria.py`); API tests for permissions,
decisions, undo; `test_published` cases for `course_prerequisites` (earlier topics only,
published targets only, nearest first, never pending); vitest for `coursePathModel.js`. Course
gold tests skip with a clear reason until the 341/345 fixtures and keys exist.

## 10. Risks

- **Few related topics:** results rest on one design pair and one test topic until more uploads.
- **Accepted precision matters most** — accepted links are what the adaptive engine may follow;
  the higher accept bar is the guard, measured on the design pair.
- **Outline flags could be noisy** — each wastes teacher time; counted against the key.
- **Ownership:** anything the adaptive engine does with the data is the groupmate's decision.
