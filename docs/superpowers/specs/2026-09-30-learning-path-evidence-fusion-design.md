# Learning-path criteria v5: related concepts, fused direction clues, Kahn

**Date:** 2026-09-30
**Status:** Design, awaiting review
**Replaces:** the v4 criteria (R1 definition, R2 containment, R3 reference) in
`backend/learning_path/services/criteria.py`, and the lead/examples/closing label tiers added
the same day (commit a17c31d on `learning-path-graph-screen`).
**Scope:** the learning-path pipeline only: concepts in, prerequisite links and step order out.
Grouping, extraction, question generation and the adaptive engine are not changed.

---

## 1. Why

Traced on the live database, 2026-09-30:

- Every piece of v4 evidence is **string identity**: a heading equal to a name (R2), a name
  appearing as a whole word (`text_signals.mentions`), a regex for "X is ..." sentences
  (`_DEFINITION_OPENING`), and fixed word lists (`_CONTRAST`, `STOP_WORDS`, label lists).
- On topics 340 and 357, **every accepted link came from heading containment** (340: 5 links,
  357: 4). R1 never fired. Links moved 2 steps in each topic; everything else is the PDFs'
  merged order (`concept_units._order_records`) used as Kahn's tie-break.
- 6 of 340's 15 concepts have no usable name (sentence titles, "As a general rule",
  "Example (Part 1)"), so v4 can never make them anyone's prerequisite.
- Rules written against the lessons we test on (label lists, definition shapes) will not carry
  over to other teachers' PDFs.

Feasibility probes on topic 357 (throwaway scripts, 2026-09-30) showed:

| Method | Right | Wrong |
|---|---|---|
| Sentence similarity, nearest sentence | Stamen/Pistil → Fertilization, Fertilization → Seed/Fruit | Examples → Seed, Pollination → Stamen |
| Sentence similarity, centroid | Stamen → Fertilization, overview → parts | Seed → Fertilization, Fruit → Fertilization |
| Term ownership (share of use) | Stamen → Pollination, Fertilization | Seed → Stamen/Pistil, Fruit → Fertilization |

No single method gets direction right at this size (about 10 concepts, 50 sentences), and each
fails for a different reason (similarity flips with concept size; ownership is thrown by tiny
concepts). Similarity is symmetric, so it cannot give direction by itself (ACE, Aytekin & Saygın
2024). Independent failures are the case where combining evidence helps.

## 2. Goals and non-goals

**Goals**
1. Links come from what the lessons say, not from headings, name strings or label lists.
2. PDF order counts only as a weak clue, and only when several PDFs agree; it can never create a
   link on its own.
3. Kahn's topological sort stays the ordering algorithm (deliverable: *Topological sorting —
   Learning Objects*). The adaptive engine (deliverable: *Selection of Learning Object —
   adaptive graph traversal and scoring*) walks the resulting graph unchanged.
4. No generative model. Outside parts are limited to one pinned sentence encoder and the
   Porter stemmer; the algorithm around them is ours.
5. Every constant is either a textbook statistic or set on the development set (Section 9).

**Non-goals**
- Fixing grouping splits ("Comparing" / "Comparing details"). The algorithm can see them; fixing
  them belongs to grouping.
- The course-level (cross-topic) path. Relatedness (Section 4) is designed so it carries over.
- Changing the adaptive engine, the database schema, or teacher-decision handling.

## 3. Overview

```text
INPUT   concepts of a topic (concepts_for_topic), stored teacher decisions
STEP 0  prepare       sentences, terms (stopwords removed, Porter stems), embeddings, PDF positions
STEP 1  relatedness   symmetric: can A and B be connected at all?        → gate
STEP 2  clues         four asymmetric votes: +1 A first, −1 B first, 0
STEP 3  fusion        weighted votes → score, confidence → verdict + reason
STEP 4  clean-up      break cycles at the weakest derived link; flag redundant links
STEP 5  Kahn          topological sort with a priority tie-break
STEP 6  use           saved steps; adaptive engine detours through the nearest prerequisite
```

Embeddings answer "related or not". Direction comes from the clues, fused.

## 4. Step 0: preparing concepts (`concept_text.py`, `embeddings.py`)

- **Sentences.** Every member passage of a concept (all PDFs grouping put in it) is split on
  `.`, `!`, `?` and line breaks. Fragments under 4 words are dropped. Each sentence remembers its
  PDF (`material_id`).
- **Figures and tables** are read through their stored description, like any passage. No special
  case.
- **Terms.** Lowercase words, a general English stopword list (no lesson-shaped words such as
  "example" or "part"), words under 3 letters dropped, then Porter-stemmed (Porter 1980):
  "fertilized" and "fertilization" both become `fertil`. A stemmer, not a lemmatizer, because
  lessons switch between verb and noun ("melts" / "melting", "pollen is carried" / "pollination").
- **Embeddings.** Our own loader in `learning_path/services/embeddings.py`: the same pinned model
  grouping uses (`sentence-transformers/all-MiniLM-L6-v2`, revision
  `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`), CPU, offline once downloaded, normalised vectors,
  with its own cache under `semantic_cache/`. Grouping's code is not imported or changed.
- **PDF positions.** A concept's position in each PDF, renumbered over the concepts that PDF
  teaches. `concept_units._material_positions` already computes this; it is made public as
  `material_positions`.
- **Model unavailable.** Relatedness and C3 are skipped; the other clues run; every link they find
  is PENDING, never ACCEPTED; the reason says the semantic check was unavailable.

## 5. Step 1: relatedness (`relatedness.py`)

```text
match(A→B) = mean over sentences s of A of  max over sentences u of B of  cos(s, u)
rel(A, B)  = (match(A→B) + match(B→A)) / 2
```

Best-match averaging, as BERTScore (Zhang et al. 2020) does over tokens: one shared idea between
two broader concepts still counts.

**Threshold without an answer key.** Pairs of concepts from topics in *different subjects* are
unrelated by construction. `θ_related` is the 95th percentile of their `rel`. Measured
2026-09-30 on 340 × 357 (150 pairs): 0.25 (max 0.35). Topics that build on each other (309, 313
on 340) are never paired for this.

Below `θ_related` a pair gets no link and skips Steps 2–3. `rel` is stored on the link.

**What the gate does and does not do.** Inside one topic nearly every pair passes (the lowest
pair involving "As a general rule" in 340 is 0.30). The gate mainly matters across topics and for
topics that mix several lessons. Inside a topic, the clues and the PARALLEL verdict do the work.
Required links the gate blocks are reported ("gate loss", Section 9).

## 6. Step 2: direction clues (`clues.py`)

Each clue returns a vote in {+1, −1, 0} for "A before B" and a record of the numbers behind it.
**A clue votes whenever its evidence differs at all**; how far to trust it is fusion's job. This
removes three thresholds that could otherwise be fitted to a lesson.

**C1 name reference.** A's name = content-word stems of its title, without part suffix or
numbering. B uses A's name when one of B's sentences contains all of them. A title with more than
6 content words is not a name; C1 abstains for it.
`vote = sign(uses(B,A) − uses(A,B))`, where `uses` is the share of sentences.

**C2 explains vs uses.** A term is owned by the concept where it is over-represented by Dunning's
log-likelihood G² (Dunning 1993), against the rest of the topic, with G² ≥ 3.84 (p < 0.05). G²
discounts small counts, which fixes the probe's "Seed formation owns *fertil*" error. Only terms
used by at least two concepts matter.
`relies(B,A)` = share of B's passages using a term A owns; `vote = sign(relies(B,A) − relies(A,B))`.

**C3 meaning reference.** For a sentence s of B and every *other* concept X,
`sim(s, X)` = best cosine between s and X's sentences. s points to X when `sim(s, X)` is above the
95th percentile of sentence-to-concept similarity between unrelated topics (same null as
Section 5). A sentence is never compared with its own concept.
`about(B,A)` = share of B's sentences pointing to A; `vote = sign(about(B,A) − about(A,B))`.
Concepts with many sentences have more chances to be matched; this is measured on the
development set, and if it biases votes, `sim` becomes the mean of the two best matches.

**C4 PDF order (weak).** Votes only when two or more PDFs teach both concepts and all of them
put the pair the same way round. Otherwise 0. A single-PDF topic never gets a C4 vote.

## 7. Step 3: fusion and verdicts (`fusion.py`)

**Weights, learned without an answer key.** For each clue k, over related pairs where k votes and
the other clues have a majority: `acc_k` = share of agreement with that majority.
`w_k = log(acc_k / (1 − acc_k))` (log-odds weighting of independent voters; Dawid & Skene 1979).
`acc_k ≤ 0.5` → weight 0 (reported). `acc_k` capped at 0.95. `w_C4` capped at half the smallest
content-clue weight, so any one content clue outvotes it.

Weights are computed by `python manage.py calibrate_learning_path` and written to
`learning_path/calibration/weights.json` (topics used, model revision, date). The file is
committed so the group shares it. Derivation reads it; if it is missing, content clues weigh 1
and C4 weighs 0.5. Weights are not recomputed when a screen opens, so a new upload never
silently changes another topic's links.

**Score and verdict.**

```text
score = Σ_k w_k · vote_k        # sign = direction
conf  = |score| / Σ_k w_k        # an abstaining clue lowers confidence
```

| Verdict | Condition |
|---|---|
| ACCEPTED | `conf ≥ 0.5` and at least 2 clues voted for the direction |
| PENDING | not accepted, and at least one content clue (C1–C3) votes for the direction |
| PARALLEL | related, but no content clue votes, or `score = 0` |
| none | failed the relatedness gate |

C4 alone never creates a link. PARALLEL is not stored as a row; it appears in the evaluation
report. Teacher decisions (`approved`, `rejected`) are never overwritten; only their evidence is
refreshed, as today.

**Stored evidence** (JSON, no schema change):

```json
{"rule": "fusion", "relatedness": 0.62, "score": 1.9, "confidence": 0.81,
 "votes": {"name": 0, "terms": 1, "meaning": 1, "order": 1},
 "records": {"terms": {"owned": ["anther", "filament"], "relies": 0.75, "relies_back": 0.0},
             "meaning": {"about": 0.5, "about_back": 0.17},
             "order": {"pdfs": 2, "agree": 2}}}
```

**Reason** (`reasons.link_reason`), built from the records, naming clues against the link too:
"Pollination uses terms Stamen explains (anther, filament). Its sentences refer to Stamen's
ideas. 2 of 2 PDFs teach Stamen first." The v4 texts stay for rows not yet re-derived.

## 8. Steps 4–5: clean-up and Kahn (`publishing.py`)

The sorted graph is ACCEPTED plus teacher-APPROVED links (`SHAPES_PATH`), as today. `path_links`
now returns each link's confidence (teacher links: unbreakable).

**Cycles.** While a cycle exists, remove the derived link in it with the lowest confidence and
report it in `ignored_links`. Teacher links are never removed (`teacher_links` already prevents a
loop of teacher links). This replaces "teach the earliest concept in the PDF".

**Kahn with a priority tie-break.**

```text
ready ← concepts whose prerequisites are all placed
while ready:
    X ← the ready concept with the highest (recency(X), −pdf_position(X))
    place X; release its dependents
recency(X) = latest placement index among X's prerequisites (−1 if none)
```

Rule 1 keeps related material together (after Solid, Liquid, Gas, what builds on them comes
next). It is kept only if Kendall's τ on the development set is not worse with it than without;
both numbers are reported. `depth` is computed as today.

**Redundant links.** A→C is flagged `redundant` when A→…→C exists through other shaping links.
It stays stored; the graph screen hides it. The adaptive engine already detours to the nearest
prerequisite (`adaptive/services.py:740`), so it is unaffected.

## 9. Evaluation

| Set | Topics | Use |
|---|---|---|
| Development | gold 62, 79, 152 (frozen fixtures) | design checks: C3 fallback, tie-break rule 1 |
| Test | 340, 357 | final numbers; nothing tuned on them |
| Unseen | 309, 311, 313, 316 once uploaded | strongest claim |

**Keys.** 340's key (`gold_map_340.json`, from `docs/learning-path-340-snapshot-2026-09-30.md`)
and 357's (from `docs/learning-path-357-snapshot-2026-09-30.md`) are **AI-drafted
recommendations from one tool, prompted the same way, not teacher-verified**. Each fixture's
`_note` says so. Results measure agreement with that reference; the manuscript states this as a
limitation. Gold 62/79/152 were partly built around v4's heading rules.

**Metrics** (`gold.gold_report`, extended):
- forbidden links accepted — must be 0 (hard gate);
- accepted precision (links in the key or implied by it);
- reachable recall (key links found as accepted or pending);
- Kendall's τ between derived and key order (replaces exact order match);
- gate loss (key links blocked by relatedness).

**Comparisons.** v4 vs v5 on the same topics; each clue alone; ablation (v5 without each clue);
tie-break rule 1 on/off.

**Pass condition before asking about a merge.** 0 forbidden accepted on every topic, and on the
test set reachable recall and Kendall's τ no worse than v4. Where v5 loses, the report says where
and why; constants are not adjusted to hide it. The v4 reachable floors in `test_gold_paths.py`
(62: 9, 79: 3, 152: 8) are re-baselined from the measured v5 numbers.

## 10. Code changes

**New** (`backend/learning_path/services/`): `embeddings.py`, `concept_text.py`,
`relatedness.py`, `clues.py`, `fusion.py`; command `calibrate_learning_path`; file
`learning_path/calibration/weights.json`; `nltk` in `backend/requirements.txt`.

**Rewritten, same interface.** `criteria.decide_pairs(concepts, runtime_instance)` keeps its
signature and output keys (`prerequisite`, `dependent`, `verdict`, `evidence`, `cross_section`),
so `publishing.refresh_prerequisites` is unchanged. `publishing.order_with_links` and
`path_links` (confidence, cycles, tie-break); their callers `path_builder.build_topic_path`,
`save_learning_path` and `gold.gold_report`. `reasons.link_reason`. `path_builder` adds
`redundant` per edge; `web-app/src/learning-path/graphModel.js` hides those edges.

**Removed.** From `concepts.py`: label lists, `structural_role`, `is_structural`,
`resolve_concept` and the lead/examples/closing tiers (and the test tying them to grouping's
list). From `text_signals.py`: `definition_subject`, `mentions`, the definition regex and the
lesson-shaped stopwords (`strip_part_suffix`, `part_marker` stay for `concept_units`).
`management/commands/evaluate_edges.py`, already broken (imports a missing
`learning_path.services.evidence`).

**Untouched.** `lessons/` (grouping, extraction), `adaptive/`, `question_generation/`, database
schema.

## 11. Naming

Names follow what `learning_path` already uses (`decide_pairs`, `order_with_links`,
`concepts_for_topic`, `link_reason`): short, lower-case verbs or nouns, one idea each, no filler.

| Module | Names |
|---|---|
| `embeddings.py` | `load_encoder()`, `embed(sentences)` |
| `concept_text.py` | `ConceptText` (dataclass: `sentences`, `vectors`, `terms`, `pdfs`), `prepare(concepts)`, `split_sentences(text)`, `terms(sentence)`, `material_positions(...)` |
| `relatedness.py` | `relatedness(a, b)`, `null_threshold(pairs)` |
| `clues.py` | `name_vote(a, b)`, `term_vote(a, b, owners)`, `meaning_vote(a, b, cutoff)`, `order_vote(a, b, positions)`, `term_owners(texts)`, `g2(...)` |
| `fusion.py` | `load_weights()`, `learn_weights(votes)`, `combine(votes, weights)`, `verdict(...)` |
| `publishing.py` | `order_with_links`, `break_cycles(links)`, `redundant_links(links)` |

Rules: no `compute_`/`get_`/`handle_` prefixes, no `helper`, `utils`, `manager`, `v2`,
`enhanced`, `robust`; no names that restate their module (`clues.clue_name_vote`); locals as
plain nouns (`score`, `conf`, `owners`, `cutoff`), single letters only for pair members (`a`,
`b`) and loop sentences (`s`, `u`), as in the maths above. Docstrings say what and why in a line
or two, in the voice of the existing modules; no "This function ...".

## 12. Risks and limits

- **Small data.** Weights learned from few topics are rough until more lessons are uploaded; the
  equal-weight fallback is reported alongside.
- **Implicit links.** Links with little shared wording or meaning may stay pending, e.g.
  "As a general rule → Changing State" (relatedness 0.40, passes the gate; direction untested).
- **Porter over-stemming** can merge unrelated words; C2 counts only terms in ≥ 2 concepts and is
  one clue of four.
- **C3 size effect** — measured, with a defined fallback (Section 6).
- **Summary vs introduction** can only be told apart by position, which is why C4 exists.

## 13. Decisions log (2026-09-30)

- Keyword rules and lesson-fitted rules are out; no generative model.
- Embeddings for relatedness only, plus one fused direction clue (C3); direction is fused.
- PDF order: weak clue from cross-PDF agreement, plus final tie-break; never a link on its own.
- Kahn stays (deliverable); tie-break and cycle breaking change.
- Own encoder loader, same pinned model as grouping.
- Stemmer (Porter), not lemmatizer.
- Size corrections: Dunning G² for C2, null-calibrated cutoff for C3.
- Weights from `calibrate_learning_path`, committed, not recomputed per request.
- Test keys: AI-drafted, same tool and prompt for 340 and 357; 357's key pending.
