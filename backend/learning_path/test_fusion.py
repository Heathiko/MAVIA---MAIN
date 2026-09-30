"""Weights, confidence, verdicts and the stored calibration (spec section 7)."""

import json
import math
import tempfile
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.core.management import call_command
from django.test import SimpleTestCase

from .services.calibration import DEFAULTS, load_calibration
from .services.fusion import ACCEPTED, PARALLEL, PENDING, confidence, learn_weights, verdict
from .testing import word_vectors



def votes(name=0, terms=0, meaning=0, heading=0, order=0, parallel=False):
    return {"name": name, "terms": terms, "meaning": meaning, "heading": heading, "order": order, "parallel": parallel}


class LearnWeightTests(SimpleTestCase):
    def test_a_clue_that_agrees_with_the_others_weighs_more(self):
        rows = [votes(1, 1, 1)] * 9 + [votes(-1, 1, 1)]

        weights, agreement = learn_weights(rows)

        self.assertAlmostEqual(agreement["terms"], 1.0)
        self.assertAlmostEqual(weights["terms"], math.log(0.95 / 0.05))
        self.assertGreater(weights["terms"], weights["name"])

    def test_a_clue_no_better_than_chance_weighs_nothing(self):
        rows = [votes(1, 1, 1), votes(-1, 1, 1)]

        self.assertEqual(learn_weights(rows)[0]["name"], 0.0)


class VerdictTests(SimpleTestCase):
    """Two families: what the text says (name, terms, meaning) and how the author
    organised it (heading, order). Agreement accepts; structure alone links nothing."""

    def test_text_and_structure_agreeing_is_accepted(self):
        self.assertEqual(verdict(votes(name=1, heading=1)), (ACCEPTED, 1))

    def test_all_three_content_clues_with_structure_silent_is_accepted(self):
        self.assertEqual(verdict(votes(name=-1, terms=-1, meaning=-1)), (ACCEPTED, -1))

    def test_text_alone_that_is_not_unanimous_is_pending(self):
        self.assertEqual(verdict(votes(terms=1)), (PENDING, 1))

    def test_text_against_the_structure_is_pending_in_the_structures_direction(self):
        """An overview names its children, so the text reads child-first while the
        headings and PDFs put the parent first (Solid -> Matter on gold 62)."""
        self.assertEqual(verdict(votes(name=-1, terms=-1, heading=1)), (PENDING, 1))

    def test_structure_alone_makes_no_link(self):
        self.assertEqual(verdict(votes(heading=1, order=1))[0], PARALLEL)

    def test_siblings_are_at_most_pending(self):
        self.assertEqual(verdict(votes(name=1, terms=1, meaning=1, order=1, parallel=True)), (PENDING, 1))

    def test_without_the_encoder_nothing_is_accepted(self):
        self.assertEqual(verdict(votes(name=1, heading=1), semantic=False), (PENDING, 1))

    def test_confidence_is_the_share_of_voting_clues_that_agree(self):
        self.assertAlmostEqual(confidence(votes(name=1, terms=1, meaning=-1, order=1), 1), 0.75)
        self.assertEqual(confidence(votes(), 1), 0.0)


class CalibrationFileTests(SimpleTestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.path = Path(folder.name) / "weights.json"

    def test_a_missing_file_gives_the_defaults(self):
        calibration = load_calibration(self.path)

        self.assertEqual(calibration["weights"], DEFAULTS["weights"])
        self.assertEqual(calibration["source"], "defaults")

    def test_a_malformed_file_gives_the_defaults_and_a_warning(self):
        self.path.write_text("{not json", encoding="utf-8")

        with self.assertLogs("learning_path.services.calibration", level="WARNING"):
            calibration = load_calibration(self.path)

        self.assertEqual(calibration["related_cutoff"], DEFAULTS["related_cutoff"])

    def test_the_defaults_are_never_shared(self):
        load_calibration(self.path)["weights"]["name"] = 0.0

        self.assertEqual(DEFAULTS["weights"]["name"], 1.0)

    def test_the_command_writes_a_readable_file(self):
        with patch("learning_path.management.commands.calibrate_learning_path.embed", word_vectors):
            call_command(
                "calibrate_learning_path", "--topics", "62", "79", "--unrelated", "62:79",
                "--out", str(self.path), stdout=StringIO(),
            )

        stored = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(stored["topics"], [62, 79])
        self.assertEqual(set(stored["weights"]), {"name", "terms", "meaning", "heading", "order"})
        self.assertEqual(load_calibration(self.path)["source"], str(self.path))
