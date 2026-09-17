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
from .concept_units import concepts_for_topic
from .text_signals import part_marker, strip_part_suffix


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


def _normal_audio_lookup(material):
    """{narration_item_order: audio_url} for one material's already-generated
    playlist (see ``lessons/services/audio_generator.py``) -- the same TTS
    pipeline legacy-mode lesson tracks use. There is no explicit FK from a
    LearningObject to its playlist entry, but both are built 1:1, in order,
    from the same narration script at ingestion, so a LearningObject's
    0-indexed ``order`` lines up with the (1-indexed) ``narration_item_order``
    on its playlist entry -- see ``_versions`` below."""
    generated_json = material.generated_json or {}
    return {
        item.get("narration_item_order"): item.get("audio_url") or ""
        for item in generated_json.get("lesson_playlist", [])
        if item.get("narration_item_order") is not None and item.get("audio_url")
    }


def _passage_parts(anchor, members):
    """The whole split passage ``anchor`` belongs to, in reading order.

    The chunker cuts an oversized passage into "(Part 1 of 2)" pieces, and
    ``concept_units`` merges those pieces back into one concept -- but a
    ``LearningPathStep`` only records the first piece's group. Reading just
    that group lost every later part: its narration never reached the student,
    and when question generation happened to put the concept's questions on a
    later part, the step had none and the engine skipped the concept outright.

    Parts are taken from the concept's own members, same material and same
    passage title, split into runs wherever the numbering restarts at 1, so a
    file carrying several passages that share one title ("Diagram description
    (Part 1 of 2)" under each state of matter) never fuses them. A chunk that
    was never split is its own single part.
    """
    marker = part_marker(anchor.title)
    if not marker:
        return [anchor]
    base, _number, total = marker
    candidates = []
    for member in members:
        member_marker = part_marker(member.title)
        if (
            member_marker
            and member.material_id == anchor.material_id
            and member_marker[0].casefold() == base.casefold()
            and member_marker[2] == total
        ):
            candidates.append((member.order, member_marker[1], member))
    candidates.sort(key=lambda entry: entry[0])

    runs, current = [], []
    for _order, number, member in candidates:
        if number == 1 and current:
            runs.append(current)
            current = []
        current.append((number, member))
    if current:
        runs.append(current)
    for run in runs:
        if any(member.id == anchor.id for _number, member in run):
            return [member for _number, member in sorted(run, key=lambda entry: entry[0])]
    return [anchor]


def _chunk_title(parts):
    """A split passage is one idea to the student, so it is named without the
    "(Part 1 of 2)" the chunker added."""
    title = parts[0].title or ""
    return strip_part_suffix(title) if len(parts) > 1 else title


def _versions(parts, audio_for):
    """Normal / simplified / elaborated for one telling of a concept.

    Every version carries ``parts``: one ``{text, audio_url}`` per chunk of the
    passage, in reading order, which is what a player should play. ``text`` is
    the whole passage; ``audio_url`` is kept for readers that predate ``parts``
    and is only filled when a single file really covers all of ``text``.

    A simplified or elaborated rung exists only when *every* part has one --
    a rung covering half a passage would silently skip the rest of it, so
    the player falls back to Normal instead.
    """
    rows = defaultdict(dict)
    for row in LessonVariant.objects.filter(
        learning_object__in=parts, variant__in=("SIMPLIFIED", "ELABORATED"),
    ):
        rows[row.learning_object_id][row.variant] = row

    def assemble(pieces):
        return {
            "text": "\n\n".join(piece["text"] for piece in pieces if piece["text"]),
            "audio_url": pieces[0]["audio_url"] if len(pieces) == 1 else "",
            "parts": pieces,
        }

    def slot(key):
        pieces = []
        for part in parts:
            row = rows[part.id].get(key)
            if row is None:
                return None
            pieces.append({"text": row.narration, "audio_url": row.audio_url or ""})
        return assemble(pieces)

    return {
        "normal": assemble([{"text": part.content or "", "audio_url": audio_for(part)} for part in parts]),
        "simplified": slot("SIMPLIFIED"),
        "elaborated": slot("ELABORATED"),
    }


def _questions(parts, include_answers):
    # One step, one assessment: the earliest-generated LOT question and the
    # earliest-generated HOT question, LOT first -- never more than 2, even
    # if question generation left extra final rows on this node (it isn't
    # guaranteed to cap itself at one per thinking_order). Drawn from every
    # part of the passage: generation attaches questions to whichever chunk
    # it was reading, which is often not the first.
    by_order = {}
    for question in GeneratedQuestion.objects.filter(node__in=parts, status="final").order_by("id"):
        order = question.thinking_order or "LOT"
        by_order.setdefault(order, question)

    questions = []
    for order in ("LOT", "HOT"):
        question = by_order.get(order)
        if question is None:
            continue
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

    # The same concept units publishing ordered, so a step sees every member
    # its concept really has -- including later parts of a split passage,
    # which live in groups of their own that no step points at.
    concepts = {concept.id: concept for concept in concepts_for_topic(node)}
    audio_by_material = {}

    def audio_for(learning_object):
        lookup = audio_by_material.get(learning_object.material_id)
        if lookup is None:
            lookup = audio_by_material[learning_object.material_id] = _normal_audio_lookup(
                learning_object.material
            )
        return lookup.get(learning_object.order + 1, "")

    payload_steps = []
    for step in steps:
        group = step.concept
        concept = concepts.get(group.id)
        if concept is not None:
            members = sorted(concept.members, key=lambda item: (item.material_id, item.order, item.id))
            representative = concept.representative
        else:
            # A step whose group no longer forms a concept (edited since the
            # path was published): read the group itself, as before.
            members = list(
                group.learning_objects.select_related("material").order_by("material_id", "order", "id")
            )
            representative = _representative(group, members)
        if representative is None:
            continue
        sources = {}
        for member in members:
            sources.setdefault(member.material_id, member.material.title)

        parts = _passage_parts(representative, members)
        # Independent alternates: other PDFs' own take on this concept, not
        # folded into another member's telling (`represented_by` marks that).
        # The adaptive engine's remediation ladder reaches for one of these
        # when re-explaining the representative's own text hasn't worked --
        # see adaptive/PATH_MODE.md "chunk switching". Each is a whole passage
        # too, and a later part of any passage is never an alternate of its own.
        seen = {part.id for part in parts}
        alternates = []
        for member in members:
            if member.id in seen or member.represented_by_id is not None:
                continue
            alternate_parts = _passage_parts(member, members)
            if any(part.id in seen for part in alternate_parts):
                continue
            seen.update(part.id for part in alternate_parts)
            alternates.append(alternate_parts)

        payload_steps.append({
            "position": step.position,
            "depth": step.depth,
            "concept_id": group.id,
            "title": _chunk_title(parts),
            "section_title": representative.section_title,
            "learning_object_id": representative.id,
            "sources": [{"material_id": mid, "title": title} for mid, title in sources.items()],
            "versions": _versions(parts, audio_for),
            "questions": _questions(parts, include_answers),
            "alternates": [
                {
                    "learning_object_id": alternate_parts[0].id,
                    "material_id": alternate_parts[0].material_id,
                    "material_title": alternate_parts[0].material.title,
                    "title": _chunk_title(alternate_parts),
                    "versions": _versions(alternate_parts, audio_for),
                    "questions": _questions(alternate_parts, include_answers),
                }
                for alternate_parts in alternates
            ],
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
