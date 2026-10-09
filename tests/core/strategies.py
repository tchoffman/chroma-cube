"""Hypothesis strategies for clues."""

from hypothesis import strategies as st

from chroma_cube.core import CLASSIC_PALETTE
from chroma_cube.core.clues import (
    BOARD_RULE_KINDS,
    PROPERTY_KINDS,
    RELATION_KINDS,
    And,
    AtLeast,
    BoardRule,
    Clue,
    ColorRef,
    Exactly,
    Not,
    Or,
    Property,
    Relation,
)

color_refs = st.one_of(
    st.sampled_from([ColorRef.named(color.id) for color in CLASSIC_PALETTE]),
    st.sampled_from(
        sorted({ColorRef.initial(color.initial) for color in CLASSIC_PALETTE}, key=str)
    ),
)


@st.composite
def relations(draw: st.DrawFn) -> Relation:
    kind = draw(st.sampled_from(sorted(RELATION_KINDS)))
    arity = RELATION_KINDS[kind].arity
    return Relation(kind, tuple(draw(st.lists(color_refs, min_size=arity, max_size=arity))))


@st.composite
def properties(draw: st.DrawFn) -> Property:
    kind = draw(st.sampled_from(sorted(PROPERTY_KINDS)))
    index = draw(st.integers(0, 2)) if PROPERTY_KINDS[kind].index else None
    return Property(kind, draw(color_refs), index)


board_rules = st.sampled_from(sorted(BOARD_RULE_KINDS)).map(BoardRule)


def _compounds(children: st.SearchStrategy[Clue]) -> st.SearchStrategy[Clue]:
    lists = st.lists(children, min_size=1, max_size=4).map(tuple)
    return st.one_of(
        children.map(Not),
        lists.map(And),
        lists.map(Or),
        lists.flatmap(lambda cs: st.integers(0, len(cs)).map(lambda n: Exactly(n, cs))),
        lists.flatmap(lambda cs: st.integers(1, len(cs)).map(lambda n: AtLeast(n, cs))),
    )


clues: st.SearchStrategy[Clue] = st.recursive(
    st.one_of(relations(), properties(), board_rules), _compounds, max_leaves=12
)
