# Learning-path criteria v6.1: evaluation, 2026-10-02

v6.1 = v6 with cleaner edges: a figure or a different PDF no longer blocks a link, and a link
resting on a single shared word becomes a teacher suggestion (`weak_terms`).
[Spec](superpowers/specs/2026-10-02-learning-path-v6-1-edge-quality-design.md) ·
[plan](superpowers/plans/2026-10-02-learning-path-v6-1-edge-quality.md) ·
raw outputs in [`learning-path-v6-1-evaluation/`](learning-path-v6-1-evaluation/).

**Frozen rule version:** commit `75e39a2`. The final check was scored once, at that commit;
nothing in `services/` changed after it. Outcome: **v6.1 passed the stop rule and is the default**
(`criteria.DEFAULT_RULE = CLEANER_EDGES`); v6 stays selectable as `rule="reference-order"`.

## Sets

| Set | Topics | Keys |
|---|---|---|
| Design | 340, 357 | AI-drafted (2026-09), seen during several designs |
| **Final check** | **351, 353, 365** (uploaded 2026-10-02, one PDF each) | Drafted by a separate AI agent from the PDF and the database concepts, concept list **shuffled**, edges decided by meaning; **reviewed and approved by the user**; frozen (445655e) before any v6.1 code |
| Seen | 341, 343, 347, 348 | AI-drafted from PDF-ordered snapshots; already scored with v6 |

The designer did not open the new PDFs, keys or fixtures before the run; it saw the concept
titles only (to export the shuffled list).

## How to read the numbers

**Covered:** required links reached by accepted links, directly or through a chain.
**Precision:** share of accepted links that are in the key or implied by it. **Wrong-way:**
accepted links the key forbids (reversed, or between concepts it lists as parallel).
**Order-only:** each concept linked to the one before it, no text read.

## Design set (340 + 357)

| | v6 | v6.1 | Order-only |
|---|---|---|---|
| 340 covered / precision / wrong-way / pending | 10/23 · 0.76 · 2 · 46 | 13/23 · 0.85 · 0 · 36 | 18/23 · 0.43 · 3 · 0 |
| 357 covered / precision / wrong-way / pending | 16/20 · 1.00 · 0 · 15 | 11/20 · 1.00 · 0 · 23 | 19/20 · 0.44 · 2 · 0 |
| Moved lessons (moves 1–4): repaired / wrong | 7 / 4 | 7 / 0 | — |

Identical to the prototype measured before the plan; `MIN_SHARED_TERMS` kept at 2.

## Final check (351 + 353 + 365, single run)

| Topic | Required | v6: covered · precision · wrong-way · pending | v6.1 | Order-only |
|---|---|---|---|---|
| 351 Major organs | 19 | 5 · 0.38 · 7 · 23 | **10 · 0.69 · 5** · 20 | 19 · 0.30 · 6 · 0 |
| 353 Organ systems at work | 8 | 2 · 0.27 · 8 · 21 | 2 · 0.23 · 7 · 21 | 8 · 0.43 · 2 · 0 |
| 365 Living things & environment | 13 | 8 · 0.85 · 1 · 14 | 2 · 0.88 · **0** · 18 | 13 · 0.29 · 3 · 0 |
| **Total** | 40 | **15 · 0.49 · 16 · 58** | **14 · 0.57 · 12 · 59** | 40 · 0.33 · 11 · 0 |

**Stop rule (fixed in the spec before the run), summed over the three topics:**
1. wrong-way v6.1 ≤ v6: 12 ≤ 16 ✔
2. precision v6.1 ≥ v6 + 0.05: 0.568 ≥ 0.538 ✔
3. covered v6.1 ≥ v6 − 3: 14 ≥ 12 ✔

**v6.1 passes.**

## Seen set (341–348, secondary)

| | v6 (2026-09-30) | v6.1 |
|---|---|---|
| covered / accepted / precision / wrong-way / pending | 20/41 · 28 · 0.68 · 0 · 35 | 8/41 · 15 · 0.73 · 0 · 48 |

## Reading it

1. **The new, blind keys show v6 was weaker than the old test said.** On 341–348 v6 had precision
   0.68 and no wrong-way link; on the new topics it has precision 0.49 and 16 wrong-way links.
   The order-only chain tells why: it had 0 wrong-way links on 341–348 but has 11 here. The old keys
   were drafted in PDF order and leaned toward it; the shuffled keys do not. The earlier figures
   flattered every method that takes direction from the PDF.
2. **v6.1 makes the automatic edges cleaner, as designed:** fewer wrong-way links (16 → 12), higher
   precision (0.49 → 0.57), the same coverage (15 → 14). On 351 it is better on every measure.
3. **The cost is coverage on lessons whose links rest on one shared word:** 365 drops from 8 to 2
   covered links (those links are now teacher suggestions, not gone), and the seen set drops from
   20 to 8. On single-PDF lessons with sentence titles, much more of the path now needs the
   teacher's approval.
4. **The main remaining error is linking parallel concepts.** Most of v6.1's wrong-way links are
   between concepts the key keeps parallel: organs on 351 (Brain → Bones and Muscles) and the four
   "teamwork" systems on 353, which are linked to each other in both directions. v6 only recognises
   parallel concepts by a shared heading that names neither, and these lessons do not provide one.
   This is where the next improvement would pay most.

## Limits

- Three single-PDF topics from one course and one subject area (the human body, environment);
  40 required links.
- Keys are AI-drafted, then reviewed by the user (not by a practising teacher); 365 and 353 merge
  some split concepts into one key (the drafting agent's judgment, approved by the user).
- The designer saw the new topics' concept titles; not their text, keys or results.
- Precision and wrong-way depend on the keys' parallel groups, which are a judgment call.
