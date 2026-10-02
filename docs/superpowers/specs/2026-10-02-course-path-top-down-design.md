# Course-level learning path: top-down shortlist — design

**Status:** 2026-10-02. Branch `learning-path-graph-screen`. The user asked for spec → plan → build
in one go; the final check waits for the user's approval of blind answer keys.
**Replaces (when it passes):** the course-level verdict of
`docs/superpowers/specs/2026-09-30-course-learning-path-design.md` (amendment 1: name and terms
must agree). The old rule stays selectable.

## 1. What changes for the teacher and the learner

Today the course level accepts a cross-topic link only when a later concept names an earlier one
and uses its words: 2 of 16 real links, so the Course path page is almost empty. Looser word rules
invent many wrong links, because topics of one subject share vocabulary.

The new course level works **from the biggest resource to the smallest**:

1. **Outline:** topics whose titles are related are compared; the rest never are.
2. **Concepts:** for each concept of a later topic, the three closest concepts of the earlier
   topic are shortlisted (by concept title, or by lesson text when the title is not a real name).
3. **Decision:** a shortlisted link the strict text rule confirms is accepted; the others are shown
   to the teacher, who ticks the real prerequisite or dismisses the list.

*Example.* "Mixtures and Their Characteristics" follows "Solid, Liquid and Gas" in the outline and
their titles are related, so they are compared. For "Solutions: Solute and Solvent" the page shows
"might build on: Liquid · Solid · Changing From One State to Another"; the teacher approves Liquid.
A learner stuck on Solutions can then be sent back to Liquid. "Grouping Materials Based on
Properties" is not compared with "Solid, Liquid and Gas": their titles are not related enough.

The page itself changes: the topic graph flows **top to bottom** like the topic-level graph, and
below it a **learning order list** shows the course as a learner goes through it, with each
step's links back to earlier topics and its shortlist to decide.

## 2. Diagnosis (2026-10-02, pairs already studied)

Design pairs: 340↔341 (same subject, key has no links), 340↔343 (5 links), 340↔347 (3),
343↔348 (8); controls 357↔340/341/343/347/348 (unrelated).

- **Concept similarity cannot decide links within a subject.** Real links score 0.36–0.45; other
  same-subject pairs reach 0.55. The current gate (0.247, set on different subjects) passes most
  pairs.
- **Word rules: precise and rare, or common and wrong.** name AND terms: 2 right / 3 wrong;
  name OR 1 term: 7 / 80; name OR 2 terms: 5 / 22; v6.1 run across two topics: 6 / 23.
- **Topic titles separate topic pairs.** Title similarity: 343↔348 0.71, 351↔353 0.67, 340↔343 0.42,
  340↔347 0.34 (all have links) vs 340↔341 0.22 (no links) and unrelated 0.00–0.20. Content
  similarity could not separate 340↔341 (0.27). Adding the unit name made it worse (340↔341 0.58).
- **Concept titles rank candidates better than content.** Key prerequisite among the top 1/2/3/5
  candidates: by title 4/8/10/10 of 12; by content 3/4/8/12.
- **Nothing reads `course_prerequisites` yet** (`backend/adaptive/` does not use it).

Literature: course-level relations constrain concept-level ones (Liang et al., AAAI 2017; Yang et
al., WSDM 2015); match large blocks first, then items inside matched blocks (Hu, Qu & Cheng 2008).
We borrow the structure, not their trained models: one outline and a handful of topics.

## 3. The rule

Inputs: the course's topics with content, in outline order, each with its title and concepts.

**Level 1 — outline gate.** For every earlier topic T1 and later topic T2, embed both **titles**
(the same pinned MiniLM encoder) and take their cosine similarity. The pair is compared only when
it is ≥ `TOPIC_TITLE_CUTOFF` (starting value 0.30, between 0.22 and 0.34 above).

**Level 2 — shortlist.** For each concept B of T2 with at least one full sentence, score every
concept A of T1 with at least one full sentence:
- **title score** (cosine of the two concept titles) when both titles are real names
  (`concept_text.name_terms(title)` is not empty);
- otherwise the **content score** (`relatedness(A, B)`, unchanged).
The `SHORTLIST_SIZE` (= 3) highest are B's shortlist, with ranks 1..3.

**Level 3 — decision.** For each shortlisted pair (A first, by the outline):

| Situation | Verdict | Evidence |
|---|---|---|
| name and terms both say A before B (today's strict rule) | **accepted** | `rule: "course-shortlist"`, `confirmed: true` |
| name and terms both say B before A | pending, flagged `contradicts_outline` | as today |
| otherwise | pending (a shortlist entry) | `confirmed: false` |

Pairs outside a shortlist, and pairs of topics that fail the gate, get nothing.
Without the encoder the gate and the ranking cannot run: the old strict rule runs instead and its
links are pending only (as today).

Stored `evidence`: `rule`, `rank`, `ranked_by` (`"title"`/`"content"`), `score`,
`topic_similarity`, `confirmed`, `votes`, `records`, `contradicts_outline`, `confidence`,
`semantic`. `reasons.link_reason` for `course-shortlist`:
- confirmed: today's course sentence ("B names A. B uses terms A explains (…). This follows your
  outline.");
- not confirmed: "One of the 3 closest matches for B in this topic (rank 1). Please confirm or
  dismiss."

Teacher control is unchanged: approve → `approved`, dismiss → `rejected`; both are never
overwritten by a re-derivation. Only `accepted` and `approved` reach `course_prerequisites`.

**Selectable.** `decide_course_pairs(..., rule=...)` with `"shortlist"` (new) and `"strict"`
(today). `COURSE_DEFAULT_RULE` stays `"strict"` until the final check passes (§5).

## 4. The Course path page

**Graph, top to bottom.** Topics are boxes laid out by the cross-topic arrows with dagre
(`rankdir: TB`), handles top and bottom, earlier topics above later ones — the same look as the
topic-level graph (`graphModel.buildGraph`). Topics no arrow touches sit in a "Not linked yet"
strip below. Arrow colours and click-to-see-details are unchanged.

**Learning order list (below the graph).** For each topic with content, in outline order:
- heading: position and title, and "not published yet" when the topic has no saved path;
- its steps in order: the published path's order when published, otherwise the topic's current
  concept order;
- under a step: **"May revisit:"** each accepted or approved course link into it
  ("Liquid — Solid, Liquid and Gas"), with Remove; **"Might build on:"** its pending links
  (shortlist entries and outline-contradicting suggestions) in rank order, each with Approve and
  Dismiss, and the reason as a tooltip/second line.
Approve/Dismiss/Undo use the existing endpoints and confirm dialog.

**API.** `course_path(course)` adds to each topic `steps`: `[{concept_id, title, position}]` and
`published` (bool). Links already carry both concept ids, so the list is built in the browser.

## 5. Evaluation

**Design (tuning allowed: `TOPIC_TITLE_CUTOFF`, `SHORTLIST_SIZE`):** the pairs of §2 and their
fixtures `fixtures/gold_course_*.json`. Topic titles for fixtures come from a new
`fixtures/course_topic_titles.json` (topic id → outline title), since fixtures carry none.

**Final check (scored once, after the rules are frozen):** new pairs whose keys are drafted
**blind** by a separate agent (the designer does not read them), from both topics' concepts in
**shuffled** order, deciding by meaning; then **approved by the user**:
351↔353, 341↔343, 341↔347, 347↔348, 351↔365, 353↔365. Each key says which concepts of the later
topic build on which of the earlier, or `"unrelated": true`.

**Measures**, old rule and new rule, same code (`evaluate_course_paths`):
- gate: pairs compared / skipped, against the key's related/unrelated;
- shortlist hit@3: dependents with a key prerequisite whose shortlist contains one;
- accepted: right / wrong; pending count (teacher workload);
- unrelated pairs: any accepted link or shortlist entry.

**Stop rule (fixed now).** The new rule becomes the default only if, summed over the final pairs:
1. pairs the key marks unrelated get no accepted link and no shortlist entry;
2. shortlist hit@3 ≥ 0.6;
3. accepted wrong links ≤ the old rule's.

Otherwise the old rule stays the default and the report says why. The page changes (§4) ship
either way; with the old rule the "Might build on" lists hold only its suggestions.

## 6. Tests

Backend: gate on title similarity; shortlist ranking by title, fallback to content for non-name
titles; top-3 cut; decision table; evidence JSON-serialisable; encoder-unavailable fallback;
`course_path` topic `steps`/`published`; evaluation command and its final-check lock; reasons.
Frontend (vitest): top-to-bottom layout (earlier topic above a later one it links to; unlinked
strip); learning-order model (steps per topic, "may revisit" vs "might build on" grouping, rank
order).

## 7. Risks

- Five design pairs set the title cut-off; three topic titles is a thin signal and depends on
  teachers naming topics clearly.
- The shortlist misses the real prerequisite about 1 time in 5. Course links cannot be added by
  hand today, so a missed one stays missing; adding them by hand is out of scope.
- Teacher workload: up to 3 entries per concept of each related later topic.
- Keys are AI-drafted and user-approved, not teacher-verified.
