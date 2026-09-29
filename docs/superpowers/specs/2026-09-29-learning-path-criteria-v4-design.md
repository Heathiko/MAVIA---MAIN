# Learning-path criteria v4: typed, research-backed prerequisite evidence

**Date:** 2026-09-29
**Status:** Design, awaiting review
**Replaces:** the three-vote criteria in `backend/learning_path/services/criteria.py`
(v3 and its 2026-09-17 revision, described in `learning_path/CRITERIA.md`)
**Scope:** the learning-path pipeline only, from concepts to stored prerequisite links to saved step order.
Remediation and every other runtime or adaptive behaviour are **out of scope and unchanged**.

---

## 1. Why

This design assumes the concepts are already correctly formed. The topic used for measurement, 308
(*Solid, Liquid and Gas*), is grouped by hand before implementation starts.

A read-only trace of topic 308 (2026-09-28) showed that the current criteria give no evidence
independent of document order:

- **Temporal order** measures position directly.
- **Semantic reference** gives each distinctive term to the *earliest* concept that uses it. As a
  result, later concepts almost always appear to refer to earlier ones: the backward score was 0 in
  83 of the 88 pairs that got a verdict.
- **Foundationality** (the inbound/outbound ratio) is computed from those same scores, so it inherits
  the same bias. It also counts how often a name is said, so `solid` (4.68) beats `matter` (2.92).
- **Acceptance requires the temporal vote**, so every accepted link points forward. Kahn's algorithm
  therefore always returns the merged document order: the links never change the path.
- **26 of the 50 accepted links** rest only on incidental shared words ("even", "air", "packed").
  Remediation follows these links (`adaptive/services.py`), so a wrong link sends a learner to the
  wrong material.

A literature check (Section 8) also found **no published source** for three parts of the current
design: earliest-concept term ownership, three equal unweighted votes, and position as a required
gate. It found a published *warning* against a fourth part: using embedding similarity to decide
direction (ACE, Aytekin & Saygın 2024).

## 2. Goals and non-goals

**Goals**
1. Every prerequisite link carries evidence that does not depend on where the concepts sit in the PDF.
2. Each link records **one named evidence type** that a teacher or a thesis panel can read.
3. Every rule traces to a published method, or is explicitly labelled as MAVIA's own design choice.
4. Links can point against document order when the evidence says so.
5. The pipeline stays deterministic: no generative model is called, and the same concepts always
   give the same links.

**Non-goals**
- Changing grouping or concept formation.
- Changing remediation, BKT, or the adaptive engine. They read the saved path and links exactly as
  they do today.
- Weighted scoring or trained classifiers. There is no training data, and the literature supports
  combining signals only through trained models.
- A full multi-relation knowledge graph (see Section 9).
- Changing the teacher review screen or the `ConceptPrerequisite` schema.

## 3. Pipeline overview

```
concepts_for_topic (unchanged)
  -> drop structural concepts (unchanged)
  -> names: resolve_concept (unchanged)
  -> evidence per ordered pair (A, B):
        R1 definition dependency
        R2 section containment
        R3 passage reference distance
  -> vetoes: same name, contrast only, parallel siblings
  -> decision: accepted | pending | none      (rule precedence, no voting)
  -> refresh_prerequisites: store rows, keep teacher decisions (unchanged)
  -> order_with_links: Kahn, ties broken by merged document order (unchanged)
```

Document order appears in exactly one place: as the tie-breaker in `order_with_links`. It casts no
vote and creates no link.

## 4. Evidence rules

Notation: `name(X)` is `resolve_concept(X)` (may be `None`). `text(X)` is `concept_text(X)`, which is
all member PDFs' text. "Mentions" means the existing `text_signals.mentions` (whole word or phrase,
with the plurals `singular` handles). Head-word matching (`head_words`) counts as a mention of a
multi-word name, as it does today.

### R1: Definition dependency

**Source:** Wang et al. 2016, *Supportive relationship in concept definition*: "A is likely to be
B's prerequisite if A is used in B's definition", with the first sentence taken as the definition.
Talukdar & Cohen 2012 use the same signal (a title mentioned in the other page's first sentence).

**Rule.** B's **defining sentences** are, for each member of B, the first sentence of that member's
content, counted only when that sentence's `definition_subject` equals `name(B)`, compared after
singularising each word. The sentence must actually open "B is / are / means / refers to / has…".

*Amended 2026-09-29 after measurement:* an earlier draft also counted the first sentence of any
member whose title resolved to `name(B)`. On gold topic 62, that made "Matter usually exists as a
solid, a liquid or a gas" count as Matter's definition. It produced Solid→Matter, which then
conflicted with containment and knocked Matter→Solid back to pending.
R1 holds for A→B when:
- `name(A)` is mentioned in a defining sentence of B, **and**
- `name(B)` is not mentioned in any defining sentence of A.

If both concepts' definitions name each other, R1 holds in neither direction.

*Example:* "Melting is when a **solid** turns into a **liquid**" gives Solid→Melting and
Liquid→Melting.

### R2: Section containment

**Source:** Wang et al. 2016 read textbook structure (table of contents, subchapters) as
prerequisite evidence, because "textbooks usually introduce concepts based on their learning
dependencies".

**Rule.** R2 holds for A→B when some member of B sits under a heading whose `heading_name` equals
`name(A)`. This is the existing `contained_in`. Only the *containment* part of the section structure
is used. Wang's subchapter-number distance is positional, so it is deliberately left out.

### R3: Passage reference distance

**Source:** Pan et al. 2017, Feature 2 (*Video Reference Distance*), which Pan introduce as a
generalisation of RefD (Liang et al. 2015) to course material that has no Wikipedia links.

**Adaptation, stated for the thesis.** Pan's unit is a course video, weighted by the term frequency
of `a` in it. In MAVIA the unit is a **learning object** (one passage), and a concept's units are
its grouped members: grouping has already decided which passages teach the concept. So
`f(a, V) = 1` when passage `V` is a member of `a`, and 0 otherwise. `r(V, b) = 1` when `V`'s text
mentions `name(b)`, or its head word, in at least one non-contrastive clause.

```
Prw(a, b) = Σ_{V ∈ members(a)} r(V, b) / |members(a)|   # share of a's passages naming b
Prd(a, b) = Prw(b, a) − Prw(a, b)                     # > 0: b's passages name a -> a before b
```

**Rule.** R3 holds for A→B when both names exist and `Prd(A, B) > θ`.

*Amended 2026-09-29 after measurement:* the first draft used Pan's Feature 3, *Sentence* Reference
Distance. That scored 0.000 on every Comparing and Changing pair of gold topic 152, because a
multi-word concept ("comparing the three states") is almost never said in a sentence. It is,
however, what its own passages are about.

**θ.** It is chosen from Liang et al.'s recommended range for RefD, **0.02–0.1**, by grid search on
gold topics 62 and 79 only, then validated unchanged on topics 152 and 308. The chosen value and its
sensitivity curve go into the evaluation report. No term is owned by any concept, and position is
never read.

### Rules considered and excluded

| Idea | Why excluded |
|---|---|
| Temporal-order vote | Position is only a weak classifier input in the literature (Pan's Average Position Distance: −2.4 F1 when removed). No source uses it as a gate. It stays as the tie-breaker only. |
| Earliest-concept term ownership | No source, and it causes the forward bias. |
| Inbound/outbound ratio | Only loosely related to Wang's in-link/out-link counts, which are inputs to a trained model. It inherits the ownership bias. |
| Embedding cosine for direction (`PHRASE_COSINE`) | ACE: it "results in false positives when it is used to determine the direction". |
| Complexity level (coverage × survival, Pan's strongest input) | It is only a classifier input in the source, and it risks repeating "solid beats matter". It may be measured later as a diagnostic, but it never creates a link. |
| Transitive reduction (ACE's minimal graph) | It would change which links remediation reads. Left out so this change stays within the pipeline; it can be proposed separately. |

## 5. Vetoes (applied before the decision)

1. **Same name.** `name(A) == name(B)` means no link. Unchanged.
2. **Contrast only.** If every mention of `name(A)` counted by R1 or R3 sits in a contrast clause
   (`only_contrastive_mentions`, unchanged marker list), that rule does not hold for A→B.
3. **Parallel siblings.** If A and B share a heading that names neither of them
   (`presented_in_parallel`), R3 alone cannot link them; only R1 can. This rule is **MAVIA's own
   design choice**, a sideways reading of the section structure in Wang et al. 2016. It is not a
   cited method, and the thesis must say so.

## 6. Decision (rule precedence, no voting)

For each ordered pair after the vetoes:

| Evidence | Status | `evidence.rule` |
|---|---|---|
| R1 or R2 holds for A→B, and neither R1 nor R2 holds for B→A | **accepted** | `definition` or `containment` (R1 is recorded when both hold) |
| R1 or R2 holds in **both** directions | **pending** | `conflict` |
| Only R3 holds for A→B | **pending** | `reference` |
| Nothing holds | none | — |

- **R3 never overrides R1 or R2.** When R3 points against an accepted R1/R2 link, the link stays
  accepted, and the opposing Prd value is recorded in its evidence. This follows the precision
  findings: structural and definitional evidence is the high-precision kind (Pan's is-a pattern
  baseline: precision 67–80%, recall 15–27%).
- **R3-only links stay pending.** The teacher confirms direction from text statistics, which is the
  position ACE takes.
- Structural concepts get no links and still close the path. Unchanged.

### Stored evidence (`ConceptPrerequisite.evidence`, JSON; schema unchanged)

```json
{
  "rule": "definition | containment | reference | conflict",
  "definition": {"sentence": "<the defining sentence of the dependent>"},
  "containment": {"heading": "<heading naming the prerequisite>"},
  "reference": {"prd": 0.0, "prw_forward": 0.0, "prw_backward": 0.0, "theta": 0.0},
  "opposing_reference": {"prd": 0.0}
}
```

Only the keys that apply are present. `cross_section` is still computed and stored as today.

## 7. Components and interfaces

| File | Change |
|---|---|
| `learning_path/services/criteria.py` | Rewrite. Keep `concept_names`, `concept_text`, `head_words`, `contained_in`, `only_contrastive_mentions`, `presented_in_parallel`, `named_sections`, `section_headings`, `crosses_sections`. Remove `key_terms`, `reference_details`, `reference_matrix`, `_phrase_hits`, `_windows`, `inbound_outbound_ratios`, `temporal_order`, `semantic_reference`, `inbound_outbound`, `cast_votes`, `decide`, `names_the_target`, and the constants `REF_MAX_DF_RATIO`, `REF_MARGIN`, `PHRASE_COSINE`, `MIN_IOL_MARGIN`, `WINDOW_SIZE`, `MAX_WINDOWS_PER_CONCEPT`, `MIN_OUTBOUND`, `MAX_IOL`. Add `defining_sentences(concept, name)`, `definition_dependency(a, b, names, heads)`, `passage_reference(concepts, names, heads)` (returns Prw/Prd per ordered pair), and constant `PRD_THRESHOLD`. `decide_pairs(concepts, runtime_instance=None)` keeps its signature. `runtime_instance` becomes unused and is kept for callers. |
| `learning_path/services/text_signals.py` | Add `first_sentence(text)`, used by R1. |
| `learning_path/services/publishing.py` | Read `decision["evidence"]` instead of `decision["votes"]` (two lines). Nothing else changes. |
| `learning_path/services/gold.py` | Report accepted and pending recall and forbidden-accepted per rule type. |
| `learning_path/management/commands/evaluate_gold_paths.py` | `--grid` sweeps θ over 0.02–0.1. |
| `learning_path/fixtures/gold_map_308.json`, `gold_topic_308.json` | New. Topic 308 after hand grouping. The answer key is drafted by Claude **from the PDFs, before implementation**, corrected by the user, then frozen. |
| `learning_path/CRITERIA.md` | New "v4" section. Earlier sections kept as history. |
| Tests | Rewrite `test_criteria.py` for R1, R2, R3, the vetoes and the decision table. Update `test_gold_paths.py` baselines. `tests.py` fixture at line ~343 uses `"votes"`, so rename it to `"evidence"`. |

Unchanged: `concept_units.py`, `concepts.py`, `order_with_links`, `path_builder.py`, `published.py`,
models, migrations, views, frontend, and all of `adaptive/`.

## 8. Research basis (verified 2026-09-29 against the full papers)

| Claim used here | Source |
|---|---|
| RefD formula, positive θ, recommended 0.02–0.1, no position used, `r` may be "mentions in books" | Liang, Wu, Huang & Giles 2015, *Measuring Prerequisite Relations Among Concepts*, EMNLP, §2–4.3 |
| Video Reference Distance (Feature 2) and Sentence Reference Distance (Feature 3) definitions. RefD "not applicable in plain text". Ablation: Apd −2.4, Cld −7.4 F1. Is-a pattern baseline P 67–80%, R 15–27% | Pan, Li, Li & Tang 2017, *Prerequisite Relation Learning for Concepts in MOOCs*, ACL, §3.2–4.4 |
| Definition supportive relation. Textbook structure (TOC) as evidence. Complexity-level features beat relatedness features | Wang et al. 2016, *Using Prerequisites to Extract Concept Maps from Textbooks*, CIKM, §3.2, §4.3 |
| First-sentence title mention as a feature | Talukdar & Cohen 2012, *Crowdsourced Comprehension*, BEA, §2.1 |
| Cosine windows give false positives for direction, so the expert decides direction. DAG axioms (asymmetry, irreflexivity, transitivity) | Aytekin & Saygın 2024, *ACE*, JEDM, §3–4 |
| Multi-relation graphs help only inside trained models | Jia et al. 2021, NAACL (R-GCN over concept, learning-object and co-occurrence edges). Bai et al. 2025, ACM CSUR (survey; abstract only) |

## 9. Knowledge-graph question (decision recorded)

A multi-relation knowledge graph would not improve the path directly. Ordering can only follow
"learn A before B" edges, and relations such as is-a or part-of do not say which comes first. They
help only as **evidence for** prerequisites, which is how R2 uses part-of (containment) here. The
reported gains from multi-relation graphs come from trained neural models, which MAVIA's
constraints rule out. **Decision:** no knowledge-graph build in this change. Making part-of,
sibling, same-concept and example-of explicit as typed relations stays a possible later step for
explainability.

## 10. Evaluation and acceptance

Run through `evaluate_gold_paths` and `test_gold_paths.py` with the real concepts.

**Metrics** (the standard ones in every cited paper):
- precision, recall and F1 of **accepted** links against required edges;
- recall of **accepted + pending**;
- forbidden links accepted;
- whether the saved order matches the expected order;
- a per-rule breakdown.

**Acceptance criteria:**
1. **0 forbidden links accepted** on topics 62, 79, 152 and 308.
2. **Expected order matches** on all four topics.
3. **Accepted + pending recall of required edges** is at least 62 ≥ 9/10, 79 ≥ 3/8, 152 ≥ 8/10
   (the measured v4 baseline, Section 10.1). Accepted recall is reported, not gated.
4. **Topic 308:**
   - accepted precision ≥ 0.8;
   - no accepted link from a figure description or an example-type concept to the concept that
     defines its subject;
   - Matter→Solid, Matter→Liquid and Matter→Gas all accepted.
5. **θ** is chosen on 62 and 79 only. The report shows 152 and 308 at that θ unchanged.

If a criterion fails, the fallback is decided with the user **before** any tuning. It is not
tuned silently.

### 10.1 Pre-implementation measurement (2026-09-29, throwaway script, no code changed)

Strict R1, R2, passage-level R3 and the decision table, run on the gold fixtures:

| Topic | Required accepted | Reachable (accepted + pending) | Forbidden accepted or pending | Extra pending |
|---|---|---|---|---|
| 62 | 3/10 | 9/10 | 0 | matter→comparing, matter→changing (true by transitivity) |
| 79 | 3/8 | 3/8 | 0 | fertilization, seed, fruit → reproduction (reversed, child→parent) |
| 152 | 3/10 | 8/10 | 0 | matter→changing |

Results were identical for θ ∈ {0.02, 0.05, 0.1}.

**Unreachable, and why:**
- **Comparing→Changing** (62, 152): no naming, definition or structural evidence in the text. v3
  accepted it only through incidental words ("explain", "four", "outline").
- **Seed→Fruit** (79): the two are siblings, and neither concept's definition names the other.
- **Gas→Changing** (152): the split Changing concepts never name gas.
- **Topic 79's known gaps:** no stemming ("fertilized" vs "fertilization"), and the linking terms
  (pollen, anther, stigma) are not concept names.

**Consequence, accepted by the user on 2026-09-29:** only containment links are accepted
automatically on these topics. Every other link is a teacher suggestion, and the order falls back
to document order wherever links are silent. This trades automatic coverage for precision: no
wrong link is accepted, and the only wrong suggestions are the three reversed ones on topic 79.
Accepting R3 on its own was rejected, because it would accept those reversed links and push
Reproduction after its own parts.

## 11. Risks

- **Sparse evidence.** Short lessons may have few definitional sentences, which lowers accepted
  recall. Mitigation: R3 still proposes those links as pending, and the path falls back to document
  order.
- **Prd on parent/child pairs.** A parent's introduction lists its children ("matter exists as
  solid, liquid and gas"), so Prd points child→parent (measured: Matter/Solid −1.0 on topic 62;
  Fertilization/Seed/Fruit → Reproduction on topic 79). Mitigation: R2 and R1 take precedence
  (Section 6).
- **Word forms.** Mentions handle only plurals, so "fertilized" does not match "fertilization"
  (topic 79's known gaps). This is recorded, not fixed here.
- **Manuscript drift.** The Theoretical Background (prerequisite section) and Chapter 3's criteria
  and algorithm text describe v3. They are rewritten after implementation, against the merged code.
  The DQN framing rule is not affected.

## 12. Follow-ups outside this spec

- Rewrite the manuscript's prerequisite sections once the code has merged.
- Measure complexity level as a diagnostic on topic 308.
- Propose transitive reduction separately, since it changes what remediation reads.
- Typed relations (part-of, sibling, same-concept, example-of) for explainability.
