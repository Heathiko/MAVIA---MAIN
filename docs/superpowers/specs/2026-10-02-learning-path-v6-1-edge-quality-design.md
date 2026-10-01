# Learning-path criteria v6.1: cleaner edges — design

**Status:** draft for review, 2026-10-02. Branch `learning-path-graph-screen`.
**Changes:** three rules inside v6 (`fusion.reference_verdict`, the owned-terms clue). Direction
logic, ordering and teacher control are unchanged.
**Background:** `docs/learning-path-v6-evaluation-2026-09-30.md`; v7 attempt (not adopted, §8);
conversation of 2026-10-02 (diagnosis and option C, chosen by the user).

## 1. What changes for the teacher and the learner

The learning path's main job is its **edges**: where the adaptive engine sends a stuck learner. v6
sends about 1 in 3 learners on a detour that is not a real prerequisite (precision 0.68 on unseen
topics) and has no edge for about half of the real prerequisites. v6.1 makes the automatic edges
**cleaner**: a link resting on a single shared word ("table", "one", "movement") is no longer
accepted automatically; it is shown to the teacher as a suggestion. Two cautions that blocked real
links (figures, concepts taught in different PDFs) are removed.

*Example (topic 340).* v6 accepts "Comparing the Three States → Everyday Example (ice)" because both
use the word "table". v6.1 shows it as a suggestion: "Only one shared word links them (table);
please confirm." A learner stuck on the ice example is no longer sent back to the comparison table
unless the teacher approves it.

The order of the path is unchanged: the teacher's PDF order, moved only by headings.

## 2. Diagnosis (design topics 340 and 357, 2026-10-02)

Missed required links (17 of 43): overview naming its parts (5), steps under one heading treated as
siblings (3), figures (4), concepts from different PDFs (2), disputed key (3). Wrongly accepted links
(9, all on 340): one weak shared word (4), headings matched on generic words or chunks under the
wrong heading (3), disputed key (2).

## 3. The three changes

**C2 — a figure no longer blocks a link.** Remove `figure` from v6's contradictions. A figure pair
the text links and nothing else contradicts is accepted in PDF order, like any other.

**C3 — different PDFs no longer block a link.** Remove `no_shared_pdf` from the contradictions. Such
a pair is accepted in the topic's merged order (`direction_from: "merged_order"`).

**C4 — the owned-terms clue needs two words.** A chunk *uses* another concept's terms only when it
contains **at least `MIN_SHARED_TERMS` (= 2) distinct stems that concept owns** (Dunning G², owners
unchanged). The name clue is unchanged.
- A pair whose **only** text evidence is single-word term use (no name use, no 2-term use, no
  heading, not `parallel`) becomes **pending** with the contradiction `weak_terms`, direction the
  PDF order (or merged order across PDFs). It is never accepted automatically and never dropped.
- `parallel` still means no link, before anything else.

Unchanged: `reverse_name`, `pdfs_disagree`, `backward_only`, heading containment, the
`pdf_agreement` suggestion, loop breaking, redundancy, Kahn ordering, teacher statuses.

Stored evidence: `records.terms` keeps `use` / `use_back` (now the 2-term shares) and adds
`single_word_use` / `single_word_use_back` (the old 1-term shares) so the review screen can say which
word. `reasons.link_reason` adds one sentence for `weak_terms`: "Only one shared word links them
(<word>); please confirm."

## 4. Rejected, with the measurement

- **Stop flagging "the earlier names the later more" (overview fix):** +2 covered, but wrong links
  in moved lessons 4 → 9. That flag is what catches misplaced concepts.
- **Shared heading blocks only when they never refer to each other (siblings fix):** 357 +1, but 340
  wrong-way links 2 → 5 (Solid ↔ Liquid linked).

## 5. Design-set measurement (prototype, 2026-10-02)

| | v6 | v6.1 (C2+C3+C4) |
|---|---|---|
| 340 covered / precision / wrong-way | 10/23 · 0.76 · 2 | 13/23 · 0.85 · 0 |
| 357 covered / precision / wrong-way | 16/20 · 1.00 · 0 | 11/20 · 1.00 · 0 |
| Moved lessons (moves 1–4): repaired / wrong | 7 / 4 | 7 / 0 |
| Pending suggestions 340 / 357 | 46 / 15 | 36 / 23 |

Cost: 357's step chain (Pollination → Fertilization → Seed) rests on single shared words and drops
from accepted to suggested.

## 6. Evaluation

**Design set:** 340, 357 (all tuning happens here; `MIN_SHARED_TERMS` is the only number).

**Final check (scored once, after the rules are frozen):** the three new topics, never read by the
designer:
- 351 Human Major Body Organs, 365 Living things depend on their environment, 353 The Human Organ
  System at Work — one PDF each, uploaded 2026-10-02.
- Keys drafted 2026-10-02 by a separate AI agent from the PDF and the database concepts, with the
  concept list in **shuffled order** and the instruction to decide by meaning, not position; then
  **reviewed by the user**. Stored as `docs/learning-path-new-topic-keys/key_<id>.json`.
- Before any v6.1 code: the user signs off the keys, and each topic is frozen with
  `python manage.py export_live_concepts <id> docs/learning-path-new-topic-keys/key_<id>.json
  learning_path/fixtures/gold_topic_<id>.json`, then committed. The designer does not print these
  fixtures.

**Measures**, v6 and v6.1 and the order-only baseline, same code (`evaluate_gold_paths`): covered,
accepted precision, wrong-way (forbidden) accepted, pending, per topic and summed over the three.

**Stop rule (fixed now).** v6.1 replaces v6 only if, summed over 351/353/365:
1. wrong-way accepted links ≤ v6's;
2. accepted precision ≥ v6's + 0.05;
3. covered ≥ v6's − 3.

Otherwise v6 stays and the report says why. 341–348 are reported as a secondary, already-seen set.

**Stated before the run:** process-step lessons (one shared word between steps) will lose accepted
links to suggestions, as 357 did.

## 7. Tests

- `test_fusion`: a figure pair and a cross-PDF pair are accepted; a single-word-only pair is
  pending with `weak_terms`; `parallel` still wins.
- `test_clues`: a chunk with one owned term does not count as term use; two do.
- `test_criteria`: v6's end-to-end tests for figures and different files change to "accepted";
  one new end-to-end single-word case.
- `test_reasons`: the `weak_terms` sentence names the word.
- `test_gold_paths`: floors for 340/357 become the v6.1 values; tests for 351/353/365 are added
  after the single run, with its values.

## 8. v7 wrap-up (same branch)

v7 (three direction votes, `docs/superpowers/specs/2026-10-01-learning-path-v7-direction-votes-design.md`)
is **not adopted**: on the design set it repaired fewer moved links than v6 (3 vs 7) because the
reference and subsumption votes both read overviews backwards. Its code stays, off by default
(`rule="three-votes"`); its final check (moves 5–9 on 341–348) is unspent. The design outputs
(`docs/learning-path-v7-evaluation/design-v6.json`, `design-v7.json`) are committed with a short
note in `CRITERIA.md`.

## 9. Risks

- Two design topics; the stop rule rests on three single-PDF topics with AI-drafted, user-reviewed
  keys.
- C4 trades coverage for precision; on lessons whose steps share one word the automatic path
  thins out, and more falls to the teacher's review.
- Heading matches on generic words ("Example") remain (3 wrong links on 340); fixing them needs a
  rule about which headings count, which this version does not attempt.
