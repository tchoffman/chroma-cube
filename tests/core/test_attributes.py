"""Clues about color attributes: neighbours, regions and hue families."""

import json
from itertools import permutations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from chroma_cube.core import (
    BOARD_4X4,
    CLASSIC_BOARD,
    CLASSIC_PALETTE,
    EXTENDED_16,
    Board,
    Cell,
    Color,
    Palette,
    Placement,
    Puzzle,
)
from chroma_cube.core.clues import (
    ATTRIBUTE_KINDS,
    And,
    AttributeClue,
    Clue,
    Not,
    Or,
    Region,
    attribute,
    attribute_clues,
)
from chroma_cube.core.evaluate import Truth, evaluate
from chroma_cube.core.parse import parse_clue
from chroma_cube.core.render import render
from chroma_cube.core.serialize import clue_from_dict, clue_to_dict
from tests.core.helpers import FULL, grid

SAT, VIOL, UNK = Truth.SATISFIED, Truth.VIOLATED, Truth.UNKNOWN


def ev(clue: Clue, placement: Placement = FULL) -> Truth:
    return evaluate(clue, placement, CLASSIC_BOARD, CLASSIC_PALETTE)


corners = Region("corners")
top_row = Region("row", 0)

# FULL is
#   black   brown   cobalt  coral
#   emerald magenta mint    mustard
#   orange  purple  teal    white

# --------------------------------------------------------------------------- nodes


def test_every_kind_is_registered() -> None:
    assert set(ATTRIBUTE_KINDS) == {
        "neighbours_all",
        "neighbours_none",
        "neighbours_some",
        "next_to_family",
        "region_all",
        "region_count",
    }


@pytest.mark.parametrize(
    "build",
    [
        lambda: attribute("teleports", "cool", color="mint"),
        lambda: attribute("neighbours_all", "green", color="mint"),  # a family, not a quality
        lambda: attribute("next_to_family", "cool", color="mint"),  # a quality, not a family
        lambda: attribute("neighbours_all", "cool"),  # no color
        lambda: attribute("neighbours_all", "cool", color="mint", region=corners),
        lambda: attribute("region_all", "cool", color="mint"),
        lambda: attribute("region_all", "cool"),  # no region
        lambda: attribute("region_count", "cool", region=corners),  # no count
        lambda: attribute("region_count", "cool", region=corners, n=-1),
        lambda: attribute("region_all", "cool", region=corners, n=1),
    ],
)
def test_malformed_attribute_clues_are_rejected(build: object) -> None:
    with pytest.raises(ValueError):
        build()  # type: ignore[operator]


@pytest.mark.parametrize(
    ("kind", "index"), [("row", None), ("corners", 0), ("diagonal", None), ("column", -1)]
)
def test_malformed_regions_are_rejected(kind: str, index: int | None) -> None:
    with pytest.raises(ValueError):
        Region(kind, index)


def test_region_cells() -> None:
    assert corners.cells(CLASSIC_BOARD) == (Cell(0, 0), Cell(0, 3), Cell(2, 0), Cell(2, 3))
    assert Region("center").cells(CLASSIC_BOARD) == (Cell(1, 1), Cell(1, 2))
    assert len(Region("edge").cells(CLASSIC_BOARD)) == 10
    assert Region("column", 1).cells(CLASSIC_BOARD) == (Cell(0, 1), Cell(1, 1), Cell(2, 1))
    with pytest.raises(ValueError):
        Region("row", 3).cells(CLASSIC_BOARD)


# --------------------------------------------------------------------------- full boards


@pytest.mark.parametrize(
    ("clue", "expected"),
    [
        # Mint's neighbours: cobalt, magenta, mustard, teal.
        (attribute("neighbours_all", "cool", color="mint"), VIOL),
        (attribute("neighbours_some", "cool", color="mint"), SAT),
        (attribute("neighbours_none", "warm", color="mint"), VIOL),
        (attribute("neighbours_none", "neutral", color="mint"), SAT),
        # Orange's neighbours: emerald and purple.
        (attribute("neighbours_all", "cool", color="orange"), SAT),
        (attribute("neighbours_none", "warm", color="orange"), SAT),
        (attribute("neighbours_some", "dark", color="orange"), SAT),
        (attribute("neighbours_all", "dark", color="orange"), VIOL),
        (attribute("next_to_family", "blue", color="mint"), SAT),
        (attribute("next_to_family", "green", color="mint"), VIOL),
        (attribute("next_to_family", "yellow", color="white"), SAT),
        # Corners: black, coral, orange, white.
        (attribute("region_all", "light", region=corners), VIOL),
        (attribute("region_count", "warm", region=corners, n=2), SAT),
        (attribute("region_count", "neutral", region=corners, n=1), VIOL),
        (attribute("region_all", "light", region=Region("row", 1)), SAT),
        (attribute("region_all", "light", region=Region("center")), SAT),
        (attribute("region_count", "dark", region=top_row, n=3), SAT),
        (attribute("region_count", "dark", region=top_row, n=2), VIOL),
        (attribute("region_count", "warm", region=Region("column", 3), n=2), SAT),
        (attribute("region_all", "cool", region=Region("edge")), VIOL),
    ],
)
def test_attribute_clues_on_a_full_board(clue: Clue, expected: Truth) -> None:
    assert ev(clue) is expected
    assert ev(Not(clue)) is {SAT: VIOL, VIOL: SAT}[expected]


@pytest.mark.parametrize(
    ("clue", "expected"),
    [
        (attribute("neighbours_all", "cool", color="O"), SAT),  # orange
        (attribute("neighbours_all", "cool", color="M"), VIOL),  # no M has only cool neighbours
        (attribute("next_to_family", "red", color="C"), SAT),  # cobalt sits next to coral
        (attribute("next_to_family", "purple", color="C"), VIOL),
        (attribute("neighbours_some", "warm", color="Z"), VIOL),
    ],
)
def test_attribute_clues_with_initials(clue: Clue, expected: Truth) -> None:
    assert ev(clue) is expected


# --------------------------------------------------------------------------- partial boards


def test_neighbours_wait_for_empty_neighbour_cells() -> None:
    clue = attribute("neighbours_all", "cool", color="orange")
    assert ev(clue, grid([[], ["emerald"], ["orange"]])) is UNK
    assert ev(clue, grid([[], ["emerald"], ["orange", "purple"]])) is SAT
    assert ev(clue, grid([[], ["coral"], ["orange"]])) is VIOL


def test_an_unplaced_subject_is_tried_on_every_free_cell() -> None:
    assert ev(attribute("neighbours_some", "cool", color="mint"), Placement()) is UNK
    # Every free cell for Mint touches a placed cool color only if the board says so.
    only_corner = grid(
        [
            [None, "teal", "brown", "coral"],
            ["emerald", "magenta", "black", "mustard"],
            ["orange", "purple", "cobalt", "white"],
        ]
    )
    assert ev(attribute("neighbours_all", "cool", color="mint"), only_corner) is SAT


def test_a_region_is_decided_when_the_unplaced_colors_agree() -> None:
    # Every unplaced color is light, so the empty top-row cells will be light too.
    placement = grid(
        [
            [None, None, None, None],
            ["black", "brown", "cobalt", "purple"],
            ["teal", "white", "mint", "orange"],
        ]
    )
    assert ev(attribute("region_all", "light", region=top_row), placement) is SAT
    assert ev(attribute("region_count", "warm", region=top_row, n=3), placement) is SAT
    assert ev(attribute("region_count", "warm", region=top_row, n=4), placement) is VIOL


def test_a_count_is_violated_once_too_many_are_placed() -> None:
    clue = attribute("region_count", "warm", region=corners, n=1)
    assert ev(clue, grid([["coral", None, None, "orange"]])) is VIOL
    assert ev(clue, grid([["coral"]])) is UNK


SMALL_BOARD = Board(2, 3)
SMALL_PALETTES = [
    Palette(tuple(CLASSIC_PALETTE.colors[:6])),
    Palette(tuple(CLASSIC_PALETTE.colors[6:11])),  # fewer colors than cells
]


def _brute_force(clue: Clue, placement: Placement, palette: Palette) -> Truth:
    free = [cell for cell in SMALL_BOARD if placement.color_at(cell) is None]
    unplaced = placement.unplaced(palette)
    seen = set()
    for cells in permutations(free, len(unplaced)):
        full = Placement({**placement.assignments, **dict(zip(unplaced, cells, strict=True))})
        seen.add(evaluate(clue, full, SMALL_BOARD, palette))
    return seen.pop() if len(seen) == 1 else UNK


@st.composite
def small_cases(draw: st.DrawFn, initials: bool) -> tuple[Clue, Placement, Palette]:
    palette = draw(st.sampled_from(SMALL_PALETTES))
    colors: list[Color] = draw(st.permutations(palette.colors))
    cells = draw(st.permutations(list(SMALL_BOARD)))
    count = draw(st.integers(0, len(colors)))
    placement = Placement(dict(zip(colors[:count], cells[:count], strict=True)))
    candidates = [c for c in attribute_clues(SMALL_BOARD, palette) if c.n is None or c.n <= 3]
    clue = draw(st.sampled_from(candidates))
    if initials and clue.color is not None:
        clue = attribute(clue.kind, clue.value, color=palette.by_id(clue.color.key).initial)
    return clue, placement, palette


@given(small_cases(initials=False))
def test_named_attribute_clues_are_exact(case: tuple[Clue, Placement, Palette]) -> None:
    clue, placement, palette = case
    assert evaluate(clue, placement, SMALL_BOARD, palette) is _brute_force(clue, placement, palette)


@given(small_cases(initials=True))
def test_attribute_clues_with_initials_are_sound(case: tuple[Clue, Placement, Palette]) -> None:
    clue, placement, palette = case
    truth = evaluate(clue, placement, SMALL_BOARD, palette)
    if truth is not UNK:
        assert truth is _brute_force(clue, placement, palette)


# --------------------------------------------------------------------------- english


@pytest.mark.parametrize(
    ("clue", "text"),
    [
        (
            attribute("neighbours_all", "cool", color="mint"),
            "Every cube next to Mint is a cool color",
        ),
        (
            Not(attribute("neighbours_all", "cool", color="mint")),
            "Not every cube next to Mint is a cool color",
        ),
        (attribute("neighbours_none", "warm", color="M"), "No cube next to M is a warm color"),
        (
            Not(attribute("neighbours_none", "warm", color="mint")),
            "Some cube next to Mint is a warm color",
        ),
        (attribute("neighbours_some", "dark", color="coral"), "Coral sits next to a dark color"),
        (
            Not(attribute("neighbours_some", "dark", color="coral")),
            "Coral doesn't sit next to a dark color",
        ),
        (
            attribute("next_to_family", "green", color="coral"),
            "Coral sits next to a shade of green",
        ),
        (
            Not(attribute("next_to_family", "grey", color="coral")),
            "Coral doesn't sit next to a shade of grey",
        ),
        (
            attribute("region_all", "warm", region=corners),
            "Every cube in the corners is a warm color",
        ),
        (
            Not(attribute("region_all", "light", region=Region("edge"))),
            "Not every cube on the edge is a light color",
        ),
        (
            attribute("region_all", "cool", region=Region("center")),
            "Every cube in the center is a cool color",
        ),
        (
            attribute("region_count", "light", region=top_row, n=2),
            "Exactly two light colors are in the top row",
        ),
        (
            attribute("region_count", "warm", region=Region("column", 1), n=1),
            "Exactly one warm color is in the second column",
        ),
        (
            Not(attribute("region_count", "dark", region=corners, n=0)),
            "It's not true that exactly zero dark colors are in the corners",
        ),
        (
            Or(
                (
                    attribute("next_to_family", "blue", color="teal"),
                    attribute("next_to_family", "blue", color="mint"),
                )
            ),
            "Either Teal or Mint sits next to a shade of blue",
        ),
    ],
)
def test_render_and_parse(clue: Clue, text: str) -> None:
    assert render(clue, CLASSIC_PALETTE) == text
    assert parse_clue(text, CLASSIC_PALETTE) == clue


def test_rows_are_named_for_the_board() -> None:
    clue = attribute("region_count", "light", region=Region("row", 2), n=3)
    text = render(clue, EXTENDED_16, BOARD_4X4)
    assert text == "Exactly three light colors are in the third row"
    assert parse_clue(text, EXTENDED_16, BOARD_4X4) == clue


@pytest.mark.parametrize(
    ("text", "clue"),
    [
        (
            "Every cube in the middle is a cool color",
            attribute("region_all", "cool", region=Region("center")),
        ),
        (
            "exactly 2 light colors are in row 1.",
            attribute("region_count", "light", region=top_row, n=2),
        ),
        (
            "Exactly one light colors is in column 2",
            attribute("region_count", "light", region=Region("column", 1), n=1),
        ),
    ],
)
def test_parse_variants(text: str, clue: Clue) -> None:
    assert parse_clue(text, CLASSIC_PALETTE) == clue


def test_short_repeat_of_an_attribute_clause() -> None:
    assert parse_clue("Mint sits next to a cool color, but Teal doesn't", CLASSIC_PALETTE) == And(
        (
            attribute("neighbours_some", "cool", color="mint"),
            Not(attribute("neighbours_some", "cool", color="teal")),
        )
    )


def test_family_names_that_are_also_color_names_parse_as_families() -> None:
    assert parse_clue("Teal sits next to a shade of orange", CLASSIC_PALETTE) == attribute(
        "next_to_family", "orange", color="teal"
    )


# --------------------------------------------------------------------------- data


def test_attribute_clue_shapes() -> None:
    assert clue_to_dict(attribute("neighbours_all", "cool", color="mint")) == {
        "type": "attribute",
        "kind": "neighbours_all",
        "value": "cool",
        "color": "mint",
    }
    assert clue_to_dict(attribute("region_count", "light", region=top_row, n=2)) == {
        "type": "attribute",
        "kind": "region_count",
        "value": "light",
        "region": "row",
        "index": 0,
        "n": 2,
    }
    assert clue_to_dict(attribute("region_all", "warm", region=corners)) == {
        "type": "attribute",
        "kind": "region_all",
        "value": "warm",
        "region": "corners",
    }


@pytest.mark.parametrize(
    "clue",
    [
        attribute("neighbours_none", "dark", color="B"),
        attribute("next_to_family", "pink", color="teal"),
        attribute("region_count", "cool", region=Region("column", 3), n=0),
        Not(attribute("region_all", "neutral", region=Region("edge"))),
    ],
)
def test_attribute_clues_round_trip_through_json(clue: Clue) -> None:
    assert clue_from_dict(json.loads(json.dumps(clue_to_dict(clue)))) == clue


@pytest.mark.parametrize(
    "bad",
    [
        {"type": "attribute", "kind": "region_all", "value": "warm"},
        {"type": "attribute", "kind": "region_all", "value": "warm", "region": "row"},
        {"type": "attribute", "kind": "region_all", "value": "warm", "region": 3},
        {"type": "attribute", "kind": "neighbours_all", "value": "hot", "color": "mint"},
        {"type": "attribute", "kind": "region_count", "value": "warm", "region": "edge", "n": True},
    ],
)
def test_malformed_attribute_data_raises_value_error(bad: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        clue_from_dict(bad)


# --------------------------------------------------------------------------- puzzles


def test_puzzles_check_attribute_clues_against_the_board_and_palette() -> None:
    def puzzle(clue: Clue) -> Puzzle:
        return Puzzle("p", "P", CLASSIC_BOARD, CLASSIC_PALETTE, Placement(), (clue,))

    puzzle(attribute("region_count", "warm", region=corners, n=4))
    with pytest.raises(ValueError):
        puzzle(attribute("region_count", "warm", region=corners, n=5))
    with pytest.raises(ValueError):
        puzzle(attribute("region_all", "warm", region=Region("row", 3)))
    with pytest.raises(ValueError):
        puzzle(attribute("neighbours_all", "warm", color="gold"))


# --------------------------------------------------------------------------- generator hook


def test_attribute_clues_lists_every_instance_once() -> None:
    found = attribute_clues(CLASSIC_BOARD, CLASSIC_PALETTE)
    assert len(found) == len(set(found))
    assert {clue.kind for clue in found} == set(ATTRIBUTE_KINDS)
    assert all(isinstance(clue, AttributeClue) for clue in found)
    assert attribute("neighbours_all", "cool", color="mint") in found
    assert attribute("region_count", "light", region=top_row, n=4) in found
    assert attribute("region_count", "light", region=top_row, n=5) not in found
    for clue in found:
        assert ev(clue) in (SAT, VIOL)


def test_attribute_clues_only_use_values_some_palette_color_has() -> None:
    palette = Palette(tuple(CLASSIC_PALETTE.colors[:3]))  # black, brown, cobalt
    values = {clue.value for clue in attribute_clues(CLASSIC_BOARD, palette)}
    assert "green" not in values and "light" not in values
    assert {"grey", "brown", "blue", "dark", "warm", "cool", "neutral"} <= values


def test_the_middle_row_is_a_row_and_the_middle_is_the_center() -> None:
    assert parse_clue("Every cube in the middle row is a cool color", CLASSIC_PALETTE) == attribute(
        "region_all", "cool", region=Region("row", 1)
    )
