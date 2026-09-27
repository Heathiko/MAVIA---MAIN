"""A description printed under a figure is the figure's narration.

Measured on a one-page handout: a picture of three containers, "SOLID",
"LIQUID", "GAS", with a paragraph right under it that opens "The image shows
the three states of matter". The paragraph was read as lesson text that
follows the figure, so it became two learning objects of its own and the
model wrote the figure a second description. A passage that says what the
model's own description of the picture says is describing that picture.
"""

from unittest.mock import patch

from django.test import SimpleTestCase

from lessons.services.content_generator import (
    _mark_figure_descriptions,
    build_section_learning_objects,
    describe_pdf_images,
)
from lessons.services.image_describer import passage_directly_below

FIGURE_BOX = (72.0, 72.0, 540.0, 335.0)
DESCRIPTION = (
    "The image shows the three states of matter: solid, liquid, and gas, based on how their "
    "particles are arranged. In a solid, the particles are packed closely together and only "
    "vibrate in place. In a gas, the particles are spread far apart and move freely."
)
# What the vision model says about the same picture.
NARRATION = (
    "The image shows three containers labelled solid, liquid and gas. In the solid the "
    "particles are packed closely together, and in the gas the particles are spread far apart."
)
LESSON_TEXT = (
    "Lines on a map running parallel to the equator are called lines of latitude. Latitude is "
    "the distance in degrees north or south of the equator. The equator is numbered zero "
    "degrees and the poles ninety degrees."
)


def block(block_id, text, top, *, left=72.0, right=540.0, page=2):
    return {
        "block_id": block_id, "block_index": block_id, "page": page, "text": text,
        "bbox": (left, top, right, top + 60), "line_count": 3, "is_bold": False,
        "font_size": 11.0, "page_width": 612.0, "page_height": 792.0,
        "category": "lesson_content", "include_in_narration": True,
    }


class PassageBelowTests(SimpleTestCase):
    def test_the_paragraph_right_under_the_figure_is_found(self):
        blocks = [block(1, "Lesson text above.", 20), block(2, DESCRIPTION, 348)]

        found = passage_directly_below(blocks, page_number=2, bbox=FIGURE_BOX)

        self.assertEqual(found["block_id"], 2)

    def test_a_caption_in_between_is_stepped_over(self):
        blocks = [block(2, "Figure 1: States of matter", 340), block(3, DESCRIPTION, 380)]

        found = passage_directly_below(blocks, page_number=2, bbox=(72, 72, 540, 330))

        self.assertEqual(found["block_id"], 3)

    def test_text_far_below_or_in_another_column_is_not_the_figures(self):
        far = [block(2, DESCRIPTION, 500)]
        beside = [block(2, DESCRIPTION, 348, left=560, right=700)]
        other_page = [block(2, DESCRIPTION, 348, page=3)]

        for blocks in (far, beside, other_page):
            with self.subTest(blocks=blocks):
                self.assertIsNone(passage_directly_below(blocks, page_number=2, bbox=FIGURE_BOX))


class FigureNarrationFromPdfTests(SimpleTestCase):
    def _image(self, index=0, bbox=FIGURE_BOX):
        return {
            "page_number": 2, "index": index, "width": 468, "height": 263, "extension": "png",
            "caption": "", "image_bytes": b"png", "bbox": bbox, "image_url": f"/media/{index}.png",
        }

    def _blocks(self, passage=DESCRIPTION):
        return [
            block(1, "Matter is anything that has mass and occupies space.", 74, page=1),
            block(2, passage, 348),
        ]

    def _describe(self, images, blocks, narration=NARRATION):
        with patch("lessons.services.content_generator.describe_image_for_lesson", return_value=narration):
            return describe_pdf_images(images, "Matter", blocks=blocks)

    def test_a_printed_description_becomes_the_narration_and_leaves_the_lesson(self):
        blocks = self._blocks()

        described = self._describe([self._image()], blocks)

        self.assertEqual(described[0]["content"], " ".join(DESCRIPTION.split()))
        self.assertEqual(described[0]["description_source"], "pdf_description")
        objects = build_section_learning_objects(_mark_figure_descriptions(blocks, described), described)
        texts = [item for item in objects if item["type"] != "image_description"]
        self.assertFalse([item for item in texts if "three states" in item["content"]])
        figure = next(item for item in objects if item["type"] == "image_description")
        self.assertEqual(figure["content"], DESCRIPTION)

    def test_lesson_text_that_only_follows_the_figure_stays_lesson_text(self):
        blocks = self._blocks(passage=LESSON_TEXT)

        described = self._describe([self._image()], blocks)

        self.assertEqual(described[0]["content"], NARRATION)
        self.assertEqual(_mark_figure_descriptions(blocks, described), blocks)

    def test_a_heading_or_short_conclusion_under_a_figure_is_never_its_description(self):
        """Measured: "Therefore, Ben is as fast as Jen ..." under a worked example."""
        for passage in (
            "States of Matter",
            "Therefore, Ben is as fast as Jen. Both have the same speed of 1 meter per second (1 m/s).",
        ):
            with self.subTest(passage=passage):
                described = self._describe([self._image()], self._blocks(passage=passage), narration=passage)

                self.assertNotEqual(described[0]["description_source"], "pdf_description")

    def test_one_passage_describes_at_most_one_figure(self):
        blocks = self._blocks()
        images = [self._image(0), self._image(1, bbox=(80.0, 80.0, 530.0, 330.0))]

        described = self._describe(images, blocks)

        self.assertEqual([item["description_source"] for item in described].count("pdf_description"), 1)
