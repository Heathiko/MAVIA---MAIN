"""Deciding a link from two evidence families (spec amendment 1).

What the text says (name, terms, meaning) and how the author organised it
(heading, PDF order) fail for different reasons, so a link is trusted when the
two agree -- the multi-view idea of co-training (Blum & Mitchell 1998). The
three content clues all measure mentions, so they count once, as a family.
Structure alone is at most a suggestion for the teacher (spec amendment 2).
"""

import math

CONTENT_CLUES = ("name", "terms", "meaning")
STRUCTURE_CLUES = ("heading", "order")
CLUES = CONTENT_CLUES + STRUCTURE_CLUES

ACCEPTED = "accepted"
PENDING = "pending"
PARALLEL = "parallel"

MAX_AGREEMENT = 0.95


def family_direction(votes, family):
    total = sum(votes[clue] for clue in family)
    return (total > 0) - (total < 0)


def verdict(votes, semantic=True):
    """``(verdict, direction)``; direction +1 means "first before second"."""
    content = family_direction(votes, CONTENT_CLUES)
    structure = family_direction(votes, STRUCTURE_CLUES)
    if not content:
        # The text is silent. Several PDFs agreeing on the order is still worth a
        # suggestion -- a process (pollination, then fertilization) is told by the
        # lesson's sequence, not its wording -- but never a link on its own, and
        # never between siblings (amendment 2).
        if votes["order"] and votes["order"] == structure and not votes.get("parallel"):
            return PENDING, structure
        return PARALLEL, 0
    if structure == -content:
        return PENDING, structure
    if votes.get("parallel"):
        return PENDING, content
    unanimous = all(votes[clue] == content for clue in CONTENT_CLUES)
    if semantic and (structure == content or unanimous):
        return ACCEPTED, content
    return PENDING, content


def confidence(votes, direction):
    """Share of the clues that voted which agree with ``direction``."""
    voting = [clue for clue in CLUES if votes[clue]]
    if not voting or not direction:
        return 0.0
    return sum(1 for clue in voting if votes[clue] == direction) / len(voting)


def _log_odds(agreement):
    if agreement <= 0.5:
        return 0.0
    agreement = min(agreement, MAX_AGREEMENT)
    return math.log(agreement / (1 - agreement))


def learn_weights(vote_rows):
    """``(weights, agreement)`` per clue, from agreement with the other clues' majority.

    Reported by the calibration, not used for verdicts: weights cannot correct
    errors the content clues share (measured on gold 62/152, 2026-09-30).
    """
    agreement = {}
    for clue in CLUES:
        agreeing = counted = 0
        for votes in vote_rows:
            if not votes[clue]:
                continue
            others = sum(votes[other] for other in CLUES if other != clue)
            if not others:
                continue
            counted += 1
            agreeing += (votes[clue] > 0) == (others > 0)
        agreement[clue] = agreeing / counted if counted else 0.5
    return {clue: _log_odds(agreement[clue]) for clue in CLUES}, agreement
