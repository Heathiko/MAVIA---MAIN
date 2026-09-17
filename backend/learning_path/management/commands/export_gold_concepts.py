"""Build a gold learning-path fixture from a teacher's concept map.

The map lists which live learning objects make up each gold concept. Several
objects from one PDF are merged exactly as the merge service would merge them,
so the fixture holds the text the criteria will see after merging -- without
changing the live database. Run it before merging anything live: merges delete
the ids the map refers to.
"""

import json
from collections import defaultdict
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from lessons.models import LearningObject
from lessons.services.object_merge import merge_text


class Command(BaseCommand):
    help = "Export gold concepts (real lesson text) for a learning-path concept map."

    def add_arguments(self, parser):
        parser.add_argument("map_path")
        parser.add_argument("out_path")

    def handle(self, *args, map_path, out_path, **options):
        spec = json.loads(Path(map_path).read_text(encoding="utf-8"))
        ids = [object_id for concept in spec["concepts"] for object_id in concept["member_ids"]]
        objects = {item.id: item for item in LearningObject.objects.filter(id__in=ids)}
        missing = sorted(set(ids) - set(objects))
        if missing:
            raise CommandError(
                f"Learning objects not found: {missing}. Export before merging on the live database."
            )

        concepts = []
        for concept in spec["concepts"]:
            by_material = defaultdict(list)
            for object_id in concept["member_ids"]:
                by_material[objects[object_id].material_id].append(objects[object_id])
            members = []
            for material_id in sorted(by_material):
                rows = sorted(by_material[material_id], key=lambda item: (item.order, item.id))
                first = rows[0]
                members.append({
                    "title": first.title if len(rows) == 1 else concept["title"],
                    "section_title": first.section_title,
                    "content": first.content if len(rows) == 1 else merge_text(rows),
                    "material_id": material_id,
                    "order": first.order,
                })
            concepts.append({
                "key": concept["key"],
                "title": concept["title"],
                "section_title": concept.get("section_title", ""),
                "members": members,
            })

        output = {name: spec[name] for name in ("topic_id", "required", "parallel", "structural", "expected_order")}
        output["concepts"] = concepts
        Path(out_path).write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(f"Wrote {len(concepts)} concepts to {out_path}"))
