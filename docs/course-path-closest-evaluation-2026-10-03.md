# Course level, closest match: final check, 2026-10-03

**Outcome: the closest-match rule failed the stop rule (it found none of the 5 needed links).
The strict rule stays the default (`COURSE_DEFAULT_RULE = "strict"`); no code changed.**

## What was tested

The closest-match rule (spec `docs/superpowers/specs/2026-10-03-course-path-closest-match-design.md`,
plan `docs/superpowers/plans/2026-10-03-course-path-closest-match.md`): for each concept of a later
topic, the earlier-topic concept whose lesson text is closest is **accepted** when the later concept
names it and shares two of its distinctive words, **suggested** when it is at least 0.10 closer
than the later concept's own topic-mates, and otherwise not linked. Rule frozen at `5066d6b`
(Task 4 freeze `76c382e` plus the same-title guard from the final code review; design output
byte-identical). Unchanged through scoring.

## Sets and keys

- **Design** (used to build the rule, keys read by the designer): 15 pairs on the backup database —
  accepted 3 (3 right), 0 accepted between unrelated topics, right concept offered for 12 of 30.
  Output `docs/course-path-closest-evaluation/design-closest.json`, `spent-closest.json`.
- **Final** (scored once, here): six pairs never scored at course level, on the re-uploaded
  lessons (live database; earlier → later by the live outline):

  | Live pair | Topics | Old ids |
  |---|---|---|
  | 2-10 | Solid, Liquid and Gas → Separating Mixture | 340-348 |
  | 3-10 | Grouping Materials Based on Properties → Separating Mixture | 341-348 |
  | 5-7 | Mixtures and Their Characteristics → Changes that Materials Undergo | 343-347 |
  | 13-19 | Human Major Body Organs → Reproduction Among Flowering Plants | 351-357 |
  | 15-19 | The Human Organ System at Work → Reproduction Among Flowering Plants | 353-357 |
  | 19-27 | Reproduction Among Flowering Plants → Living Things Depend on Their Environment | 357-365 |

  Keys drafted blind by a separate agent from the lesson text only (`docs/course-path-closest-keys/`),
  approved by the user, frozen as fixtures in `c9ebd80`. The designer did not open them or look at
  either rule's output on these pairs before scoring. The key-drafting agent's first attempt
  stopped because the snapshots carried no concept ids; ids were added (`f4b77b5`) and the agent
  re-ran — it never saw rule output.

## Results

Raw output: `docs/course-path-closest-evaluation/final-strict.json`, `final-closest.json`.

| Pair | Key | Strict: accepted (right) · suggested | Closest: accepted (right) · suggested | Right concept offered (strict / closest) |
|---|---|---|---|---|
| 2-10 | 1 link | 5 (0) · 0 | 1 (0) · 3 | 0/1 · 0/1 |
| 3-10 | 3 links | 0 · 0 | 0 · 0 | 0/3 · 0/3 |
| 5-7 | 1 link | 0 · 0 | 0 · 0 | 0/1 · 0/1 |
| 13-19 | unrelated | 0 · 0 | 0 · 0 | — |
| 15-19 | unrelated | 0 · 0 | 0 · 0 | — |
| 19-27 | unrelated | 0 · 0 | 0 · 0 | — |
| **Total** | 5 links | **5 (0), 5 wrong** | **1 (0), 1 wrong · 3** | **0/5 · 0/5** |

## Stop rule (spec section 5)

| Condition | Closest | |
|---|---|---|
| 1. No accepted link between unrelated topics | 0 | pass |
| 2. Accepted wrong ≤ strict's and ≤ 1 | 1 vs 5 | pass |
| 3. Right concept offered for ≥ 30 % and more than strict | 0/5 vs 0/5 | **fail** |

## Why it failed

The five links the key needs are all **implicit**: the later concept uses an idea from the earlier
topic without naming it or sharing its wording.

| Needed link | What the rule did |
|---|---|
| Changing From One State to Another → Evaporation | suggested "Everyday Examples → Evaporation" instead (a near miss: that concept's text is about water evaporating) |
| Properties of Materials → Why Mixtures Can Be Separated | nothing |
| Ability to float or sink → Scooping | nothing |
| Ability to float or sink → Decantation | nothing |
| Air as a Mixture → Changes Caused by Heat and by Oxygen | nothing |

1. **The margin cannot fire inside a topic of look-alike concepts.** Separating Mixture is a list of
   techniques (sieving, winnowing, scooping, decantation…) whose texts resemble each other, so the
   later concept's own topic-mates are already close and no earlier concept stands out by 0.10.
   Every 3-10 dependent missed this way.
2. **Sentence titles cannot be named.** "Ability to float or sink. Place the material…" is a
   sentence, so it has no name and can never be accepted, only suggested.
3. **One wrong acceptance:** Liquid → Decantation ("a liquid from a solid"), named and sharing two
   words. The key judged decantation to rest on float or sink, not on Liquid. The strict rule made
   the same link plus four more of the same kind (Liquid → every technique that mentions liquid).

## What this means

- The default stays strict. On these pairs the strict rule's five accepted links were all wrong;
  the closest rule's one accepted link was wrong too. Neither found a needed link.
- The final pairs are now **spent**.
- Across both final checks (2026-10-02 shortlist, 2026-10-03 closest), automatic course-level
  links from lesson text alone did not reach the pre-set bar. The cross-topic dependencies the keys
  describe are mostly implicit (an idea reused without its words), which none of the text
  signals in this project detects reliably.

## Limits

Keys AI-drafted and user-approved, not teacher-written. One course; six final pairs, three of them
unrelated by the key, so only **5 needed links** — a small test that cannot separate a weak rule
from an unlucky one. The designer had seen the materials lessons' text at topic level. Settings came
from 15 pairs whose keys the designer had read.
