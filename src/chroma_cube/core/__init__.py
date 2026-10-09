"""The pure game model: colors, the board, where cubes sit, and the clue language."""

from chroma_cube.core.board import CLASSIC_BOARD, Board, Cell
from chroma_cube.core.clues import (
    BOARD_RULE_KINDS,
    PROPERTY_KINDS,
    RELATION_KINDS,
    And,
    AtLeast,
    BoardRule,
    BoardRuleKind,
    Clue,
    ColorRef,
    Exactly,
    Not,
    Or,
    Property,
    PropertyKind,
    Relation,
    RelationKind,
    prop,
    ref,
    relation,
)
from chroma_cube.core.colors import CLASSIC_PALETTE, Color, Palette
from chroma_cube.core.evaluate import Truth, evaluate
from chroma_cube.core.placement import Placement
from chroma_cube.core.puzzle import Puzzle, puzzle_from_dict, puzzle_to_dict
from chroma_cube.core.render import render
from chroma_cube.core.serialize import clue_from_dict, clue_to_dict

__all__ = [
    "BOARD_RULE_KINDS",
    "CLASSIC_BOARD",
    "CLASSIC_PALETTE",
    "PROPERTY_KINDS",
    "RELATION_KINDS",
    "And",
    "AtLeast",
    "Board",
    "BoardRule",
    "BoardRuleKind",
    "Cell",
    "Clue",
    "Color",
    "ColorRef",
    "Exactly",
    "Not",
    "Or",
    "Palette",
    "Placement",
    "Property",
    "Puzzle",
    "PropertyKind",
    "Relation",
    "RelationKind",
    "Truth",
    "clue_from_dict",
    "clue_to_dict",
    "evaluate",
    "prop",
    "puzzle_from_dict",
    "puzzle_to_dict",
    "ref",
    "relation",
    "render",
]
