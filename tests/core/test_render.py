import pytest

from chroma_cube.core import CLASSIC_BOARD, CLASSIC_PALETTE, Board, Cell
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
    prop,
    relation,
)
from chroma_cube.core.render import cell_name, render

RELATION_SENTENCES = {
    "same_row": "Black and White are in the same row",
    "same_column": "Black and White are in the same column",
    "next_to": "Black sits next to White",
    "knows": "Black knows White",
    "diagonal": "Black is diagonal to White",
    "above": "Black is above White",
    "below": "Black is below White",
    "left_of": "Black is left of White",
    "right_of": "Black is right of White",
    "directly_above": "Black is directly above White",
    "directly_below": "Black is directly below White",
    "directly_left_of": "Black is directly left of White",
    "directly_right_of": "Black is directly right of White",
    "between": "Black is between White and Teal",
}


def test_every_relation_kind_has_a_sentence() -> None:
    assert set(RELATION_SENTENCES) == set(RELATION_KINDS)


@pytest.mark.parametrize(("kind", "sentence"), RELATION_SENTENCES.items())
def test_relations(kind: str, sentence: str) -> None:
    colors = ("black", "white", "teal")[: RELATION_KINDS[kind].arity]
    assert render(relation(kind, *colors), CLASSIC_PALETTE) == sentence


PROPERTY_SENTENCES: list[tuple[Clue, str]] = [
    (prop("in_corner", "black"), "Black is in a corner"),
    (prop("on_edge", "black"), "Black is on an edge"),
    (prop("in_center", "black"), "Black is in the center"),
    (prop("in_row", "black", 0), "Black is in the top row"),
    (prop("in_row", "black", 1), "Black is in the middle row"),
    (prop("in_row", "black", 2), "Black is in the bottom row"),
    (prop("in_col", "black", 0), "Black is in the first column"),
    (prop("in_col", "black", 1), "Black is in the second column"),
    (prop("in_col", "black", 3), "Black is in the fourth column"),
]


def test_every_property_kind_has_a_sentence() -> None:
    kinds = {clue.kind for clue, _ in PROPERTY_SENTENCES}  # type: ignore[union-attr]
    assert kinds == set(PROPERTY_KINDS)


@pytest.mark.parametrize(("clue", "sentence"), PROPERTY_SENTENCES)
def test_properties(clue: Clue, sentence: str) -> None:
    assert render(clue, CLASSIC_PALETTE) == sentence


def test_row_names_follow_the_board() -> None:
    tall = Board(5, 4)
    assert render(prop("in_row", "black", 0), CLASSIC_PALETTE, tall) == "Black is in the top row"
    assert render(prop("in_row", "black", 2), CLASSIC_PALETTE, tall) == "Black is in the third row"
    assert render(prop("in_row", "black", 4), CLASSIC_PALETTE, tall) == "Black is in the bottom row"


def test_initials_render_as_the_bare_letter() -> None:
    assert render(relation("next_to", "B", "M"), CLASSIC_PALETTE) == "B sits next to M"
    assert render(prop("in_corner", "C"), CLASSIC_PALETTE) == "C is in a corner"


@pytest.mark.parametrize(
    ("clue", "sentence"),
    [
        (Not(prop("in_corner", "black")), "Black isn't in a corner"),
        (Not(prop("in_row", "black", 0)), "Black isn't in the top row"),
        (Not(relation("knows", "black", "white")), "Black doesn't know White"),
        (Not(relation("next_to", "black", "white")), "Black doesn't sit next to White"),
        (Not(relation("same_row", "black", "white")), "Black and White aren't in the same row"),
        (
            Not(And((prop("in_corner", "black"), prop("in_corner", "white")))),
            "It's not true that Black is in a corner and White is in a corner",
        ),
        (Not(Not(prop("in_corner", "black"))), "It's not true that Black isn't in a corner"),
    ],
)
def test_not(clue: Clue, sentence: str) -> None:
    assert render(clue, CLASSIC_PALETTE) == sentence


def test_and_joins_clauses() -> None:
    clue = And((prop("in_corner", "black"), relation("next_to", "teal", "white")))
    assert render(clue, CLASSIC_PALETTE) == "Black is in a corner and Teal sits next to White"
    three = And((prop("in_corner", "black"), prop("on_edge", "teal"), prop("in_center", "mint")))
    assert (
        render(three, CLASSIC_PALETTE)
        == "Black is in a corner, Teal is on an edge and Mint is in the center"
    )


def test_and_of_relations_sharing_the_first_color_merges() -> None:
    clue = And(
        (
            relation("knows", "black", "white"),
            relation("knows", "black", "teal"),
            relation("knows", "black", "mint"),
        )
    )
    assert render(clue, CLASSIC_PALETTE) == "Black knows White, Teal and Mint"
    next_to = And((relation("next_to", "black", "M"), relation("next_to", "black", "teal")))
    assert render(next_to, CLASSIC_PALETTE) == "Black sits next to M and Teal"


def test_and_does_not_merge_when_the_sentence_would_break() -> None:
    clue = And((relation("same_row", "black", "white"), relation("same_row", "black", "teal")))
    assert (
        render(clue, CLASSIC_PALETTE)
        == "Black and White are in the same row and Black and Teal are in the same row"
    )


def test_or() -> None:
    two = Or((prop("in_corner", "black"), relation("knows", "teal", "white")))
    assert render(two, CLASSIC_PALETTE) == "Either Black is in a corner or Teal knows White"
    three = Or((prop("in_corner", "black"), prop("on_edge", "teal"), prop("in_corner", "mint")))
    assert (
        render(three, CLASSIC_PALETTE)
        == "Either Black is in a corner, Teal is on an edge or Mint is in a corner"
    )


def test_nested_compounds_are_bracketed() -> None:
    clue = Or(
        (
            And((prop("in_corner", "black"), prop("in_corner", "white"))),
            Not(prop("in_center", "teal")),
        )
    )
    assert (
        render(clue, CLASSIC_PALETTE)
        == "Either (Black is in a corner and White is in a corner) or Teal isn't in the center"
    )


def test_counting() -> None:
    clues = (prop("in_corner", "black"), prop("in_corner", "teal"), prop("in_corner", "mint"))
    assert (
        render(Exactly(1, clues), CLASSIC_PALETTE)
        == "Exactly one of these is true: Black is in a corner; Teal is in a corner; "
        "Mint is in a corner"
    )
    assert (
        render(AtLeast(2, clues), CLASSIC_PALETTE)
        == "At least two of these are true: Black is in a corner; Teal is in a corner; "
        "Mint is in a corner"
    )


def test_board_rules() -> None:
    assert (
        render(BoardRule("rows_alphabetical"), CLASSIC_PALETTE)
        == "Every row is in alphabetical order from left to right"
    )
    assert (
        render(BoardRule("columns_alphabetical"), CLASSIC_PALETTE)
        == "Every column is in alphabetical order from top to bottom"
    )


def test_fixed_openers_are_lowercased_mid_sentence() -> None:
    clue = Not(Or((prop("in_corner", "black"), prop("on_edge", "white"))))
    assert (
        render(clue, CLASSIC_PALETTE)
        == "It's not true that either Black is in a corner or White is on an edge"
    )
    short = Not(Or((prop("in_corner", "black"), prop("in_corner", "white"))))
    assert (
        render(short, CLASSIC_PALETTE) == "It's not true that either Black or White is in a corner"
    )


def test_far_columns_use_numeric_ordinals() -> None:
    wide = Board(3, 23)
    for index, word in [(5, "sixth"), (6, "7th"), (10, "11th"), (20, "21st"), (22, "23rd")]:
        assert render(prop("in_col", "black", index), CLASSIC_PALETTE, wide) == (
            f"Black is in the {word} column"
        )


def test_and_does_not_merge_when_the_shared_color_is_an_initial() -> None:
    # Each part picks its own B color, so one merged sentence would claim too much.
    clue = And((relation("knows", "B", "white"), relation("knows", "B", "teal")))
    assert render(clue, CLASSIC_PALETTE) == "B knows White and B knows Teal"


def test_a_one_item_or_is_just_its_clue() -> None:
    assert render(Or((prop("in_corner", "black"),)), CLASSIC_PALETTE) == "Black is in a corner"


def test_card_one_either_or_reads_like_the_card() -> None:
    clue = Or((relation("same_row", "teal", "cobalt"), relation("same_row", "black", "cobalt")))
    assert render(clue, CLASSIC_PALETTE) + "." == (
        "Either Teal or Black is in the same row as Cobalt."
    )


@pytest.mark.parametrize(
    ("clue", "sentence"),
    [
        (
            Or((relation("next_to", "teal", "white"), relation("next_to", "mint", "white"))),
            "Either Teal or Mint sits next to White",
        ),
        (
            Or(
                (
                    relation("above", "teal", "white"),
                    relation("above", "mint", "white"),
                    relation("above", "B", "white"),
                )
            ),
            "Either Teal, Mint or B is above White",
        ),
        (
            Or(
                (relation("same_column", "teal", "white"), relation("same_column", "mint", "white"))
            ),
            "Either Teal or Mint is in the same column as White",
        ),
        (
            Or((prop("in_corner", "teal"), prop("in_corner", "mint"))),
            "Either Teal or Mint is in a corner",
        ),
        (
            Or((prop("in_row", "teal", 2), prop("in_row", "M", 2), prop("in_row", "white", 2))),
            "Either Teal, M or White is in the bottom row",
        ),
        (
            And(
                (prop("in_corner", "black"), Or((prop("on_edge", "teal"), prop("on_edge", "mint"))))
            ),
            "Black is in a corner and (either Teal or Mint is on an edge)",
        ),
    ],
)
def test_either_or_sharing_a_color_collapses(clue: Clue, sentence: str) -> None:
    assert render(clue, CLASSIC_PALETTE) == sentence


@pytest.mark.parametrize(
    "clue",
    [
        # The shared color is first: swapping it to the end would change the clue.
        Or((relation("next_to", "white", "teal"), relation("next_to", "white", "mint"))),
        # Different kinds, rows or second colors.
        Or((relation("next_to", "teal", "white"), relation("knows", "mint", "white"))),
        Or((relation("next_to", "teal", "white"), relation("next_to", "mint", "black"))),
        Or((prop("in_row", "teal", 0), prop("in_row", "mint", 1))),
        # Negated branches, a three-color relation, four branches, a repeated color.
        Or((Not(prop("in_corner", "teal")), Not(prop("in_corner", "mint")))),
        Or(
            (
                relation("between", "teal", "white", "black"),
                relation("between", "mint", "white", "black"),
            )
        ),
        Or(tuple(prop("in_corner", color) for color in ("teal", "mint", "white", "black"))),
        Or((prop("in_corner", "teal"), prop("in_corner", "teal"))),
        # A shared initial: each branch picks its own B, so one sentence would say too much.
        Or((relation("knows", "teal", "B"), relation("knows", "mint", "B"))),
    ],
)
def test_other_either_or_clues_keep_the_long_form(clue: Or) -> None:
    first = render(clue.clues[0], CLASSIC_PALETTE)
    assert render(clue, CLASSIC_PALETTE).startswith(f"Either {first}")


def test_cells_are_named_by_row_then_column() -> None:
    assert cell_name(Cell(0, 1), CLASSIC_BOARD) == "the top row, second column"
    assert cell_name(Cell(1, 3), CLASSIC_BOARD) == "the middle row, fourth column"
    assert cell_name(Cell(2, 0), Board(4, 4)) == "the third row, first column"
