"""Re-derive automatic concept labels under the single-object rule.

Design 3.5 says a concept takes its bundle's heading as a name only when that
bundle holds two or more objects; a lone object keeps its own title. The
automatic labelling used the heading unconditionally, so on the live upload
Solid, Liquid and Gas -- each alone under the heading "Matter" -- were all
called "Matter", and so were Shape, Volume, Particle arrangement and Flow
("Comparing the Three States"). The criteria's same-name veto then deleted
those concepts' edges.

The fix changed the pipeline; this command repairs the rows it already wrote.
A label the teacher locked (``version_selection.label_locked``) or one this
module never claimed as its own (no matching ``auto_label``) is reported and
left alone -- it is a teacher's wording, and no repair may overwrite it.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from course.version_assignment import (
    _eligible_bundles,
    _normal_id,
    clean_group_label,
)
from lessons.models import LearningObjectGroup, OutlineNode
from lessons.services.concept_bundles import bundle_label, ordered_members


class Command(BaseCommand):
    help = "Re-derive automatic concept labels: the heading names only a bundle of 2+."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would change without writing anything.",
        )
        parser.add_argument(
            "--topic",
            type=int,
            action="append",
            dest="topics",
            help="Limit to one topic id; repeatable. Default: every topic with materials.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        topics = OutlineNode.objects.filter(materials__isnull=False).distinct()
        if options.get("topics"):
            topics = topics.filter(pk__in=options["topics"])
        topics = topics.order_by("id")

        changed = kept = locked = empty = 0
        for topic in topics:
            groups = list(
                topic.learning_object_groups.prefetch_related(
                    "learning_objects__material",
                ).order_by("id")
            )
            if not groups:
                continue
            self.stdout.write(f"\nTopic {topic.id}: {topic.title}")
            for group in groups:
                members = ordered_members(group)
                if not members:
                    empty += 1
                    self.stdout.write(f"  [empty]   #{group.id} {group.label!r}")
                    continue

                selection = group.version_selection or {}
                current = (group.label or "").strip()
                written = (selection.get("auto_label") or "").strip()

                if selection.get("label_locked"):
                    locked += 1
                    self.stdout.write(f"  [locked]  #{group.id} {current!r}")
                    continue
                if current and current.casefold() != written.casefold():
                    # Not the label this pipeline last wrote: a teacher typed it.
                    locked += 1
                    self.stdout.write(f"  [teacher] #{group.id} {current!r}")
                    continue

                bundles = _eligible_bundles(group)
                normal_id = _normal_id(group, bundles)
                bundle = bundles.get(normal_id) or next(iter(bundles.values()), members)
                label = clean_group_label(bundle_label(bundle))[:255]
                if not label or label == current:
                    kept += 1
                    continue

                changed += 1
                size = len(bundle)
                self.stdout.write(
                    self.style.WARNING(
                        f"  [fix]     #{group.id} {current!r} -> {label!r} "
                        f"(Normal bundle holds {size} object{'' if size == 1 else 's'})"
                    )
                )
                if dry_run:
                    continue
                with transaction.atomic():
                    group.label = label
                    group.version_selection = {**selection, "auto_label": label}
                    group.save(update_fields=["label", "version_selection"])

        summary = (
            f"\n{changed} label(s) {'would be ' if dry_run else ''}corrected, "
            f"{kept} already correct, {locked} left to the teacher, "
            f"{empty} empty concept(s) skipped."
        )
        self.stdout.write(self.style.SUCCESS(summary))
        if dry_run:
            self.stdout.write("Dry run: nothing was written.")
