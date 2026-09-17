"""Propose merging several objects of one PDF that another PDF teaches as one.

Measured on topic 62 before this was written: the cross-encoder scored nearly
every item of one PDF between 0.5 and 0.65 against every section of the other,
so scores cannot find these units. Document structure finds candidates -- runs
of consecutive objects under one heading -- but on its own it over-merges: a
"Matter" section may hold Matter, Solid, Liquid and Gas. A unit is therefore
proposed only when the *other* PDF names it with a matching heading or title,
the cross-encoder confirms at the review threshold, and the teacher accepts.
"""

from collections import defaultdict
from dataclasses import dataclass

from ..models import LearningObject, LearningObjectMatchSuggestion
from .learning_resource_linker import normalize_learning_object_title
from .object_merge import choose_kept_row, merge_text
from . import semantic_grouping

METHOD = "heading_unit_v1"


def heading_key(text):
    """A heading or title reduced to what two PDFs would share."""
    return semantic_grouping._singular_label(normalize_learning_object_title(text or ""))


@dataclass(frozen=True)
class Unit:
    label: str
    members: tuple

    @property
    def material_id(self):
        return self.members[0].material_id

    @property
    def ids(self):
        return [item.id for item in self.members]


def find_units(objects):
    """Runs of two or more consecutive objects under one heading.

    A run continues while the next object sits under the same section heading,
    or carries that heading as its own title -- extraction sometimes drops the
    section of a figure ("5. Comparing the Three States") but keeps its title.
    """
    ordered = sorted(objects, key=lambda item: (item.order, item.id))
    units, index = [], 0
    while index < len(ordered):
        first = ordered[index]
        label = heading_key(first.section_title) or heading_key(first.title)
        end = index + 1
        while label and end < len(ordered) and label in (
            heading_key(ordered[end].section_title),
            heading_key(ordered[end].title),
        ):
            end += 1
        if end - index >= 2:
            units.append(Unit(label, tuple(ordered[index:end])))
            index = end
        else:
            index += 1
    return units


def _agrees_across_pdfs(unit):
    """Two or more members already connected to other PDFs: they agree at a finer grain."""
    connected = [
        item for item in unit.members
        if item.group_id and LearningObject.objects.filter(group_id=item.group_id)
        .exclude(material_id=item.material_id).exists()
    ]
    return len(connected) >= 2


def heading_unit_candidates(node):
    """``[{"label", "left": [...], "right": [...]}]`` -- unit pairs worth scoring."""
    objects = list(
        LearningObject.objects.filter(
            material__outline_node=node,
            material__generated_json__learning_objects_confirmed=True,
        ).select_related("material")
    )
    by_material = defaultdict(list)
    for item in objects:
        by_material[item.material_id].append(item)
    all_units = {material_id: find_units(rows) for material_id, rows in by_material.items()}
    open_units = {
        material_id: [unit for unit in units if not _agrees_across_pdfs(unit)]
        for material_id, units in all_units.items()
    }

    candidates, seen = [], set()
    for left_id, units in open_units.items():
        for right_id, rows in by_material.items():
            if right_id == left_id:
                continue
            for unit in units:
                same_label_members = {
                    item.id for other in all_units[right_id] if other.label == unit.label
                    for item in other.members
                }
                singles = [
                    item for item in rows
                    if heading_key(item.title) == unit.label and item.id not in same_label_members
                ]
                others = [other for other in open_units[right_id] if other.label == unit.label]
                if len(singles) + len(others) != 1:
                    continue
                right = list(others[0].members) if others else singles
                pair = frozenset((*unit.ids, *(item.id for item in right)))
                if pair in seen:
                    continue
                seen.add(pair)
                left, right_rows = (list(unit.members), right)
                if left_id > right_id:
                    left, right_rows = right_rows, left
                candidates.append({"label": unit.label, "left": left, "right": right_rows})
    return candidates


def refresh_heading_unit_suggestions(node, runtime_instance=None):
    """Create or refresh pending unit suggestions for this topic. Never merges."""
    engine = runtime_instance or semantic_grouping.runtime()
    threshold = semantic_grouping.policy()["review_threshold"]
    created = 0
    for candidate in heading_unit_candidates(node):
        left, right = candidate["left"], candidate["right"]
        try:
            kept_left, kept_right = choose_kept_row(left), choose_kept_row(right)
            score = engine.pair_scores([(merge_text(left), merge_text(right))])[0]
        except Exception:  # noqa: BLE001 -- MergeError or model limits: no suggestion
            continue
        if score < threshold:
            continue
        source, candidate_row = (kept_left, kept_right) if kept_left.id < kept_right.id else (kept_right, kept_left)
        source_side, candidate_side = (left, right) if source is kept_left else (right, left)
        source_extra = sorted(item.id for item in source_side if item.id != source.id)
        candidate_extra = sorted(item.id for item in candidate_side if item.id != candidate_row.id)

        existing = LearningObjectMatchSuggestion.objects.filter(
            source_learning_object=source, candidate_learning_object=candidate_row,
        ).first()
        if (
            existing
            and existing.status == LearningObjectMatchSuggestion.Status.REJECTED
            and existing.source_extra_ids == source_extra
            and existing.candidate_extra_ids == candidate_extra
        ):
            continue
        LearningObjectMatchSuggestion.objects.update_or_create(
            source_learning_object=source,
            candidate_learning_object=candidate_row,
            defaults={
                "outline_node": node,
                "similarity_score": round(score, 6),
                "confidence": LearningObjectMatchSuggestion.Confidence.MEDIUM,
                "status": LearningObjectMatchSuggestion.Status.PENDING,
                "source_extra_ids": source_extra,
                "candidate_extra_ids": candidate_extra,
                "evidence": {
                    "method": METHOD,
                    "label": candidate["label"],
                    "score": round(score, 6),
                    "source_ids": [item.id for item in source_side],
                    "candidate_ids": [item.id for item in candidate_side],
                    "title_used": True,
                },
            },
        )
        created += 1
    return created
