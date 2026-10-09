"""Small puzzles and a brute-force reference solver for checking the real one."""

from collections.abc import Sequence
from itertools import permutations

from chroma_cube.core import CLASSIC_PALETTE, Board, Clue, Palette, Placement, Puzzle
from chroma_cube.core.evaluate import Truth, evaluate

SMALL_PALETTE = Palette(CLASSIC_PALETTE.colors[:6])
"""Black, Brown, Cobalt, Coral, Emerald, Magenta: two B and two C initials."""


def small_palette(size: int) -> Palette:
    return Palette(SMALL_PALETTE.colors[:size])


def puzzle(
    board: Board,
    palette: Palette,
    clues: Sequence[Clue] = (),
    givens: Placement | None = None,
) -> Puzzle:
    return Puzzle(
        id="test",
        title="test",
        board=board,
        palette=palette,
        givens=givens or Placement(),
        clues=tuple(clues),
    )


def brute_force(p: Puzzle) -> set[Placement]:
    """Every solution, found by trying every arrangement of the colors that are not given."""
    free = [cell for cell in p.board if p.givens.color_at(cell) is None]
    loose = p.givens.unplaced(p.palette)
    found: set[Placement] = set()
    for cells in permutations(free, len(loose)):
        candidate = Placement({**p.givens.assignments, **dict(zip(loose, cells, strict=True))})
        if all(
            evaluate(clue, candidate, p.board, p.palette) is Truth.SATISFIED for clue in p.clues
        ):
            found.add(candidate)
    return found
