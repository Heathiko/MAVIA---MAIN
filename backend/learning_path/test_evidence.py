"""R1 and R3 of the v4 criteria, tested on their own.

The decision table that combines them lives in ``test_criteria.py``. These tests
pin the two measurements, so a failure here says which piece of evidence
changed rather than only that a verdict moved. See
``docs/superpowers/specs/2026-09-29-learning-path-criteria-v4-design.md``.
"""

from django.test import SimpleTestCase

from .services.criteria import (
    concept_names,
    defining_sentences,
    definition_dependency,
    head_words,
    passage_reference,
    says,
    says_plainly,
)
from .services.text_signals import first_sentence


class Headed:
    """A concept stub whose members carry their own title, content and heading."""

    def __init__(self, id, order, title, contents, sections=None):
        if isinstance(contents, str):
            contents = (contents,)
        sections = sections or ("",) * len(contents)
        self.id = id
        self.order = order
        self.title = title
        self.content = contents[0]
        self.member_text = "\n".join(contents)
        self.section_title = sections[0]
        self.kind = "text"
        self.members = tuple(
            type("Member", (), {"title": title, "content": content, "section_title": section})()
            for content, section in zip(contents, sections)
        )


def names_and_heads(concepts):
    names = concept_names(concepts)
    return names, head_words(names)


class FirstSentenceTests(SimpleTestCase):
    def test_the_text_up_to_the_first_break(self):
        self.assertEqual(
            first_sentence("Melting is when a solid melts. Then it flows."),
            "Melting is when a solid melts",
        )

    def test_empty_text_has_no_sentence(self):
        self.assertEqual(first_sentence(""), "")
        self.assertEqual(first_sentence(None), "")


class SaysTests(SimpleTestCase):
    def test_plural_and_head_word_mentions_count(self):
        solid = Headed(1, 0, "Solid", "A solid keeps its shape.")
        seed = Headed(2, 1, "Seed formation", "The ovule becomes a seed.")
        names, heads = names_and_heads([solid, seed])

        self.assertTrue(says("Solids keep their shape.", 1, names, heads))
        self.assertTrue(says("The fruit protects the seed.", 2, names, heads))
        self.assertFalse(says("Liquids flow.", 1, names, heads))

    def test_an_unnamed_concept_is_never_said(self):
        self.assertFalse(says("anything at all", 1, {1: None}, {}))

    def test_a_contrastive_mention_is_not_plain(self):
        solid = Headed(1, 0, "Solid", "A solid keeps its shape.")
        names, heads = names_and_heads([solid])
        text = "A gas spreads out, unlike a solid."

        self.assertTrue(says(text, 1, names, heads))
        self.assertFalse(says_plainly(text, 1, names, heads))


class DefiningSentenceTests(SimpleTestCase):
    def test_a_sentence_that_defines_the_concept(self):
        melting = Headed(1, 0, "Melting", "Melting is when a solid turns into a liquid. It needs heat.")

        self.assertEqual(
            defining_sentences(melting, "melting"),
            ["Melting is when a solid turns into a liquid"],
        )

    def test_a_plural_subject_still_defines(self):
        solid = Headed(1, 0, "Solid", "Solids are hard and keep their shape.")

        self.assertEqual(defining_sentences(solid, "solid"), ["Solids are hard and keep their shape"])

    def test_a_description_is_not_a_definition(self):
        solid = Headed(1, 0, "Solid", "Solids keep their shape.")

        self.assertEqual(defining_sentences(solid, "solid"), [])

    def test_a_members_title_alone_does_not_make_a_definition(self):
        """Amended 2026-09-29: counting the first sentence of any member
        titled "Matter" made "It comes in three states: solid..." Matter's
        definition, which produced Solid -> Matter on gold topic 62."""
        matter = Headed(1, 0, "Matter", "It comes in three states: solid, liquid and gas.")

        self.assertEqual(defining_sentences(matter, "matter"), [])

    def test_every_members_definition_counts(self):
        melting = Headed(1, 0, "Melting", (
            "Melting is when a solid turns into a liquid.",
            "Melting means heat breaks the solid apart.",
        ))

        self.assertEqual(len(defining_sentences(melting, "melting")), 2)

    def test_no_name_no_definition(self):
        self.assertEqual(defining_sentences(Headed(1, 0, "x", "X is y."), None), [])


class DefinitionDependencyTests(SimpleTestCase):
    def setUp(self):
        self.solid = Headed(1, 0, "Solid", "A solid keeps its shape.")
        self.liquid = Headed(2, 1, "Liquid", "A liquid flows.")
        self.melting = Headed(3, 2, "Melting", "Melting is when a solid turns into a liquid.")
        self.concepts = [self.solid, self.liquid, self.melting]
        self.names, self.heads = names_and_heads(self.concepts)

    def test_a_concept_used_in_anothers_definition_comes_first(self):
        self.assertEqual(
            definition_dependency(self.solid, self.melting, self.names, self.heads),
            "Melting is when a solid turns into a liquid",
        )

    def test_the_reverse_direction_does_not_hold(self):
        self.assertIsNone(definition_dependency(self.melting, self.solid, self.names, self.heads))

    def test_definitions_naming_each_other_decide_nothing(self):
        heat = Headed(1, 0, "Heat", "Heat is energy that causes melting.")
        melting = Headed(2, 1, "Melting", "Melting is what heat does to ice.")
        names, heads = names_and_heads([heat, melting])

        self.assertIsNone(definition_dependency(heat, melting, names, heads))
        self.assertIsNone(definition_dependency(melting, heat, names, heads))

    def test_a_contrastive_mention_in_a_definition_is_not_a_dependency(self):
        gas = Headed(2, 1, "Gas", "A gas is a state that spreads out, unlike a solid.")
        names, heads = names_and_heads([self.solid, gas])

        self.assertIsNone(definition_dependency(self.solid, gas, names, heads))

    def test_a_head_word_in_a_definition_names_the_concept(self):
        seed = Headed(1, 0, "Seed formation", "The ovule becomes a seed.")
        fruit = Headed(2, 1, "Fruit formation", "Fruit formation is when the ovary grows around the seed.")
        names, heads = names_and_heads([seed, fruit])

        self.assertEqual(
            definition_dependency(seed, fruit, names, heads),
            "Fruit formation is when the ovary grows around the seed",
        )

    def test_an_unnamed_concept_takes_no_part(self):
        figure = Headed(4, 3, "The image shows three boxes of dots representing the states", "Dots.")
        names, heads = names_and_heads([self.solid, figure])

        self.assertIsNone(names[4])
        self.assertIsNone(definition_dependency(figure, self.solid, names, heads))
        self.assertIsNone(definition_dependency(self.solid, figure, names, heads))


class PassageReferenceTests(SimpleTestCase):
    def test_passages_naming_another_concept_point_to_it(self):
        solid = Headed(1, 0, "Solid", "It keeps its shape.")
        comparing = Headed(2, 1, "Comparing", "The table puts the solid beside the gas.")
        names, heads = names_and_heads([solid, comparing])

        references = passage_reference([solid, comparing], names, heads)

        self.assertEqual(references[(1, 2)], {"prw_forward": 1.0, "prw_backward": 0.0, "prd": 1.0, "passages_forward": 1, "passages_backward": 1})
        self.assertEqual(references[(2, 1)]["prd"], -1.0)

    def test_the_share_is_over_the_dependents_passages(self):
        solid = Headed(1, 0, "Solid", "It keeps its shape.")
        changing = Headed(2, 1, "Changing", ("A solid can melt.", "Heat is added."))
        names, heads = names_and_heads([solid, changing])

        self.assertEqual(passage_reference([solid, changing], names, heads)[(1, 2)]["prw_forward"], 0.5)

    def test_a_contrastive_passage_does_not_count(self):
        solid = Headed(1, 0, "Solid", "It keeps its shape.")
        gas = Headed(2, 1, "Gas", "A gas spreads out, unlike a solid.")
        names, heads = names_and_heads([solid, gas])

        self.assertEqual(passage_reference([solid, gas], names, heads)[(1, 2)]["prd"], 0.0)

    def test_an_unnamed_concept_has_no_reference(self):
        figure = Headed(1, 0, "The image shows three boxes of dots representing the states", "A solid.")
        solid = Headed(2, 1, "Solid", "It keeps its shape.")
        names, heads = names_and_heads([figure, solid])

        references = passage_reference([figure, solid], names, heads)

        self.assertNotIn((1, 2), references)
        self.assertNotIn((2, 1), references)

    def test_a_parents_overview_points_the_reference_backwards(self):
        """The known weakness R2 has to overrule (spec Section 11): Matter's
        overview names its children, so the passage score reads Solid -> Matter.
        Measured on gold topic 62 at -1.0 for Matter -> Solid."""
        matter = Headed(1, 0, "Matter", "Matter can be a solid, a liquid or a gas.")
        solid = Headed(2, 1, "Solid", "It keeps its shape.", ("Matter",))
        names, heads = names_and_heads([matter, solid])

        self.assertEqual(passage_reference([matter, solid], names, heads)[(2, 1)]["prd"], 1.0)
