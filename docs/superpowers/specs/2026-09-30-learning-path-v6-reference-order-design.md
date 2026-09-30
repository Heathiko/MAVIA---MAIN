# Learning-path criteria v6: the text decides a link, the order decides its direction

**Date:** 2026-09-30 · **Branch:** `learning-path-graph-screen` (not merged) · **Scope:** topic level only.
**Replaces:** the verdict of v5 (`docs/superpowers/specs/2026-09-30-learning-path-evidence-fusion-design.md`
§7, §14, §15). Steps 0, 4 and 5 of v5 (preparing text, clean-up, Kahn's sort) stay.
**Course level:** unchanged today (`course_criteria.py` keeps its own verdict).

## 1. Why

Known defects at the 2026-09-30 push (`docs/open-issues-2026-09-30.md`): text-only links stay
pending, so the adaptive engine cannot use them; 62 suggestions on topic 340; the meaning clue is
at chance on direction; 357's process chain exists only as suggestions.

Measured on the development set (62, 79, 152, 340, 357; read-only simulation, keyed pairs only):

| Finding | Number |
|---|---|
| The relatedness gate passes almost every pair inside a topic | 254 of 257 keyed pairs |
| PDF order agrees with the key's direction on linked pairs | 145 of 156 |
| Name clue direction, when it votes | 56 right / 14 wrong; strong asymmetry 22 / 0 |
| Meaning clue | fires on unlinked pairs as often as on linked ones |
| "Earlier concept names the later one" used to reverse the order | right 4, wrong 14 (overview naming its parts) |
| Pairs that refer to each other | almost all real links; the true siblings (Solid/Liquid/Gas) all carry v5's `parallel` flag |
| Required links covered by v5's accepted links (directly or through a chain) | 21 of 71 |

So telling "related" from "prerequisite" is the hard question, and direction is the easy one.
v6 answers them separately: **whether** a link exists comes from the text, **which way** from
the lesson's order.

## 2. Goals and non-goals

**Goals**
1. A link exists only when the text connects the two concepts (a name, owned terms, or a heading).
   Order never creates a link, except the v5 amendment-2 suggestion (2+ PDFs agree, text silent).
2. Direction comes from the order in the PDF, single-PDF topics included, unless a heading says
   otherwise.
3. A text link with nothing against it is **accepted**, so the adaptive engine can use it without
   a teacher. Anything contradicted becomes a suggestion.
4. No generative model; Kahn's sort stays; the adaptive engine, database schema, review screen and
   teacher decisions are unchanged (as in v5).
5. Tuned on the development set only; the test set is scored once, at the end.

**Non-goals:** the course-level path; grouping or extraction fixes; reordering the lesson beyond
what headings and figures justify.

**Consequence to state in the manuscript:** derived links follow the PDF order, so the automatic
order equals the PDF order except where a heading or figure moves a concept. The system's
contribution is the prerequisite graph the adaptive engine detours through, not a reordering.
Unlike v3 (retired because every vote collapsed into document order), order here never decides
whether a link exists.

## 3. The decision, per pair of concepts in one topic

Inputs per pair (all exist in v5 except "shares a PDF" and "is a figure", both read from the
concepts' members): name use each way, owned-term use each way (Dunning G² owners, unchanged),
heading vote, order vote (2+ PDFs), `parallel` flag, each concept's `kind`, each concept's PDFs and
positions.

"Earlier" and "later" mean positions in the PDF(s) both concepts appear in. When the two share no
PDF, the topic's merged order (`concepts_for_topic`) is used, and that is a contradiction (below).
When they share several PDFs that disagree on the order, that is also a contradiction
(`pdfs_disagree`), and the merged order is used.

| # | Situation | Verdict | Direction |
|---|---|---|---|
| 1 | `parallel` flag (both under one heading naming neither) | no link | — |
| 2 | Text silent (no name, term or heading reference either way), 2+ PDFs agree on order | pending | the PDFs' order (v5 amendment 2) |
| 3 | Text silent, otherwise | no link | — |
| 4 | Heading vote | accepted | the heading's direction |
| 5 | The later concept refers to the earlier (name or owned terms) and there is **no contradiction** | **accepted** | earlier → later |
| 6 | Any other text reference | pending | see below |

**Contradictions** (any one turns row 5 into row 6):
- `reverse_name` — the earlier concept uses the later one's name more than the reverse;
- `figure` — either concept is a figure (`kind == "image"`); extraction places a page's figure
  first, so its position means nothing;
- `no_shared_pdf` — the two come from different PDFs, so their order is the merge's guess;
- `pdfs_disagree` — the PDFs they share put them in different orders;
- `backward_only` — only the earlier concept refers to the later one.

**Direction of a suggestion (row 6):**
- figure pair: the text concept first when the figure's description refers to it; otherwise the
  order;
- `no_shared_pdf` or `pdfs_disagree`: the name clue's direction if it has one, otherwise the merged
  order;
- otherwise: the order (measured: order beats the reversing name clue 14 to 4).

The figure and no-shared-PDF directions are checked on the development set during
implementation; if a different choice measures better there, this section is amended before the
test run.

**Development-set simulation of this table** (before implementation; the implementation's
measured numbers replace these in the report):

| | Covered (of 71) | Forbidden accepted | Suggestions 62 / 79 / 152 / 340 / 357 |
|---|---|---|---|
| v5 | 21 | 0 | 15 / 25 / 20 / 62 / 29 |
| v6 | 47 | 2 | 0 / 11 / 20 / 46 / 15 |

The two forbidden links are "As a general rule → Liquid / Gas" on 340: the PDF puts the rule
first and only the AI key disagrees. 340 keeps many suggestions because its three PDFs make many
figure and no-shared-PDF pairs; the test topics are single-PDF.

The option "trust the order, fix figures only" measured 61 covered but 6 forbidden accepted on
340; the user chose the contradiction rule (2026-09-30).

## 4. What is stored and shown

- `ConceptPrerequisite.evidence` (no schema change): `rule: "reference-order"`; the clue votes and
  records as in v5 (name, terms, heading, order); `direction_from` (`heading`, `pdf_order`,
  `figure`, `name`, `merged_order`, `pdf_agreement`); `contradictions` (list, empty when accepted);
  `relatedness` and the meaning numbers, **recorded only**; `confidence` (share of voting clues
  that agree, kept for `break_cycles`, which still meets teacher-made loops).
- `reasons.link_reason`: one sentence from the same parts, e.g. "Gas uses terms Solid explains
  (particle, vibrate); Solid comes first in the lesson." / "The text links them, but one is a
  figure, so its place in the PDF does not give the order." v5 rows keep their wording until
  re-derived.
- Without the sentence encoder the verdicts are identical; only the recorded relatedness and
  meaning numbers are missing. (v5 accepted nothing without it.)
- `calibration/weights.json` and `calibrate_learning_path` stay; at topic level their cutoffs no
  longer gate or vote. The course level still uses them.
- Review screen: unchanged.

## 5. Measuring

- **New headline number, "covered":** a required link of the key counts when the accepted links
  reach it directly or through a chain (the adaptive engine walks chains). Reported with reach,
  forbidden accepted, τ, accepted precision and the number of suggestions.
- Development set: 62, 79, 152 (teacher maps), 340, 357 (AI-drafted keys, measured after several
  design changes). All choices in §3 are made here.
- **Test set:** 341, 343, 347, 348 — all single-PDF; AI-drafted keys received 2026-09-30 before any
  design work, from `docs/learning-path-<id>-snapshot-2026-09-30.md`; fixtures
  `learning_path/fixtures/gold_{map,topic}_<id>.json`. Scored **once**, v5 and v6 side by side,
  reported as they come out. A forbidden link or a poor number there is recorded, not tuned away.
- Report: `docs/learning-path-v6-evaluation-<date>.md`; `CRITERIA.md` rewritten for v6.

**Guards against overfitting** (added 2026-09-30 at the user's request):
- **Order-only baseline.** Every report shows, next to v5 and v6, a baseline that links each
  concept to the one just before it in PDF order (figures included, no text used). If v6 does not
  clearly beat it on covered links and forbidden links, the text rules add nothing, and the report
  says so.
- **Rules frozen before the test run.** The commit that runs the test set records the rule
  version; §3 is not changed after that run. Any later idea is a new version, measured on a new
  unseen topic.
- **One lesson of a different kind**, if the user can upload one: a lesson from another subject
  (e.g. Math, English, Filipino, Araling Panlipunan) or a science lesson written by another
  teacher in another style. Same procedure as the test set: snapshot → key → scored once. It is the
  only check on the assumption that the author's order is the learning order.
- **One key from a different source**, if available: a teacher, or at least a different AI tool
  given the concepts **shuffled** (not in PDF order), for one test topic. Its agreement with the
  existing key, and v6's score against both, show how much the keys lean on PDF order.
- **Stated scope.** The report and the manuscript say: grade-school science lessons from one
  course, one lesson template, AI-drafted keys.

## 6. Code changes (`backend/learning_path/`)

| File | Change |
|---|---|
| `services/fusion.py` | `verdict` replaced by the §3 table; returns verdict, direction, `direction_from`, `contradictions`. `learn_weights` stays for the calibration report. Constants the course level imports stay. |
| `services/criteria.py` | Builds the per-pair facts (figure, shared PDFs, positions); relatedness gate removed; evidence per §4. |
| `services/clues.py` | Helper: shared PDFs and their order for a pair. Existing clue functions unchanged. |
| `services/reasons.py` | Sentences for `reference-order` evidence. |
| `services/gold.py`, `management/commands/evaluate_gold_paths.py` | "Covered" metric. |
| `test_*.py` | One test per row and contradiction of §3; development floors updated; test-set fixtures loaded, floors set only from the single final run. |
| `CRITERIA.md` | v6. |

## 7. Risks and limits

- **Implicit links stay invisible.** Pairs with no shared words (Pollination → Fertilization,
  Fertilization → Fruit) get no link on a single-PDF topic; only a teacher can add them.
- **The keys are AI-drafted** and may lean toward the PDF order, which flatters a design that
  takes direction from it. Teacher-verified keys would be stronger evidence.
- **Author order against the key** ("As a general rule" before the states) is accepted as the
  author wrote it.
- **Porter stemming** can miss plural forms ("gas"/"gases") and merge unrelated words; unchanged
  from v5.
- **Headings.** The `parallel` flag depends on section headings; sentence-fragment titles from
  extraction may hide siblings on single-PDF topics.
- One course, one subject area; development and test topics share a curriculum and, it appears,
  one lesson template (single PDF, competency references). The test set checks new topics, not new
  authors or subjects.
- **Rules found on one topic.** The `figure` and `no_shared_pdf` contradictions were added after
  seeing topic 340 accept wrong links, and several variants were simulated on the development set.
  They are general in intent (extraction puts figures first; a merged order is a guess), but were
  chosen by looking.
- **Test text was read.** The test topics' text was read while writing their snapshots, before the
  design; their keys were not scored. Some of them were also used in the course-level work.
- **Few fitted numbers.** v6's verdict uses yes/no references and one textbook statistic (G² ≥
  3.84); v5's topic-level cutoffs no longer decide anything. This lowers, but does not remove, the
  risk of fitting these lessons.
