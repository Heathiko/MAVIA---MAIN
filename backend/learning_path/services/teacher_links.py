"""A teacher adding, approving or removing prerequisite links on the review screen.

Three rules, agreed for this screen:

* **Changes reach students only at the next publish.** They are stored at once
  and the review preview follows them immediately, but the saved path is
  replaced only by a successful publish.
* **Removing a link rejects it.** A rejected pair is never proposed again by the
  criteria; a teacher can still add it back by hand.
* **A change that would create a loop is refused**, naming the concepts caught
  in it, so the path can always be produced.
"""

from django.utils import timezone

from lessons.models import LearningObjectGroup

from ..models import ConceptPrerequisite, LearningPathStep


class LinkError(ValueError):
    """A teacher change that cannot be applied, with a message fit to show them."""


def _group(node, concept_id):
    group = LearningObjectGroup.objects.filter(pk=concept_id, outline_node=node).first()
    if group is None:
        raise LinkError("That concept is not part of this topic.")
    return group


def _loop_through(node, prerequisite, dependent, ignore_id=None):
    """Concept ids forming a loop if ``prerequisite -> dependent`` were added, else None."""
    successors = {}
    rows = ConceptPrerequisite.objects.filter(
        outline_node=node, status__in=ConceptPrerequisite.SHAPES_PATH,
    )
    if ignore_id is not None:
        rows = rows.exclude(pk=ignore_id)
    for row in rows:
        successors.setdefault(row.prerequisite_id, []).append(row.dependent_id)

    # A loop exists if the dependent already leads back to the prerequisite.
    trail = {dependent.id: None}
    stack = [dependent.id]
    while stack:
        current = stack.pop()
        if current == prerequisite.id:
            chain, step = [], current
            while step is not None:
                chain.append(step)
                step = trail[step]
            return list(reversed(chain))
        for following in successors.get(current, []):
            if following not in trail:
                trail[following] = current
                stack.append(following)
    return None


def _refuse_loop(node, prerequisite, dependent, ignore_id=None):
    chain = _loop_through(node, prerequisite, dependent, ignore_id)
    if chain:
        labels = {
            group.id: group.learning_objects.order_by("material_id", "order").values_list("title", flat=True).first()
            or group.label
            for group in LearningObjectGroup.objects.filter(pk__in=chain)
        }
        # The new link runs prerequisite -> dependent; the chain already runs
        # dependent -> ... -> prerequisite, which closes the loop.
        route = " → ".join(labels[cid] for cid in [prerequisite.id, *chain])
        raise LinkError(
            f"That would make a loop: {route}. Remove one of those links first."
        )


def add_link(node, prerequisite_id, dependent_id):
    """``dependent`` needs ``prerequisite`` first, by a teacher's decision."""
    prerequisite = _group(node, prerequisite_id)
    dependent = _group(node, dependent_id)
    if prerequisite.id == dependent.id:
        raise LinkError("A concept cannot be its own prerequisite.")

    existing = ConceptPrerequisite.objects.filter(prerequisite=prerequisite, dependent=dependent).first()
    _refuse_loop(node, prerequisite, dependent, ignore_id=existing.id if existing else None)

    row, _ = ConceptPrerequisite.objects.update_or_create(
        prerequisite=prerequisite,
        dependent=dependent,
        defaults={
            "outline_node": node,
            "status": ConceptPrerequisite.Status.APPROVED,
            "source": ConceptPrerequisite.Source.TEACHER,
            "decided_at": timezone.now(),
        },
    )
    return row


def decide_link(node, link_id, status):
    """Approve a suggestion, or reject (remove) any link."""
    if status not in ConceptPrerequisite.TEACHER_DECIDED:
        raise LinkError("Choose approve or reject.")
    row = ConceptPrerequisite.objects.filter(pk=link_id, outline_node=node).select_related(
        "prerequisite", "dependent",
    ).first()
    if row is None:
        raise LinkError("That link no longer exists. Refresh the page.")
    if status == ConceptPrerequisite.Status.APPROVED:
        _refuse_loop(node, row.prerequisite, row.dependent, ignore_id=row.id)

    row.status = status
    row.source = ConceptPrerequisite.Source.TEACHER
    row.decided_at = timezone.now()
    row.save(update_fields=["status", "source", "decided_at", "updated_at"])
    return row


def changed_since_publish(node):
    """True when a teacher decided a link after the path was last saved."""
    step = LearningPathStep.objects.filter(outline_node=node).order_by("-published_at").first()
    if step is None:
        return False
    return ConceptPrerequisite.objects.filter(
        outline_node=node, decided_at__gt=step.published_at,
    ).exists()
