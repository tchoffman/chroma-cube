"""Puzzles on the classic 3x4 tray, including the speed the solver must keep."""

import time

from chroma_cube.core import CLASSIC_BOARD, CLASSIC_PALETTE, Cell, Placement, Puzzle
from chroma_cube.core.clues import BoardRule, Not, prop, relation
from chroma_cube.solver import first_solution, is_unique, solve
from tests.core.helpers import FULL
from tests.solver.helpers import brute_force, puzzle


def givens(**cells: tuple[int, int]) -> Placement:
    return Placement({CLASSIC_PALETTE.by_id(color): Cell(*cell) for color, cell in cells.items()})


#   black   brown   cobalt  coral
#   emerald magenta mint    mustard
#   orange  purple  teal    white
FIVE_GIVENS = puzzle(
    CLASSIC_BOARD,
    CLASSIC_PALETTE,
    [
        relation("directly_left_of", "cobalt", "coral"),
        relation("directly_above", "emerald", "orange"),
        relation("directly_above", "magenta", "purple"),
        relation("directly_left_of", "teal", "white"),
        Not(prop("in_row", "mustard", 0)),
    ],
    givens(black=(0, 0), brown=(0, 1), mint=(1, 2), orange=(2, 0), white=(2, 3)),
)

EMPTY_TRAY = puzzle(
    CLASSIC_BOARD,
    CLASSIC_PALETTE,
    [
        prop("in_corner", "black"),
        relation("directly_left_of", "black", "brown"),
        relation("knows", "black", "magenta"),
        relation("same_row", "cobalt", "coral"),
        relation("directly_below", "orange", "emerald"),
        relation("between", "magenta", "emerald", "mint"),
        relation("diagonal", "mint", "white"),
        relation("between", "purple", "orange", "teal"),
        prop("in_col", "coral", 3),
        relation("above", "mustard", "white"),
    ],
)


def test_a_five_given_puzzle_is_unique_and_brute_force_agrees() -> None:
    assert is_unique(FIVE_GIVENS)
    assert first_solution(FIVE_GIVENS) == FULL
    assert brute_force(FIVE_GIVENS) == {FULL}


def test_an_empty_tray_puzzle_is_unique() -> None:
    assert is_unique(EMPTY_TRAY)
    assert first_solution(EMPTY_TRAY) == FULL


def test_alphabetical_rows_and_columns_have_462_solutions() -> None:
    # The number of standard Young tableaux of a 3x4 shape.
    rules = [BoardRule("rows_alphabetical"), BoardRule("columns_alphabetical")]
    result = solve(puzzle(CLASSIC_BOARD, CLASSIC_PALETTE, rules), limit=1000)
    assert result.count == 462
    assert not result.truncated
    assert FULL in result.solutions


def _seconds_to_prove_unique(p: Puzzle) -> float:
    start = time.perf_counter()
    assert is_unique(p)
    return time.perf_counter() - start


def test_benchmark_five_givens_is_well_under_a_second() -> None:
    assert _seconds_to_prove_unique(FIVE_GIVENS) < 1.0


def test_benchmark_empty_tray_is_under_a_second() -> None:
    assert _seconds_to_prove_unique(EMPTY_TRAY) < 1.0
