"""Count reasoning over candidates: what it rules out, and what it charges."""

from itertools import permutations

from hypothesis import given, settings
from hypothesis import strategies as st

from chroma_cube.core import EXTENDED_16, Board, Cell, Clue, Color, Palette, Placement
from chroma_cube.core.clues import Not, Region, attribute, attribute_clues, relation
from chroma_cube.core.evaluate import Truth, evaluate
from chroma_cube.solver.counts import CountPropagator
from chroma_cube.solver.search import _twins

BOARD = Board(2, 3)
SIX = Palette(
    tuple(EXTENDED_16.by_id(i) for i in ("purple", "lavender", "black", "brown", "coral", "white"))
)
PURPLE, LAVENDER, BLACK, BROWN, CORAL, WHITE = SIX.colors


def narrow(
    clues: list[Clue], candidates: dict[Color, tuple[Cell, ...]], widest: int = 0
) -> tuple[bool, dict[Color, tuple[Cell, ...]], int]:
    counts = CountPropagator(BOARD, SIX, clues, ())
    charged = [0]

    def charge(trials: int) -> None:
        charged[0] += trials

    narrowed = dict(candidates)
    alive = set(range(len(clues)))
    ok = counts.narrow(Placement(), narrowed, alive, charge, widest=widest)
    return ok, narrowed, charged[0]


def everywhere(**fixed: tuple[Cell, ...]) -> dict[Color, tuple[Cell, ...]]:
    return {color: fixed.get(color.id, tuple(BOARD)) for color in SIX}


def test_a_neighbour_clue_keeps_the_only_matching_color_next_to_its_subject() -> None:
    # Lavender is the only other purple, so it must sit next to wherever Purple can go.
    ok, narrowed, _ = narrow(
        [attribute("next_to_family", "purple", color="purple")],
        everywhere(purple=(Cell(0, 0),)),
    )
    assert ok
    assert narrowed[LAVENDER] == (Cell(0, 1), Cell(1, 0))


def test_a_neighbour_clue_keeps_its_subject_where_a_match_can_reach() -> None:
    ok, narrowed, _ = narrow(
        [attribute("next_to_family", "purple", color="purple")],
        everywhere(lavender=(Cell(1, 2),)),
    )
    assert ok
    assert narrowed[PURPLE] == (Cell(0, 2), Cell(1, 1))


def test_a_region_count_with_no_room_left_ends_the_branch() -> None:
    # Two dark colors in the top row, but every dark color is kept in the bottom row.
    bottom = tuple(BOARD.row(1))
    ok, _, _ = narrow(
        [attribute("region_count", "dark", region=Region("row", 0), n=2)],
        everywhere(purple=bottom, black=bottom, brown=bottom),
    )
    assert not ok


def test_probing_drops_a_cell_that_settles_into_a_dead_end_and_is_charged() -> None:
    # Every cube in the right column is light, so dark Purple must take the top-left
    # cell. The counts alone leave Coral that cell too; putting Coral there leaves Purple
    # nowhere, so a probe rules it out.
    clues = [attribute("region_all", "light", region=Region("column", 2))]
    start = everywhere(purple=(Cell(0, 0), Cell(1, 2)), coral=(Cell(0, 0), Cell(0, 2)))
    _, without, nothing = narrow(clues, start, widest=0)
    ok, probed, charged = narrow(clues, start, widest=len(BOARD))
    assert ok
    assert without[PURPLE] == probed[PURPLE] == (Cell(0, 0),)
    assert without[CORAL] == (Cell(0, 0), Cell(0, 2))
    assert probed[CORAL] == (Cell(0, 2),)
    assert nothing == 0 and charged > 0


@st.composite
def narrowing_cases(
    draw: st.DrawFn,
) -> tuple[Board, Palette, Placement, dict[Color, tuple[Cell, ...]], list[Clue], bool, int]:
    """A planted solution, some of it placed, candidate cells for the rest that include
    the planted cell, and attribute clues (some negated, some false) plus a relation."""
    board = draw(st.sampled_from([Board(2, 2), Board(2, 3), Board(1, 5), Board(3, 3), Board(2, 4)]))
    palette = Palette(tuple(draw(st.permutations(EXTENDED_16.colors)))[: len(board)])
    cells = draw(st.permutations(list(board)))
    solution = Placement(dict(zip(palette.colors, cells, strict=True)))
    pool = attribute_clues(board, palette)
    clues: list[Clue] = [
        Not(clue) if draw(st.booleans()) else clue
        for clue in draw(st.lists(st.sampled_from(pool), min_size=1, max_size=len(board)))
    ]
    if draw(st.booleans()):
        a, b = draw(st.permutations(palette.colors))[:2]
        clues.append(relation("next_to", a.id, b.id))
    loose = draw(st.integers(1, min(6, len(board))))
    order = draw(st.permutations(palette.colors))
    placed = Placement({color: solution.assignments[color] for color in order[loose:]})
    free = [cell for cell in board if placed.color_at(cell) is None]
    candidates = {
        color: tuple(
            cell for cell in free if cell == solution.assignments[color] or draw(st.booleans())
        )
        for color in order[:loose]
    }
    twins = draw(st.booleans())
    widest = draw(st.sampled_from([0, len(board) // 2, len(board)]))
    return board, palette, placed, candidates, clues, twins, widest


@settings(max_examples=200, deadline=None)
@given(narrowing_cases())
def test_narrowing_keeps_every_arrangement_within_the_candidates_that_satisfies_the_clues(
    case: tuple[Board, Palette, Placement, dict[Color, tuple[Cell, ...]], list[Clue], bool, int],
) -> None:
    board, palette, placed, candidates, clues, use_twins, widest = case
    twins = _twins(palette, clues, Placement()) if use_twins else ()
    loose = list(candidates)
    free = [cell for cell in board if placed.color_at(cell) is None]
    order = {cell: i for i, cell in enumerate(board)}
    solutions = []
    for spots in permutations(free, len(loose)):
        if any(spot not in candidates[color] for color, spot in zip(loose, spots, strict=True)):
            continue
        full = Placement({**placed.assignments, **dict(zip(loose, spots, strict=True))})
        in_order = all(
            order[full.assignments[a]] < order[full.assignments[b]]
            for group in twins
            for a, b in zip(group, group[1:], strict=False)
        )
        if in_order and all(
            evaluate(clue, full, board, palette) is Truth.SATISFIED for clue in clues
        ):
            solutions.append(full)
    counts = CountPropagator(board, palette, clues, twins)
    narrowed = dict(candidates)
    ok = counts.narrow(placed, narrowed, set(range(len(clues))), lambda _: None, widest=widest)
    if solutions:
        assert ok
        for solution in solutions:
            for color in loose:
                assert solution.assignments[color] in narrowed[color]
