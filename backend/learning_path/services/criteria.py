"""Prerequisite links for the learning path (criteria v6).

For each pair of concepts in a topic: the text decides whether a link exists (a
name, terms one concept explains, or a heading), the lesson's order decides which
way, and a link nothing contradicts is accepted. Relatedness and meaning are
recorded, not counted. Nothing here writes to the database. See
docs/superpowers/specs/2026-09-30-learning-path-v6-reference-order-design.md.
"""

from . import embeddings
from .calibration import load_calibration
from .clues import (
    clue_records, find_term_owners, heading_vote, meaning_vote, name_vote, order_vote,
    presented_in_parallel, reference_uses, shared_pdf_order, term_vote,
)
from .concept_text import material_positions, prepare
from .fusion import (
    ACCEPTED, DECIDING_CLUES, DISAGREE, NONE_SHARED, PENDING, SHARED,
    PairFacts, confidence, reference_verdict,
)
from .relatedness import relatedness

__all__ = ["ACCEPTED", "PENDING", "crosses_sections", "decide_pairs"]

_PDF_ORDER = {1: SHARED, -1: SHARED, 0: DISAGREE, None: NONE_SHARED}
_NAME_FIELDS = ("later_names_earlier", "earlier_names_later")
_TERM_FIELDS = ("later_uses_earlier_terms", "earlier_uses_later_terms")


def section_headings(concept):
    """The lesson headings a concept sits under, across every file teaching it."""
    members = getattr(concept, "members", None) or (concept,)
    return {
        (getattr(member, "section_title", "") or "").strip().casefold()
        for member in members
        if (getattr(member, "section_title", "") or "").strip()
    }


def crosses_sections(first, second):
    """True when both concepts sit under headings and share none; shown to the teacher, never decisive."""
    left, right = section_headings(first), section_headings(second)
    return bool(left and right and not (left & right))


def _is_figure(text):
    return getattr(text.concept, "kind", "text") == "image"


def _facts(first, second, owners, positions, without):
    """``(facts, earlier, later)``; ``first`` precedes ``second`` in the topic's merged order."""
    order, _ = shared_pdf_order(first, second, positions)
    earlier, later = (second, first) if order == -1 else (first, second)
    uses = reference_uses(earlier, later, owners)
    for clue, fields in (("name", _NAME_FIELDS), ("terms", _TERM_FIELDS)):
        if clue in without:
            uses.update({field: 0.0 for field in fields})
    facts = PairFacts(
        **uses,
        heading=0 if "heading" in without else heading_vote(earlier, later)[0],
        pdf_agreement=0 if "order" in without else order_vote(earlier, later, positions)[0],
        parallel=presented_in_parallel(first, second),
        earlier_is_figure=_is_figure(earlier),
        later_is_figure=_is_figure(later),
        pdf_order=_PDF_ORDER[order],
    )
    return facts, earlier, later


def _votes(prerequisite, dependent, owners, positions, meaning_cutoff, semantic, without):
    """Each clue's vote, +1 when it supports ``prerequisite`` first."""
    votes = {
        "name": name_vote(prerequisite, dependent)[0],
        "terms": term_vote(prerequisite, dependent, owners)[0],
        "meaning": meaning_vote(prerequisite, dependent, meaning_cutoff)[0] if semantic else 0,
        "heading": heading_vote(prerequisite, dependent)[0],
        "order": order_vote(prerequisite, dependent, positions)[0],
    }
    return {clue: 0 if clue in without else vote for clue, vote in votes.items()}


def decide_pairs(concepts, runtime_instance=None, calibration=None, embed=None, without=()):
    """Every pair the text links: accepted when nothing contradicts it, pending otherwise.

    ``concepts`` arrive in the topic's merged order (``concepts_for_topic``).
    ``runtime_instance`` is kept for callers and ignored. Without the encoder
    the verdicts are the same; only relatedness and meaning are not recorded.
    ``without`` silences clues, for the evaluation's ablations.
    """
    concepts = list(concepts)
    if len(concepts) < 2:
        return []
    calibration = calibration or load_calibration()
    semantic = True
    try:
        texts = prepare(concepts, embed=embed or embeddings.embed)
    except embeddings.EncoderUnavailable:
        texts, semantic = prepare(concepts), False
    owners = find_term_owners(texts)
    positions = material_positions(concepts)
    meaning_cutoff = calibration["meaning_cutoff"]

    decisions = []
    for index, first in enumerate(texts):
        for second in texts[index + 1:]:
            # A concept with no full sentence has nothing to compare (kept from v5).
            if not (first.sentences and second.sentences):
                continue
            facts, earlier, later = _facts(first, second, owners, positions, without)
            decision = reference_verdict(facts)
            if decision.verdict not in (ACCEPTED, PENDING):
                continue
            prerequisite, dependent = (earlier, later) if decision.direction > 0 else (later, earlier)
            votes = _votes(prerequisite, dependent, owners, positions, meaning_cutoff, semantic, without)
            decisions.append({
                "prerequisite": prerequisite.concept,
                "dependent": dependent.concept,
                "verdict": decision.verdict,
                "evidence": {
                    "rule": "reference-order",
                    "direction_from": decision.direction_from,
                    "contradictions": list(decision.contradictions),
                    "votes": votes,
                    "records": clue_records(prerequisite, dependent, owners, positions, meaning_cutoff, semantic),
                    "relatedness": round(relatedness(first, second), 3) if semantic else None,
                    "confidence": round(confidence(votes, 1, DECIDING_CLUES), 3),
                    "semantic": semantic,
                },
                "cross_section": crosses_sections(prerequisite.concept, dependent.concept),
            })
    return decisions
