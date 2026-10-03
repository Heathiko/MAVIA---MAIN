# Course-level learning path: closest match — design

**Status:** 2026-10-03, approved section by section in conversation; awaiting review of this file.
Branch `course-path-closest` (from `improved-learning-path`).
**Replaces (when it passes):** the default course rule (`"strict"`,
`docs/superpowers/specs/2026-09-30-course-learning-path-design.md`, amendment 1). The failed
top-down shortlist (`docs/superpowers/specs/2026-10-02-course-path-top-down-design.md`, report
`docs/course-path-v2-evaluation-2026-10-03.md`) stays in the code, switched off.

## 1. What changes for the teacher and the learner

A course link sends a learner who is stuck on a concept back to a concept of an **earlier topic**.
Today's rule accepts a link when a later concept mentions an earlier one's name and shares one word
with it. It accepts wrong links (a human-body figure as the prerequisite of an ecology lesson) and
misses most real ones (none of the materials lessons' links).

The new rule asks one question per concept: **which concept of the earlier topic is this one's
lesson text closest to?** It then

- **accepts** that concept automatically when the evidence is strong (section 3), so learners get the
  link without any teacher action;
- **suggests** it to the teacher when it stands out but the evidence is weaker; the teacher may
  approve it or ignore it — nothing breaks if they never look;
- otherwise makes **no link**.

Nothing is required from the teacher. The rule prefers a missing link to a wrong one: a missing link
leaves the learner on the topic's own path, which already works; a wrong link sends them to
unrelated material.

*Example.* "Teamwork 2: Getting Energy from Food" (The Human Organ System at Work) is closest in
text to "The Stomach" (Human Major Body Organs), names it, and shares *food, digest* with it: the
link is accepted, and a learner stuck on Teamwork 2 can be sent back to The Stomach. A figure
description elsewhere in the course can at most be a suggestion, and only when its text really is
the closest.

## 2. Diagnosis (2026-10-03, on the 15 already-scored pairs)

Design pairs 340-341, 340-343, 340-347, 343-348 and controls 340/341/343/347/348-357, plus the
spent final pairs 351-353, 341-343, 341-347, 347-348, 351-365, 353-365 (backup database; keys were
used once in `docs/course-path-v2-evaluation-2026-10-03.md`, so they may now be read for diagnosis).
30 later concepts need a prerequisite.

**Ranking.** The right earlier concept among the 3 closest, by evidence:

| Ranked by | Top 3 | Top 1 |
|---|---|---|
| Lesson-text meaning (`relatedness`) | 25/30 | 17/30 |
| Shared distinctive words (tf-idf) | 23/30 | 14/30 |
| Name mentions | 21/30 | 12/30 |
| Concept titles (the failed shortlist) | 19/30 | 8/30 |

**Topic relatedness cannot be read from text.** The best concept matches between unrelated topics
(0.17-0.34) overlap those between related ones (0.28-0.54); outline titles overlap the same way.
"Living things depend on their environment" looks as close to the organ topics as related pairs do.
So the rule has **no topic gate**: each concept is judged on its own.

**Accepting.** Each later concept linked to its closest earlier concept, under a condition:

| Condition | Links | Right | Wrong | Wrong between unrelated topics |
|---|---|---|---|---|
| Today's strict rule | 16 | 8 | 8 | 3 |
| Closest + named ≥ 1 sentence + ≥ 2 shared distinctive words | **3** | **3** | **0** | **0** |
| Closest + named in ≥ 2 sentences + ≥ 2 words | 1 | 1 | 0 | 0 |
| Closest + ≥ 2 words (no name) | 20 | 7 | 13 | 6 |
| Closest + ≥ 2 words + margin ≥ 0.10 | 8 | 5 | 3 | 0 |
| Closest + margin ≥ 0.10 (**suggestions**) | 17 | 11 | 6 | 0 |
| Closest + margin ≥ 0.15 | 12 | 8 | 4 | 0 |

**Rejected:** treating a title as a real name only when the concept "owns" its words (Dunning G²).
On the 70 titles it called "Solid", "Pollination" and "Shelter" not names and "As a general rule"
a name. The existing `name_terms` (no sentence titles, at most 6 stems) is kept.

## 3. The rule

For every concept *L* of a later topic, against each earlier topic *E* in outline order (concepts
with no sentences are skipped on both sides):

1. **Closest.** *C* = the concept of *E* with the highest `relatedness(C, L)`. Ties keep *E*'s order.
2. **Margin.** `own` = the median `relatedness(M, L)` over the other concepts *M* of *L*'s own topic;
   `margin = relatedness(C, L) − own`. With no other concept in *L*'s topic, the margin is undefined
   and only step 3 can link.
3. **Accepted** when both:
   - *L* names *C*: at least one of *L*'s sentences contains every stem of *C*'s name
     (`name_use(L, C) > 0`; *C* must have a name under `name_terms`);
   - *L* and *C* share at least `MIN_SHARED_TERMS` (2) distinctive words in one passage
     (`term_use(L, C, owners, 2) > 0`, owners found over the two topics together, as today).
4. **Suggested (pending)** otherwise, when `margin ≥ CLOSEST_MARGIN` (0.10).
5. **No link** otherwise.

At most one link per later concept per earlier topic. The direction is always earlier topic →
later topic (the outline); the rule never reverses it. Titles are not used for ranking.

Settings, fixed in this spec before any new key exists and not changed afterwards:
`CLOSEST_MARGIN = 0.10`, `MIN_SHARED_TERMS = 2` (existing), name named in ≥ 1 sentence.

## 4. Code

- **`services/course_closest.py`** (new): `closest_earlier(earlier, later_text)` → (concept,
  score); `own_topic_median(later_text, later)`; `closest_verdict(...)` → accepted / pending / none
  with its evidence. Uses only existing measures: `relatedness`, `name_use`, `term_use`.
- **`services/course_criteria.py`**: new rule `CLOSEST = "closest"` in `COURSE_RULES`;
  `decide_course_pairs(rule="closest")` runs section 3 per pair of topics.
  `COURSE_DEFAULT_RULE` stays `STRICT` until the final check passes (section 5).
- **Evidence** stored on each `CourseConceptLink` row: `rule: "course-closest"`, `score`,
  `own_median`, `margin`, `name_sentences`, `shared_words` (the shared distinctive words),
  `relatedness`, `contradicts_outline: false`. No `rank`, so the page's dialog shows no
  "closest match N".
- **`services/reasons.py`**: `link_reason` gets a `"course-closest"` branch:
  - accepted: *"{L} is closest in meaning to {C}, names it, and shares {words}."*
  - suggested: *"{L} is closest in meaning to {C}, clearly closer than the concepts of its own
    topic. Please confirm or dismiss."*
- **Unchanged:** the `CourseConceptLink` table (no migration), teacher approve / reject / undo and
  their survival across a re-derive, the Course path page, published steps
  (`_course_prerequisites`: accepted and approved only) and the adaptive hand-off.
- **Encoder unavailable:** `"closest"` needs the meaning vectors. Without them it runs the strict
  rule with suggestions only (the existing `semantic=False` path) and never crashes.
- **`evaluate_course_paths --rule closest`** works through `COURSE_RULES`; `course_gold_report`
  and `course_shortlist_hits` (offered = accepted or pending) score it unchanged.

## 5. Evaluation

**Final pairs (6), on the re-uploaded lessons** (live database; earlier/later per the live outline;
old ids for reference):

| Pair | Old ids |
|---|---|
| Solid, Liquid and Gas → Separating Mixture | 340-348 |
| Grouping Materials Based on Properties → Separating Mixture | 341-348 |
| Mixtures and Their Characteristics → Changes that Materials Undergo | 343-347 |
| Reproduction Among Flowering Plants ↔ Living Things Depend on Their Environment | 357-365 |
| Human Major Body Organs ↔ Reproduction Among Flowering Plants | 351-357 |
| The Human Organ System at Work ↔ Reproduction Among Flowering Plants | 353-357 |

None has been scored at course level. The last three test same-subject pairs, where the strict
rule made its worst mistakes.

**Keys.** After the four biology lessons are re-uploaded: `export_course_pairs <a> <b> --snapshot`
for each pair; a **separate agent** drafts `course_map_<a>_<b>.json` + `_review.md` blind (it sees
the lesson text only, never a rule's output) in `docs/course-path-closest-keys/`; the user reviews
and approves; the maps are frozen with `export_course_pairs --map --out` as
`gold_course_<a>_<b>.json` and the live topic titles are added to `course_topic_titles.json`. The
designer does not open the keys or look at either rule's output on these pairs before scoring.

**Score once,** both rules: `evaluate_course_paths --pairs ... --final-check --rule strict` and
`--rule closest`.

**Stop rule** (all three, summed over the 6 pairs):
1. pairs the key marks unrelated: **no accepted link** under `"closest"` (suggestions are reported);
2. accepted wrong links under `"closest"` ≤ the strict rule's, **and ≤ 1**;
3. the right earlier concept is offered (accepted or suggested) for **≥ 30 %** of the later concepts
   that need one, **and** for more of them than the strict rule offers.

On the design pairs: (1) 0, (2) 0 vs 8, (3) about 37 % vs 17 %.

**Passes:** `COURSE_DEFAULT_RULE = CLOSEST` with a dated comment; old course tests keep testing
`"strict"` explicitly; report `docs/course-path-closest-evaluation-<date>.md`; `CRITERIA.md`
"Course level" updated. **Fails:** the default stays `"strict"`; the report says why.

## 6. Tests

Fake concepts with a fake encoder, as the existing course tests do:
- the closest earlier concept is the one with the highest relatedness; ties keep outline order;
- accepted only with name **and** two shared words; one shared word, or no name → at most a
  suggestion;
- a suggestion needs margin ≥ 0.10; below it, no link;
- a later topic with one concept: no suggestion, acceptance still possible;
- at most one link per later concept per earlier topic; direction always earlier → later;
- encoder unavailable → strict rule, pending only, no crash;
- a teacher-rejected link stays rejected after re-deriving with `"closest"`;
- `link_reason` gives the two sentences above;
- existing course tests pass unmodified (they run `"strict"`, still the default).

## 7. Risks and limits

- **Few automatic links.** On the design pairs 3 of 30 needed links were accepted; most links are
  suggestions. This is the intended trade (section 1).
- **The name check reads titles.** A misleading but name-like title on the closest concept can
  still pass if the text also shares two distinctive words; the closest-text requirement makes
  that rare (0 cases on the design pairs).
- **One closest concept per earlier topic.** A later concept that builds on two concepts of one
  earlier topic gets at most one of them.
- **Evaluation:** keys AI-drafted and user-approved, not teacher-written; one course; 6 pairs. The
  final pairs are new at course level, but the designer has seen the materials lessons' text at
  topic level. The settings come from 15 pairs whose keys the designer has read.
