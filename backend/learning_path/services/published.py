"""Read a topic's published learning path -- the contract for the adaptive rules.

``get_published_path`` is the single source of truth. Python code in this
backend calls it directly; anything else (a student app, a frontend) reads the
same data from ``GET /api/learning-path/topics/<id>/published/``, which only
wraps it. Keeping one function behind both means the database layout can change
without breaking either reader, as long as the returned shape stays the same.

See ``learning_path/HANDOFF.md`` for the shape and how to use it.
"""

from collections import defaultdict

from course.models import LessonVariant
from course.version_assignment import assign_group_versions
from question_generation.models import GeneratedQuestion

from ..models import ConceptPrerequisite, LearningPathStep


def _representative(group, members):
    """The member whose text is the concept's Normal version."""
    try:
        representative_id = assign_group_versions(group).get("representative_id")
    except Exception:  # noqa: BLE001 -- a readable path beats a failed request
        representative_id = None
    by_id = {member.id: member for member in members}
    if representative_id in by_id:
        return by_id[representative_id]
    return next((m for m in members if m.represented_by_id is None), members[0] if members else None)


def _versions(representative):
    rows = {
        row.variant: row
        for row in LessonVariant.objects.filter(
            learning_object=representative, variant__in=("SIMPLIFIED", "ELABORATED"),
        )
    }

    def slot(key):
        row = rows.get(key)
        return {"text": row.narration, "audio_url": row.audio_url or ""} if row else None

    return {
        "normal": {"text": representative.content or "", "audio_url": ""},
        "simplified": slot("SIMPLIFIED"),
        "elaborated": slot("ELABORATED"),
    }


def _questions(representative, include_answers):
    questions = []
    for question in GeneratedQuestion.objects.filter(node=representative, status="final").order_by("id"):
        entry = {
            "id": question.id,
            "text": question.question_text,
            "format": question.question_format,
            "choices": question.choices,
            "bloom_level": question.bloom_level,
            "thinking_order": question.thinking_order,
            "difficulty": question.difficulty,
            "category": question.category,
        }
        if include_answers:
            entry["correct_answer"] = question.correct_answer
            entry["explanation"] = question.explanation
        questions.append(entry)
    return questions


def get_published_path(node, *, include_answers=True):
    """The topic's saved learning path, or ``None`` if it was never published.

    ``include_answers`` adds each question's correct answer and explanation.
    Server-side rules need them; anything sent to a student's device should not
    have them.
    """
    steps = list(
        LearningPathStep.objects.filter(outline_node=node)
        .select_related("concept")
        .order_by("position")
    )
    if not steps:
        return None

    concept_ids = {step.concept_id for step in steps}
    position_of = {step.concept_id: step.position for step in steps}
    needs, leads = defaultdict(list), defaultdict(list)
    for row in ConceptPrerequisite.objects.filter(
        outline_node=node,
        status__in=ConceptPrerequisite.SHAPES_PATH,
        prerequisite_id__in=concept_ids,
        dependent_id__in=concept_ids,
    ):
        needs[row.dependent_id].append(row.prerequisite_id)
        leads[row.prerequisite_id].append(row.dependent_id)

    payload_steps = []
    for step in steps:
        group = step.concept
        members = list(group.learning_objects.select_related("material").order_by("material_id", "order", "id"))
        representative = _representative(group, members)
        if representative is None:
            continue
        sources = {}
        for member in members:
            sources.setdefault(member.material_id, member.material.title)
        payload_steps.append({
            "position": step.position,
            "depth": step.depth,
            "concept_id": group.id,
            "title": representative.title,
            "section_title": representative.section_title,
            "learning_object_id": representative.id,
            "sources": [{"material_id": mid, "title": title} for mid, title in sources.items()],
            "versions": _versions(representative),
            "questions": _questions(representative, include_answers),
            "prerequisites": sorted(needs[group.id], key=position_of.get),
            "leads_to": sorted(leads[group.id], key=position_of.get),
        })

    return {
        "topic": {"id": node.id, "title": node.title},
        "published": node.published,
        "published_at": steps[0].published_at.isoformat(),
        "includes_answers": include_answers,
        "steps": payload_steps,
    }
