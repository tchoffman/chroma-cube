from itertools import permutations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from chroma_cube.core import (
    CLASSIC_BOARD,
    CLASSIC_PALETTE,
    Board,
    Cell,
    Color,
    Palette,
    Placement,
)
from chroma_cube.core.clues import (
    PROPERTY_KINDS,
    RELATION_KINDS,
    And,
    AtLeast,
    BoardRule,
    Clue,
    Exactly,
    Not,
    Or,
    Property,
    Relation,
    prop,
    relation,
)
from chroma_cube.core.evaluate import Truth, evaluate
from tests.core.helpers import FULL, grid

SAT, VIOL, UNK = Truth.SATISFIED, Truth.VIOLATED, Truth.UNKNOWN


def ev(clue: Clue, placement: Placement = FULL) -> Truth:
    return evaluate(clue, placement, CLASSIC_BOARD, CLASSIC_PALETTE)


# --------------------------------------------------------------------------- full boards
#
#   black   brown   cobalt  coral
#   emerald magenta mint    mustard
#   orange  purple  teal    white


RELATION_CASES = [
    ("same_row", ("black", "coral"), SAT),
    ("same_row", ("black", "emerald"), VIOL),
    ("same_column", ("black", "orange"), SAT),
    ("same_column", ("black", "brown"), VIOL),
    ("next_to", ("black", "brown"), SAT),
    ("next_to", ("black", "emerald"), SAT),
    ("next_to", ("black", "magenta"), VIOL),
    ("knows", ("black", "brown"), SAT),
    ("knows", ("black", "magenta"), SAT),
    ("knows", ("black", "cobalt"), VIOL),
    ("diagonal", ("black", "magenta"), SAT),
    ("diagonal", ("mint", "brown"), SAT),
    ("diagonal", ("black", "brown"), VIOL),
    ("above", ("black", "orange"), SAT),
    ("above", ("orange", "black"), VIOL),
    ("above", ("black", "purple"), VIOL),
    ("below", ("orange", "black"), SAT),
    ("below", ("black", "orange"), VIOL),
    ("left_of", ("black", "coral"), SAT),
    ("left_of", ("coral", "black"), VIOL),
    ("left_of", ("black", "mustard"), VIOL),
    ("right_of", ("coral", "black"), SAT),
    ("right_of", ("black", "coral"), VIOL),
    ("directly_above", ("black", "emerald"), SAT),
    ("directly_above", ("black", "orange"), VIOL),
    ("directly_below", ("emerald", "black"), SAT),
    ("directly_below", ("orange", "black"), VIOL),
    ("directly_left_of", ("black", "brown"), SAT),
    ("directly_left_of", ("black", "cobalt"), VIOL),
    ("directly_right_of", ("brown", "black"), SAT),
    ("directly_right_of", ("black", "brown"), VIOL),
    ("between", ("brown", "black", "cobalt"), SAT),
    ("between", ("brown", "cobalt", "black"), SAT),
    ("between", ("magenta", "brown", "purple"), SAT),
    ("between", ("black", "brown", "cobalt"), VIOL),
    ("between", ("brown", "black", "coral"), VIOL),
    ("between", ("magenta", "brown", "mint"), VIOL),
]


@pytest.mark.parametrize(("kind", "colors", "expected"), RELATION_CASES)
def test_relations_on_a_full_board(kind: str, colors: tuple[str, ...], expected: Truth) -> None:
    assert ev(relation(kind, *colors)) is expected


def test_every_relation_kind_is_covered_on_a_full_board() -> None:
    assert {kind for kind, _, _ in RELATION_CASES} == set(RELATION_KINDS)


@pytest.mark.parametrize(
    ("kind", "color", "index", "expected"),
    [
        ("in_corner", "black", None, SAT),
        ("in_corner", "white", None, SAT),
        ("in_corner", "brown", None, VIOL),
        ("on_edge", "brown", None, SAT),
        ("on_edge", "black", None, SAT),
        ("on_edge", "magenta", None, VIOL),
        ("in_center", "magenta", None, SAT),
        ("in_center", "mint", None, SAT),
        ("in_center", "emerald", None, VIOL),
        ("in_row", "mint", 1, SAT),
        ("in_row", "mint", 0, VIOL),
        ("in_col", "mint", 2, SAT),
        ("in_col", "mint", 1, VIOL),
    ],
)
def test_properties_on_a_full_board(
    kind: str, color: str, index: int | None, expected: Truth
) -> None:
    assert ev(prop(kind, color, index)) is expected
    assert kind in PROPERTY_KINDS


# --------------------------------------------------------------------------- partial boards


def test_two_placed_cubes_in_different_rows_already_violate_same_row() -> None:
    placement = grid([["black"], [], [None, None, None, "white"]])
    assert ev(relation("same_row", "black", "white"), placement) is VIOL


def test_one_placed_cube_leaves_same_row_unknown() -> None:
    placement = grid([["black"]])
    assert ev(relation("same_row", "black", "white"), placement) is UNK
    assert ev(relation("same_row", "black", "white"), Placement()) is UNK


def test_a_cube_in_a_corner_already_satisfies_in_corner() -> None:
    assert ev(prop("in_corner", "black"), grid([["black"]])) is SAT
    assert ev(prop("in_corner", "black"), Placement()) is UNK


def test_a_cube_whose_neighbours_are_all_taken_by_others_violates_next_to() -> None:
    placement = grid([["black", "brown"], ["emerald"]])
    assert ev(relation("next_to", "black", "cobalt"), placement) is VIOL
    assert ev(relation("next_to", "cobalt", "black"), placement) is VIOL
    assert ev(relation("next_to", "black", "brown"), placement) is SAT


def test_an_unplaced_cube_is_decided_when_every_free_cell_agrees() -> None:
    # Only the four corners are free, so white can only end up in a corner.
    rows: list[list[str | None]] = [
        [None, "black", "brown", None],
        ["cobalt", "coral", "emerald", "magenta"],
        [None, "mint", "mustard", None],
    ]
    placement = grid(rows)
    assert ev(prop("in_corner", "white"), placement) is SAT
    assert ev(prop("in_center", "white"), placement) is VIOL
    assert ev(prop("in_row", "white", 1), placement) is VIOL


def test_a_corner_cube_can_never_be_between_two_others() -> None:
    placement = grid([["black"]])
    assert ev(relation("between", "black", "white", "teal"), placement) is VIOL
    assert ev(relation("between", "white", "black", "teal"), placement) is UNK


def test_directional_relations_decide_early() -> None:
    placement = grid([[None, "black"], [], ["white"]])
    assert ev(relation("above", "black", "white"), placement) is VIOL
    assert ev(relation("left_of", "white", "black"), placement) is VIOL
    assert ev(relation("above", "black", "teal"), placement) is UNK


SMALL_BOARD = Board(2, 3)
SMALL_PALETTE = Palette(tuple(CLASSIC_PALETTE.colors[:6]))


def _brute_force(clue: Clue, placement: Placement) -> Truth:
    """Evaluate a clue on every completion of a small board and summarise the results."""
    free = [cell for cell in SMALL_BOARD if placement.color_at(cell) is None]
    unplaced = placement.unplaced(SMALL_PALETTE)
    seen = set()
    for cells in permutations(free, len(unplaced)):
        full = Placement({**placement.assignments, **dict(zip(unplaced, cells, strict=True))})
        seen.add(evaluate(clue, full, SMALL_BOARD, SMALL_PALETTE))
    assert seen <= {SAT, VIOL}
    return seen.pop() if len(seen) == 1 else UNK


@st.composite
def small_partial_placements(draw: st.DrawFn) -> Placement:
    colors: list[Color] = draw(st.permutations(SMALL_PALETTE.colors))
    cells = draw(st.permutations(list(SMALL_BOARD)))
    count = draw(st.integers(0, len(colors)))
    return Placement(dict(zip(colors[:count], cells[:count], strict=True)))


ids = st.sampled_from([color.id for color in SMALL_PALETTE])


@st.composite
def primitive_clues(draw: st.DrawFn) -> Clue:
    if draw(st.booleans()):
        kind = draw(st.sampled_from(sorted(RELATION_KINDS)))
        arity = RELATION_KINDS[kind].arity
        colors = draw(st.lists(ids, min_size=arity, max_size=arity, unique=True))
        return relation(kind, *colors)
    kind = draw(st.sampled_from(sorted(PROPERTY_KINDS)))
    index = draw(st.integers(0, 2)) if PROPERTY_KINDS[kind].index else None
    return prop(kind, draw(ids), index)


@given(primitive_clues(), small_partial_placements())
def test_primitive_clues_are_unknown_only_when_completions_disagree(
    clue: Relation | Property, placement: Placement
) -> None:
    assert evaluate(clue, placement, SMALL_BOARD, SMALL_PALETTE) is _brute_force(clue, placement)


refs_with_initials = st.one_of(ids, st.sampled_from(sorted({c.initial for c in SMALL_PALETTE})))


@st.composite
def primitive_clues_with_initials(draw: st.DrawFn) -> Clue:
    if draw(st.booleans()):
        kind = draw(st.sampled_from(sorted(RELATION_KINDS)))
        arity = RELATION_KINDS[kind].arity
        return relation(kind, *draw(st.lists(refs_with_initials, min_size=arity, max_size=arity)))
    kind = draw(st.sampled_from(sorted(PROPERTY_KINDS)))
    index = draw(st.integers(0, 2)) if PROPERTY_KINDS[kind].index else None
    return prop(kind, draw(refs_with_initials), index)


@given(primitive_clues_with_initials(), small_partial_placements())
def test_clues_with_initials_are_sound(clue: Clue, placement: Placement) -> None:
    # Initials are decided one candidate color at a time, so they may stay UNKNOWN when a
    # joint search would decide them, but a decided answer must hold on every completion.
    truth = evaluate(clue, placement, SMALL_BOARD, SMALL_PALETTE)
    if truth is not UNK:
        assert truth is _brute_force(clue, placement)
    negated = evaluate(Not(clue), placement, SMALL_BOARD, SMALL_PALETTE)
    if negated is not UNK:
        assert negated is _brute_force(Not(clue), placement)


# --------------------------------------------------------------------------- initials


@pytest.mark.parametrize(
    ("clue", "expected"),
    [
        (relation("next_to", "B", "M"), SAT),  # brown sits next to magenta
        (relation("next_to", "black", "M"), VIOL),
        (prop("in_corner", "C"), SAT),  # coral
        (prop("in_corner", "M"), VIOL),
        (relation("knows", "B", "B"), SAT),  # black and brown are two different B colors
        (relation("knows", "T", "T"), VIOL),  # teal cannot know itself
        (prop("in_corner", "Z"), VIOL),  # no Z color at all
        (Not(prop("in_corner", "M")), SAT),
    ],
)
def test_initials_on_a_full_board(clue: Clue, expected: Truth) -> None:
    assert ev(clue) is expected


def test_initials_are_not_searched_jointly() -> None:
    # Black, Brown and White go on the three free cells, two of which are corners, so some
    # B color always lands in a corner. Each B on its own might not, so this stays open.
    placement = FULL.without(CLASSIC_PALETTE.by_id("black"))
    placement = placement.without(CLASSIC_PALETTE.by_id("coral"))
    placement = placement.without(CLASSIC_PALETTE.by_id("magenta"))
    for color_id in ("brown", "white"):
        placement = placement.without(CLASSIC_PALETTE.by_id(color_id))
    placement = placement.with_color(CLASSIC_PALETTE.by_id("coral"), Cell(0, 1))
    placement = placement.with_color(CLASSIC_PALETTE.by_id("magenta"), Cell(2, 3))
    assert placement.unplaced(CLASSIC_PALETTE) == tuple(
        CLASSIC_PALETTE.by_id(i) for i in ("black", "brown", "white")
    )
    assert ev(prop("in_corner", "B"), placement) is UNK


def test_initials_stay_unknown_while_any_candidate_is_undecided() -> None:
    black_in_center = grid([[], [None, "black"]])
    assert ev(prop("in_corner", "B"), black_in_center) is UNK
    both_in_center = grid([[], [None, "black", "brown"]])
    assert ev(prop("in_corner", "B"), both_in_center) is VIOL
    brown_in_corner = grid([["brown"], [None, "black"]])
    assert ev(prop("in_corner", "B"), brown_in_corner) is SAT
    assert ev(Not(prop("in_corner", "B")), brown_in_corner) is VIOL


# --------------------------------------------------------------------------- combinators

_PARTIAL = grid([["black", "brown"]])
LEAF = {
    SAT: prop("in_corner", "black"),
    VIOL: prop("in_corner", "brown"),
    UNK: prop("in_corner", "teal"),
}


def test_the_leaves_used_for_combinators_have_the_intended_values() -> None:
    for truth, leaf in LEAF.items():
        assert ev(leaf, _PARTIAL) is truth


@pytest.mark.parametrize(("inner", "expected"), [(SAT, VIOL), (VIOL, SAT), (UNK, UNK)])
def test_not_is_kleene(inner: Truth, expected: Truth) -> None:
    assert ev(Not(LEAF[inner]), _PARTIAL) is expected


@pytest.mark.parametrize(
    ("a", "b", "conjunction", "disjunction"),
    [
        (SAT, SAT, SAT, SAT),
        (SAT, VIOL, VIOL, SAT),
        (SAT, UNK, UNK, SAT),
        (VIOL, VIOL, VIOL, VIOL),
        (VIOL, UNK, VIOL, UNK),
        (UNK, UNK, UNK, UNK),
    ],
)
def test_and_or_are_kleene(a: Truth, b: Truth, conjunction: Truth, disjunction: Truth) -> None:
    for pair in ((LEAF[a], LEAF[b]), (LEAF[b], LEAF[a])):
        assert ev(And(pair), _PARTIAL) is conjunction
        assert ev(Or(pair), _PARTIAL) is disjunction


@pytest.mark.parametrize(
    ("subs", "expected"), [((VIOL, VIOL), SAT), ((VIOL, UNK), UNK), ((SAT,), VIOL)]
)
def test_exactly_zero(subs: tuple[Truth, ...], expected: Truth) -> None:
    assert ev(Exactly(0, tuple(LEAF[truth] for truth in subs)), _PARTIAL) is expected


@pytest.mark.parametrize(
    ("n", "subs", "exactly", "at_least"),
    [
        (1, (SAT, VIOL, VIOL), SAT, SAT),
        (1, (SAT, SAT, VIOL), VIOL, SAT),
        (1, (SAT, UNK, VIOL), UNK, SAT),
        (2, (SAT, UNK, VIOL), UNK, UNK),
        (2, (SAT, VIOL, VIOL), VIOL, VIOL),
        (2, (UNK, UNK, UNK), UNK, UNK),
    ],
)
def test_counting_combinators(
    n: int, subs: tuple[Truth, ...], exactly: Truth, at_least: Truth
) -> None:
    clues = tuple(LEAF[truth] for truth in subs)
    assert ev(Exactly(n, clues), _PARTIAL) is exactly
    assert ev(AtLeast(n, clues), _PARTIAL) is at_least


# --------------------------------------------------------------------------- board rules

ROWS = BoardRule("rows_alphabetical")
COLUMNS = BoardRule("columns_alphabetical")


def test_alphabetical_rules_on_full_boards() -> None:
    assert ev(ROWS) is SAT
    assert ev(COLUMNS) is SAT
    swapped = grid(
        [
            ["brown", "black", "cobalt", "coral"],
            ["emerald", "magenta", "mint", "mustard"],
            ["orange", "purple", "teal", "white"],
        ]
    )
    assert ev(ROWS, swapped) is VIOL
    assert ev(COLUMNS, swapped) is SAT
    rows_swapped = grid(
        [
            ["emerald", "magenta", "mint", "mustard"],
            ["black", "brown", "cobalt", "coral"],
            ["orange", "purple", "teal", "white"],
        ]
    )
    assert ev(ROWS, rows_swapped) is SAT
    assert ev(COLUMNS, rows_swapped) is VIOL


def test_alphabetical_rules_on_partial_boards() -> None:
    assert ev(ROWS, Placement()) is UNK
    # Placed cubes in order, with room between them: still open.
    assert ev(ROWS, grid([["black", None, None, "white"]])) is UNK
    # Placed cubes out of order: already broken.
    assert ev(ROWS, grid([["coral", None, None, "black"]])) is VIOL
    # Nothing sorts after White, so the cells to its right can never be filled in order.
    assert ev(ROWS, grid([["white"]])) is VIOL
    # No color sorts strictly between Black and Brown to fill the gap.
    assert ev(ROWS, grid([["black", None, "brown"]])) is VIOL
    # Columns read top to bottom.
    assert ev(COLUMNS, grid([["teal"], [], ["black"]])) is VIOL
    assert ev(COLUMNS, grid([["black"], [], ["teal"]])) is UNK


def test_alphabetical_rule_waits_for_the_last_cubes() -> None:
    # Teal and White are left for the last two cells, in either order.
    almost = FULL.without(CLASSIC_PALETTE.by_id("teal")).without(CLASSIC_PALETTE.by_id("white"))
    assert ev(ROWS, almost) is UNK
