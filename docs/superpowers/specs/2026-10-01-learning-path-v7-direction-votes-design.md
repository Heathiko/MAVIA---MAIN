# Learning-path criteria v7: direction by three votes — design

**Status:** draft for review, 2026-10-01. Branch `learning-path-graph-screen`.
**Replaces:** v6's direction rule (`fusion.reference_verdict`). v6's existence rule is kept.
**Background:** `docs/learning-path-v6-evaluation-2026-09-30.md`; the conversation of 2026-10-01
(literature: Sanderson & Croft 1999 subsumption; Liang et al. 2015 RefD; Wang et al. 2016 headings;
Pan et al. 2017 order features).

## 1. What changes for the teacher and the learner

In v6 the lesson's order **decides** which way every link points; only a heading can overrule it.
In v7 the order is **one of three votes**. A concept can move away from its PDF position when the
two votes that do not read the order both say it belongs elsewhere.

*Example.* If a lesson put "Comparing the Three States" before "Solid", v6 would link
Comparing → Solid (wrong). In v7, if the hierarchy and reference votes both say Solid comes first,
they outvote the order and the link is Solid → Comparing, labelled "outvoted the lesson order" on
the review screen.

When a lesson is too thin for the other two votes to say anything (one chunk per concept), the
order still decides, and the link says so ("direction from lesson order only").

## 2. Scope

- **In:** the direction of each link that v6's existence rule finds; the evidence stored on it; the
  review-screen sentence; a spreadsheet export; the moved-concept test harness; the evaluation.
- **Out:** which pairs are related (stage 1). v6's rule stays as it is: text reference (name or owned
  terms) or heading → candidate; `parallel` → no link; text silent + 2+ PDFs agree → pending.
  Replacing it with similarity is separate, later work.
- **Unchanged:** teacher statuses (`approved`/`rejected` never overwritten), loop breaking,
  redundancy flags, Kahn ordering with ties to merged PDF order, the adaptive engine.

## 3. Constraints (user, 2026-10-01)

1. No LLM / black box. 2. No template or regex hunting for phrases; matching a concept's **own name**
(stemmed) and its statistically **owned terms** is allowed. 3. Every number and verdict can be
recomputed in a spreadsheet with `SUM`, `SUMPRODUCT`, `COUNTIF`, `IF`, `AVERAGE`.

## 4. The block × concept matrix

- **Block** = one extracted chunk (a concept's member). Each block has an **owner** (the concept it
  belongs to), a PDF (`material_id`) and a position (`order`).
- **Present(c, k) = 1** when block k is owned by c, **or** contains every stem of c's name
  (`name_terms`; titles that are sentences have no name), **or** contains at least `MIN_OWNED_TERMS`
  (= 2) distinct stems that c owns (Dunning G², `find_term_owners`, unchanged). Otherwise 0.
- `Blocks(c)` = number of blocks where c is present. `Both(a, b)` = `SUMPRODUCT` of the two rows.

## 5. The three votes

Each vote is **+1** (A before B), **−1** (B before A) or **0** (abstains). A and B are the pair in the
topic's merged order.

**H — Hierarchy (is one broader?)**
1. Heading: B under a heading naming A → +1; A under a heading naming B → −1 (v6 `heading_vote`).
2. Else, if `Blocks(A) ≥ MIN_BLOCKS` (3) and `Blocks(B) ≥ MIN_BLOCKS`: coverage subsumption
   (Sanderson & Croft 1999). `P(A|B) = Both/Blocks(B)`, `P(B|A) = Both/Blocks(A)`.
   `P(A|B) ≥ SUBSUME_HIGH` (0.8) and `P(B|A) ≤ SUBSUME_LOW` (0.5) → +1; the mirror → −1.
3. Else 0.

**O — Order (which is taught first?)**
- **Teaching centre** of c in a PDF = `AVERAGE` of the positions of c's **own** blocks in that PDF.
- In every PDF that has own blocks of both: the one with the lower centre is first. All such PDFs
  agree → that direction; they disagree, or no PDF has both → 0.

**R — Reference (which builds on the other?)**
- `B_refers_A` = share of B's own blocks where A is present; `A_refers_B` likewise.
- `B_refers_A − A_refers_B ≥ REFERENCE_GAP` (0.25) → +1; `≤ −REFERENCE_GAP` → −1; else 0.

Known failures, by design different from each other: H — examples-first lessons, recaps;
O — a concept placed wrongly; R — overviews (they mention their children).

## 6. The verdict

`Voters` = number of non-zero votes; `Total` = H + O + R.

| # | Situation | Verdict | `direction_from` |
|---|---|---|---|
| 1 | no vote against the majority, `Voters ≥ 2` | **accepted** | `votes_agree` |
| 2 | `Voters = 3`, two against one | **accepted** | `outvoted_order` if O is the one outvoted, else `majority` |
| 3 | only O votes (H and R abstain) | **accepted** | `order_only` |
| 4 | only H or only R votes | pending | that vote |
| 5 | `Voters = 2` and they disagree | pending | the order's direction (shown as contested) |
| 6 | no vote | pending | merged order |

Silence is not disagreement (user decision A, 2026-10-01): row 3 lets the order accept alone.
Rows 1–3 only apply to pairs the existence rule admits; v6's `pdf_agreement`-only pending is kept.
In spreadsheet form (one row per pair, H/O/R in three cells):

```
Voters  =COUNTIF(H2:J2,"<>0")
Total   =SUM(H2:J2)
Verdict =IF(Voters=0,"pending",IF(AND(Voters=1,I2=0),"pending",IF(ABS(Total)>=Voters-(Voters=3)*2,"accepted","pending")))
```
(`I2` is O. With 3 voters, |Total| ≥ 1 means a 2–1 or 3–0 majority; with 2, |Total| = 2 means agreement;
with 1, only O accepts.)

Stored on each link's `evidence`: `rule: "three-votes"`, `votes {hierarchy, order, reference}`,
`hierarchy_from` (`heading`/`subsumption`/none), the matrix numbers (`blocks_a`, `blocks_b`, `both`,
`p_a_given_b`, `p_b_given_a`, `a_refers_b`, `b_refers_a`, the teaching centres per PDF),
`direction_from`, `relatedness`, `confidence` (= share of voters agreeing with the verdict's
direction). `reasons.link_reason` gets one plain sentence per `direction_from`, e.g.
"Solid comes first: it is the broader idea and Comparing refers to it, though the lesson teaches
Comparing earlier."

## 7. Spreadsheet export

Management command `export_direction_sheet <topic>` (also on gold fixtures: `--gold <id>`)
writes one CSV that Excel opens with live formulas: the matrix (concepts × blocks, 0/1), then a pair
table whose `Blocks`, `Both`, `P(A|B)`, `P(B|A)`, reference shares, votes, `Voters`, `Total` and
`Verdict` cells are formulas over the matrix (`SUMPRODUCT`, `SUM`, `COUNTIF`, `IF`). Teaching centres
are exported as values (positions are data). A test opens the CSV's numbers against the Python result
for 340 and 357. No new dependency (no `openpyxl` installed).

## 8. Evaluation

**Sets (user, 2026-10-01).** Design: 340, 357. Final check: 341, 343, 347, 348 — scored **once**,
after the rules and cut-offs are frozen at a named commit. 62/79/152 are left out.

**Moves (approved 2026-10-01, fixed before any v7 code).** Stored in
`fixtures/direction_moves.json`. A move relocates all blocks of one concept; in every PDF where the
concept has blocks it is placed immediately before the target's first block ("before"),
immediately after the target's last block ("after"), or at the PDF's start/end. A PDF without the
target leaves the concept where it is. The answer key is unchanged.

| # | Set | Topic | Move |
|---|---|---|---|
| 1 | design | 340 | `summary` → start |
| 2 | design | 340 | `comparing` and `comparing_detail` → before `solid` |
| 3 | design | 357 | `fertilization` → before `pollination` |
| 4 | design | 357 | `reproduction` → after `petals` |
| 5 | final | 341 | `properties` → end |
| 6 | final | 343 | `activity` → start |
| 7 | final | 347 | `reversible` → start |
| 8 | final | 348 | `choosing_text` and `choosing_table` → after `why_separable` |
| 9 | final | 348 | `filtering` → before `decantation` |

Each move is scored separately (one moved copy of the topic per move).

**Measures**, v6 and v7 side by side, same measuring code (`gold.py`):
- *Unmoved topics:* covered, accepted precision, forbidden accepted, wrong-way accepted, pending.
- *Moved copies:* of the moved concept's key links, how many are accepted the key's way, accepted
  the wrong way, pending; plus wrong-way accepted links elsewhere in the topic.
- *Votes:* right / wrong / silent per vote on key links (as `clue_accuracy`).

**What may be tuned on the design set only:** `MIN_OWNED_TERMS`, `MIN_BLOCKS`, `SUBSUME_HIGH`,
`SUBSUME_LOW`, `REFERENCE_GAP`. Starting values are the spike's (§4–5).

**Stop rule (fixed now).** v7 is kept only if, on the final check: forbidden accepted = 0 on unmoved
topics; accepted precision on unmoved topics ≥ v6's − 0.05 (v6: 0.68); and on the moved copies v7
accepts more key links the key's way than v6 does. Otherwise v6 stays and the report says why.

**Expected weakness, stated before the run:** in 347 and 348 most concepts are one chunk that
mentions nothing else (median 1 block per concept), so H and R will mostly abstain, the order will
decide, and moves 7–9 will probably not be repaired.

## 9. Feasibility spike (2026-10-01, throwaway)

On the 43 key links of 340 + 357 with the starting values: 20 accepted right, **0 accepted wrong**,
23 pending (with the old "2 voters" rule; row 3 will turn order-only pairs into accepted).
H voted 6 times (4 headings, 2 subsumption), all right; O 35 right / 3 wrong (the disputed
"general rule" links); R 18 right / 7 wrong (overviews), always outvoted. One link was accepted
against the order: Solid → "As a general rule", the key's direction.

## 10. Risks

- Subsumption seldom fires on real lessons (2 of 43); H is mostly headings. Loosening it is a
  design-set decision, not a test-set one.
- The test keys lean toward PDF order (AI-drafted from PDF-ordered snapshots); the moves are the
  check that does not depend on that.
- Two design topics with AI-drafted keys are a thin base for tuning five numbers; prefer leaving the
  starting values over fitting them.
- Name/owned-term presence misses concepts referred to by parts or synonyms.
