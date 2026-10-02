# Course level, top down: final check, 2026-10-03

**Outcome: the shortlist rule failed the stop rule. The strict rule stays the default
(`COURSE_DEFAULT_RULE = "strict"`); no code changed.**

## What was tested

The shortlist ("top down") rule: compare two topics only if their outline titles are close
(cosine ≥ 0.30); for each concept of the later topic, offer the 3 earlier concepts with the closest
titles (content when a title is not a real name); accept one only if the strict rule's clues also
agree, otherwise leave it pending for the teacher. Spec
`docs/superpowers/specs/2026-10-02-course-path-top-down-design.md`, plan
`docs/superpowers/plans/2026-10-02-course-path-top-down.md`. Rules frozen at `bd7498e` (later only
the error-handling fix `5d41376`, design output byte-identical).

## Sets and keys

- **Design pairs** (used to build the rule): 340-341, 340-343, 340-347, 343-348, plus five unrelated
  controls with 357.
- **Final pairs** (scored once, here): 351-353, 341-343, 341-347, 347-348, 351-365, 353-365.
  Keys drafted blind by a separate agent from the topics' text, reviewed and approved by the user
  on 2026-10-03, frozen as fixtures in `3375208` from the database backup
  `db.sqlite3.pre-reupload.20261002` (the live database was reset for re-upload). The designer
  did not open the keys. Front-matter concepts ("What I Need to Know", "2", "4") were left unkeyed
  by the drafter; any accepted link touching them counts as wrong.
- Before scoring, the designer had seen the strict rule's live output on 351-353, 351-365 and
  353-365 (titles and evidence, not keys; recorded in `docs/course-path-open-issues-2026-10-02.md`).
  Both rules were frozen then, so this does not bias the result.

## Results

Raw output: `docs/course-path-v2-evaluation/final-strict.json`, `final-shortlist.json`.
"Hit" = later concepts with a key prerequisite that were offered the right one (accepted or pending).

| Pair | Key | Title similarity | Compared | Strict: accepted (right) | Strict hit | Shortlist: accepted / pending | Shortlist hit |
|---|---|---|---|---|---|---|---|
| 351-353 | related, 23 links | 0.67 | yes | 8 (6) | 4/10 | 0 / 36 | 3/10 |
| 341-343 | related, 2 links | 0.46 | yes | 0 | 0/2 | 0 / 18 | 1/2 |
| 341-347 | related, 4 links | 0.25 | **no** | 0 | 0/4 | 0 / 0 | 0/4 |
| 347-348 | related, 3 links | 0.13 | **no** | 0 | 0/2 | 0 / 0 | 0/2 |
| 351-365 | unrelated | 0.20 | no | **3 (0)** | — | 0 / 0 | — |
| 353-365 | unrelated | 0.24 | no | 0 | — | 0 / 0 | — |
| **Total** | | | | **11 (6), 5 wrong** | **4/18** | **0 / 54** | **4/18 = 0.22** |

Design pairs, for comparison: strict 5 accepted (2 right), hit 1/12; shortlist 2 accepted (1 right),
82 pending, hit 9/12.

## Stop rule (spec section 5)

| Condition | Result | |
|---|---|---|
| 1. Unrelated pairs: no accepted, no pending | 0 and 0 | pass |
| 2. Hit rate ≥ 0.6 | 4/18 = 0.22 | **fail** |
| 3. Accepted wrong ≤ strict's | 0 vs 5 | pass |

## Why it failed

1. **The outline gate closed two related pairs.** "Grouping Materials Based on Properties" vs
   "Changes that Materials Undergo due to Oxygen and Heat" (0.25) and the latter vs "Separating
   Mixture" (0.13) fall under 0.30, yet the key links them. Those two pairs hold 6 of the 18 later
   concepts that need a prerequisite. Topic titles alone do not show that topics are related.
2. **Meaningless titles fill the 3 slots.** On 351-353, the shortlist slots went to "What Is It",
   "Picture description for Figure 2" and unkeyed front matter instead of the organs. Later concepts
   whose titles are not names ("Teamwork 2", "Table on page 4") fall back to content ranking, which
   is not on the same scale as title ranking (known limit recorded at the final review). 7 of the
   10 dependents on 351-353 missed.
3. **The design result did not carry over.** 9/12 on the design pairs, 4/18 here. Every design pair
   had a gate decision the spec's cut-off happened to get right; the new pairs did not.

The strict rule, for its part, accepted 3 links between unrelated topics (the "Picture description
for Figure 2" title used as a name, one shared word), and 6 of its 8 links on 351-353 were right.

## What this means

- No change to the default; the course page keeps showing the strict rule's links.
- These six pairs are now **spent**: they may be used to diagnose, but any rule change must be
  tested on pairs not yet seen.
- The two strongest causes point at inputs, not the ranking: topic titles as the gate, and
  extractor titles that are not names. The re-upload with the new extraction (2026-10-02/03) may
  change the second; it is assessed separately on the new uploads.

## Limits

Keys AI-drafted and user-approved, not teacher-written. One course (primary-school science), six
final pairs, 18 later concepts with a prerequisite. The hit rate counts pending suggestions, which
still need a teacher's approval.
