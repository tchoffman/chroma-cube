"""Board-wide rules, decided three-valued on a possibly partial placement."""

from __future__ import annotations

from chroma_cube.core.board import Board, Cell
from chroma_cube.core.colors import Color, Palette
from chroma_cube.core.placement import Placement
from chroma_cube.core.truth import Truth


def rows_alphabetical(placement: Placement, board: Board, palette: Palette) -> Truth:
    """Every row reads in alphabetical order of color name, left to right."""
    return _alphabetical([board.row(i) for i in range(board.rows)], placement, palette)


def columns_alphabetical(placement: Placement, board: Board, palette: Palette) -> Truth:
    """Every column reads in alphabetical order of color name, top to bottom."""
    return _alphabetical([board.column(i) for i in range(board.cols)], placement, palette)


def _alphabetical(lines: list[tuple[Cell, ...]], placement: Placement, palette: Palette) -> Truth:
    """Each line, read in order, is in alphabetical name order.

    VIOLATED as soon as a line's placed cubes are out of order, or a run of free cells
    in a line cannot be filled because too few unplaced colors sort between its ends.
    SATISFIED once every line is full and in order. The lines are checked one at a time,
    so a board whose lines compete for the same few colors can stay UNKNOWN.
    """
    unplaced = sorted(_key(color) for color in placement.unplaced(palette))
    full = True
    for line in lines:
        names: list[str | None] = [
            None if (color := placement.color_at(cell)) is None else _key(color) for cell in line
        ]
        if None in names:
            full = False
        if not _line_can_be_ordered(names, unplaced):
            return Truth.VIOLATED
    return Truth.SATISFIED if full else Truth.UNKNOWN


def _key(color: Color) -> str:
    return color.name.casefold()


def _line_can_be_ordered(names: list[str | None], unplaced: list[str]) -> bool:
    """Placed names ascend, and every run of free cells has enough names to fit in it."""
    low: str | None = None
    gap = 0
    for name in names:
        if name is None:
            gap += 1
            continue
        if low is not None and name <= low:
            return False
        if not _enough_between(low, name, gap, unplaced):
            return False
        low, gap = name, 0
    return _enough_between(low, None, gap, unplaced)


def _enough_between(low: str | None, high: str | None, gap: int, unplaced: list[str]) -> bool:
    fits = [
        name for name in unplaced if (low is None or name > low) and (high is None or name < high)
    ]
    return len(fits) >= gap
