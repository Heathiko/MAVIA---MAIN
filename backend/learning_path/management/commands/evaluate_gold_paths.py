"""Print the gold report; ``--grid`` sweeps ``PRD_THRESHOLD``.

v4 has one constant. The spec fixes its range to Liang et al.'s recommended
0.02-0.1 and chooses it on topics 62 and 79 only; 152 and 308 are then read at
that value unchanged (docs/superpowers/specs/2026-09-29-learning-path-criteria-v4-design.md).
"""

import json

from django.core.management.base import BaseCommand

from learning_path.services import criteria
from learning_path.services.gold import gold_report, load_gold

GRID = (0.02, 0.05, 0.1)


class Command(BaseCommand):
    help = "Report derived learning paths against the gold standard."

    def add_arguments(self, parser):
        parser.add_argument("--grid", action="store_true")
        parser.add_argument("--topics", nargs="*", type=int, default=[62, 79])

    def _reports(self, topics):
        reports = []
        for topic_id in topics:
            data, concepts = load_gold(topic_id)
            reports.append(gold_report(data, concepts, criteria.decide_pairs(concepts)))
        return reports

    def handle(self, *args, grid=False, topics=(62, 79), **options):
        if not grid:
            self.stdout.write(json.dumps(self._reports(topics), indent=2))
            return

        default = criteria.PRD_THRESHOLD
        rows = []
        try:
            for value in GRID:
                criteria.PRD_THRESHOLD = value
                reports = self._reports(topics)
                rows.append({
                    "PRD_THRESHOLD": value,
                    "forbidden": sum(len(report["forbidden_accepted"]) for report in reports),
                    "reachable": {report["topic"]: report["reachable_count"] for report in reports},
                    "accepted_precision": {report["topic"]: report["accepted_precision"] for report in reports},
                    "orders_match": all(report["order_matches"] for report in reports),
                })
        finally:
            criteria.PRD_THRESHOLD = default
        self.stdout.write(json.dumps(rows, indent=2))
