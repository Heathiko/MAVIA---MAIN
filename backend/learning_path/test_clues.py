"""Relatedness and the four direction clues, each on its own (spec sections 5-6)."""

from types import SimpleNamespace

import numpy as np
from django.test import SimpleTestCase

from .services import clues
from .services.clues import (
    SIGNIFICANT_G2,
    find_term_owners,
    heading_vote,
    log_likelihood,
    meaning_cutoff,
    meaning_vote,
    name_vote,
    order_vote,
    pair_votes,
    presented_in_parallel,
    term_vote,
)
from .services.concept_text import prepare, terms
from .services.relatedness import best_match_average, related_cutoff, relatedness
from .testing import concept, member, word_vectors


def vectors(*rows):
    return SimpleNamespace(vectors=np.array(rows, dtype="float32"))


class RelatednessTests(SimpleTestCase):
    def test_best_match_average_takes_each_sentences_closest_match(self):
        self.assertAlmostEqual(best_match_average(np.array([[1.0, 0.0]]), np.array([[1.0, 0.0], [0.0, 1.0]])), 1.0)

    def test_relatedness_is_symmetric(self):
        first, second = vectors([1.0, 0.0], [0.0, 1.0]), vectors([1.0, 0.0])

        self.assertAlmostEqual(relatedness(first, second), relatedness(second, first))

    def test_a_concept_without_sentences_is_related_to_nothing(self):
        self.assertEqual(relatedness(vectors([1.0, 0.0]), SimpleNamespace(vectors=np.zeros((0, 2)))), 0.0)

    def test_the_cutoff_is_the_95th_percentile_of_unrelated_pairs(self):
        pairs = [(vectors([1.0, 0.0]), vectors([np.cos(angle), np.sin(angle)])) for angle in np.linspace(0, 1.5, 21)]

        self.assertAlmostEqual(related_cutoff(pairs), float(np.percentile([relatedness(*pair) for pair in pairs], 95)))
        self.assertIsNone(related_cutoff([]))


class NameVoteTests(SimpleTestCase):
    def test_a_concept_whose_text_names_another_comes_after_it(self):
        stamen, pollination = prepare([
            concept(1, "Stamen", "The stamen makes pollen grains."),
            concept(2, "Pollination", "Pollen leaves the stamen on the wind."),
        ])

        self.assertEqual(name_vote(stamen, pollination)[0], 1)
        self.assertEqual(name_vote(pollination, stamen)[0], -1)

    def test_two_concepts_with_one_title_do_not_vote(self):
        first, second = prepare([
            concept(1, "Comparing the Three States", "Comparing the three states shows shape."),
            concept(2, "Comparing the Three States", "Comparing the three states shows volume."),
        ])

        self.assertEqual(name_vote(first, second)[0], 0)


class TermOwnerTests(SimpleTestCase):
    def setUp(self):
        self.stamen, self.pollination, self.pistil = prepare([
            concept(1, "Stamen", "The anther makes pollen grains. " * 8),
            concept(2, "Pollination", "Pollen travels from an anther to a stigma."),
            concept(3, "Pistil", "The stigma is sticky and holds the style. " * 8),
        ])
        self.owners = find_term_owners([self.stamen, self.pollination, self.pistil])

    def test_log_likelihood_needs_real_evidence(self):
        self.assertGreater(log_likelihood(10, 100, 10, 1000), SIGNIFICANT_G2)
        self.assertLess(log_likelihood(1, 6, 1, 9), SIGNIFICANT_G2)

    def test_a_term_belongs_where_it_is_over_represented(self):
        self.assertEqual(self.owners[terms("anther")[0]], 1)
        self.assertEqual(self.owners[terms("stigma")[0]], 3)

    def test_using_a_term_another_explains_puts_that_concept_first(self):
        vote, record = term_vote(self.stamen, self.pollination, self.owners)

        self.assertEqual(vote, 1)
        self.assertIn("anther", record["owned"])


class MeaningVoteTests(SimpleTestCase):
    def test_sentences_about_another_concept_put_it_first(self):
        stamen = vectors([1.0, 0.0], [0.0, 1.0])
        pollination = vectors([1.0, 0.0])

        vote, record = meaning_vote(stamen, pollination, 0.5)

        self.assertEqual(vote, 1)
        self.assertEqual((record["use"], record["use_back"]), (1.0, 0.5))

    def test_the_cutoff_comes_from_unrelated_sentences(self):
        pairs = [(vectors([1.0, 0.0]), vectors([0.0, 1.0], [0.6, 0.8]))]

        self.assertAlmostEqual(meaning_cutoff(pairs), float(np.percentile([0.6, 0.0, 0.6], 95)))

    def test_two_best_matches_can_be_averaged(self):
        self.addCleanup(setattr, clues, "MEANING_MATCHES", clues.MEANING_MATCHES)
        clues.MEANING_MATCHES = 2
        holder, target = vectors([1.0, 0.0]), vectors([1.0, 0.0], [0.0, 1.0])

        self.assertEqual(clues.meaning_use(holder, target, 0.6), 0.0)


class OrderVoteTests(SimpleTestCase):
    def test_all_pdfs_agreeing_votes(self):
        positions = {10: {1: 0, 2: 1}, 11: {1: 3, 2: 5}}

        self.assertEqual(order_vote(SimpleNamespace(id=1), SimpleNamespace(id=2), positions)[0], 1)

    def test_one_pdf_never_votes(self):
        self.assertEqual(order_vote(SimpleNamespace(id=1), SimpleNamespace(id=2), {10: {1: 0, 2: 1}})[0], 0)

    def test_pdfs_that_disagree_do_not_vote(self):
        positions = {10: {1: 0, 2: 1}, 11: {1: 1, 2: 0}}

        self.assertEqual(order_vote(SimpleNamespace(id=1), SimpleNamespace(id=2), positions)[0], 0)


class PairVoteTests(SimpleTestCase):
    def test_every_pair_is_voted_once_as_first_before_second(self):
        texts = prepare([
            concept(1, "Stamen", "The stamen makes pollen grains."),
            concept(2, "Pollination", "Pollen leaves the stamen on the wind."),
            concept(3, "Fruit", "A fruit grows around the seed."),
        ], embed=word_vectors)

        pairs = list(pair_votes(texts, {}, {}, related_cutoff=0.1, meaning_cutoff=0.3))

        self.assertEqual([(pair["first"].id, pair["second"].id) for pair in pairs], [(1, 2), (1, 3), (2, 3)])
        self.assertEqual(pairs[0]["votes"]["name"], 1)
        self.assertEqual(set(pairs[0]["votes"]), {"name", "terms", "meaning", "heading", "order", "parallel"})

    def test_without_the_encoder_every_pair_passes_and_meaning_abstains(self):
        texts = prepare([concept(1, "Stamen", "The stamen makes pollen grains."), concept(2, "Fruit", "A fruit grows around the seed.")])

        [pair] = pair_votes(texts, {}, {}, related_cutoff=0.25, meaning_cutoff=0.3, semantic=False)

        self.assertTrue(pair["related"])
        self.assertIsNone(pair["relatedness"])
        self.assertEqual(pair["votes"]["meaning"], 0)


class HeadingTests(SimpleTestCase):
    def setUp(self):
        self.matter, self.solid, self.gas = prepare([
            concept(1, "Matter", member("Matter has mass and takes up space.")),
            concept(2, "Solid", member("A solid keeps its own shape.", section_title="Matter")),
            concept(3, "Gas", member("A gas spreads out to fill space.", section_title="Matter")),
        ])

    def test_a_concept_under_a_heading_naming_another_comes_after_it(self):
        self.assertEqual(heading_vote(self.matter, self.solid)[0], 1)
        self.assertEqual(heading_vote(self.solid, self.matter)[0], -1)

    def test_two_concepts_under_a_heading_naming_neither_are_parallel(self):
        self.assertTrue(presented_in_parallel(self.solid, self.gas))

    def test_the_concept_a_shared_heading_names_is_the_parent_not_a_sibling(self):
        parent = prepare([concept(1, "Matter", member("Matter has mass and takes up space.", section_title="Matter"))])[0]

        self.assertFalse(presented_in_parallel(parent, self.solid))

    def test_pair_votes_carry_the_heading_clue_and_the_parallel_flag(self):
        [pair, *_] = pair_votes([self.matter, self.solid, self.gas], {}, {}, related_cutoff=0.0, meaning_cutoff=0.3, semantic=False)

        self.assertEqual(pair["votes"]["heading"], 1)
        self.assertFalse(pair["votes"]["parallel"])
