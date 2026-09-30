# Course-level learning path: evaluation, 2026-09-30

Rules as committed after course spec amendment 1 (`docs/superpowers/specs/2026-09-30-course-learning-path-design.md`
§11): across topics only name and terms vote, and they must agree; the outline decides accepted
(follows it) vs pending-flagged (contradicts it). Calibration: `backend/learning_path/calibration/weights.json`.
Fixtures: `backend/learning_path/fixtures/gold_course_*.json` (keys: `gold_course_map_*.json`).

## Sets

| Role | Pair | Key |
|---|---|---|
| Design | 340 Solid, Liquid and Gas ↔ 341 Grouping Materials | AI-drafted: no links |
| Test | 340 ↔ 343 Mixtures | AI-drafted: 5 links |
| Test | 340 ↔ 347 Changes due to Oxygen and Heat | AI-drafted: 3 links |
| Test | 343 ↔ 348 Separating Mixture | AI-drafted: 8 links |
| Unrelated control | 357 Flowering plants ↔ 340, 341, 343, 347, 348 | none needed |

Keys come from the same AI tool as the topic-level keys, asked per pair which concepts of the
second topic need which of the first (snapshots `docs/course-pair-<a>-<b>-2026-09-30.md`). Not
teacher-verified. 347 replaced 345 because the "Changes" PDF was placed there.

## Design pair (340 ↔ 341), where the rule was chosen

| Rule | Accepted | Pending | Outline flags |
|---|---|---|---|
| spec §3 (≥ 2 of name/terms/meaning agree) | 8 (all wrong) | 41 | 17 (all wrong) |
| meaning silenced | 0 | 31 | 13 (all wrong) |
| **amendment 1: name and terms must agree** | **0** | **0** | **0** |

## Test pairs and controls (rule frozen, measured once)

| Pair | Key links | Reached | Accepted | Accepted precision | Pending | Flags |
|---|---|---|---|---|---|---|
| 340 ↔ 343 | 5 | 2 | 5 | 0.40 | 0 | 0 |
| 340 ↔ 347 | 3 | 0 | 0 | — | 0 | 0 |
| 343 ↔ 348 | 8 | 0 | 0 | — | 0 | 0 |
| 357 ↔ each (5 pairs) | 0 | — | **0** | — | **0** | 0 |

**The unrelated control holds perfectly; recall on related topics is poor (2 of 16).**

## Why (diagnosis only; nothing was changed after this)

Clue votes on the 16 key links of the test pairs:

| Clue | Right | Wrong | Silent |
|---|---|---|---|
| name | 4 | 0 | 12 |
| terms | 5 | 4 | 7 |
| meaning | 11 | 4 | 1 |

- On real cross-topic links the meaning clue mostly points the right way (11 / 4) — unlike within
  a topic, where it was at chance.
- The design pair's false links were an **existence** problem, not a direction problem: topics of
  one subject are "related" almost everywhere (relatedness 0.25–0.45 against a cutoff of 0.25
  calibrated on *different* subjects), so clues vote on pairs that have no prerequisite at all.
- Requiring name *and* terms removes the invented links but also the real ones: the name clue is
  silent on 12 of 16 key links (the second topic rarely names the first topic's concept).

## What this suggests (not implemented)

Separate the two questions: **existence** from a same-subject relatedness cutoff (the design pair
is exactly a "related subject, no prerequisites" null distribution), **direction** from the
content clues including meaning. Because the three test pairs above have now been examined, any
such change must be measured on pairs not yet used: 341 ↔ 343, 341 ↔ 347, 347 ↔ 348.

## Caveats

AI-drafted keys; one course, one subject chain; the first design pair's key has no links, so the
design step could only tune against false positives.
