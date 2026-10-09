"""The shipped puzzle sets."""

from chroma_cube.core import (
    CLASSIC_BOARD,
    CLASSIC_PALETTE,
    Cell,
    Or,
    Placement,
    Puzzle,
    relation,
)


def classic_puzzles() -> tuple[Puzzle, ...]:
    """The classic cards, easiest first."""
    palette = CLASSIC_PALETTE
    givens = {
        "cobalt": Cell(0, 2),
        "emerald": Cell(1, 0),
        "orange": Cell(1, 1),
        "brown": Cell(1, 2),
        "mustard": Cell(1, 3),
        "black": Cell(2, 2),
        "purple": Cell(2, 3),
    }
    return (
        Puzzle(
            id="classic-01",
            title="First steps",
            board=CLASSIC_BOARD,
            palette=palette,
            givens=Placement({palette.by_id(color): cell for color, cell in givens.items()}),
            clues=(
                relation("same_column", "coral", "magenta"),
                relation("next_to", "black", "magenta"),
                Or(
                    (
                        relation("same_row", "teal", "cobalt"),
                        relation("same_row", "black", "cobalt"),
                    )
                ),
                relation("next_to", "coral", "white"),
            ),
            difficulty="easy",
        ),
    )
