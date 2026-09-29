"""Combining the clues into one confidence and verdict (spec section 7).

Weights come from how often each clue agrees with the others -- log-odds
weighting of independent voters (Dawid & Skene 1979) -- so no answer key is
read and nothing is fitted to one lesson.
"""

import math

CLUES = ("name", "terms", "meaning", "order")
CONTENT_CLUES = ("name", "terms", "meaning")

ACCEPTED = "accepted"
PENDING = "pending"
PARALLEL = "parallel"

ACCEPT_CONFIDENCE = 0.5
MIN_SUPPORTING_CLUES = 2
MAX_AGREEMENT = 0.95


def _log_odds(agreement):
    if agreement <= 0.5:
        return 0.0
    agreement = min(agreement, MAX_AGREEMENT)
    return math.log(agreement / (1 - agreement))


def learn_weights(vote_rows):
    """``(weights, agreement)`` per clue, from agreement with the other clues' majority."""
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
    weights = {clue: _log_odds(agreement[clue]) for clue in CLUES}
    content = [weights[clue] for clue in CONTENT_CLUES if weights[clue] > 0]
    weights["order"] = min(weights["order"], min(content) / 2 if content else 0.0)
    return weights, agreement


def combine(votes, weights):
    """``(score, confidence)``: the sign of the score is the direction; an abstaining clue lowers confidence."""
    score = sum(weights[clue] * votes[clue] for clue in CLUES)
    total = sum(weights[clue] for clue in CLUES)
    return score, (abs(score) / total if total else 0.0)


def verdict(votes, score, confidence, semantic=True):
    """``(verdict, direction)``; direction +1 means "first before second"."""
    direction = (score > 0) - (score < 0)
    supporting = [clue for clue in CLUES if direction and votes[clue] == direction]
    if not any(clue in CONTENT_CLUES for clue in supporting):
        return PARALLEL, 0
    if semantic and confidence >= ACCEPT_CONFIDENCE and len(supporting) >= MIN_SUPPORTING_CLUES:
        return ACCEPTED, direction
    return PENDING, direction
