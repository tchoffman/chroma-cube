"""The pure game model: colors, the board and where cubes sit."""

from chroma_cube.core.board import CLASSIC_BOARD, Board, Cell
from chroma_cube.core.colors import CLASSIC_PALETTE, Color, Palette
from chroma_cube.core.placement import Placement

__all__ = [
    "CLASSIC_BOARD",
    "CLASSIC_PALETTE",
    "Board",
    "Cell",
    "Color",
    "Palette",
    "Placement",
]
