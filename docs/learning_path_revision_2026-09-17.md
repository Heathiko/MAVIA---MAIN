# Learning-path criteria revision (2026-09-17)

For the manuscript's revision notes beside §2.6. Gold standard: the teacher's
prerequisite map for two uploaded lessons (`backend/learning_path/fixtures/gold_map_*.json`).

## Before (criteria v3: name-to-window SBERT similarity, cross-section cap)

| Topic | Required accepted | Forbidden accepted | Order matches |
|---|---|---|---|
| 62 Solid, Liquid and Gas | 0 / 10 | 1 | yes |
| 79 Reproduction Among Flowering Plants | 1 / 8 | 0 | yes |

## After (RefD key-term reference, Examples structural, no cross-section cap)

Constants: REF_MAX_DF_RATIO = 0.34, REF_MARGIN = 0.0, PHRASE_COSINE = 0.80, MIN_IOL_MARGIN = 0.25

Only `REF_MARGIN` moved from its previous default (0.05 -> 0.0); the grid
(`evaluate_gold_paths --grid`) confirmed the other three at their existing
values -- no row in the top 15 (sorted by forbidden ascending, then required
hits descending, then orders matching) beat them.

| Topic | Required accepted | Forbidden accepted | Order matches |
|---|---|---|---|
| 62 Solid, Liquid and Gas | 10 / 10 | 0 | yes |
| 79 Reproduction Among Flowering Plants | 4 / 8 | 0 | yes |

Extra accepted edges (not required, not forbidden):
- Topic 62: matter->changing, matter->comparing
- Topic 79: reproduction->pollination

## Known gaps

Two calibration runs stopped short of the full gold standard. The first, at
the defaults, reached 6/10 on topic 62 and 0/8 on topic 79. The second, after
the Task 7b amendment below, reached 9/10 and 4/8 at the defaults; its grid
found no row with 0 forbidden edges above 14 of the 18 required edges, and the
best such row differed from the defaults only in `REF_MARGIN` (the values above). The user decided to stop tuning here and accept this result
rather than add lesson-specific rules, word lists, or thresholds tuned to a
single edge. Four required edges on topic 79 (Reproduction Among Flowering
Plants) are not accepted under any grid row that keeps 0 forbidden edges, and
are recorded as `known_missing` in `gold_map_79.json` / `gold_topic_79.json`
rather than silently dropped from the test assertions:

- **Stamen -> Pollination** and **Pistil -> Pollination** come out **pending**
  (teacher-approvable): shared part-terms ("anther", "stigma", "pollen")
  exceed the distinctiveness limit (`REF_MAX_DF_RATIO`), because the
  Reproduction overview section also uses them, pushing their document
  frequency past the cap that would let them count as key terms.
- **Pollination -> Fertilization** and **Fertilization -> Seed** are **not
  proposed at all**. The same shared-part-terms cause applies to
  Pollination -> Fertilization. Fertilization -> Seed additionally fails
  because Seed's text says "fertilized ovule", not "fertilization", and
  `singular()` does not unify "fertilized" with "fertilization" -- fixing that
  would need stemming or lemmatization, a logic change outside this task's
  scope.

The amendment landed in Task 7b (head-word mention and section containment as
reference, `criteria.py` `head_words`/`contained_in`, spec §6) closed 7 of the
original 11 missing edges (6/10 -> 10/10 on topic 62, 0/8 -> 4/8 on topic 79)
before calibration; the remaining four are the ones above.

## Live re-run (2026-09-18)

Both topics were merged by the teacher in the UI and republished, then the
derived paths were compared with the gold standard.

| Topic | Required accepted | Forbidden accepted | Order matches |
|---|---|---|---|
| 62 Solid, Liquid and Gas | 10 / 10 | 0 | yes |
| 79 Reproduction Among Flowering Plants | 4 / 8 | 0 | yes |

Live matches the fixture-based measurement exactly, including which four edges
are missing (the documented known gaps in topic 79). Extra accepted edges:
topic 62 `matter -> comparing`, `matter -> changing`; topic 79
`reproduction -> pollination`. All three are transitive or plausible, none
forbidden.

Merges the teacher applied on topic 62: the four comparison items with the
comparison section and its table; Solid, Liquid and Gas each with the other
file's section, diagram and examples; both Everyday Examples sections; the
particle figure with Matter; "Changing From One State to Another" with its
figure; the two-part Matter introduction. On topic 79: the flower figure with
the introduction in each file. 23 concepts became 7 (topic 62) and 10 became 9
(topic 79).

Three defects surfaced during the run and were fixed before the comparison
above (`object_merge.py`, plus two UI bugs):

1. A merged concept took its title from the first member, so a figure with no
   heading named the concept ("Okay, let's describe this figure for the
   student"). The concept then had no usable name and lost its edges. The title
   now comes from the first heading among the members. Measured before the fix:
   7/10 and 1/8.
2. A merged row kept a stale "taught through" marker, so the versions screen
   refused to generate its missing versions.
3. Resetting the group's version selection discarded a locked label, and the
   group label kept the pre-merge title.

Rows merged before the fix were repaired in place from their stored snapshots,
and both paths were re-derived.
