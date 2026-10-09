import pytest

from chroma_cube.core.clues import (
    PROPERTY_KINDS,
    RELATION_KINDS,
    And,
    AtLeast,
    BoardRule,
    ColorRef,
    Exactly,
    Not,
    Or,
    Property,
    Relation,
    prop,
    ref,
    relation,
)


def test_color_ref_by_id_and_by_initial() -> None:
    assert ColorRef.named("black") == ColorRef("black")
    assert ColorRef.initial("b") == ColorRef("B", by_initial=True)
    assert ref("black") == ColorRef.named("black")
    assert ref("B") == ColorRef.initial("B")
    assert ref(ColorRef.named("teal")) == ColorRef.named("teal")


@pytest.mark.parametrize("bad", ["", "BB", "1"])
def test_initial_must_be_one_letter(bad: str) -> None:
    with pytest.raises(ValueError):
        ColorRef.initial(bad)


def test_an_id_cannot_look_like_an_initial() -> None:
    with pytest.raises(ValueError):
        ColorRef.named("B")
    with pytest.raises(ValueError):
        ColorRef.named("")


def test_every_documented_relation_and_property_has_a_kind() -> None:
    assert set(RELATION_KINDS) == {
        "same_row",
        "same_column",
        "next_to",
        "knows",
        "diagonal",
        "above",
        "below",
        "left_of",
        "right_of",
        "directly_above",
        "directly_below",
        "directly_left_of",
        "directly_right_of",
        "between",
    }
    assert set(PROPERTY_KINDS) == {"in_corner", "on_edge", "in_center", "in_row", "in_col"}


def test_relation_factory_builds_refs_from_strings() -> None:
    clue = relation("next_to", "black", "M")
    assert clue == Relation("next_to", (ColorRef.named("black"), ColorRef.initial("M")))


def test_relation_checks_kind_and_arity() -> None:
    with pytest.raises(ValueError):
        relation("hugs", "black", "white")
    with pytest.raises(ValueError):
        relation("next_to", "black")
    with pytest.raises(ValueError):
        relation("between", "black", "white")
    assert len(relation("between", "black", "white", "teal").colors) == 3


def test_property_checks_kind_and_index() -> None:
    assert prop("in_row", "black", 0) == Property("in_row", ColorRef.named("black"), 0)
    with pytest.raises(ValueError):
        prop("in_row", "black")
    with pytest.raises(ValueError):
        prop("in_corner", "black", 1)
    with pytest.raises(ValueError):
        prop("in_row", "black", -1)
    with pytest.raises(ValueError):
        prop("in_attic", "black")


def test_combinators_validate_their_arguments() -> None:
    a = prop("in_corner", "black")
    with pytest.raises(ValueError):
        And(())
    with pytest.raises(ValueError):
        Or(())
    with pytest.raises(ValueError):
        Exactly(-1, (a,))
    with pytest.raises(ValueError):
        AtLeast(2, (a,))
    with pytest.raises(ValueError):
        BoardRule("diagonals_alphabetical")


def test_every_node_is_hashable_and_compares_by_value() -> None:
    def build() -> object:
        a = relation("knows", "black", "W")
        b = prop("in_col", "teal", 2)
        return And(
            (
                Not(a),
                Or((a, b)),
                Exactly(1, (a, b)),
                AtLeast(1, (a, b)),
                BoardRule("rows_alphabetical"),
            )
        )

    assert build() == build()
    assert hash(build()) == hash(build())
    assert len({build(), build()}) == 1
