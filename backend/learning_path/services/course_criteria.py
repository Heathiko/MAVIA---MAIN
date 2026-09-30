"""Prerequisite links between topics of one course (the course-level path).

The topic-level v5 evidence, read across topics: relatedness gates a pair, the
name, terms and meaning clues are the content family, and the teacher's
outline order is the structure -- headings and PDF order cannot compare two
topics. See docs/superpowers/specs/2026-09-30-course-learning-path-design.md.
"""

from lessons.models import OutlineNode

from . import embeddings
from .calibration import load_calibration
from .clues import clue_records, find_term_owners, meaning_vote, name_vote, term_vote
from .concept_text import prepare
from .fusion import ACCEPTED, CONTENT_CLUES, PARALLEL, PENDING, family_direction
from .relatedness import relatedness

# The outline always votes, so one content clue -- the meaning clue is at chance
# on direction -- must not be enough to send a learner to another topic.
MIN_AGREEING_CONTENT = 2


def course_topics(course, with_content=True):
    """The course's topics in the order its outline teaches them (unit order, then topic order)."""
    nodes = {node.id: node for node in OutlineNode.objects.filter(course=course)}
    with_children = {node.parent_id for node in nodes.values() if node.parent_id}
    if with_content:
        topic_ids = set(
            OutlineNode.objects.filter(course=course, learning_object_groups__isnull=False)
            .values_list("id", flat=True)
        )
    else:
        # Leaves, plus any node holding content itself -- a PDF with no matching
        # subtopic is placed on its unit, and its links must stay visible.
        topic_ids = {node_id for node_id in nodes if node_id not in with_children} | set(
            OutlineNode.objects.filter(course=course, learning_object_groups__isnull=False)
            .values_list("id", flat=True)
        )

    def outline_position(node):
        chain = []
        while node is not None:
            chain.append((node.order, node.id))
            node = nodes.get(node.parent_id)
        return tuple(reversed(chain))

    return sorted((nodes[node_id] for node_id in topic_ids), key=outline_position)


def course_verdict(votes, semantic=True):
    """``(verdict, direction)`` for concepts of two topics; direction +1 means "first before second"."""
    content = family_direction(votes, CONTENT_CLUES)
    if not content:
        return PARALLEL, 0
    if content == -votes["outline"]:
        return PENDING, content
    agreeing = sum(1 for clue in CONTENT_CLUES if votes[clue] == content)
    against = sum(1 for clue in CONTENT_CLUES if votes[clue] == -content)
    if semantic and agreeing >= MIN_AGREEING_CONTENT and not against:
        return ACCEPTED, content
    return PENDING, content


def _decide(first, second, owners, calibration, semantic):
    """The link between ``first`` (earlier topic) and ``second`` (later topic), or ``None``."""
    if not (first.sentences and second.sentences):
        return None
    score = relatedness(first, second) if semantic else None
    if semantic and score < calibration["related_cutoff"]:
        return None
    meaning_cutoff = calibration["meaning_cutoff"]
    votes = {
        "name": name_vote(first, second)[0],
        "terms": term_vote(first, second, owners)[0],
        "meaning": meaning_vote(first, second, meaning_cutoff)[0] if semantic else 0,
        "outline": 1,
    }
    outcome, direction = course_verdict(votes, semantic)
    if outcome not in (ACCEPTED, PENDING):
        return None
    prerequisite, dependent = (first, second) if direction > 0 else (second, first)
    oriented = {clue: vote * direction for clue, vote in votes.items()}
    voting = [clue for clue in oriented if oriented[clue]]
    records = clue_records(prerequisite, dependent, owners, {}, meaning_cutoff, semantic)
    records.pop("heading", None)
    records.pop("order", None)
    return {
        "prerequisite": prerequisite.concept,
        "dependent": dependent.concept,
        "verdict": outcome,
        "evidence": {
            "rule": "course",
            "relatedness": None if score is None else round(score, 3),
            "confidence": round(sum(1 for clue in voting if oriented[clue] == 1) / len(voting), 3),
            "votes": oriented,
            "records": records,
            "contradicts_outline": direction < 0,
            "semantic": semantic,
        },
    }


def decide_course_pairs(topic_concepts, calibration=None, embed=None):
    """Every cross-topic pair the evidence accepts or sends to the teacher.

    ``topic_concepts`` lists each topic's concepts, topics in outline order.
    Term ownership is read over the two topics of a pair together, so a term a
    later topic introduces can point back at an earlier topic's concept.
    """
    calibration = calibration or load_calibration()
    concepts = [concept for topic in topic_concepts for concept in topic]
    semantic = True
    try:
        texts = prepare(concepts, embed=embed or embeddings.embed)
    except embeddings.EncoderUnavailable:
        texts, semantic = prepare(concepts), False
    by_topic, start = [], 0
    for topic in topic_concepts:
        by_topic.append(texts[start:start + len(topic)])
        start += len(topic)

    decisions = []
    for first_index, earlier in enumerate(by_topic):
        for later in by_topic[first_index + 1:]:
            owners = find_term_owners(earlier + later)
            for first in earlier:
                for second in later:
                    row = _decide(first, second, owners, calibration, semantic)
                    if row:
                        decisions.append(row)
    return decisions
