import json

import pytest
from hypothesis import given
from hypothesis import strategies as st

from chroma_cube.core import (
    CLASSIC_BOARD,
    CLASSIC_PALETTE,
    And,
    Board,
    Cell,
    Clue,
    Color,
    Not,
    Palette,
    Placement,
    Puzzle,
    prop,
    puzzle_from_dict,
    puzzle_to_dict,
    relation,
)
from tests.core.strategies import clues

black = CLASSIC_PALETTE.by_id("black")
white = CLASSIC_PALETTE.by_id("white")


def make(**overrides: object) -> Puzzle:
    fields: dict[str, object] = {
        "id": "classic-01",
        "title": "First steps",
        "board": CLASSIC_BOARD,
        "palette": CLASSIC_PALETTE,
        "givens": Placement({black: Cell(0, 0)}),
        "clues": (relation("next_to", "white", "B"), prop("in_corner", "teal")),
    }
    fields.update(overrides)
    return Puzzle(**fields)  # type: ignore[arg-type]


def test_defaults_for_optional_fields() -> None:
    puzzle = make()
    assert puzzle.difficulty == ""
    assert puzzle.notes == ""


def test_rendered_clues() -> None:
    assert make().rendered_clues() == ("White sits next to B", "Teal is in a corner")


def test_rendered_clues_use_the_puzzles_board_for_row_names() -> None:
    tall = make(board=Board(5, 4), clues=(prop("in_row", "teal", 2),))
    assert tall.rendered_clues() == ("Teal is in the third row",)


def test_givens_must_use_palette_colors() -> None:
    stranger = Color("gold", "Gold", "#ffd700")
    with pytest.raises(ValueError):
        make(givens=Placement({stranger: Cell(0, 0)}))


def test_givens_must_be_on_the_board() -> None:
    with pytest.raises(ValueError):
        make(givens=Placement({black: Cell(3, 0)}))


@pytest.mark.parametrize(
    "clue",
    [
        relation("next_to", "white", "gold"),
        Not(prop("in_corner", "gold")),
        prop("in_row", "black", 3),
        prop("in_col", "black", 4),
        And((prop("in_corner", "teal"), prop("in_row", "teal", 7))),
    ],
)
def test_clues_must_name_palette_colors_and_on_board_lines(clue: Clue) -> None:
    with pytest.raises(ValueError):
        make(clues=(clue,))


def test_clues_may_use_any_initial_and_last_row_and_column() -> None:
    make(clues=(prop("in_row", "Z", 2), prop("in_col", "black", 3)))


def test_puzzles_are_hashable_values() -> None:
    assert make() == make()
    assert hash(make()) == hash(make())


def test_dict_shape() -> None:
    data = puzzle_to_dict(make(difficulty="easy", notes="Reconstructed from a walkthrough"))
    assert data["id"] == "classic-01"
    assert data["title"] == "First steps"
    assert data["difficulty"] == "easy"
    assert data["notes"] == "Reconstructed from a walkthrough"
    assert data["board"] == {"rows": 3, "cols": 4}
    assert data["palette"][0] == {"id": "black", "name": "Black", "hex": black.hex}
    assert len(data["palette"]) == 12
    assert data["givens"] == [{"color": "black", "row": 0, "col": 0}]
    assert data["clues"][1] == {"type": "property", "kind": "in_corner", "color": "teal"}


def test_optional_fields_may_be_missing_from_data() -> None:
    data = puzzle_to_dict(make())
    del data["difficulty"], data["notes"]
    assert puzzle_from_dict(data) == make()


@pytest.mark.parametrize(
    "breakage",
    [
        lambda d: d.pop("title"),
        lambda d: d["givens"].append({"color": "gold", "row": 1, "col": 1}),
        lambda d: d["givens"].append({"color": "white", "row": 9, "col": 1}),
        lambda d: d["board"].update(rows="three"),
        lambda d: d["clues"].append({"type": "teleport"}),
        lambda d: d["givens"].append({"color": "black", "row": 1, "col": 1}),
    ],
)
def test_malformed_data_raises_value_error(breakage: object) -> None:
    data = puzzle_to_dict(make())
    breakage(data)  # type: ignore[operator]
    with pytest.raises(ValueError):
        puzzle_from_dict(data)


@st.composite
def puzzles(draw: st.DrawFn) -> Puzzle:
    colors = draw(st.permutations(CLASSIC_PALETTE.colors))
    cells = draw(st.permutations(list(CLASSIC_BOARD)))
    count = draw(st.integers(0, len(colors)))
    text = st.text(max_size=20)
    return Puzzle(
        id=draw(text),
        title=draw(text),
        board=CLASSIC_BOARD,
        palette=Palette(tuple(colors)),
        givens=Placement(dict(zip(colors[:count], cells[:count], strict=True))),
        clues=tuple(draw(st.lists(clues, max_size=4))),
        difficulty=draw(text),
        notes=draw(text),
    )


@given(puzzles())
def test_round_trip_through_json(puzzle: Puzzle) -> None:
    assert puzzle_from_dict(json.loads(json.dumps(puzzle_to_dict(puzzle)))) == puzzle
