"""The search gives up instead of hanging, and never passes "gave up" off as an answer."""

import time

import pytest

from chroma_cube.core import CLASSIC_BOARD, CLASSIC_PALETTE, Board
from chroma_cube.core.clues import BoardRule, Clue, Not, Or, prop
from chroma_cube.solver import (
    SearchBudgetExceeded,
    count_solutions,
    first_solution,
    is_solvable,
    is_unique,
    solve,
)
from tests.solver.helpers import puzzle, small_palette

COLUMNS = BoardRule("columns_alphabetical")
ROWS = BoardRule("rows_alphabetical")
OPEN_TRAY = puzzle(CLASSIC_BOARD, CLASSIC_PALETTE)
"""No clues: billions of solutions, so any full count runs out of budget."""


@pytest.mark.parametrize(
    "clues",
    [
        [COLUMNS, Not(COLUMNS)],
        [ROWS, Not(ROWS)],
        [COLUMNS, Not(Or((COLUMNS, prop("in_corner", "white"))))],
        [
            Not(Or((Not(COLUMNS), prop("in_center", "black")))),
            Not(Or((COLUMNS, prop("in_corner", "white")))),
        ],
    ],
    ids=["columns-and-not", "rows-and-not", "columns-and-not-either", "hidden-in-negations"],
)
def test_a_clue_contradicting_another_is_rejected_quickly(clues: list[Clue]) -> None:
    start = time.perf_counter()
    result = solve(puzzle(CLASSIC_BOARD, CLASSIC_PALETTE, clues))
    assert time.perf_counter() - start < 1.0
    assert result.count == 0
    assert not result.gave_up


def test_the_search_gives_up_when_the_budget_runs_out() -> None:
    start = time.perf_counter()
    result = solve(OPEN_TRAY, limit=10**9, max_nodes=2_000)
    assert time.perf_counter() - start < 1.0
    assert result.gave_up
    assert not result.truncated
    assert 0 < result.count < 10**9


def test_no_budget_searches_to_the_end() -> None:
    result = solve(puzzle(Board(2, 2), small_palette(4)), limit=100, max_nodes=None)
    assert not result.gave_up
    assert result.count == 24


def test_a_search_that_finishes_has_not_given_up() -> None:
    result = solve(OPEN_TRAY, limit=3, max_nodes=2_000)
    assert result.count == 3
    assert result.truncated
    assert not result.gave_up


def test_helpers_raise_rather_than_guess_when_the_budget_runs_out() -> None:
    with pytest.raises(SearchBudgetExceeded):
        count_solutions(OPEN_TRAY, cap=10**9, max_nodes=2_000)
    unsolved = puzzle(CLASSIC_BOARD, CLASSIC_PALETTE, [COLUMNS, prop("in_corner", "white")])
    with pytest.raises(SearchBudgetExceeded):
        is_solvable(unsolved, max_nodes=1)
    with pytest.raises(SearchBudgetExceeded):
        first_solution(unsolved, max_nodes=1)
    with pytest.raises(SearchBudgetExceeded):
        is_unique(unsolved, max_nodes=1)


def test_helpers_answer_when_the_budget_suffices_to_decide() -> None:
    assert is_solvable(OPEN_TRAY, max_nodes=2_000)
    assert first_solution(OPEN_TRAY, max_nodes=2_000) is not None
    assert not is_unique(OPEN_TRAY, max_nodes=2_000)


def test_max_nodes_must_be_positive() -> None:
    with pytest.raises(ValueError):
        solve(OPEN_TRAY, max_nodes=0)
