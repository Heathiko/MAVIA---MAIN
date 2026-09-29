"""Print the gold report for frozen topics."""

import json

from django.core.management.base import BaseCommand

from learning_path.services import criteria
from learning_path.services.gold import gold_report, load_gold


class Command(BaseCommand):
    help = "Report derived learning paths against the gold standard."

    def add_arguments(self, parser):
        parser.add_argument("--topics", nargs="*", type=int, default=[62, 79, 152])

    def handle(self, *args, topics, **options):
        reports = []
        for topic_id in topics:
            data, concepts = load_gold(topic_id)
            reports.append(gold_report(data, concepts, criteria.decide_pairs(concepts)))
        self.stdout.write(json.dumps(reports, indent=2))
