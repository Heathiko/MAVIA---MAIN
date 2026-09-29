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
