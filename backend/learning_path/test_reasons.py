"""The one-sentence reason a teacher reads beside each link."""

from django.test import SimpleTestCase

from .services.reasons import link_reason


def reference(forward, n, backward, p):
    return {"rule": "reference", "reference": {
        "prw_forward": forward, "prw_backward": backward, "prd": forward - backward,
        "theta": 0.05, "passages_forward": n, "passages_backward": p,
    }}


class LinkReasonTests(SimpleTestCase):
    def test_definition_quotes_the_sentence(self):
        evidence = {"rule": "definition", "definition": {"sentence": "Melting is when a solid turns into a liquid"}}

        self.assertEqual(
            link_reason(evidence, "Solid", "Melting"),
            "Melting's definition uses Solid: “Melting is when a solid turns into a liquid”",
        )

    def test_containment_names_the_heading(self):
        evidence = {"rule": "containment", "containment": {"heading": "matter"}}

        self.assertEqual(link_reason(evidence, "Matter", "Solid"), "Solid sits under the heading “Matter”.")

    def test_reference_counts_passages(self):
        self.assertEqual(
            link_reason(reference(0.8, 5, 0.0, 3), "Solid", "Comparing"),
            "Comparing's text names Solid in 4 of 5 passages; Solid's text never names Comparing.",
        )

    def test_reference_both_ways(self):
        self.assertEqual(
            link_reason(reference(1.0, 2, 0.5, 2), "Solid", "Comparing"),
            "Comparing's text names Solid in 2 of 2 passages; Solid's text names Comparing in 1 of 2.",
        )

    def test_reference_without_counts_still_reads(self):
        evidence = {"rule": "reference", "reference": {"prw_forward": 1.0, "prw_backward": 0.0}}

        self.assertEqual(
            link_reason(evidence, "Solid", "Comparing"),
            "Comparing's text names Solid more often than Solid's text names Comparing.",
        )

    def test_conflict(self):
        self.assertEqual(link_reason({"rule": "conflict"}, "A", "B"), "The lesson files point both ways; choose one.")

    def test_a_teacher_link_has_no_evidence(self):
        self.assertEqual(link_reason({}, "A", "B"), "Added by you.")
        self.assertEqual(link_reason(None, "A", "B"), "Added by you.")

    def test_an_accepted_v6_link_names_its_words_and_the_order(self):
        evidence = {"rule": "reference-order", "direction_from": "pdf_order", "contradictions": [],
                    "votes": {"name": 0, "terms": 1, "meaning": 1, "heading": 0, "order": 0},
                    "records": {"terms": {"owned": ["particle", "vibrate"]}}}

        self.assertEqual(
            link_reason(evidence, "Solid", "Gas"),
            "Gas uses terms Solid explains (particle, vibrate). Solid comes first in the lesson.",
        )

    def test_a_v6_link_by_heading_and_name(self):
        evidence = {"rule": "reference-order", "direction_from": "heading", "contradictions": [],
                    "votes": {"name": 1, "terms": 0, "heading": 1}, "records": {}}

        self.assertEqual(
            link_reason(evidence, "Matter", "Solid"),
            "Solid sits under a heading naming Matter. Solid names Matter.",
        )

    def test_a_v6_suggestion_says_what_stands_against_it(self):
        evidence = {"rule": "reference-order", "direction_from": "pdf_order",
                    "contradictions": ["reverse_name", "backward_only"],
                    "votes": {"name": -1, "terms": 0, "heading": 0}, "records": {}}

        self.assertEqual(
            link_reason(evidence, "Matter", "Solid"),
            "Matter comes first in the lesson. But Matter's text names Solid more than the reverse. "
            "But only Matter's text refers to Solid.",
        )

    def test_a_v6_figure_suggestion(self):
        evidence = {"rule": "reference-order", "direction_from": "figure", "contradictions": ["figure"],
                    "votes": {"name": 0, "terms": 1, "heading": 0},
                    "records": {"terms": {"owned": ["particle"]}}}

        self.assertEqual(
            link_reason(evidence, "Solid", "Particles in a solid"),
            "Particles in a solid uses terms Solid explains (particle). "
            "The figure's description refers to Solid. "
            "One of them is a figure, so its place in the file does not give the order.",
        )

    def test_v6_suggestions_from_different_or_disagreeing_files(self):
        evidence = {"rule": "reference-order", "direction_from": "merged_order",
                    "contradictions": ["no_shared_pdf"], "votes": {"terms": 1},
                    "records": {"terms": {"owned": []}}}

        self.assertEqual(
            link_reason(evidence, "Stamen", "Pollination"),
            "Pollination uses terms Stamen explains. Stamen comes first in the topic's combined order. "
            "They come from different files, so their order is a guess.",
        )
        evidence["contradictions"] = ["pdfs_disagree"]
        self.assertTrue(link_reason(evidence, "Stamen", "Pollination").endswith("The files put them in different orders."))

    def test_a_v6_suggestion_from_the_files_alone(self):
        evidence = {"rule": "reference-order", "direction_from": "pdf_agreement", "contradictions": [],
                    "votes": {"order": 1}, "records": {"order": {"pdfs": 2, "agree": 2}}}

        self.assertEqual(
            link_reason(evidence, "Pollination", "Fertilization"),
            "2 of 2 files teach Pollination first; the text says nothing either way.",
        )

    def test_a_fused_link_names_its_clues(self):
        evidence = {
            "rule": "fusion", "confidence": 0.81, "semantic": True,
            "votes": {"name": 0, "terms": 1, "meaning": 1, "order": 1},
            "records": {"terms": {"owned": ["anther", "filament"]}, "order": {"pdfs": 2, "agree": 2}},
        }

        self.assertEqual(
            link_reason(evidence, "Stamen", "Pollination"),
            "Pollination uses terms Stamen explains (anther, filament). "
            "Pollination's sentences refer to Stamen's ideas. "
            "2 of 2 files teach Stamen first. Confidence 0.81.",
        )

    def test_a_fused_link_says_which_clues_disagree_and_when_meaning_was_unavailable(self):
        evidence = {"rule": "fusion", "confidence": 0.3, "semantic": False,
                    "votes": {"name": 1, "terms": 0, "meaning": 0, "order": -1}, "records": {}}

        self.assertEqual(
            link_reason(evidence, "Stamen", "Pollination"),
            "Pollination names Stamen. Against it: the files' order. "
            "The meaning check was unavailable. Confidence 0.30.",
        )

    def test_a_fused_link_against_the_text_says_so(self):
        evidence = {"rule": "fusion", "confidence": 0.5, "semantic": True, "disagreement": True, "parallel": False,
                    "votes": {"name": -1, "terms": 0, "meaning": 0, "heading": 1, "order": 0}, "records": {}}

        self.assertEqual(
            link_reason(evidence, "Matter", "Solid"),
            "Solid sits under a heading naming Matter. Against it: the name. "
            "The text reads the other way; this follows how the files are organised. Confidence 0.50.",
        )

    def test_siblings_are_explained(self):
        evidence = {"rule": "fusion", "confidence": 1.0, "semantic": True, "disagreement": False, "parallel": True,
                    "votes": {"name": 1, "terms": 0, "meaning": 0, "heading": 0, "order": 0}, "records": {}}

        self.assertEqual(
            link_reason(evidence, "Solid", "Gas"),
            "Gas names Solid. The files present Solid and Gas side by side under one heading. Confidence 1.00.",
        )

    def test_a_suggestion_from_the_files_alone_says_the_text_is_silent(self):
        evidence = {"rule": "fusion", "confidence": 1.0, "semantic": True, "disagreement": False, "parallel": False,
                    "votes": {"name": 0, "terms": 0, "meaning": 0, "heading": 0, "order": 1},
                    "records": {"order": {"pdfs": 2, "agree": 2}}}

        self.assertEqual(
            link_reason(evidence, "Pollination", "Fertilization"),
            "2 of 2 files teach Pollination first. The text says nothing either way. Confidence 1.00.",
        )

    def test_a_course_link_that_follows_the_outline(self):
        evidence = {"rule": "course", "confidence": 1.0, "semantic": True, "contradicts_outline": False,
                    "votes": {"name": 1, "terms": 1, "meaning": 0, "outline": 1},
                    "records": {"terms": {"owned": ["anther"]}}}

        self.assertEqual(
            link_reason(evidence, "Stamen", "Pollination"),
            "Pollination uses terms Stamen explains (anther). Pollination names Stamen. "
            "This follows your outline. Confidence 1.00.",
        )

    def test_a_course_link_against_the_outline_says_so(self):
        evidence = {"rule": "course", "confidence": 0.67, "semantic": True, "contradicts_outline": True,
                    "votes": {"name": 1, "terms": 1, "meaning": 0, "outline": -1}, "records": {}}

        self.assertEqual(
            link_reason(evidence, "Stamen", "Pollination"),
            "Pollination uses terms Stamen explains. Pollination names Stamen. "
            "This contradicts your outline: Stamen's topic comes later. Confidence 0.67.",
        )
