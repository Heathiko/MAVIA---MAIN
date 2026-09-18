"""Merge several learning objects of one PDF into one row, and split them back.

One PDF may teach a concept as four short items ("Shape", "Volume", ...) while
another teaches it as one section. Grouping admits one object per PDF, and
everything downstream -- version assignment, audio, the mobile package -- keys
on a concept's single representative row. Merging the items into one row keeps
all of that working unchanged.

The merge is reversible. The kept row stores a snapshot of every original
member, so "Split back" restores them with their original metadata ids, order
and question links. Hidden rows were rejected: every module that queries
learning objects would have to learn to skip them.
"""

import uuid

from django.db import transaction
from django.db.models import F

from course.models import LessonVariant
from course.version_assignment import release_from_group
from question_generation.models import GeneratedQuestion

from ..models import (
    LearningObject,
    LearningObjectGroup,
    OutlineNode,
    Question,
    QuestionLearningObjectLink,
)

SNAPSHOT_FIELDS = (
    "title", "content", "kind", "order", "section_title", "source_page",
    "source_block_id", "source_excerpt", "image_url", "image_prompt",
)


class MergeError(ValueError):
    """A merge or split the teacher asked for that cannot be carried out."""


def merge_text(members):
    """The merged content: each member's title as a lead-in, in the given order."""
    return "\n".join(
        f"{item.title}: {item.content}".strip() for item in members
    )


def _connected_elsewhere(item):
    return bool(
        item.group_id
        and LearningObject.objects.filter(group_id=item.group_id).exclude(pk=item.pk).exists()
    )


def choose_kept_row(members):
    """The row that survives: the one already connected to other objects, if any.

    Keeping that row keeps its group, so the other PDFs' versions of the concept
    stay attached. Two such rows would mean two different concepts.
    """
    connected = [item for item in members if _connected_elsewhere(item)]
    if len(connected) > 1:
        raise MergeError(
            "More than one of these objects is already connected to other objects. "
            "Separate them first."
        )
    if connected:
        return connected[0]
    return min(members, key=lambda item: (item.order, item.id))


def _renumber(material):
    for index, item in enumerate(material.learning_objects.order_by("order", "id")):
        if item.order != index:
            LearningObject.objects.filter(pk=item.pk).update(order=index)


def _drop_playlist_entries(material, object_ids):
    data = dict(material.generated_json or {})
    playlist = data.get("lesson_playlist") or []
    kept_entries = [entry for entry in playlist if entry.get("learning_object_id") not in object_ids]
    if len(kept_entries) != len(playlist):
        data["lesson_playlist"] = kept_entries
        material.generated_json = data
        material.save(update_fields=["generated_json"])


def _remove_empty_groups(node_id):
    LearningObjectGroup.objects.filter(
        outline_node_id=node_id, learning_objects__isnull=True,
    ).delete()


def _unpublish(node_id):
    # Read the flag from the database: callers hold cached topic instances.
    if node_id is None:
        return False
    return bool(
        OutlineNode.objects.filter(pk=node_id, published=True)
        .update(published=False, published_at=None)
    )


def _snapshot(item):
    return {
        "id": item.id,
        "metadata_id": str(item.metadata_id),
        **{name: getattr(item, name) for name in SNAPSHOT_FIELDS},
        "question_links": [
            {
                "id": link.id,
                "question_id": link.question_id,
                "relevance_score": link.relevance_score,
                "method": link.method,
                "is_primary": link.is_primary,
                "review_status": link.review_status,
            }
            for link in QuestionLearningObjectLink.objects.filter(learning_object=item)
        ],
        "generated_question_ids": list(
            GeneratedQuestion.objects.filter(node=item).values_list("id", flat=True)
        ),
    }


def _move_links(source, kept):
    for link in QuestionLearningObjectLink.objects.filter(learning_object=source):
        duplicate = QuestionLearningObjectLink.objects.filter(
            question_id=link.question_id, learning_object=kept,
        ).first()
        if duplicate is None:
            link.learning_object = kept
            link.save(update_fields=["learning_object"])
            continue
        promote = link.is_primary and not duplicate.is_primary
        link.delete()
        if promote:
            duplicate.is_primary = True
            duplicate.save(update_fields=["is_primary"])
    GeneratedQuestion.objects.filter(node=source).update(node=kept)


@transaction.atomic
def merge_learning_objects(members, *, title=None):
    """Merge ``members`` (one PDF) into one row. Returns ``(kept, unpublished)``."""
    members = sorted(members, key=lambda item: (item.order, item.id))
    if len(members) < 2:
        raise MergeError("Select at least two learning objects to merge.")
    if len({item.material_id for item in members}) != 1:
        raise MergeError("Only objects from the same PDF can be merged into one.")
    if any(item.merged_from for item in members):
        raise MergeError("Split an already merged object back before merging it again.")

    kept = choose_kept_row(members)
    material = kept.material
    first = members[0]
    snapshot = [_snapshot(item) for item in members]
    others = [item for item in members if item.pk != kept.pk]
    member_ids = [item.id for item in members]

    for item in others:
        _move_links(item, kept)
    LessonVariant.objects.filter(learning_object_id__in=member_ids).delete()
    LessonVariant.objects.filter(source_learning_object_id__in=member_ids).delete()

    # The heading names the concept, but the earliest member need not carry it:
    # a figure extracted ahead of the text has no section at all, and taking its
    # empty heading would title the merged row with the figure's narration. The
    # learning path names concepts from this title, so take the first heading
    # any member actually has, in document order.
    heading = next((item.section_title for item in members if item.section_title), "")
    kept.content = merge_text(members)
    kept.title = (title or heading or first.title)[:255]
    kept.kind = LearningObject.Kind.TEXT
    kept.order = first.order
    kept.section_title = heading
    kept.image_url = ""
    # Version assignment re-decides which object a concept is taught through
    # after the merge, and the variants the old representative supplied were
    # just deleted -- a stale marker only makes the versions screen send the
    # teacher to a row that no longer teaches this.
    kept.represented_by = None
    kept.merged_from = snapshot
    kept.mark_grouping_current()
    kept.save()
    if kept.group_id:
        # The stored representative may have been one of the deleted rows, but a
        # teacher's locked label is their decision and survives the merge; an
        # unlocked label still shows the pre-merge title, so follow the merge.
        group = LearningObjectGroup.objects.filter(pk=kept.group_id).first()
        if group is not None:
            locked = bool((group.version_selection or {}).get("label_locked"))
            group.version_selection = {"label_locked": True} if locked else {}
            if not locked:
                group.label = kept.title[:255]
            group.save(update_fields=["version_selection", "label"])

    LearningObject.objects.filter(pk__in=[item.pk for item in others]).delete()
    _renumber(material)
    _drop_playlist_entries(material, member_ids)
    _remove_empty_groups(material.outline_node_id)
    kept.refresh_from_db()
    return kept, _unpublish(material.outline_node_id)


@transaction.atomic
def split_learning_object(learning_object):
    """Rebuild a merged row's originals. Returns ``(rows, unpublished)``."""
    kept = learning_object
    snapshot = list(kept.merged_from or [])
    if not snapshot:
        raise MergeError("This learning object was not created by a merge.")
    material = kept.material
    base = kept.order

    LearningObject.objects.filter(material=material, order__gt=base).update(
        order=F("order") + len(snapshot) - 1,
    )
    if kept.group_id:
        companions = list(LearningObject.objects.filter(group_id=kept.group_id).exclude(pk=kept.pk))
        release_from_group(kept, companions)
        LearningObjectGroup.objects.filter(pk=kept.group_id).update(version_selection={})
    LessonVariant.objects.filter(learning_object=kept).delete()
    LessonVariant.objects.filter(source_learning_object=kept).delete()
    _drop_playlist_entries(material, [kept.id])

    restored = []
    for index, entry in enumerate(snapshot):
        row = kept if entry["id"] == kept.id else LearningObject(
            material=material, metadata_id=uuid.UUID(entry["metadata_id"]),
        )
        for name in SNAPSHOT_FIELDS:
            setattr(row, name, entry[name])
        row.order = base + index
        row.group = None
        row.represented_by = None
        row.merged_from = []
        row.grouping_content_hash = ""
        row.save()
        restored.append((entry, row))

    for entry, row in restored:
        if row.pk != kept.pk:
            GeneratedQuestion.objects.filter(
                pk__in=entry["generated_question_ids"], node=kept,
            ).update(node=row)
        for link in entry["question_links"]:
            if not Question.objects.filter(pk=link["question_id"]).exists():
                continue
            existing = QuestionLearningObjectLink.objects.filter(pk=link["id"]).first()
            if existing is not None:
                if existing.learning_object_id != row.id:
                    existing.learning_object = row
                    existing.is_primary = False
                    existing.save(update_fields=["learning_object", "is_primary"])
            elif not QuestionLearningObjectLink.objects.filter(
                question_id=link["question_id"], learning_object=row,
            ).exists():
                QuestionLearningObjectLink.objects.create(
                    question_id=link["question_id"], learning_object=row,
                    relevance_score=link["relevance_score"], method=link["method"],
                    is_primary=False, review_status=link["review_status"],
                )

    # Primary flags last: at most one primary per question at any moment.
    for entry, row in restored:
        for link in entry["question_links"]:
            QuestionLearningObjectLink.objects.filter(
                question_id=link["question_id"], learning_object=row,
            ).update(is_primary=False)
    for entry, row in restored:
        for link in entry["question_links"]:
            if link["is_primary"]:
                QuestionLearningObjectLink.objects.filter(
                    question_id=link["question_id"],
                ).update(is_primary=False)
                QuestionLearningObjectLink.objects.filter(
                    question_id=link["question_id"], learning_object=row,
                ).update(is_primary=True)

    _remove_empty_groups(material.outline_node_id)
    return [row for _, row in restored], _unpublish(material.outline_node_id)
