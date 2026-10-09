"""The solver handles clues about color attributes."""

import time

from hypothesis import given, settings
from hypothesis import strategies as st

from chroma_cube.core import (
    BOARD_4X4,
    CLASSIC_BOARD,
    CLASSIC_PALETTE,
    EXTENDED_16,
    Board,
    Cell,
    Placement,
    Puzzle,
)
from chroma_cube.core.clues import (
    ATTRIBUTE_KINDS,
    Not,
    Region,
    attribute,
    attribute_clues,
    prop,
    relation,
)
from chroma_cube.core.evaluate import Truth, evaluate
from chroma_cube.solver import is_unique, solve
from chroma_cube.solver.hints import HintReason, next_hint
from chroma_cube.solver.search import colors_in, colors_named
from chroma_cube.solver.simplify import simplify
from tests.core.helpers import FULL
from tests.solver.helpers import brute_force, puzzle, small_palette

# FULL is
#   black   brown   cobalt  coral
#   emerald magenta mint    mustard
#   orange  purple  teal    white
ONE_OF_EACH = (
    attribute("neighbours_all", "cool", color="orange"),
    attribute("neighbours_some", "warm", color="mint"),
    Not(attribute("neighbours_some", "neutral", color="mint")),
    attribute("next_to_family", "blue", color="mint"),
    attribute("region_all", "light", region=Region("row", 1)),
    attribute("region_count", "dark", region=Region("row", 0), n=3),
)


def test_the_clues_cover_every_kind_and_hold_on_the_solution() -> None:
    kinds = {(clue.clue if isinstance(clue, Not) else clue).kind for clue in ONE_OF_EACH}
    assert kinds == set(ATTRIBUTE_KINDS)
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


UNIQUE_SMALL_CLUES = (
    attribute("neighbours_all", "cool", color="magenta"),
    attribute("region_count", "neutral", region=Region("column", 0), n=1),
    attribute("neighbours_some", "dark", color="black"),
    attribute("next_to_family", "pink", color="cobalt"),
    attribute("region_count", "dark", region=Region("row", 0), n=3),
)


def test_a_small_attribute_puzzle_is_proved_unique() -> None:
    p = puzzle(SMALL, SIX, UNIQUE_SMALL_CLUES)
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


# --------------------------------------------------------------------------- hints

ROW = Board(1, 3)
THREE = small_palette(3)  # black (neutral), brown (warm), cobalt (cool)


def test_colors_a_clue_depends_on_and_names() -> None:
    black, brown, cobalt = THREE.colors
    neighbours = attribute("neighbours_all", "dark", color="brown")
    region = attribute("region_all", "dark", region=Region("corners"))
    assert colors_in(neighbours, THREE) == colors_in(region, THREE) == set(THREE)
    assert colors_named(neighbours, THREE) == {brown}
    assert colors_named(attribute("neighbours_all", "dark", color="B"), THREE) == {black, brown}
    assert colors_named(region, THREE) == set()
    assert colors_named(Not(neighbours), THREE) == {brown}
    assert colors_named(relation("next_to", "black", "cobalt"), THREE) == {black, cobalt}


def test_hints_place_the_cube_an_attribute_clue_is_about() -> None:
    # Black must take the first column, so Cobalt, kept away from black, takes the third.
    # Both clues force both moves; only the first clue is about one of the two cubes, so
    # the hint places Cobalt rather than Black, whom neither clue names.
    p = puzzle(
        ROW,
        THREE,
        [
            Not(attribute("neighbours_some", "neutral", color="cobalt")),
            attribute("region_count", "neutral", region=Region("column", 0), n=1),
        ],
    )
    hint = next_hint(p, Placement())
    assert hint is not None
    assert (hint.color.id, hint.cell, hint.reason) == ("cobalt", Cell(0, 2), HintReason.ONLY_CELL)
    assert hint.clues == (0, 1)


def test_hints_lead_through_an_attribute_puzzle_to_its_solution() -> None:
    p = puzzle(SMALL, SIX, UNIQUE_SMALL_CLUES)
    placement = p.givens
    while (hint := next_hint(p, placement)) is not None:
        assert hint.reason is not HintReason.MISPLACED
        placement = placement.with_color(hint.color, hint.cell)
    assert placement == Placement(dict(zip(SIX.colors, list(SMALL), strict=True)))


# --------------------------------------------------------------------------- speed

FOUR_BY_FOUR_SOLUTION = (
    ("azure", "coral", "magenta", "mint"),
    ("white", "cobalt", "garnet", "purple"),
    ("teal", "emerald", "black", "mustard"),
    ("silver", "orange", "brown", "lavender"),
)
FOUR_BY_FOUR_GIVENS = ("azure", "brown", "cobalt", "emerald", "purple", "silver")
FOUR_BY_FOUR_CLUES = (
    attribute("region_count", "light", region=Region("column", 2), n=1),
    prop("in_row", "mint", 0),
    attribute("neighbours_some", "light", color="lavender"),
    relation("directly_above", "white", "teal"),
    attribute("region_count", "neutral", region=Region("row", 1), n=1),
    relation("directly_left_of", "coral", "magenta"),
    attribute("region_count", "cool", region=Region("corners"), n=3),
    prop("in_col", "mustard", 3),
)


def test_a_4x4_attribute_puzzle_is_proved_unique_quickly() -> None:
    solution = Placement(
        {
            EXTENDED_16.by_id(color_id): Cell(row, col)
            for row, line in enumerate(FOUR_BY_FOUR_SOLUTION)
            for col, color_id in enumerate(line)
        }
    )
    givens = Placement(
        {
            color: cell
            for color, cell in solution.assignments.items()
            if color.id in FOUR_BY_FOUR_GIVENS
        }
    )
    p = puzzle(BOARD_4X4, EXTENDED_16, FOUR_BY_FOUR_CLUES, givens)
    start = time.perf_counter()
    result = solve(p, limit=2)
    elapsed = time.perf_counter() - start
    assert result.solutions == (solution,)
    assert not result.truncated and not result.gave_up
    assert elapsed < 3, f"took {elapsed:.2f}s"
