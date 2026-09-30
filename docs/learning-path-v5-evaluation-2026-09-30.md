# Learning-path criteria v5: evaluation, 2026-09-30

Measured (after the final-review fixes, with topic 357 added) with
`python manage.py evaluate_gold_paths` on the frozen fixtures, the stored calibration
(`backend/learning_path/calibration/weights.json`, topics 62/79/152/340/357) and the pinned
encoder. Raw outputs are in [`learning-path-v5-evaluation/`](learning-path-v5-evaluation/).
v4 numbers: [`learning-path-v4-baseline-2026-09-30.json`](learning-path-v4-baseline-2026-09-30.json)
and, for 357, [`learning-path-v4-baseline-357.json`](learning-path-v4-baseline-357.json) (v4 run
read-only from commit db3671a with the same 357 fixture). v4 is as it stood on this branch,
including the trail-section links of commit a17c31d.
Design: [spec](superpowers/specs/2026-09-30-learning-path-evidence-fusion-design.md), §14 = the
two-family amendment.

## Sets

| Set | Topics | Key source |
|---|---|---|
| Development | 62, 79, 152 | teacher maps from 2026-09; examples un-marked as structural 2026-09-30 (user decision) |
| Test | 340, 357 | AI-drafted recommendations (one tool, same prompt), not teacher-verified |

## v4 vs v5

| Topic | Required | v4 reachable | v5 reachable | v4 τ | v5 τ | v4 forbidden | v5 forbidden | v5 accepted | v5 accepted precision | v5 pending | gate loss |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 62 (dev) | 10 | 9 | **5** | 1.00 | 1.00 | 0 | 0 | 2 | 0.00 | 11 | 0 |
| 79 (dev) | 8 | 3 | 3 | 1.00 | 1.00 | 0 | 0 | 8 | 0.50 | 12 | 0 |
| 152 (dev) | 10 | 8 | **10** | 1.00 | 0.81 | 0 | 0 | 7 | 0.57 | 20 | 0 |
| **340 (test)** | 23 | 11 | **18** | 0.70 | **0.75** | 0 | **0** | 24 | **0.92** | 62 | 0 |
| **357 (test)** | 20 | 8 | **14** | 1.00 | 1.00 | 0 | **0** | 13 | **1.00** | 18 | 0 |

Reachable = required links found as accepted or pending. Accepted precision = accepted links that
are in the key or implied by it.

**Reading it.**
- On both test topics v5 finds far more of the key's links (340: 18 vs 11 of 23; 357: 14 vs 8 of
  20), accepts no forbidden link, and its accepted links are almost all right (0.92 and 1.00).
  Order agreement is as good or better (340: 0.75 vs 0.70; 357: 1.00 both).
- Gold 62 loses reach (5 vs 9): v4 accepted heading containment on its own; v5 needs the text to
  agree, and 62's short passages often do not name their parent.
- Accepted precision on 62/79 is low because most accepted links there touch "examples", which
  the development keys no longer score (neither required nor forbidden) — they count as extras.
- 62 pending suggestions on 340 is a lot for one review screen; each is a text-only or disputed
  link the teacher decides.
- The relatedness gate blocked none of the key's links (gate loss 0 everywhere).

## Clue by clue (right / wrong on the key's links, when the clue votes)

| Clue | 62 | 79 | 152 | 340 | 357 | Total |
|---|---|---|---|---|---|---|
| name (content) | 6 / 3 | 1 / 2 | 7 / 0 | 12 / 3 | 3 / 2 | 29 / 10 |
| terms (content) | 2 / 4 | 2 / 0 | 9 / 4 | 15 / 6 | 8 / 2 | 36 / 16 |
| meaning (content) | 2 / 6 | 3 / 1 | 8 / 6 | 9 / 8 | 5 / 4 | 27 / 25 |
| heading (structure) | 3 / 0 | 3 / 0 | 3 / 0 | 0 / 0 | 4 / 0 | 13 / 0 |
| PDF order (structure) | 6 / 0 | 8 / 0 | 3 / 0 | 3 / 0 | 19 / 0 | 39 / 0 |

- The two structure clues are never wrong when they vote but often do not vote (single-PDF pairs,
  pairs without a shared heading); structure alone never makes a link.
- **The meaning clue is at chance on direction** (27 / 25). It stays in the content family because
  removing it lowers reach on 152, 340 and 357 (ablation below), but it should not be described in
  the manuscript as a direction signal — only as part of the content family's vote.
- Calibration agreement with the other clues' majority (`weights.json`): name 0.73, terms 0.56,
  meaning 0.58, heading 0.50, order 0.56 (294 related pairs). Heading and order disagree with the
  content clues on parent/child pairs — the overview effect — which is why learned weights were
  dropped for verdicts (spec §14). Cutoffs: related 0.247, meaning 0.301.

## Ablation (v5 without one clue): reachable, τ, forbidden, accepted

| Without | 62 | 79 | 152 | 340 | 357 |
|---|---|---|---|---|---|
| — (v5) | 5, 1.00, 0, 2 | 3, 1.00, 0, 8 | 10, 0.81, 0, 7 | 18, 0.75, 0, 24 | 14, 1.00, 0, 13 |
| name | 5, 1.00, 0, 0 | 4, 1.00, 0, 10 | 10, 0.81, 0, 1 | 11, 0.68, 0, 8 | 12, 1.00, 0, 12 |
| terms | 2, 1.00, 0, 2 | 2, 1.00, 0, 7 | 9, 0.81, 0, 3 | 14, 0.68, 0, 8 | 7, 0.96, 0, 9 |
| meaning | 8, 1.00, 0, 4 | 5, 1.00, 0, 5 | 7, 0.81, 0, 3 | 15, 0.68, 0, 9 | 8, 1.00, 0, 8 |
| heading | 5, 1.00, 0, 2 | 3, 1.00, 0, 8 | 7, 0.81, 0, 7 | 18, 0.75, 0, 21 | 14, 0.96, 0, 12 |
| order | 5, 1.00, 0, 0 | 3, 1.00, 0, 1 | 10, 0.81, 0, 5 | 15, 0.71, **1**, 22 | 11, 1.00, 0, 4 |

- Every content clue earns its place on both test topics (removing any one lowers reach there).
- **PDF order is the safety net:** without it, 340 accepts a forbidden link; on 357 it carries
  most accepted links (4 without it vs 13).
- Removing meaning *raises* reach on 62 and 79 — consistent with it being at chance there.

## Development-set decisions (made on 62/79/152 only, by rules fixed in the plan)

1. **Meaning clue size fallback (average of 2 best matches): not adopted.** Meaning right/wrong on
   the development set was 13/13 with one match and 14/14 with two — no bias to correct.
2. **Kahn tie-break "build on the latest step": off by default.** Mean τ over 62/79/152 was 0.78
   with it and 0.94 without. Because the development keys still put examples last, it was
   re-measured with examples left out: 62 1.00/1.00, 79 0.71/1.00, 152 0.73/1.00 (with/without).
   It stays available as `order_with_links(..., build_on_latest=True)` and
   `evaluate_gold_paths --build-on-latest`. Consequence: on 340 examples are not pulled before
   Changing State unless a link requires it. (Read afterwards, not used to decide: on 357 it would
   have lowered τ from 1.00 to 0.78.)

## Limitations

- The test keys for 340 and 357 are **AI-drafted recommendations**, not teacher-verified: the
  numbers measure agreement with that reference, not with teachers.
- The development keys were partly built around v4's heading rules, and their expected orders
  still put examples last, against the 2026-09-30 decision.
- Two test topics from one course; the unseen uploads (309, 311, 313, 316) are needed before a
  general claim.
- Heading containment compares headings with concept names (word matching). It is used only in
  the structure family and never makes a link alone.
