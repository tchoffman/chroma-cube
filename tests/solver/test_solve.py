import pytest

from chroma_cube.core import CLASSIC_BOARD, CLASSIC_PALETTE, Board, Cell, Placement
from chroma_cube.core.clues import Clue, Not, prop, relation
from chroma_cube.core.evaluate import Truth, evaluate
from chroma_cube.solver import (
    count_solutions,
    first_solution,
    is_solvable,
    is_unique,
    solve,
    solve_clues,
)
from tests.solver.helpers import brute_force, puzzle, small_palette

TINY = Board(2, 2)
FOUR = small_palette(4)  # black, brown, cobalt, coral
black, brown, cobalt, coral = FOUR.colors


def test_no_clues_on_a_2x2_board_has_24_solutions() -> None:
    result = solve(puzzle(TINY, FOUR), limit=100)
    assert result.count == 24
    assert len(set(result.solutions)) == 24
    assert not result.truncated


def test_no_clues_on_the_classic_board_is_more_than_the_cap() -> None:
    result = solve(puzzle(CLASSIC_BOARD, CLASSIC_PALETTE), limit=5)
    assert result.count == 5
    assert result.truncated


def test_contradictory_clues_have_no_solutions() -> None:
    clues = [prop("in_row", "black", 0), prop("in_row", "black", 1)]
    result = solve(puzzle(TINY, FOUR, clues))
    assert result.count == 0
    assert result.solutions == ()
    assert not result.truncated
    assert not is_solvable(puzzle(TINY, FOUR, clues))
    assert first_solution(puzzle(TINY, FOUR, clues)) is None


def test_a_clue_naming_a_missing_initial_has_no_solutions() -> None:
    assert solve(puzzle(TINY, FOUR, [prop("in_corner", "Z")])).count == 0


def test_givens_that_break_a_clue_have_no_solutions() -> None:
    givens = Placement({black: Cell(1, 0)})
    assert solve(puzzle(TINY, FOUR, [prop("in_row", "black", 0)], givens)).count == 0


def test_givens_are_respected() -> None:
    givens = Placement({black: Cell(1, 1), coral: Cell(0, 0)})
    result = solve(puzzle(TINY, FOUR, givens=givens), limit=10)
    assert result.count == 2
    for solution in result.solutions:
        assert solution.cell_of(black) == Cell(1, 1)
        assert solution.cell_of(coral) == Cell(0, 0)


UNIQUE_TINY = [
    relation("directly_left_of", "black", "brown"),
    relation("directly_above", "black", "cobalt"),
]
"""black brown / cobalt coral is forced."""


def test_a_hand_built_unique_puzzle_is_unique() -> None:
    p = puzzle(TINY, FOUR, UNIQUE_TINY)
    assert is_unique(p)
    assert first_solution(p) == Placement(
        {black: Cell(0, 0), brown: Cell(0, 1), cobalt: Cell(1, 0), coral: Cell(1, 1)}
    )


def test_a_non_unique_puzzle_is_not_unique() -> None:
    p = puzzle(TINY, FOUR, [relation("next_to", "black", "brown")])
    assert solve(p).count >= 1
    assert solve(p).truncated
    assert count_solutions(p, cap=100) == len(brute_force(p)) == 16
    assert not is_unique(p)
    assert is_solvable(p)


def test_limit_caps_the_solutions_returned() -> None:
    p = puzzle(TINY, FOUR)
    for limit in (1, 5, 23, 24):
        result = solve(p, limit=limit)
        assert result.count == len(result.solutions) == limit
        assert result.truncated is (limit < 24)


def test_count_solutions_stops_at_the_cap() -> None:
    p = puzzle(TINY, FOUR)
    assert count_solutions(p, cap=10) == 10
    assert count_solutions(p, cap=24) == 24
    assert count_solutions(p, cap=50) == 24


def test_limit_must_be_positive() -> None:
    with pytest.raises(ValueError):
        solve(puzzle(TINY, FOUR), limit=0)


def test_the_palette_must_fill_the_board() -> None:
    with pytest.raises(ValueError):
        solve(puzzle(TINY, small_palette(3)))


def test_every_solution_satisfies_every_clue() -> None:
    clues: list[Clue] = [relation("knows", "B", "C"), Not(prop("in_corner", "coral"))]
    p = puzzle(Board(2, 3), small_palette(6), clues)
    result = solve(p, limit=1000)
    assert set(result.solutions) == brute_force(p)
    for solution in result.solutions:
        assert solution.is_complete(p.palette)
        for clue in clues:
            assert evaluate(clue, solution, p.board, p.palette) is Truth.SATISFIED


def test_solve_clues_takes_the_parts_of_a_puzzle() -> None:
    result = solve_clues(TINY, FOUR, UNIQUE_TINY, givens=Placement(), limit=2)
    assert result.count == 1
    assert not result.truncated
    assert solve_clues(TINY, FOUR, []).count == 1


def test_solve_clues_rejects_givens_off_the_board() -> None:
    with pytest.raises(ValueError):
        solve_clues(TINY, FOUR, [], givens=Placement({black: Cell(5, 5)}))


def test_solve_clues_rejects_givens_outside_the_palette() -> None:
    teal = CLASSIC_PALETTE.by_id("teal")
    with pytest.raises(ValueError):
        solve_clues(TINY, FOUR, [], givens=Placement({teal: Cell(0, 0)}))
