"""Which way a prerequisite link points: three votes (criteria v7).

Spec: docs/superpowers/specs/2026-10-01-learning-path-v7-direction-votes-design.md,
sections 4-6. The lesson's order is one vote; the hierarchy and the references
are the other two. Every number here can be recomputed in a spreadsheet from the
block x concept matrix (``export_direction_sheet``).
"""

from dataclasses import dataclass

MIN_OWNED_TERMS = 2
MIN_BLOCKS = 3
SUBSUME_HIGH = 0.8
SUBSUME_LOW = 0.5
REFERENCE_GAP = 0.25


@dataclass(frozen=True)
class Block:
    """One extracted chunk: the concept it belongs to, its PDF, its place there, its stems."""

    owner: int
    material_id: object
    order: float
    stems: frozenset


@dataclass(frozen=True)
class BlockMatrix:
    """Which concepts appear in which blocks; ``present[concept id][i]`` is block i."""

    blocks: tuple
    present: dict

    def count(self, concept_id):
        return sum(self.present[concept_id])

    def together(self, first_id, second_id):
        return sum(1 for a, b in zip(self.present[first_id], self.present[second_id]) if a and b)

    def own_blocks(self, concept_id):
        return [index for index, block in enumerate(self.blocks) if block.owner == concept_id]


def _chunks(concept):
    # Same fallback as concept_text.prepare, so chunks line up with ``passages``.
    return getattr(concept, "members", None) or (concept,)


def build_block_matrix(texts, term_owners):
    """The 0/1 matrix of spec section 4, from ``prepare``'s texts and ``find_term_owners``."""
    blocks = tuple(
        Block(text.id, getattr(chunk, "material_id", None), getattr(chunk, "order", 0), frozenset(stems))
        for text in texts
        for chunk, stems in zip(_chunks(text.concept), text.passages)
    )
    owned = {text.id: set() for text in texts}
    for stem, owner in term_owners.items():
        if owner in owned:
            owned[owner].add(stem)
    present = {}
    for text in texts:
        name = set(text.name)
        present[text.id] = tuple(
            block.owner == text.id
            or (bool(name) and name <= block.stems)
            or len(owned[text.id] & block.stems) >= MIN_OWNED_TERMS
            for block in blocks
        )
    return BlockMatrix(blocks, present)
