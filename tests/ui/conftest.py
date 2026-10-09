"""Shared test data for the UI tests."""

from chroma_cube.core import CLASSIC_BOARD, CLASSIC_PALETTE, Cell, Or, Placement, Puzzle
from chroma_cube.core.clues import relation

DEMO = Puzzle(
    id="demo",
    title="Demo",
    board=CLASSIC_BOARD,
    palette=CLASSIC_PALETTE,
    givens=Placement(
        {
            CLASSIC_PALETTE.by_id(color): cell
            for color, cell in {
                "cobalt": Cell(0, 2),
                "emerald": Cell(1, 0),
                "orange": Cell(1, 1),
                "brown": Cell(1, 2),
                "mustard": Cell(1, 3),
                "black": Cell(2, 2),
                "purple": Cell(2, 3),
            }.items()
        }
    ),
    clues=(
        relation("same_column", "coral", "magenta"),
        relation("next_to", "black", "magenta"),
        Or((relation("same_row", "teal", "cobalt"), relation("same_row", "black", "cobalt"))),
        relation("next_to", "coral", "white"),
    ),
    difficulty="easy",
)
"""A fixed card for driving the app, so these tests do not follow edits to the shipped set."""
