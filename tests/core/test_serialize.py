import json

import pytest
from hypothesis import given

from chroma_cube.core import CLASSIC_PALETTE
from chroma_cube.core.clues import (
    And,
    AtLeast,
    BoardRule,
    Clue,
    Exactly,
    Not,
    Or,
    prop,
    relation,
)
from chroma_cube.core.render import render
from chroma_cube.core.serialize import clue_from_dict, clue_to_dict
from tests.core.strategies import clues


def test_leaf_shapes() -> None:
    assert clue_to_dict(relation("next_to", "black", "M")) == {
        "type": "relation",
        "kind": "next_to",
        "colors": ["black", "M"],
    }
    assert clue_to_dict(prop("in_corner", "black")) == {
        "type": "property",
        "kind": "in_corner",
        "color": "black",
    }
    assert clue_to_dict(prop("in_row", "B", 2)) == {
        "type": "property",
        "kind": "in_row",
        "color": "B",
        "index": 2,
    }
    assert clue_to_dict(BoardRule("rows_alphabetical")) == {
        "type": "board_rule",
        "kind": "rows_alphabetical",
    }


def test_combinator_shapes() -> None:
    leaf = prop("in_corner", "black")
    leaf_dict = clue_to_dict(leaf)
    assert clue_to_dict(Not(leaf)) == {"type": "not", "clue": leaf_dict}
    assert clue_to_dict(And((leaf,))) == {"type": "and", "clues": [leaf_dict]}
    assert clue_to_dict(Or((leaf,))) == {"type": "or", "clues": [leaf_dict]}
    assert clue_to_dict(Exactly(1, (leaf,))) == {"type": "exactly", "n": 1, "clues": [leaf_dict]}
    assert clue_to_dict(AtLeast(1, (leaf,))) == {"type": "at_least", "n": 1, "clues": [leaf_dict]}


@given(clues)
def test_round_trip_through_json(clue: Clue) -> None:
    data = json.loads(json.dumps(clue_to_dict(clue)))
    assert clue_from_dict(data) == clue


@given(clues)
def test_every_generated_clue_renders(clue: Clue) -> None:
    assert render(clue, CLASSIC_PALETTE)


@pytest.mark.parametrize(
    "bad",
    [
        {},
        {"type": "teleport"},
        {"type": "relation", "kind": "hugs", "colors": ["black", "white"]},
        {"type": "relation", "kind": "next_to", "colors": ["black"]},
        {"type": "relation", "kind": "next_to"},
        {"type": "property", "kind": "in_row", "color": "black"},
        {"type": "property", "kind": "in_corner", "color": ""},
        {"type": "and", "clues": []},
        {"type": "exactly", "n": 3, "clues": [{"type": "board_rule", "kind": "rows_alphabetical"}]},
        {"type": "not", "clue": "black"},
        "black",
        {"type": "relation", "kind": "next_to", "colors": "BM"},
        {"type": "property", "kind": "in_row", "color": "black", "index": True},
        {"type": "property", "kind": "in_row", "color": "black", "index": "1"},
        {"type": "property", "kind": "in_row", "color": "black", "index": 1.0},
    ],
)
def test_malformed_data_raises_value_error(bad: object) -> None:
    with pytest.raises(ValueError):
        clue_from_dict(bad)  # type: ignore[arg-type]
