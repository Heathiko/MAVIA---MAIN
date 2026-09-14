# Prerequisite edge scoring v3: three weighted criteria

**Date:** 2026-09-13
**Status:** Design, pending review
**Replaces:** the ordinal strong/medium/weak acceptance in
`learning_path/services/evidence.py`
**Source spec:** MAVIA Edge-Based Prerequisite Scoring, Final Criteria
Specification (v3)

## Scope

**One path per topic, whose steps are concept groups.**

Revised after review. The earlier scope was "learning-object level only, one
material", which produced a separate path per uploaded PDF -- three disconnected
sequences for a topic with three files. Grouping already asserts which chunks
across PDFs teach the same concept, so the concept is the teaching unit: a
learner meets "Solid" once, with its three versions, not three times.

Two facts made the change cheap to take now rather than later:

* **Nothing outside `learning_path/` consumes the path.**
  `LessonPackageService` still serves chunks in `order, id`, so no downstream
  behaviour depends on the current shape.
* **No teacher-authored edges exist.** All 18 stored edges are `derived`
  (14 voted, 4 chunk continuation), and derived edges are regenerated from text,
  so nothing a person created is lost.

It gets materially more expensive once the learner flow starts reading paths.

**Still out of scope:** ordering *subtopics against one another* within a course.
That is a different graph, and of 24 subtopics in the current outline only one
has any materials attached -- there is nothing to derive it from yet.

### What this changes

* `PrerequisiteEdge` references `LearningObjectGroup` rather than
  `LearningObject`, and its validation requires one shared `outline_node`
  instead of one shared material.
* `build_learning_path(material_id)` becomes `build_topic_path(node_id)`, and
  the topic endpoint returns a single path rather than a list.
* The criteria read a concept's text from its representative's Normal version.
* **TemO needs a cross-PDF rule**, because a concept sits at different positions
  in different files. Decided: a concept's position is its **earliest first
  appearance across the topic's materials** -- "which is taught first" is the
  question TemO asks, and the earliest appearance is the honest answer to it.

## What changes and what stays

**Replaced.** The tier machinery in `evidence.py`: the strong/medium/weak split
and `accept(strong, medium)`. Scoring becomes three votes plus a threshold.

**Retained out of `gather()`: the S1 explicit-dependency detector.** This is not
a tidying detail. `suppressed()` takes two arguments that `gather()` supplies,
and each carries a different override:

* `author_says_so` (S1 fired) overrides **sibling** and **contrastive**
  suppression -- both of which claim there is no dependency at all, a claim only
  the author may contradict.
* `strong` (any strong signal) overrides **mutual reference**, which claims only
  that the *direction* is ambiguous.
* Same-concept suppression is absolute and overridden by nothing.

Retiring `gather()` wholesale and calling `suppressed(a, b, ctx)` with its
defaults would make every suppressor absolute. That errs toward fewer edges, so
it would pass testing while silently deleting a documented, deliberate override
structure.

Therefore:

* The S1 block survives as its own detector and supplies `author_says_so`. It
  finds the author stating pedagogy directly -- "to understand X you must know
  Y" -- which **none of the three criteria expresses**, and which is scoped to
  name the concept in the same sentence precisely because an unscoped version
  once produced 46 edges from two sentences.
* **Decided at review: S1 also accepts an edge on its own**, joining
  `chunk_continuation` as a signal that bypasses the vote entirely. The author
  stating a dependency outright is better evidence than three inferred votes.
  The sentence-level scoping above is what keeps this safe.
* `strong=` is supplied by the vote outcome: an edge scoring 3/3 counts as
  strong for the mutual-reference override.

S2 (taxonomic is-a), S3 (scope framing), S4 (aggregation) and the medium tiers
are retired; those are the association signals the three criteria replace.

**Kept, deliberately.**

* **`chunk_continuation`.** "(Part 1 of 3)" -> "(Part 2 of 3)" is one passage the
  chunker cut. It is structural fact, not a vote, and no combination of the
  three criteria expresses it. Unchanged: weight 1.0, its own signal.
* **The suppressors** (`suppressed()`), which are exactly four, in the order it
  applies them: **same concept** (co-definers), **siblings**, **every mention
  contrastive**, and **mutual reference** -- with `author_says_so`
  short-circuiting between the first and second. These stay as a **veto applied
  after voting**.

  Note what is *not* a suppressor: aggregation. S4 aggregation was an evidence
  signal -- a comparison chunk depends on what it compares -- and it is retired
  above.

  The reason is concrete. "Unlike a solid, a liquid takes the shape of its
  container" makes liquid's text mention solid, so CSR votes `solid -> liquid`.
  The sentence is a *contrast*, not a dependency. No voter can tell those apart;
  the suppressor already can. Dropping it re-imports a defect this codebase has
  already fixed once.
* **Cycle breaking** (`_break_cycles`) and the topological sort, unchanged.

## The three criteria

### 1. Temporal order (TemO)

```
TemO(A, B) = 1  if Position(A) < Position(B)
           = 0  otherwise
```

Positions come from `scan_positions()`. Glossary and vocabulary sections are
excluded from indexing, as the source spec requires: those are usually
alphabetical and would inject ordering that means nothing. `concepts.py` already
carries `STRUCTURAL_LABELS` for this kind of document furniture and is reused
rather than duplicated.

**TemO fires on one direction of every pair.** With 20 objects, 190 of 380
ordered pairs receive this vote before any content is read. This is the single
largest density risk in the design; see *Density guard* below.

### 2. Semantic reference score (CSR)

```
CSR(A, B) = mean over windows j of  cosine( window_j of B's text, name of A )
Direction: A is prerequisite of B when CSR(A, B) > CSR(B, A)
```

10-token sliding windows over the dependent's text, embedded with
`all-MiniLM-L6-v2` through `semantic_grouping.runtime()` -- the model is already
loaded in this process for grouping, so this adds no new dependency.

**Deviation from the source spec, and why.** The spec sums the per-window
cosines. A sum grows with the number of windows, so a long chunk would outscore
a short one regardless of relatedness, and our chunks vary from 9 to 80+ words.
The mean measures the same thing without the length bias. Recorded as a
deviation rather than a silent change.

**"The name of A" is not always available.** `resolve_concept()` is explicitly
allowed to return nothing -- a chunk titled "Matter usually exists in one of
three everyday states" owns no concept name to embed against. The rule follows
what `concepts.py` already establishes:

> A chunk owning no concept can still depend on other chunks; nothing can
> depend on it.

So when A owns no concept, `CSR(A, *) = 0` and A cannot win the CSR vote in
either direction. It can still be a dependent.

When **neither** object owns a concept, both directions score zero and **no CSR
vote is cast either way** -- rather than a tie being resolved arbitrarily toward
one direction. Combined with the density guard below, such a pair can never
become an edge on position alone.

### 3. Inbound/outbound reference ratio (IOLR)

```
IOL(x)      = (sum of inbound CSR to x) / (sum of outbound CSR from x)
IOLR(A, B)  = 1 if IOL(A) > IOL(B) else 0
```

Computed from the CSR matrix criterion 2 already builds; no new text pass.

**Zero outbound.** A chunk that references nothing divides by zero. The
denominator is floored at a small epsilon, and the resulting ratio is capped, so
"references nothing" reads as strongly foundational without producing infinity
or `NaN` -- values that would make the comparison in `IOLR` undefined and would
propagate into stored evidence. Both constants live beside the criterion rather
than being inlined, so the tuning step can see them.

## Decision layer

Each criterion casts one binary vote, equally weighted:

```
score(A, B) = (TemO + CSR_direction + IOLR) / 3
```

**A consequence worth stating plainly:** three binary votes produce exactly four
possible scores -- 0, 1/3, 2/3, 1. "Two tuned thresholds" therefore means
choosing among three cut points, not tuning a continuous dial. That makes
tuning tractable and honest, but it is not the fine-grained calibration the
phrase suggests.

| score | outcome |
|---|---|
| 3/3 | accepted, edge constrains the path |
| 2/3 | **pending** -- surfaced for teacher review, does not constrain the path |
| <= 1/3 | discarded |

Two signals produce an accepted edge without carrying a score at all:
`chunk_continuation` and S1 (explicit author statement). Both are recorded with
their own signal rather than as `voted`, so the review screen can say *why* an
edge exists without implying the criteria produced it.

**Density guard: TemO alone may never create an edge.** At least one *content*
vote (CSR or IOLR) is required. Without this, every forward pair starts at 1/3
from position alone and the middle band fills with pairs whose only evidence is
"this paragraph came first" -- which is document order, not dependency, and is
what produced 28% edge density in the design before last.

**Pending edges do not constrain the ordering.** An unreviewed guess should not
silently shape what a learner is taught. It is shown, not applied.

## Model change

`PrerequisiteEdge` gains a status:

| value | meaning |
|---|---|
| `accepted` | derived above the high threshold, or teacher-authored |
| `pending` | in the middle band, awaiting teacher review |
| `rejected` | teacher said no |

`rejected` is a stored state rather than a deletion, because re-derivation must
not propose the same pair again next time the material is reprocessed. This
mirrors how `LearningObjectMatchSuggestion` already preserves teacher decisions
in the lessons app.

Re-derivation rules, extending what `rebuild_edges_for_material` already does
for teacher-authored edges: derived rows are replaced; teacher-authored and
teacher-rejected pairs survive.

One migration, with a default of `accepted` so existing rows keep their current
behaviour.

## Evidence recorded per edge

Enough to reconstruct the decision without re-running it: each criterion's vote,
`CSR(A,B)` and `CSR(B,A)`, both IOL values, the combined score, the thresholds
in force, and the embedding model fingerprint. The existing review screen already
renders evidence, so this stays inspectable.

## Thresholds

There is no public dataset that can set these. Checked directly: AL-CPL is
`(concept, concept, label)` and the university-course dataset is
`(concept, concept, 13 annotators)`. Neither carries document positions or
source text, so TemO cannot be computed on them, CSR has nothing to window, and
IOLR follows from CSR. All three criteria are uncomputable on that data. No K-12
prerequisite dataset exists.

Thresholds are therefore set from `docs/prerequisite_labelling_sample.csv`: 42
pairs from material 14, stratified across the similarity range, of which 6 are
`Part N -> Part N+1` continuations whose answer is known and which act as a
consistency check on the annotator.

Procedure: label, then report precision and recall at each of the three possible
cut points, then choose. A tuning script prints that table; it is not a training
process.

Interim, until labels exist: the strictest setting (3/3 accepts, 2/3 pends,
everything else discarded), so the graph errs toward too few edges rather than
too many.

## Files

| file | change |
|---|---|
| `learning_path/services/criteria.py` | **new** -- the three voters and the CSR matrix |
| `learning_path/services/edge_derivation.py` | rewired to vote-and-threshold; keeps continuation edges and cycle breaking |
| `learning_path/services/evidence.py` | keeps `build_context()`, `suppressed()` and the S1 explicit-dependency detector out of `gather()`; the remaining tier logic retired |
| `learning_path/models.py` + migration | `status` field |
| `learning_path/views.py` | accept/reject a pending edge |
| `frontend/.../LearningPathPanel.jsx` | pending band in the review screen |
| `learning_path/management/commands/tune_prerequisite_thresholds.py` | **new** -- reads the labelled CSV, prints precision/recall per cut point |

## Testing

* Each voter unit-tested in isolation, with a fake embedding runtime so results
  are deterministic (the `FakeRuntime` pattern in `lessons/test_semantic_grouping.py`).
* TemO: glossary sections excluded; a pair with no content vote never becomes an
  edge.
* CSR: direction flips when the referencing direction flips; a chunk owning no
  concept never wins as prerequisite; the mean is length-insensitive.
* IOLR: zero-outbound does not divide by zero.
* Decision layer: each band maps to the right status; pending edges are absent
  from the constraints passed to the sort.
* Re-derivation preserves teacher-authored and teacher-rejected pairs.
* A density assertion on real material, so a future change that reintroduces
  dense edges fails a test rather than being noticed months later.

## Deliberately not in this change

Subtopic-level ordering. Adaptive reordering, mastery tracking, remediation.
Wiring the derived order into what learners actually see -- `LessonPackageService`
still serves `order, id`, and changing that is its own decision.

## Decisions taken at review

1. **Pending edges do not constrain the ordering.** Confirmed. An unverified
   guess must not shape what a learner is taught.

   Two consequences follow and are part of the work: the review screen must show
   **what the ordering would become** if a pending edge were accepted -- otherwise
   the teacher approves a constraint without seeing its effect -- and accepting
   must run the cycle check and roll back, as `create_edge` already does.

2. **Votes stay binary; margins are recorded anyway.** Three yes/no votes give
   only four possible scores, so threshold "tuning" is a choice among three cut
   points. Using the CSR margin would make the score continuous and genuinely
   tunable, but 42 labelled pairs cannot support fine tuning, and equal-weight
   binary voting is what the cited work did. `CSR(A,B)` and `CSR(B,A)` are stored
   per edge regardless, so moving to a margin-based score later requires no
   re-derivation.

3. **An explicit author statement accepts an edge on its own.** Confirmed. S1
   joins `chunk_continuation` as a signal that bypasses the vote: the author
   stating a dependency outright is better evidence than three inferred votes.
   Its existing sentence-level scoping is what keeps this safe -- an unscoped
   version produced 46 edges from two sentences.
