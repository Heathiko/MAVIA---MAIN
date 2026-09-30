"""Print the gold report for frozen topics, with the switches the evaluation needs.

--without CLUE       silence one clue (ablation)
--build-on-latest    Kahn ties prefer the concept building on the latest step (off by default)
--meaning-matches N  average the N best matches in the meaning clue (size check)
--by-clue            add each clue's right/wrong count on the key's links
--baseline order     link each concept to the one before it (no text read)
"""

import json

from django.core.management.base import BaseCommand

from learning_path.services import clues, criteria
from learning_path.services.calibration import load_calibration
from learning_path.services.fusion import CLUES
from learning_path.services.gold import clue_accuracy, gate_loss, gold_report, load_gold, order_only_decisions


class Command(BaseCommand):
    help = "Report derived learning paths against the gold standard."

    def add_arguments(self, parser):
        parser.add_argument("--topics", nargs="*", default=["62", "79", "152"])
        parser.add_argument("--baseline", choices=["order"])
        parser.add_argument("--without", choices=CLUES)
        parser.add_argument("--build-on-latest", action="store_true")
        parser.add_argument("--meaning-matches", type=int, default=1)
        parser.add_argument("--by-clue", action="store_true")

    def handle(self, *args, topics, without, build_on_latest, meaning_matches, by_clue, baseline, **options):
        calibration = load_calibration()
        previous_matches = clues.MEANING_MATCHES
        clues.MEANING_MATCHES = meaning_matches
        try:
            reports = []
            for topic_id in topics:
                data, concepts = load_gold(topic_id)
                if baseline == "order":
                    decisions = order_only_decisions(concepts)
                else:
                    decisions = criteria.decide_pairs(
                        concepts, calibration=calibration, without=(without,) if without else (),
                    )
                report = gold_report(data, concepts, decisions, build_on_latest=build_on_latest)
                report["gate_loss"] = gate_loss(data, concepts, calibration)
                if by_clue:
                    report["clue_accuracy"] = clue_accuracy(data, concepts, calibration)
                reports.append(report)
        finally:
            clues.MEANING_MATCHES = previous_matches
        self.stdout.write(json.dumps({
            "calibration": calibration["source"],
            "without": without,
            "baseline": baseline,
            "build_on_latest": build_on_latest,
            "meaning_matches": meaning_matches,
            "reports": reports,
        }, indent=2))
