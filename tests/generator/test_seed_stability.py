"""A seed names one puzzle whatever order the solver searches in."""

import hashlib
import itertools
import json
import random
from collections.abc import Iterator
from typing import cast

import pytest

import chroma_cube.solver.search as search
from chroma_cube.core import (
    BOARD_4X4,
    BOARD_4X5,
    CLASSIC_BOARD,
    CLASSIC_PALETTE,
    EXTENDED_16,
    EXTENDED_20,
    Board,
    Cell,
    Color,
    Palette,
    Placement,
    Puzzle,
    puzzle_to_dict,
)
from chroma_cube.core.clues import Clue, relation
from chroma_cube.generator import DIFFICULTIES, Difficulty, generate
from chroma_cube.generator.build import solver_rivals
from chroma_cube.generator.candidates import cells_of, compile_clue, random_solution
from tests.generator.helpers import extended, generated

LAYOUT = {
    "classic": (CLASSIC_BOARD, CLASSIC_PALETTE),
    "4x4": (BOARD_4X4, EXTENDED_16),
    "4x5": (BOARD_4X5, EXTENDED_20),
}

_PLAIN_BRANCHES = search._Search._branches


def _reversed(self: search._Search, candidates: search.Candidates) -> list[tuple[Color, Cell]]:
    return list(reversed(_PLAIN_BRANCHES(self, candidates)))


def _shuffled(self: search._Search, candidates: search.Candidates) -> list[tuple[Color, Cell]]:
    branches = _PLAIN_BRANCHES(self, candidates)
    random.Random(len(branches)).shuffle(branches)
    return branches


@pytest.fixture(params=["reversed", "shuffled"])
def other_search_order(request: pytest.FixtureRequest) -> Iterator[None]:
    """The solver tries its placements in another order, finding solutions in another order."""
    patch = pytest.MonkeyPatch()
    patch.setattr(
        search._Search, "_branches", _reversed if request.param == "reversed" else _shuffled
    )
    yield
    patch.undo()


def _digest(puzzle: Puzzle) -> str:
    return hashlib.sha256(json.dumps(puzzle_to_dict(puzzle), sort_keys=True).encode()).hexdigest()[
        :16
    ]


def _generate(key: str, *, cached: bool = True) -> Puzzle:
    layout, level, number = key.split("-")
    seed, difficulty = int(number), cast(Difficulty, level)
    if cached and layout == "classic":
        return generated(seed, difficulty)
    if cached:
        rows, cols = (int(n) for n in layout.split("x"))
        return extended(seed, difficulty, rows, cols)
    board, palette = LAYOUT[layout]
    return generate(seed, difficulty, board=board, palette=palette)


PINNED = {
    "classic-easy-0": "fb8150669927ca5b",
    "classic-easy-1": "078319856aa1be41",
    "classic-easy-2": "50940834e5d70f4a",
    "classic-medium-0": "00d80c4a4301d1d4",
    "classic-medium-1": "633a0439ef58ebf1",
    "classic-medium-2": "aa33bae5f66df840",
    "classic-hard-0": "23f0de4dffbc35e0",
    "classic-hard-1": "69e19397780664f8",
    "classic-hard-2": "74d5ce62b056cc7f",
    "classic-expert-0": "a00f552a5eecb622",
    "classic-expert-1": "3a5f581d53b49228",
    "classic-expert-2": "608d349c110d38ed",
    "4x4-easy-0": "689914cc47e1da5c",
    "4x4-medium-0": "60d17bf5b7d4d191",
    "4x4-hard-0": "2042a97194d30d42",
    "4x4-expert-0": "d68e2317248ffcda",
    "4x5-easy-0": "9da6b278369ec4b3",
    "4x5-medium-0": "f0059d0f297dbc6d",
    "4x5-hard-0": "5ab00bc87c54c6f5",
    "4x5-expert-0": "b4bfbd680290f549",
}
"""Generated puzzles by board, difficulty and seed. A change to how the solver searches
must never change these."""


@pytest.mark.parametrize("key", sorted(PINNED))
def test_pinned_seeds_build_the_same_puzzle(key: str) -> None:
    assert _digest(_generate(key)) == PINNED[key]


@pytest.mark.parametrize("level", DIFFICULTIES)
@pytest.mark.usefixtures("other_search_order")
def test_classic_seeds_do_not_depend_on_search_order(level: Difficulty) -> None:
    for key in sorted(PINNED):
        if key.startswith(f"classic-{level}-"):
            assert _digest(_generate(key, cached=False)) == PINNED[key], key


@pytest.mark.parametrize("layout", ["4x4", "4x5"])
def test_larger_board_seeds_do_not_depend_on_search_order(
    layout: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(search._Search, "_branches", _reversed)
    for level in DIFFICULTIES:
        key = f"{layout}-{level}-0"
        assert _digest(_generate(key, cached=False)) == PINNED[key], key


def _loose(board: Board, palette: Palette) -> tuple[Placement, list[Clue], Placement]:
    """A solution, one clue true on it, and two givens: thousands of other solutions."""
    solution = random_solution(random.Random(1), board, palette)
    a, b = next(
        (a, b)
        for a, b in itertools.combinations(palette, 2)
        if solution.assignments[a].row == solution.assignments[b].row
    )
    c, d = [color for color in palette if color not in (a, b)][:2]
    clue = relation("same_row", a.id, b.id)
    givens = Placement({c: solution.assignments[c], d: solution.assignments[d]})
    assert compile_clue(clue, board, palette)(cells_of(solution, palette))
    return solution, [clue], givens


def _rivals(board: Board, palette: Palette, cap: int) -> list[tuple[Cell, ...]]:
    solution, clues, givens = _loose(board, palette)
    return solver_rivals(
        random.Random(7), board, palette, clues, givens, cells_of(solution, palette), cap
    )


@pytest.mark.parametrize("cap", [1, 5, 16])
def test_solver_rivals_are_real_other_solutions(cap: int) -> None:
    board, palette = CLASSIC_BOARD, CLASSIC_PALETTE
    solution, clues, givens = _loose(board, palette)
    rivals = _rivals(board, palette, cap)
    assert 1 <= len(rivals) <= cap
    assert len(rivals) == len(set(rivals))
    planted = cells_of(solution, palette)
    check = compile_clue(clues[0], board, palette)
    for rival in rivals:
        assert rival != planted
        assert check(rival)
        for color, cell in givens.assignments.items():
            assert rival[palette.colors.index(color)] == cell


@pytest.mark.parametrize("cap", [1, 5, 16])
def test_solver_rivals_do_not_depend_on_search_order(
    cap: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    plain = _rivals(CLASSIC_BOARD, CLASSIC_PALETTE, cap)
    for order in (_reversed, _shuffled):
        monkeypatch.setattr(search._Search, "_branches", order)
        assert _rivals(CLASSIC_BOARD, CLASSIC_PALETTE, cap) == plain


def test_solver_rivals_list_every_one_when_there_are_few() -> None:
    board, palette = Board(2, 3), Palette(CLASSIC_PALETTE.colors[:6])
    solution, clues, givens = _loose(board, palette)
    planted = cells_of(solution, palette)
    check = compile_clue(clues[0], board, palette)
    every = sorted(
        cells
        for cells in itertools.permutations(board)
        if cells != planted
        and check(cells)
        and all(cells[palette.colors.index(c)] == cell for c, cell in givens.assignments.items())
    )
    assert 1 < len(every) < 16
    rivals = solver_rivals(random.Random(7), board, palette, clues, givens, planted, 16)
    assert rivals == every
