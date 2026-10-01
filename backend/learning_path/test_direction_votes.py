"""v7: the block x concept matrix and the three direction votes (v7 spec sections 4-6)."""

from django.test import SimpleTestCase

from .services.concept_text import prepare
from .services.direction_votes import build_block_matrix
from .testing import concept, member


def three_states():
    """Solid is taught before Matter (the wrong way round); Liquid comes last."""
    return [
        concept(1, "Solid",
                member("A solid is matter with a fixed shape.", order=0),
                member("Solid matter keeps its own volume.", order=1),
                member("Ice is solid matter when it is frozen.", order=2)),
        concept(2, "Matter", member("Matter is everything that takes up space.", order=3)),
        concept(3, "Liquid",
                member("A liquid is matter that flows freely.", order=4),
                member("Liquid matter fills the bottom of a cup.", order=5)),
    ]


class BlockMatrixTests(SimpleTestCase):
    def test_a_concept_is_present_in_its_own_blocks_and_where_its_name_appears(self):
        matrix = build_block_matrix(prepare(three_states()), {})

        self.assertEqual(len(matrix.blocks), 6)
        self.assertEqual(matrix.present[1], (True, True, True, False, False, False))
        self.assertEqual(matrix.present[2], (True,) * 6)
        self.assertEqual(matrix.present[3], (False, False, False, False, True, True))

    def test_two_owned_terms_make_a_concept_present_without_its_name(self):
        lesson = [concept(1, "Stamen", member("The anther makes pollen.", order=0)),
                  concept(2, "Pollination", member("Pollen moves from the anther to the stigma.", order=1))]

        matrix = build_block_matrix(prepare(lesson), {"anther": 1, "pollen": 1})

        self.assertEqual(matrix.present[1], (True, True))

    def test_one_owned_term_is_not_enough(self):
        lesson = [concept(1, "Stamen", member("The anther makes pollen.", order=0)),
                  concept(2, "Pollination", member("Pollen moves from the anther to the stigma.", order=1))]

        matrix = build_block_matrix(prepare(lesson), {"anther": 1})

        self.assertEqual(matrix.present[1], (True, False))

    def test_a_title_that_is_a_sentence_names_nothing(self):
        lesson = [concept(1, "Picking is the simplest method of all the ways to separate things by hand",
                          member("Picking removes big pieces by hand.", order=0)),
                  concept(2, "Sieving", member("Sieving keeps big pieces and picking is slower.", order=1))]

        matrix = build_block_matrix(prepare(lesson), {})

        self.assertEqual(matrix.present[1], (True, False))

    def test_counts_shared_blocks_and_own_blocks(self):
        matrix = build_block_matrix(prepare(three_states()), {})

        self.assertEqual(matrix.count(2), 6)
        self.assertEqual(matrix.together(1, 2), 3)
        self.assertEqual(matrix.own_blocks(3), [4, 5])
