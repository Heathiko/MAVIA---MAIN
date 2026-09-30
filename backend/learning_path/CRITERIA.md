# Prerequisite link criteria (v5)

**Status (2026-09-30):** implemented on branch `learning-path-graph-screen`.
Design: `docs/superpowers/specs/2026-09-30-learning-path-evidence-fusion-design.md`
(§14 and §15 = the amendments that are what the code does).
Measurements: `docs/learning-path-v5-evaluation-2026-09-30.md`. Numbers live there, not here.

**Scope:** one path per **topic**, whose steps are **concepts** (grouping's concept bundles
across every PDF of the topic, `services/concept_units.py`). Grouping and extraction are read,
never changed.

## The six steps

| Step | Code | What it does |
|---|---|---|
| 0 Prepare | `concept_text.py`, `embeddings.py` | Sentences (≥ 4 words) with their PDF, Porter-stemmed terms (general English stopwords only), sentence vectors from our own loader of the pinned `all-MiniLM-L6-v2`, each PDF's order of concepts. |
| 1 Relatedness | `relatedness.py` | Symmetric best-match average of sentence similarity. Pairs below `related_cutoff` get no link. |
| 2 Clues | `clues.py` | Five votes per pair: +1 first-before-second, −1, or 0; plus a `parallel` flag. |
| 3 Verdict | `fusion.py`, `criteria.py` | Two evidence families must agree for a link to be accepted. |
| 4 Clean-up | `publishing.py` | Loops broken at the least confident derived link; links a longer chain implies are flagged `redundant` (hidden on the graph). |
| 5 Order | `publishing.order_with_links` | Kahn's topological sort; ties go to the topic's merged PDF order. |

The adaptive engine then walks the saved path and detours through the nearest prerequisite
(`adaptive/services.py`), unchanged.

## The clues

| Clue | Family | Votes "A first" when | Known failure |
|---|---|---|---|
| name | content | B's sentences contain all of A's name stems more than the reverse | lessons refer to a concept by its parts ("anther", not "stamen") |
| terms | content | B's passages use terms A owns (Dunning G² ≥ 3.84) more than the reverse | an overview uses its children's terms |
| meaning | content | more of B's sentences have a close match (above `meaning_cutoff`) in A than the reverse | at chance on direction in the development set; kept for its family vote |
| heading | structure | B sits under a heading whose stems contain A's name | word matching on headings; silent when headings are missing |
| PDF order | structure | two or more PDFs teach both and all put A first | silent for single-PDF pairs |
| `parallel` flag | structure | — both sit under one heading that names neither | — |

Cutoffs come from pairs of concepts in topics of **different subjects** (95th percentile), so no
answer key is read: `python manage.py calibrate_learning_path --topics … --unrelated 62:79 …`
writes `calibration/weights.json` (committed; shared by the group). The file also reports each
clue's agreement with the others; those weights do **not** decide verdicts.

## The verdict

Content = sign of name + terms + meaning. Structure = sign of heading + order.

| Situation | Verdict, direction |
|---|---|
| content silent, ≥ 2 PDFs agree on the order, structure agrees, not siblings | pending, the files' direction (amendment 2) |
| content silent or cancelling, otherwise | no link |
| structure disagrees with content | pending, structure's direction (`disagreement: true`) |
| `parallel` flag | pending, content's direction |
| structure agrees with content | **accepted** |
| all three content clues agree, structure silent | **accepted** |
| otherwise | pending, content's direction |

Without the encoder (model not downloaded, offline) nothing is accepted: every link the other
clues find is pending, and the reason says the meaning check was unavailable.

Each stored link's `evidence` holds the votes (oriented prerequisite-first), each clue's numbers,
`confidence` (share of voting clues that agree), `relatedness`, `parallel`, `disagreement` and
`semantic`. `reasons.link_reason` turns that into one sentence for the review screen.

## Edge status and teacher control

Unchanged from v4. `ConceptPrerequisite` rows: `accepted` and `pending` come from the criteria and
are replaced on every derivation; `approved` and `rejected` come from a teacher and are never
overwritten. Only `accepted` and `approved` shape the order. Loops made of teacher links are
refused (`services/teacher_links.py`). Screen: `docs/superpowers/specs/2026-09-29-learning-path-graph-screen-design.md`.

## Course level (across topics)

Spec: `docs/superpowers/specs/2026-09-30-course-learning-path-design.md`.
`services/course_criteria.py` pairs concepts of **different** topics of one course, with the same
relatedness gate and content clues; the structure is the teacher's **outline order** (headings and
PDF order cannot compare topics). Only name and terms vote, and they must agree (spec amendment 1):
with the outline → accepted; against it → pending, `contradicts_outline`; anything else → no link.
The meaning clue is recorded, not counted. Stored as `CourseConceptLink` (`services/course_links.py`), shown on the Course path page,
refreshed when a topic is published. `published.course_prerequisites` gives the adaptive engine
accepted/approved earlier-topic prerequisites (hand-off: `docs/handoff-course-prerequisites.md`).

## Measuring

```bash
python manage.py evaluate_gold_paths --topics 62 79 152 340 357 --by-clue
python manage.py evaluate_gold_paths --topics 340 --without meaning      # ablation
python manage.py evaluate_gold_paths --topics 62 79 152 --build-on-latest
python manage.py test learning_path.test_gold_paths
```

Development set: gold 62, 79, 152, plus 340 and 357 (AI-drafted keys; measured after several
design changes, so no longer clean test topics). Test set (from 2026-09-30): 341, 343, 347, 348
(AI-drafted keys from `docs/learning-path-<id>-snapshot-2026-09-30.md`, drafted before any design
work). Never tune on the test set.

## History

- v3 (three equal votes: temporal order, RefD key terms, foundationality):
  `docs/superpowers/specs/2026-09-13-prerequisite-criteria-v3-design.md`,
  revisions in `docs/learning_path_revision_2026-09-17.md`. Retired because all three votes
  collapsed into document order.
- v4 (R1 definition, R2 heading containment, R3 reference; accepted by R1/R2):
  `docs/superpowers/specs/2026-09-29-learning-path-criteria-v4-design.md`. Retired because only
  heading containment ever accepted a link and every rule was string matching.
- v5 (this document), 2026-09-30.
