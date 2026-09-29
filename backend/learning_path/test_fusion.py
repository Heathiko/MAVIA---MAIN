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
from .services.fusion import ACCEPTED, PARALLEL, PENDING, combine, learn_weights, verdict
from .testing import word_vectors

EQUAL = {"name": 1.0, "terms": 1.0, "meaning": 1.0, "order": 0.5}


def votes(name=0, terms=0, meaning=0, order=0):
    return {"name": name, "terms": terms, "meaning": meaning, "order": order}


class LearnWeightTests(SimpleTestCase):
    def test_a_clue_that_agrees_with_the_others_weighs_more(self):
        rows = [votes(1, 1, 1, 0)] * 9 + [votes(-1, 1, 1, 0)]

        weights, agreement = learn_weights(rows)

        self.assertAlmostEqual(agreement["terms"], 1.0)
        self.assertAlmostEqual(weights["terms"], math.log(0.95 / 0.05))
        self.assertGreater(weights["terms"], weights["name"])

    def test_a_clue_no_better_than_chance_weighs_nothing(self):
        rows = [votes(1, 1, 1, 0), votes(-1, 1, 1, 0)]

        self.assertEqual(learn_weights(rows)[0]["name"], 0.0)

    def test_pdf_order_never_outweighs_a_content_clue(self):
        rows = [votes(1, 1, 1, 1)] * 10

        weights, _ = learn_weights(rows)

        self.assertLessEqual(weights["order"], min(weights[c] for c in ("name", "terms", "meaning")) / 2)


class VerdictTests(SimpleTestCase):
    def test_two_agreeing_clues_with_most_of_the_weight_are_accepted(self):
        pair = votes(terms=1, meaning=1, order=1)
        score, confidence = combine(pair, EQUAL)

        self.assertEqual(verdict(pair, score, confidence), (ACCEPTED, 1))

    def test_one_content_clue_is_only_pending(self):
        pair = votes(terms=-1)
        score, confidence = combine(pair, EQUAL)

        self.assertEqual(verdict(pair, score, confidence), (PENDING, -1))

    def test_pdf_order_alone_makes_no_link(self):
        pair = votes(order=1)
        score, confidence = combine(pair, EQUAL)

        self.assertEqual(verdict(pair, score, confidence)[0], PARALLEL)

    def test_clues_that_cancel_are_parallel(self):
        pair = votes(terms=1, meaning=-1)
        score, confidence = combine(pair, EQUAL)

        self.assertEqual(verdict(pair, score, confidence)[0], PARALLEL)

    def test_without_the_encoder_nothing_is_accepted(self):
        pair = votes(name=1, terms=1, order=1)
        score, confidence = combine(pair, EQUAL)

        self.assertEqual(verdict(pair, score, confidence, semantic=False), (PENDING, 1))


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
        self.assertEqual(set(stored["weights"]), {"name", "terms", "meaning", "order"})
        self.assertEqual(load_calibration(self.path)["source"], str(self.path))
