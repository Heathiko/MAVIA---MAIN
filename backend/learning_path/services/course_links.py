"""Course-level links: storing what the criteria derive, the page's roll-up, teacher edits.

Mirrors ``publishing.refresh_prerequisites`` and ``teacher_links`` for
``CourseConceptLink``: derived rows are updated in place so ids stay stable,
and a teacher's ``approved`` or ``rejected`` is never overwritten.
"""

from collections import defaultdict

from django.db import transaction
from django.utils import timezone

from ..models import CourseConceptLink
from .concept_units import concepts_for_topic
from .course_criteria import course_topics, decide_course_pairs
from .reasons import link_reason


def refresh_course_links(course, embed=None):
    """Re-derive the course's cross-topic links, keeping every teacher decision."""
    topics = course_topics(course)
    decisions = decide_course_pairs([list(concepts_for_topic(topic)) for topic in topics], embed=embed)
    fresh = {(row["prerequisite"].id, row["dependent"].id): row for row in decisions}

    with transaction.atomic():
        existing = {
            (row.prerequisite_id, row.dependent_id): row
            for row in CourseConceptLink.objects.select_for_update().filter(course=course)
        }
        decided = {pair for pair, row in existing.items() if row.status in CourseConceptLink.TEACHER_DECIDED}
        for pair, decision in fresh.items():
            row = existing.get(pair)
            if row is None:
                row, created = CourseConceptLink.objects.get_or_create(
                    prerequisite_id=pair[0],
                    dependent_id=pair[1],
                    defaults={
                        "course": course,
                        "status": decision["verdict"],
                        "source": CourseConceptLink.Source.DERIVED,
                        "evidence": decision["evidence"],
                    },
                )
                if created:
                    continue
            if row.status in CourseConceptLink.TEACHER_DECIDED:
                row.evidence = decision["evidence"]
                row.save(update_fields=["evidence", "updated_at"])
                continue
            CourseConceptLink.objects.filter(pk=row.pk).exclude(
                status__in=CourseConceptLink.TEACHER_DECIDED,
            ).update(
                status=decision["verdict"],
                source=CourseConceptLink.Source.DERIVED,
                evidence=decision["evidence"],
                updated_at=timezone.now(),
            )
        stale = [
            row.pk for pair, row in existing.items()
            if pair not in fresh and row.status not in CourseConceptLink.TEACHER_DECIDED
        ]
        CourseConceptLink.objects.filter(pk__in=stale).exclude(
            status__in=CourseConceptLink.TEACHER_DECIDED,
        ).delete()

    counts = {"accepted": 0, "pending": 0, "teacher_decided": len(decided)}
    for pair, decision in fresh.items():
        if pair not in decided:
            counts[decision["verdict"]] += 1
    return counts


def _concept_titles(topics):
    return {concept.id: concept.title for topic in topics for concept in concepts_for_topic(topic)}


def course_path(course):
    """The Course path page: outline topics, and one arrow per pair of topics with links."""
    topics = course_topics(course, with_content=False)
    with_content = {topic.id for topic in course_topics(course)}
    position = {topic.id: index for index, topic in enumerate(topics)}
    titles = _concept_titles([topic for topic in topics if topic.id in with_content])

    arrows = defaultdict(list)
    rows = (
        CourseConceptLink.objects.filter(course=course)
        .exclude(status=CourseConceptLink.Status.REJECTED)
        .select_related("prerequisite", "dependent")
    )
    for row in rows:
        from_topic, to_topic = row.prerequisite.outline_node_id, row.dependent.outline_node_id
        if from_topic not in position or to_topic not in position:
            continue
        before = titles.get(row.prerequisite_id) or row.prerequisite.label or "Untitled concept"
        after = titles.get(row.dependent_id) or row.dependent.label or "Untitled concept"
        arrows[(from_topic, to_topic)].append({
            "id": row.id,
            "status": row.status,
            "prerequisite": {"concept_id": row.prerequisite_id, "title": before, "topic_id": from_topic},
            "dependent": {"concept_id": row.dependent_id, "title": after, "topic_id": to_topic},
            "reason": link_reason(row.evidence, before, after),
            "contradicts_outline": position[from_topic] > position[to_topic],
        })

    return {
        "course": {"id": course.id, "title": course.title},
        "topics": [
            {"id": topic.id, "title": topic.title, "position": position[topic.id], "has_content": topic.id in with_content}
            for topic in topics
        ],
        "arrows": [
            {
                "from_topic": from_topic,
                "to_topic": to_topic,
                "contradicts_outline": position[from_topic] > position[to_topic],
                "shaping": sum(1 for link in links if link["status"] in CourseConceptLink.SHAPES_PATH),
                "pending": sum(1 for link in links if link["status"] == CourseConceptLink.Status.PENDING),
                "links": sorted(links, key=lambda link: link["id"]),
            }
            for (from_topic, to_topic), links in sorted(arrows.items(), key=lambda item: (position[item[0][0]], position[item[0][1]]))
        ],
    }
