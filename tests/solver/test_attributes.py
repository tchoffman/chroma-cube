"""The solver handles clues about color attributes."""

from hypothesis import given, settings
from hypothesis import strategies as st

from chroma_cube.core import CLASSIC_BOARD, CLASSIC_PALETTE, Board, Placement, Puzzle
from chroma_cube.core.clues import ATTRIBUTE_KINDS, Not, Region, attribute, attribute_clues
from chroma_cube.core.evaluate import Truth, evaluate
from chroma_cube.solver import is_unique, solve
from chroma_cube.solver.simplify import simplify
from tests.core.helpers import FULL
from tests.solver.helpers import brute_force, puzzle, small_palette

# FULL is
#   black   brown   cobalt  coral
#   emerald magenta mint    mustard
#   orange  purple  teal    white
ONE_OF_EACH = (
    attribute("neighbours_all", "cool", color="orange"),
    attribute("neighbours_none", "neutral", color="mint"),
    attribute("neighbours_some", "warm", color="mint"),
    attribute("next_to_family", "blue", color="mint"),
    attribute("region_all", "light", region=Region("row", 1)),
    attribute("region_count", "dark", region=Region("row", 0), n=3),
)


def test_the_clues_cover_every_kind_and_hold_on_the_solution() -> None:
    assert {clue.kind for clue in ONE_OF_EACH} == set(ATTRIBUTE_KINDS)
    for clue in ONE_OF_EACH:
        assert evaluate(clue, FULL, CLASSIC_BOARD, CLASSIC_PALETTE) is Truth.SATISFIED


def test_a_classic_puzzle_with_one_attribute_clue_of_each_kind_solves() -> None:
    given_ids = ("black", "cobalt", "emerald", "magenta", "orange", "white")
    givens = Placement(
        {color: cell for color, cell in FULL.assignments.items() if color.id in given_ids}
    )
    p = puzzle(CLASSIC_BOARD, CLASSIC_PALETTE, ONE_OF_EACH, givens)
    result = solve(p, limit=50)
    assert FULL in result.solutions
    for solution in result.solutions:
        for clue in ONE_OF_EACH:
            assert evaluate(clue, solution, CLASSIC_BOARD, CLASSIC_PALETTE) is Truth.SATISFIED


SMALL = Board(2, 3)
SIX = small_palette(6)  # black, brown, cobalt, coral, emerald, magenta


def test_a_small_attribute_puzzle_is_proved_unique() -> None:
    p = puzzle(
        SMALL,
        SIX,
        [
            attribute("neighbours_all", "cool", color="magenta"),
            attribute("region_count", "neutral", region=Region("column", 0), n=1),
            attribute("neighbours_some", "dark", color="black"),
            attribute("next_to_family", "pink", color="cobalt"),
            attribute("region_count", "dark", region=Region("row", 0), n=3),
        ],
    )
    expected = Placement(dict(zip(SIX.colors, list(SMALL), strict=True)))
    assert is_unique(p)
    assert solve(p).solutions == (expected,)
    assert brute_force(p) == {expected}


@st.composite
def attribute_puzzles(draw: st.DrawFn) -> Puzzle:
    board = draw(st.sampled_from([Board(2, 2), Board(2, 3)]))
    palette = small_palette(len(board))
    pool = attribute_clues(board, palette)
    clues = draw(st.lists(st.sampled_from(pool), min_size=1, max_size=4))
    clues = [Not(clue) if draw(st.booleans()) else clue for clue in clues]
    return puzzle(board, palette, clues)


@settings(max_examples=60, deadline=None)
@given(attribute_puzzles())
def test_the_solver_agrees_with_brute_force_on_attribute_clues(p: Puzzle) -> None:
    assert set(solve(p, limit=1000).solutions) == brute_force(p)


def test_simplify_keeps_attribute_clues_as_whole_facts() -> None:
    clue = attribute("region_all", "warm", region=Region("corners"))
    assert simplify([clue, Not(clue)]) is None
    assert simplify([Not(clue)]) == (Not(clue),)
    other = attribute("neighbours_some", "cool", color="mint")
    assert simplify([clue, Not(other)]) == (clue, Not(other))
