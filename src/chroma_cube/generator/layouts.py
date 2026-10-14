"""The boards a generated puzzle can be played on, each with the palette that fills it."""

from __future__ import annotations

from dataclasses import dataclass

from chroma_cube.core.board import BOARD_4X4, BOARD_4X5, CLASSIC_BOARD, Board
from chroma_cube.core.colors import CLASSIC_PALETTE, EXTENDED_16, EXTENDED_20, Palette


@dataclass(frozen=True)
class Layout:
    """A board and its palette. `key` names it in puzzle ids and saved choices."""

    key: str
    label: str
    board: Board
    palette: Palette


LAYOUTS: tuple[Layout, ...] = (
    Layout("classic", "Classic 3×4, 12 colors", CLASSIC_BOARD, CLASSIC_PALETTE),
    Layout("4x4", "4×4, 16 colors", BOARD_4X4, EXTENDED_16),
    Layout("4x5", "4×5, 20 colors", BOARD_4X5, EXTENDED_20),
)
"""Every layout, classic first."""


def layout(key: str) -> Layout:
    """The layout with this key. Raises `KeyError` if there is none."""
    for found in LAYOUTS:
        if found.key == key:
            return found
    raise KeyError(key)
