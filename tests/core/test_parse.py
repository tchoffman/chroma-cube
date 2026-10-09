import contextlib
import time

import pytest
from hypothesis import given
from hypothesis import strategies as st

from chroma_cube.core import CLASSIC_PALETTE, Board, Color, Palette
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
from chroma_cube.core.parse import ClueParseError, parse_clue, parse_clues
from chroma_cube.core.render import render
from tests.core.strategies import clues, color_refs


def parse(text: str) -> Clue:
    return parse_clue(text, CLASSIC_PALETTE)


def canonical(clue: Clue) -> Clue:
    """The clue with one-clue `and`/`or` collapsed: they render exactly like their only part."""
    match clue:
        case And(clues=(only,)) | Or(clues=(only,)):
            return canonical(only)
        case And(clues=parts):
            return And(tuple(canonical(part) for part in parts))
        case Or(clues=parts):
            return Or(tuple(canonical(part) for part in parts))
        case Not(clue=inner):
            return Not(canonical(inner))
        case Exactly(n=n, clues=parts):
            return Exactly(n, tuple(canonical(part) for part in parts))
        case AtLeast(n=n, clues=parts):
            return AtLeast(n, tuple(canonical(part) for part in parts))
    return clue


# --------------------------------------------------------------------------- round trip


@given(clues)
def test_parse_inverts_render(clue: Clue) -> None:
    assert parse(render(clue, CLASSIC_PALETTE)) == canonical(clue)


@given(clues)
def test_render_parse_render_is_the_identity(clue: Clue) -> None:
    text = render(canonical(clue), CLASSIC_PALETTE)
    assert render(parse(text), CLASSIC_PALETTE) == text


@st.composite
def either_ors(draw: st.DrawFn) -> Or:
    """An `or` of like clauses that differ in their first color: the kind the renderer
    shortens to "Either Teal or Black ..."."""
    subjects = draw(st.lists(color_refs, min_size=2, max_size=3, unique=True))
    if draw(st.booleans()):
        kind = draw(st.sampled_from(sorted(PROPERTY_KINDS)))
        index = draw(st.integers(0, 2)) if PROPERTY_KINDS[kind].index else None
        return Or(tuple(Property(kind, subject, index) for subject in subjects))
    kind = draw(st.sampled_from(sorted(k for k, v in RELATION_KINDS.items() if v.arity == 2)))
    other = draw(color_refs)
    return Or(tuple(Relation(kind, (subject, other)) for subject in subjects))


@given(either_ors())
def test_shortened_either_or_round_trips(clue: Or) -> None:
    assert parse(render(clue, CLASSIC_PALETTE)) == clue
    assert parse(render(Not(clue), CLASSIC_PALETTE)) == Not(clue)
    nested = And((prop("in_corner", "black"), clue))
    assert parse(render(nested, CLASSIC_PALETTE)) == nested


def test_card_one_either_or_round_trips() -> None:
    text = "Either Teal or Black is in the same row as Cobalt."
    clue = parse(text)
    assert clue == Or(
        (relation("same_row", "teal", "cobalt"), relation("same_row", "black", "cobalt"))
    )
    assert render(clue, CLASSIC_PALETTE) + "." == text


def test_row_names_follow_the_board() -> None:
    tall = Board(5, 4)
    for index in range(5):
        clue = prop("in_row", "black", index)
        assert parse_clue(render(clue, CLASSIC_PALETTE, tall), CLASSIC_PALETTE, tall) == clue


def test_far_columns_round_trip() -> None:
    wide = Board(3, 23)
    for index in range(23):
        clue = prop("in_col", "black", index)
        assert parse_clue(render(clue, CLASSIC_PALETTE, wide), CLASSIC_PALETTE, wide) == clue


# --------------------------------------------------------------------------- variants


@pytest.mark.parametrize(
    ("text", "clue"),
    [
        ("Black sits next to White", relation("next_to", "black", "white")),
        ("Black is next to White", relation("next_to", "black", "white")),
        ("Black is beside White", relation("next_to", "black", "white")),
        ("Black doesn't sit next to White", Not(relation("next_to", "black", "white"))),
        ("Black does not sit next to White", Not(relation("next_to", "black", "white"))),
        ("Black isn't next to White", Not(relation("next_to", "black", "white"))),
        ("Black is not beside White", Not(relation("next_to", "black", "white"))),
        ("Black doesn't know White", Not(relation("knows", "black", "white"))),
        ("Black does not know White", Not(relation("knows", "black", "white"))),
        ("Black is not above White", Not(relation("above", "black", "white"))),
        ("Black and White are not in the same row", Not(relation("same_row", "black", "white"))),
        ("Black is in the same row as White", relation("same_row", "black", "white")),
        ("Black is to the left of White", relation("left_of", "black", "white")),
        ("Black is in a corner.", prop("in_corner", "black")),
        ("black is in a corner", prop("in_corner", "black")),
        ("BLACK is in a corner", prop("in_corner", "black")),
        ("B is in a corner", prop("in_corner", "B")),
        ("Black is in the corner", prop("in_corner", "black")),
        ("Black is on an edge", prop("on_edge", "black")),
        ("Black is on the edge", prop("on_edge", "black")),
        ("Black isn't on the edge", Not(prop("on_edge", "black"))),
        ("Black is in the center", prop("in_center", "black")),
        ("Black is in the middle", prop("in_center", "black")),
        ("Black is in the middle row", prop("in_row", "black", 1)),
        ("Black is in the top row", prop("in_row", "black", 0)),
        ("Black is in the bottom row", prop("in_row", "black", 2)),
        ("Black is in the third row", prop("in_row", "black", 2)),
        ("Black is in row 1", prop("in_row", "black", 0)),
        ("Black is in the first column", prop("in_col", "black", 0)),
        ("Black is in the fourth column", prop("in_col", "black", 3)),
        ("Black is in column 2", prop("in_col", "black", 1)),
        ("Black isn't in column 4", Not(prop("in_col", "black", 3))),
        ("It is not true that Black knows White", Not(relation("knows", "black", "white"))),
    ],
)
def test_leaf_variants(text: str, clue: Clue) -> None:
    assert parse(text) == clue


CORNER_B = prop("in_corner", "black")
CORNER_W = prop("in_corner", "white")
CORNER_T = prop("in_corner", "teal")


@pytest.mark.parametrize(
    ("text", "clue"),
    [
        ("Either Black is in a corner or White is in a corner", Or((CORNER_B, CORNER_W))),
        ("Black is in a corner or White is in a corner", Or((CORNER_B, CORNER_W))),
        (
            "Black is in a corner, White is in a corner or Teal is in a corner",
            Or((CORNER_B, CORNER_W, CORNER_T)),
        ),
        (
            "Either Black is in a corner, White is in a corner, or Teal is in a corner",
            Or((CORNER_B, CORNER_W, CORNER_T)),
        ),
        (
            "Black is in a corner, White is in a corner and Teal is in a corner",
            And((CORNER_B, CORNER_W, CORNER_T)),
        ),
        (
            "Black is in a corner, White is in a corner, and Teal is in a corner",
            And((CORNER_B, CORNER_W, CORNER_T)),
        ),
        (
            "Black is in a corner and White is in a corner and Teal is in a corner",
            And((CORNER_B, CORNER_W, CORNER_T)),
        ),
        ("Black is in a corner but White is in a corner", And((CORNER_B, CORNER_W))),
        ("Either Black or White is in a corner", Or((CORNER_B, CORNER_W))),
        ("Black or White is in a corner", Or((CORNER_B, CORNER_W))),
        (
            "Black knows White, Teal, and Mint",
            And(
                (
                    relation("knows", "black", "white"),
                    relation("knows", "black", "teal"),
                    relation("knows", "black", "mint"),
                )
            ),
        ),
        (
            "Exactly 2 of these are true: Black is in a corner; White is in a corner",
            Exactly(2, (CORNER_B, CORNER_W)),
        ),
        (
            "at least one of these is true: Black is in a corner; White is in a corner.",
            AtLeast(1, (CORNER_B, CORNER_W)),
        ),
        ("(Black is in a corner)", CORNER_B),
        ("every row is in alphabetical order from left to right", BoardRule("rows_alphabetical")),
    ],
)
def test_compound_variants(text: str, clue: Clue) -> None:
    assert parse(text) == clue


def test_merged_objects_do_not_swallow_a_following_clause() -> None:
    assert parse("Black knows White and Teal and Mint are in the same row") == And(
        (relation("knows", "black", "white"), relation("same_row", "teal", "mint"))
    )


def test_game_examples() -> None:
    """The clue sentences quoted in docs/GAME.md."""
    assert parse("Coral and Magenta are in the same column.") == relation(
        "same_column", "coral", "magenta"
    )
    assert parse("Black sits next to Magenta.") == relation("next_to", "black", "magenta")
    assert parse("Either Teal or Black is in the same row as Cobalt.") == Or(
        (relation("same_row", "teal", "cobalt"), relation("same_row", "black", "cobalt"))
    )
    assert parse("White isn't in a corner, but Mustard is.") == And(
        (Not(prop("in_corner", "white")), prop("in_corner", "mustard"))
    )
    assert parse("Mint knows Cobalt, Magenta, and Brown.") == And(
        (
            relation("knows", "mint", "cobalt"),
            relation("knows", "mint", "magenta"),
            relation("knows", "mint", "brown"),
        )
    )


@pytest.mark.parametrize(
    "text",
    [
        "Black knows White, but Teal is",
        "Black is in a corner but Teal does",
        "Black isn't in a corner, but Teal doesn't",
        "Black doesn't know White, but Teal isn't",
    ],
)
def test_ellipsis_verb_must_match_the_first_clause(text: str) -> None:
    with pytest.raises(ClueParseError):
        parse(text)


def test_ellipsis_follows_the_verb_of_a_variant() -> None:
    assert parse("Black is next to White, but Teal isn't") == And(
        (relation("next_to", "black", "white"), Not(relation("next_to", "teal", "white")))
    )


def test_ellipsis_can_negate() -> None:
    assert parse("Black is in a corner, but White isn't") == And((CORNER_B, Not(CORNER_W)))
    assert parse("Black knows Teal but White doesn't") == And(
        (relation("knows", "black", "teal"), Not(relation("knows", "white", "teal")))
    )


def test_multi_word_color_names() -> None:
    palette = Palette((Color("sky", "Sky Blue", "#87ceeb"), Color("sea", "Sea", "#2e8b57")))
    assert parse_clue("Sky Blue sits next to Sea", palette) == relation("next_to", "sky", "sea")


def test_color_names_with_punctuation() -> None:
    palette = Palette(
        (
            Color("black", "Black", "#000000"),
            Color("off_white", "Off-White", "#faf9f6"),
            Color("rnb", "R&B Red", "#aa0000"),
        )
    )
    assert parse_clue("Black is in a corner", palette) == prop("in_corner", "black")
    assert parse_clue("off-white sits next to R&B Red", palette) == relation(
        "next_to", "off_white", "rnb"
    )
    clue = Or((prop("in_corner", "off_white"), prop("in_corner", "rnb")))
    assert parse_clue(render(clue, palette), palette) == clue
    with pytest.raises(ClueParseError) as caught:
        parse_clue("Black is in a corner & Off-White", palette)
    assert caught.value.position == 21


# --------------------------------------------------------------------------- many clues


def test_parse_clues_reads_one_clue_per_line() -> None:
    text = """
    1. Black is in a corner.
    2) White is on an edge

    Teal knows Mint
    """
    assert parse_clues(text, CLASSIC_PALETTE) == (
        CORNER_B,
        prop("on_edge", "white"),
        relation("knows", "teal", "mint"),
    )


def test_parse_clues_reports_positions_in_the_whole_text() -> None:
    text = "Black is in a corner\nWhite is on an ledge"
    with pytest.raises(ClueParseError) as caught:
        parse_clues(text, CLASSIC_PALETTE)
    assert caught.value.position == text.index("ledge")


# --------------------------------------------------------------------------- errors


@pytest.mark.parametrize(
    ("text", "position", "fragment"),
    [
        ("", 0, "empty"),
        ("Purpel is in a corner", 0, "unknown color 'Purpel'"),
        ("Black is in a cornr", 14, "found 'cornr'"),
        ("Black is in a corner Teal", 21, "the end of the clue"),
        ("Black sits next to", 18, "found the end of the clue"),
        ("Black is in the fourth row", 16, "3 rows"),
        ("Black is in column 5", 19, "4 columns"),
        ("Black is in a corner & White", 21, "'&'"),
        ("Exactly three of these are true: Black is in a corner; White is in a corner", 8, "2"),
        ("At least zero of these are true: Black is in a corner", 9, "at least"),
        ("(Black is in a corner", 21, "')'"),
        ("Black is in a corner and White is on an edge or Teal is in the center", 45, "'or'"),
        ("Black is. in a corner", 8, "'.'"),
    ],
)
def test_errors_point_at_the_problem(text: str, position: int, fragment: str) -> None:
    with pytest.raises(ClueParseError) as caught:
        parse(text)
    assert caught.value.position == position
    assert fragment in caught.value.message
    assert str(position) in str(caught.value)


def test_parse_error_is_a_value_error() -> None:
    assert issubclass(ClueParseError, ValueError)


# --------------------------------------------------------------------------- limits


def _parse_time(text: str) -> float:
    start = time.perf_counter()
    with contextlib.suppress(ClueParseError):
        parse(text)
    return time.perf_counter() - start


@pytest.mark.parametrize(
    "text",
    [
        ("Black knows White" + ", Teal" * 400)[:2000],
        ("Black knows White" + " or Teal" * 300)[:2000],
        ("Either Black" + ", Teal" * 400)[:2000],
        ("Black is in a corner and " * 100)[:2000],
        ("(Black is in a corner or " * 100)[:2000],
        ("zq " * 700)[:2000],
    ],
)
def test_long_garbage_fails_fast(text: str) -> None:
    assert len(text) == 2000
    assert _parse_time(text + " ???") < 0.1


def test_a_long_valid_list_parses_fast() -> None:
    text = "Black knows White" + ", Teal" * 38 + " and Mint"
    start = time.perf_counter()
    clue = parse(text)
    assert time.perf_counter() - start < 0.1
    assert isinstance(clue, And) and len(clue.clues) == 40
    corners = ", ".join(["Black is in a corner"] * 39) + " and White is in a corner"
    assert _parse_time(corners) < 0.1
    assert len(parse(corners).clues) == 40  # type: ignore[union-attr]


def test_alternatives_stop_at_three() -> None:
    assert parse("Either Black, White or Teal is in a corner") == Or((CORNER_B, CORNER_W, CORNER_T))
    with pytest.raises(ClueParseError):
        parse("Either Black, White, Mint or Teal is in a corner")


def test_deep_brackets_raise_a_parse_error() -> None:
    sixteen = "(" * 16 + "Black is in a corner" + ")" * 16
    assert parse(sixteen) == CORNER_B
    text = "(" * 400 + "Black is in a corner" + ")" * 400
    with pytest.raises(ClueParseError) as caught:
        parse(text)
    assert caught.value.position == 16
    assert "deep" in caught.value.message


def test_deep_negation_raises_a_parse_error() -> None:
    text = "it's not true that " * 400 + "Black is in a corner"
    with pytest.raises(ClueParseError) as caught:
        parse(text)
    assert "deep" in caught.value.message
