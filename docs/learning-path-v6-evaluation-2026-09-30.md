# Learning-path criteria v6: evaluation, 2026-09-30

v6 = the text decides whether a prerequisite link exists, the lesson's order decides which way;
uncontradicted links are accepted, contradicted ones are suggestions.
[Spec](superpowers/specs/2026-09-30-learning-path-v6-reference-order-design.md) ·
[plan](superpowers/plans/2026-09-30-learning-path-v6-reference-order.md) ·
raw outputs in [`learning-path-v6-evaluation/`](learning-path-v6-evaluation/).

**Frozen rule version:** commit `b42b364` (branch `learning-path-graph-screen`). The test set was
scored once, at that commit, after the development work; nothing in `services/` changed after it.
v5 was run from commit `3ae921d` in a temporary worktree with the same measuring code
(`gold.py`, `evaluate_gold_paths.py` copied in), so all three columns are measured the same way.

## Sets

| Set | Topics | Keys |
|---|---|---|
| Development | 62, 79, 152 (teacher maps, 2026-09); 340, 357 | 340/357: AI-drafted, measured after several design changes |
| Test | 341, 343, 347, 348 | AI-drafted 2026-09-30 from the snapshots, before any design work; all single-PDF |

No extra lesson of a different kind and no second key existed at the freeze; either can still be
scored later at `b42b364`.

## How to read the numbers

- **Covered:** a required link of the key is reached by accepted links, directly or through a
  chain (how the adaptive engine uses them).
- **Accepted precision:** share of accepted links that are in the key or implied by it — the
  detours a learner would really be sent on.
- **Order-only baseline:** each concept linked to the one just before it, no text read. Its chain
  covers every required link that follows the PDF order *by construction*, so covered alone cannot
  judge it; the comparison is precision (spec §5, amended before the test run).
- Cells: reachable (accepted + pending) / covered / τ / forbidden accepted / accepted / precision /
  pending.

## Development set

| Topic | Required | v5 | Order-only | v6 |
|---|---|---|---|---|
| 62 | 10 | 8 / 0 / 1.00 / 0 / 2 / 0.00 / 15 | 3 / 10 / 1.00 / 2 / 6 / 0.50 / 0 | 9 / 9 / 1.00 / 0 / 17 / 0.65 / 0 |
| 79 | 8 | 7 / 2 / 1.00 / 0 / 8 / 0.50 / 25 | 4 / 8 / 1.00 / 0 / 8 / 0.50 / 0 | 5 / 5 / 1.00 / 0 / 16 / 0.62 / 11 |
| 152 | 10 | 10 / 4 / 0.81 / 0 / 7 / 0.57 / 20 | 2 / 10 / 0.81 / 2 / 7 / 0.29 / 0 | 9 / 7 / 0.81 / 0 / 11 / 0.64 / 13 |
| 340 | 23 | 18 / 5 / 0.75 / 0 / 24 / 0.92 / 62 | 4 / 18 / 0.68 / 3 / 14 / 0.43 / 0 | 19 / 10 / 0.64 / 2 / 37 / 0.76 / 46 |
| 357 | 20 | 20 / 10 / 1.00 / 0 / 13 / 1.00 / 29 | 4 / 19 / 0.96 / 2 / 9 / 0.44 / 0 | 16 / 16 / 1.00 / 0 / 18 / 1.00 / 15 |
| **Total** | 71 | covered **21**, forbidden 0, precision 0.80, pending **151** | covered 65, forbidden **9**, precision 0.43 | covered **47**, forbidden **2**, precision 0.75, pending **85** |

- The two forbidden links are "As a general rule → Liquid / Gas" on 340: the PDF teaches the rule
  first; only the AI key disagrees. Known before implementation (spec §3) and pinned in
  `test_gold_paths.KNOWN_FORBIDDEN`.
- Costs against v5: τ on 340 falls 0.75 → 0.64 (v6 follows the PDFs; the key follows the
  teacher-shaped path), reachable on 357 falls 20 → 16 and on 79 7 → 5 (some v5 suggestions are
  now neither accepted nor suggested).
- Figure-suggestion direction (spec §3, checked here): the spec's rule and the "follow the order"
  alternative both reach 58 required links with 2 wrong-way suggestions; the spec's rule was kept.

## Test set (single run)

| Topic | Required | v5 | Order-only | v6 |
|---|---|---|---|---|
| 341 | 10 | 3 / 0 / 1.00 / 0 / 0 / — / 20 | 2 / 10 / 1.00 / 0 / 7 / 0.29 / 0 | 7 / 8 / 1.00 / 0 / 10 / 0.90 / 4 |
| 343 | 5 | 3 / 0 / 1.00 / 0 / 0 / — / 7 | 1 / 5 / 1.00 / 0 / 5 / 0.20 / 0 | 5 / 4 / 1.00 / 0 / 6 / 0.67 / 6 |
| 347 | 8 | 0 / 0 / 1.00 / 0 / 0 / — / 19 | 1 / 8 / 1.00 / 0 / 7 / 0.14 / 0 | 5 / 5 / 1.00 / 0 / 6 / 0.67 / 8 |
| 348 | 18 | 2 / 0 / 1.00 / 0 / 1 / 0.00 / 40 | 2 / 18 / 1.00 / 0 / 13 / 0.15 / 0 | 7 / 3 / 1.00 / 0 / 6 / 0.33 / 17 |
| **Total** | 41 | covered **0**, accepted 1, pending **86** | covered 41 (by construction), precision **0.19** | covered **20**, precision **0.68**, pending **35** |

## Reading it

1. **v5 on unseen single-PDF topics accepts essentially nothing** (1 link in four topics, and it
   is wrong), so the adaptive engine could send a learner nowhere without a teacher. This is the
   defect v6 was built for, and it is confirmed on topics v5 never saw.
2. **v6 covers 20 of 41 required links on the test set, with no forbidden link, and its accepted
   links are right 68 % of the time** (19 of 28), against 19 % (6 of 32) for the order-only chain.
   The comparison fixed in advance (spec §5) asks for higher precision **at a comparable covered
   count**, and that condition is **not met**: the chain covers 41 by construction, v6 covers 20.
   So the pre-registered test is **inconclusive**. What the numbers do show is that the order
   alone would send learners on mostly wrong detours, while v6's accepted links are mostly right
   and cover about half of the required links.
3. **Suggestions drop from 86 to 35** on the test set (151 → 85 on the development set).
4. **Where v6 fails (348: covered 3 of 18, precision 0.33).** The key links "Why Mixtures Can Be
   Separated" (one sentence) to every technique, and the techniques to "Choosing the Right
   Technique"; those concepts share almost no words, and the technique concepts have sentence
   titles, so they have no name to be referred to by. Without headings the `parallel` flag cannot
   see that the techniques are siblings, so "Picking → Sieving" is accepted. These are the limits
   named in spec §7 (implicit links; headings).
5. **Clues on the test set:** heading and PDF order never voted (single PDF, sentence titles); the
   meaning clue pointed the right way 7 times and the wrong way 23 — worse than chance, which
   supports recording it and not counting it.
6. **τ is 1.00 for every method on the test set** and says nothing here: the keys list their
   concepts in PDF order and every method keeps the PDF order.

## Scope and limits (spec §5, §7)

- Grade-school science lessons from one course, apparently one lesson template; four test topics.
  The test set checks new topics, not new authors or subjects.
- All test keys are AI-drafted from snapshots listed in PDF order; they may lean toward the PDF
  order, which flatters any method taking direction from it (the forbidden count of 0 for the
  order-only chain on the test set is a sign of this).
- Two v6 rules (`figure`, `no_shared_pdf`) were added after seeing topic 340; `no_shared_pdf`
  cannot fire on the single-PDF test topics.
- The test topics' text was read while writing their snapshots, before the design; their keys
  were not scored until this run.
- Open: a lesson of a different kind, and a second key drafted from shuffled concepts, are the two
  remaining checks (spec §5).
