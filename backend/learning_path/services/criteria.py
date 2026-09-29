"""Prerequisite links for the learning path (criteria v5).

Two questions for each pair of concepts. Are they related? Sentence embeddings
answer that, and the answer is symmetric. Which comes first? Four clues vote --
name use, explained terms and meaning reference (what the text says), heading
containment and PDF order (how the author organised it) -- and a link is
accepted when the two families agree (spec amendment 1). Nothing here writes to the
database. See docs/superpowers/specs/2026-09-30-learning-path-evidence-fusion-design.md.
"""

from . import embeddings
from .calibration import load_calibration
from .clues import clue_records, find_term_owners, pair_votes
from .concept_text import material_positions, prepare
from .fusion import ACCEPTED, CLUES, CONTENT_CLUES, PENDING, confidence, family_direction, verdict

__all__ = ["ACCEPTED", "PENDING", "crosses_sections", "decide_pairs"]


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


def decide_pairs(concepts, runtime_instance=None, calibration=None, embed=None, without=()):
    """Every pair the evidence accepts or sends to the teacher.

    ``runtime_instance`` is kept for callers and ignored: the learning path
    loads its own encoder. Without the encoder, links are derived from the
    other clues and are never more than pending. ``without`` silences clues,
    for the evaluation's ablations.
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
    for pair in pair_votes(texts, owners, positions, calibration["related_cutoff"], meaning_cutoff, semantic):
        if not pair["related"]:
            continue
        votes = {clue: 0 if clue in without else pair["votes"][clue] for clue in CLUES}
        votes["parallel"] = pair["votes"]["parallel"]
        outcome, direction = verdict(votes, semantic)
        if outcome not in (ACCEPTED, PENDING):
            continue
        if direction > 0:
            prerequisite, dependent = pair["first"], pair["second"]
        else:
            prerequisite, dependent = pair["second"], pair["first"]
        decisions.append({
            "prerequisite": prerequisite.concept,
            "dependent": dependent.concept,
            "verdict": outcome,
            "evidence": {
                "rule": "fusion",
                "relatedness": None if pair["relatedness"] is None else round(pair["relatedness"], 3),
                "confidence": round(confidence(votes, direction), 3),
                "votes": {clue: votes[clue] * direction for clue in CLUES},
                "records": clue_records(prerequisite, dependent, owners, positions, meaning_cutoff, semantic),
                "parallel": votes["parallel"],
                "disagreement": family_direction(votes, CONTENT_CLUES) == -direction,
                "semantic": semantic,
            },
            "cross_section": crosses_sections(prerequisite.concept, dependent.concept),
        })
    return decisions
