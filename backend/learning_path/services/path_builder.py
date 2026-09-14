"""The topic's learning path as the review screen previews it.

The preview uses the same ordering the publish step saves
(``publishing.order_with_links``) over the links already stored -- ``accepted``
from the last publish and anything a teacher ``approved`` -- so what a teacher
reviews before publishing is what the saved path will look like. It never runs
the criteria itself: deriving links calls the sentence encoder, which is too
slow for a page load and happens at publish instead.
"""

from lessons.models import OutlineNode

from ..models import ConceptPrerequisite, LearningPathStep
from .concept_units import concepts_for_topic
from .publishing import order_with_links, path_links
from .teacher_links import changed_since_publish


def build_topic_path(node_id):
    node = OutlineNode.objects.get(pk=node_id)
    concepts = concepts_for_topic(node)
    concept_ids = {concept.id for concept in concepts}
    links = path_links(node, concept_ids)
    ordered, depth, ignored = order_with_links(concepts, links)

    document_index = {concept.id: index for index, concept in enumerate(concepts)}
    object_id = {concept.id: concept.representative.id for concept in concepts}
    title = {concept.id: concept.title for concept in concepts}
    prerequisites = {concept.id: [] for concept in concepts}
    for before, after in links:
        prerequisites[after].append(before)

    # Every stored link between live concepts, split by what the teacher sees:
    # links shaping the order are shown on the step; pending ones are offered as
    # suggestions, collapsed; rejected ones are not shown at all.
    link_rows = list(ConceptPrerequisite.objects.filter(
        outline_node=node, prerequisite_id__in=concept_ids, dependent_id__in=concept_ids,
    ))
    shown = {concept.id: [] for concept in concepts}
    suggested = {concept.id: [] for concept in concepts}
    order_index = {concept.id: index for index, concept in enumerate(ordered)}
    for row in sorted(link_rows, key=lambda r: order_index[r.prerequisite_id]):
        entry = {
            "link_id": row.id,
            "concept_id": row.prerequisite_id,
            "title": title[row.prerequisite_id],
            "status": row.status,
            "cross_section": row.cross_section,
        }
        if row.status in ConceptPrerequisite.SHAPES_PATH:
            shown[row.dependent_id].append(entry)
        elif row.status == ConceptPrerequisite.Status.PENDING:
            suggested[row.dependent_id].append(entry)

    steps = []
    for position, concept in enumerate(ordered, start=1):
        steps.append({
            "prerequisites": shown[concept.id],
            "suggestions": suggested[concept.id],
            "position": position,
            "concept_id": concept.id,
            # The representative's id: the review screen keys steps and
            # prerequisite references by learning object.
            "learning_object_id": object_id[concept.id],
            "title": concept.title,
            "section_title": concept.section_title,
            "kind": concept.kind,
            "content": concept.content,
            "source_material_ids": concept.source_material_ids,
            "source_count": len(concept.members),
            "source_order": document_index[concept.id],
            "dag_depth": depth[concept.id],
            "prerequisite_ids": sorted(object_id[cid] for cid in prerequisites[concept.id]),
            "prerequisite_count": len(prerequisites[concept.id]),
        })

    rows = ConceptPrerequisite.objects.filter(
        outline_node=node,
        status__in=ConceptPrerequisite.SHAPES_PATH,
        prerequisite_id__in=concept_ids,
        dependent_id__in=concept_ids,
    )
    edges = [
        {
            "id": row.id,
            "prerequisite_id": object_id[row.prerequisite_id],
            "prerequisite_title": title[row.prerequisite_id],
            "dependent_id": object_id[row.dependent_id],
            "dependent_title": title[row.dependent_id],
            "signal_label": row.get_status_display(),
            "status": row.status,
            "weight": 1.0,
            "evidence": row.evidence,
        }
        for row in rows
    ]

    material_ids = sorted({mid for concept in concepts for mid in concept.source_material_ids})
    return {
        "topic_id": node.id,
        "topic_title": node.title,
        "learning_path": [concept.id for concept in ordered],
        "steps": steps,
        "edges": edges,
        "diagnostics": {
            # "document_order" until a link exists: then the order is the
            # documents' own, adjusted only where a link requires it.
            "ordering": "prerequisite_links" if links else "document_order",
            "concept_count": len(concepts),
            "material_count": len(material_ids),
            "material_ids": material_ids,
            "multi_source_concept_count": sum(
                1 for concept in concepts if len(concept.source_material_ids) > 1
            ),
            "edge_count": len(links),
            "displaced_object_count": sum(
                1 for index, concept in enumerate(ordered) if concepts[index].id != concept.id
            ),
            "ignored_links": [[title[a], title[b]] for a, b in ignored],
            "published_at": (
                LearningPathStep.objects.filter(outline_node=node)
                .order_by("-published_at").values_list("published_at", flat=True).first()
            ),
            # A teacher changed links after the path was last saved: students
            # still follow the old one until the topic is published again.
            "changed_since_publish": changed_since_publish(node),
        },
    }
