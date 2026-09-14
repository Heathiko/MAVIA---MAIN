"""The three criteria that decide whether one concept precedes another.

Each criterion casts a single vote, they are weighted equally, and two
thresholds turn the tally into an edge, a question for the teacher, or nothing.
See ``learning_path/CRITERIA.md``.

Nothing here writes to the database, and nothing calls a generative model: the
only model involved is the sentence encoder already loaded for grouping, so the
same concepts always produce the same votes.
"""

import re
from collections import defaultdict

from lessons.services.semantic_grouping import runtime as semantic_runtime

from .concepts import resolve_concept
from .text_signals import mentions, normalize

# ACE's methodology windows the dependent's text rather than embedding it whole,
# so a single sentence referring to another concept is not diluted by a long
# passage around it.
WINDOW_SIZE = 10

# Runtime is O(windows x concepts). A very long concept would otherwise dominate
# a topic's cost for no gain, since its later windows repeat the same subject.
MAX_WINDOWS_PER_CONCEPT = 120

# A ratio needs a denominator. A concept that refers to nothing is maximally
# foundational, and the cap keeps that comparable and sortable instead of
# infinite -- `inf > inf` is False, which would silently drop such a pair.
MIN_OUTBOUND = 1e-6
MAX_IOL = 1e6

# How much more foundational one concept must be before the ratio counts as
# evidence rather than as noise. See `inbound_outbound`.
MIN_IOL_MARGIN = 0.25


def _windows(text):
    """Sliding word windows over a concept's text."""
    words = normalize(text).split()
    if not words:
        return []
    if len(words) <= WINDOW_SIZE:
        return [" ".join(words)]
    windows = [
        " ".join(words[start:start + WINDOW_SIZE])
        for start in range(len(words) - WINDOW_SIZE + 1)
    ]
    if len(windows) <= MAX_WINDOWS_PER_CONCEPT:
        return windows
    # Keep an even spread rather than the first N: the end of a passage is as
    # likely to name what it depends on as the beginning.
    stride = len(windows) / MAX_WINDOWS_PER_CONCEPT
    return [windows[int(index * stride)] for index in range(MAX_WINDOWS_PER_CONCEPT)]


def concept_names(concepts):
    """The name each concept can be *referred to by*, or None.

    A concept with no name cannot be referred to, so nothing can be shown to
    depend on it -- the same rule `concepts.py` already applies to chunks.
    """
    return {concept.id: resolve_concept(concept) for concept in concepts}


def reference_matrix(concepts, runtime_instance=None):
    """``{(a, b): CSR(a, b)}`` -- how strongly b's text refers to a.

    The source spec sums the per-window cosines. A sum grows with the number of
    windows, so a long concept would outscore a short one regardless of how
    related they are, and these concepts run from nine words to several hundred.
    The mean measures the same thing without the length bias; recorded as a
    deviation rather than made silently.
    """
    engine = runtime_instance or semantic_runtime()
    names = concept_names(concepts)

    named = [concept for concept in concepts if names[concept.id]]
    windowed = {
        concept.id: _windows(concept.content) for concept in concepts
    }

    # One encode call for everything: names first, then every window.
    payload = [names[concept.id] for concept in named]
    offsets = {}
    for concept in concepts:
        offsets[concept.id] = (len(payload), len(windowed[concept.id]))
        payload.extend(windowed[concept.id])
    if not payload:
        return {}

    vectors = engine.embeddings(payload)
    name_vectors = {
        concept.id: vectors[index] for index, concept in enumerate(named)
    }

    matrix = {}
    for target in named:
        name_vector = name_vectors[target.id]
        for holder in concepts:
            if holder.id == target.id:
                continue
            start, count = offsets[holder.id]
            if not count:
                matrix[(target.id, holder.id)] = 0.0
                continue
            # Vectors come back normalised, so the dot product is the cosine.
            total = 0.0
            for index in range(start, start + count):
                window = vectors[index]
                total += sum(left * right for left, right in zip(name_vector, window))
            matrix[(target.id, holder.id)] = total / count
    return matrix


def inbound_outbound_ratios(concepts, matrix):
    """``{concept id: IOL}`` -- referenced a lot, referring little, is foundational.

    **Only nameable concepts get a ratio.** Inbound reference is how strongly
    other text refers to a concept's *name*, so a concept with no name has an
    inbound of zero by construction, not by measurement. Giving it a ratio of 0
    made every named concept look more foundational than it -- measured on real
    content, 55 verdicts came from nothing but that. The matrix only holds rows
    for nameable targets, so those are exactly the concepts measured here.
    """
    inbound = defaultdict(float)
    outbound = defaultdict(float)
    for (target_id, holder_id), score in matrix.items():
        inbound[target_id] += score
        outbound[holder_id] += score

    nameable = {target_id for target_id, _ in matrix}
    ratios = {}
    for concept in concepts:
        if concept.id not in nameable:
            continue
        denominator = max(outbound[concept.id], MIN_OUTBOUND)
        ratios[concept.id] = min(inbound[concept.id] / denominator, MAX_IOL)
    return ratios


def temporal_order(a, b):
    """1 when the topic presents ``a`` first.

    ``order`` is already the concept's earliest appearance across the topic's
    materials, so this reads the same whichever file introduced it.
    """
    return 1 if a.order < b.order else 0


def semantic_reference(a, b, matrix):
    """1 when b's text refers to a more than a's refers to b.

    **Both concepts must be nameable for this to mean anything.** A concept with
    no name -- "Everyday Examples", "Examples" -- cannot be searched for, so its
    side of the comparison is structurally zero. Comparing a measured number
    against one that could never be measured is not evidence of direction; it
    just means the named concept always wins. Measured on real data that made
    every nameless concept a dependent of nearly everything.

    The matrix holds a row for each nameable concept, so a missing key is
    exactly the case where no comparison is possible.
    """
    forward_key, backward_key = (a.id, b.id), (b.id, a.id)
    if forward_key not in matrix or backward_key not in matrix:
        return 0

    forward, backward = matrix[forward_key], matrix[backward_key]
    if forward <= 0.0 and backward <= 0.0:
        return 0
    return 1 if forward > backward else 0


def inbound_outbound(a, b, ratios):
    """1 when ``a`` is *clearly* the more foundational of the pair.

    A bare ``>`` makes this a coin toss. Measured on real content the ratios sat
    between 1.60 and 2.12 -- close enough that 2.001 beating 2.000 cast a full
    vote, on every pair, which is what filled the review queue. Requiring a real
    gap means the criterion abstains when it cannot tell the two apart, which is
    the honest answer far more often than not.

    The margin is relative because the ratio is scale-free: what matters is
    being half again as foundational, not being 0.4 higher.

    A concept with no ratio has no name to be referred to by, so the
    comparison is not a measurement and no vote is cast -- the same rule
    ``semantic_reference`` applies.
    """
    if a.id not in ratios or b.id not in ratios:
        return 0
    return 1 if ratios[a.id] > ratios[b.id] * (1.0 + MIN_IOL_MARGIN) else 0


def cast_votes(a, b, matrix, ratios):
    """Every criterion's vote for "a comes before b", plus the numbers behind it."""
    forward = matrix.get((a.id, b.id), 0.0)
    backward = matrix.get((b.id, a.id), 0.0)
    return {
        "temporal_order": temporal_order(a, b),
        "semantic_reference": semantic_reference(a, b, matrix),
        "inbound_outbound": inbound_outbound(a, b, ratios),
        "csr_forward": round(forward, 6),
        "csr_backward": round(backward, 6),
        # Stored even though the vote is binary: moving to a margin-based score
        # later needs these and nothing else, so no re-derivation.
        "csr_margin": round(forward - backward, 6),
        "iol_prerequisite": round(ratios.get(a.id, 0.0), 6),
        "iol_dependent": round(ratios.get(b.id, 0.0), 6),
    }


ACCEPTED = "accepted"
PENDING = "pending"


def decide(votes):
    """``accepted``, ``pending`` or ``None`` for one ordered pair.

    Three binary votes produce exactly four scores, so "two thresholds" means
    choosing among three cut points rather than turning a dial. 3/3 is an edge,
    2/3 is a question for the teacher, anything less is discarded.

    **Position alone never creates an edge.** Temporal order votes on one
    direction of *every* pair -- with 24 concepts that is 276 votes cast before
    a word is read -- so at least one content criterion has to agree. Without
    that guard the middle band fills with pairs whose only evidence is that one
    paragraph came first, which is document order, not dependency.
    """
    content_votes = votes["semantic_reference"] + votes["inbound_outbound"]
    if not content_votes:
        return None

    score = votes["temporal_order"] + content_votes
    if score == 3:
        return ACCEPTED
    if score == 2:
        return PENDING
    return None


# A mention inside a contrastive clause says what something is *not* like.
#
# KNOWN LIMITATION, kept deliberately: this is a fixed list of English markers.
# It misses contrasts phrased without them ("solids do not flow", "different
# from a solid"), and it would not carry over to another language. A model that
# recognises contrast (NLI) would generalise; it was not adopted because it adds
# a model and slows the build, and whether contrast causes wrong edges in
# practice had not yet been measured.
_CONTRAST = re.compile(r"\b(while|whereas|unlike|but not|although|however)\b", re.I)
_SENTENCE = re.compile(r"(?<=[.!?])\s+")


def only_contrastive_mentions(name, text):
    """True when every mention of ``name`` in ``text`` is contrastive.

    Contrast is scoped to the clause, not the sentence. "Liquids and gases can
    flow, while solids normally do not" contrasts *solids* only -- liquids and
    gases are what it is about.
    """
    records = []
    for sentence in _SENTENCE.split(text or ""):
        marker = _CONTRAST.search(sentence)
        if not marker:
            if mentions(normalize(sentence), name):
                records.append(False)
            continue
        before, after = sentence[:marker.start()], sentence[marker.end():]
        if mentions(normalize(before), name):
            records.append(False)
        if mentions(normalize(after), name):
            records.append(True)
    return bool(records) and all(records)


def vetoed(a, b, names):
    """A pair the votes allow but that must not become an edge.

    The criteria measure *how much* one concept looks like groundwork for
    another; they cannot recognise a pair that should never be an edge. Two
    checks remain, and both are about the pair itself rather than the lesson's
    wording elsewhere:

    * **Same concept.** Two concepts owning the same name cannot depend on
      each other.
    * **Only contrasted.** If ``b`` mentions ``a`` only to say what it is not
      like, reading ``b`` does not build on ``a``.

    Removed, and why:

    * *Siblings* keyed on the words of the topic's title. Renaming one object
      to "Diagram description for Solid" silently made it a sibling of Solid,
      Liquid and Gas and deleted 13 edges -- a rule whose output depends on
      title wording does not generalise.
    * *Mutual reference* matched names literally and fired on none of 139
      measured pairs.
    * The *author-statement override* of the contrast check was itself a fixed
      phrase list, and existed only to override the rules above.
    """
    a_name, b_name = names.get(a.id), names.get(b.id)
    if a_name and a_name == b_name:
        return True
    if a_name and only_contrastive_mentions(a_name, b.content):
        return True
    return False


def section_headings(concept):
    """The lesson headings a concept sits under, across every file teaching it.

    Taken from the documents' own structure (the heading each passage was
    extracted beneath), never from the words of a title, so renaming an object
    does not change it.
    """
    members = getattr(concept, "members", None) or (concept,)
    return {
        (member.section_title or "").strip().casefold()
        for member in members
        if (member.section_title or "").strip()
    }


def crosses_sections(a, b):
    """True when both concepts sit under headings and share none of them.

    Measured on a blind hand-check of 62 proposed edges: all 35 that crossed
    between sections ("Everyday examples of solids" -> "Gas") were judged wrong,
    because a lesson's Solids, Liquids and Gases sections are parallel topics.
    A concept with no heading -- a comparison at the end, the opening definition
    -- is not treated as crossing anything.
    """
    left, right = section_headings(a), section_headings(b)
    return bool(left and right and not (left & right))


def decide_pairs(concepts, runtime_instance=None):
    """Every ordered pair the criteria accept or send to the teacher, after vetoes.

    **A cross-section edge is never accepted automatically** -- it is at most
    pending. Parallel sections are the common case, but some lessons do build
    section on section (Addition before Multiplication), so these edges are
    left for a teacher to approve rather than discarded.
    """
    concepts = list(concepts)
    if len(concepts) < 2:
        return []

    matrix = reference_matrix(concepts, runtime_instance)
    ratios = inbound_outbound_ratios(concepts, matrix)
    names = concept_names(concepts)

    decisions = []
    for a in concepts:
        for b in concepts:
            if a.id == b.id:
                continue

            votes = cast_votes(a, b, matrix, ratios)
            verdict = decide(votes)
            if verdict is None or vetoed(a, b, names):
                continue

            cross_section = crosses_sections(a, b)
            if cross_section and verdict == ACCEPTED:
                verdict = PENDING

            decisions.append({
                "prerequisite": a,
                "dependent": b,
                "verdict": verdict,
                "votes": votes,
                "cross_section": cross_section,
            })
    return decisions
