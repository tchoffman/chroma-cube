"""Fixtures shared by every test."""

from collections.abc import Iterator
from pathlib import Path

import pytest

from chroma_cube.core import CLASSIC_BOARD, CLASSIC_PALETTE, Cell, Or, Placement, Puzzle
from chroma_cube.core.clues import relation


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    """Point the progress store at a throwaway directory so no test touches real saves."""
    data_dir = tmp_path_factory.mktemp("data")
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("CHROMA_CUBE_DATA_DIR", str(data_dir))
        yield data_dir


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
"""A fixed card for tests that drive play, so they do not follow edits to the shipped set."""
