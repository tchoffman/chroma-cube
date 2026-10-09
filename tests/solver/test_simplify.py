"""Folding clues that repeat or negate other clues never changes the solutions."""

import pytest

from chroma_cube.core import Board
from chroma_cube.core.clues import And, AtLeast, Clue, Exactly, Not, Or, prop, relation
from chroma_cube.solver import solve
from chroma_cube.solver.simplify import simplify
from tests.solver.helpers import brute_force, puzzle, small_palette

TOP = prop("in_row", "black", 0)
NEXT = relation("next_to", "black", "brown")


@pytest.mark.parametrize(
    "clues",
    [
        [Not(TOP)],
        [Not(TOP), Not(TOP)],
        [TOP, TOP],
        [Not(Not(TOP)), Not(TOP)],
        [And((TOP, NEXT)), Or((TOP, Not(NEXT)))],
        [Not(TOP), Or((TOP, NEXT))],
        [TOP, Exactly(1, (TOP, NEXT))],
        [TOP, AtLeast(2, (TOP, NEXT))],
        [Not(NEXT), Exactly(1, (TOP, NEXT))],
    ],
)
def test_folding_keeps_the_solutions(clues: list[Clue]) -> None:
    p = puzzle(Board(2, 3), small_palette(6), clues)
    assert set(solve(p, limit=1000).solutions) == brute_force(p)


def test_a_clue_and_its_negation_contradict() -> None:
    assert simplify([TOP, Not(TOP)]) is None
    assert simplify([TOP, Not(Or((TOP, NEXT)))]) is None


def test_a_clue_implied_by_another_is_dropped() -> None:
    assert simplify([TOP, Or((TOP, NEXT))]) == (TOP,)


def test_a_lone_negation_is_kept() -> None:
    assert simplify([Not(TOP)]) == (Not(TOP),)
