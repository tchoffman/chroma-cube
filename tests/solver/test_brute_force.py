"""The solver finds exactly the solutions a brute-force search finds."""

from hypothesis import given, settings
from hypothesis import strategies as st

from chroma_cube.core import Board, Palette, Placement, Puzzle
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
from chroma_cube.solver import solve
from tests.solver.helpers import brute_force, puzzle, small_palette


def color_refs(palette: Palette) -> st.SearchStrategy[ColorRef]:
    return st.one_of(
        st.sampled_from([ColorRef.named(color.id) for color in palette]),
        st.sampled_from(sorted({ColorRef.initial(color.initial) for color in palette}, key=str)),
    )


def clues(palette: Palette, board: Board) -> st.SearchStrategy[Clue]:
    refs = color_refs(palette)

    @st.composite
    def relations(draw: st.DrawFn) -> Relation:
        kind = draw(st.sampled_from(sorted(RELATION_KINDS)))
        arity = RELATION_KINDS[kind].arity
        return Relation(kind, tuple(draw(st.lists(refs, min_size=arity, max_size=arity))))

    @st.composite
    def properties(draw: st.DrawFn) -> Property:
        kind = draw(st.sampled_from(sorted(PROPERTY_KINDS)))
        line = PROPERTY_KINDS[kind].index
        top = board.rows if line == "row" else board.cols
        index = draw(st.integers(0, top - 1)) if line else None
        return Property(kind, draw(refs), index)

    def compounds(children: st.SearchStrategy[Clue]) -> st.SearchStrategy[Clue]:
        lists = st.lists(children, min_size=1, max_size=3).map(tuple)
        return st.one_of(
            children.map(Not),
            lists.map(And),
            lists.map(Or),
            lists.flatmap(lambda cs: st.integers(0, len(cs)).map(lambda n: Exactly(n, cs))),
            lists.flatmap(lambda cs: st.integers(1, len(cs)).map(lambda n: AtLeast(n, cs))),
        )

    leaves = st.one_of(
        relations(),
        relations(),
        properties(),
        st.sampled_from(sorted(BOARD_RULE_KINDS)).map(BoardRule),
    )
    return st.recursive(leaves, compounds, max_leaves=4)


@st.composite
def small_puzzles(draw: st.DrawFn) -> Puzzle:
    board = draw(st.sampled_from([Board(2, 2), Board(2, 3), Board(3, 2)]))
    palette = small_palette(len(board))
    clue_list = draw(st.lists(clues(palette, board), max_size=4))
    given_colors = draw(st.lists(st.sampled_from(palette.colors), max_size=2, unique=True))
    given_cells = draw(
        st.lists(
            st.sampled_from(list(board)),
            min_size=len(given_colors),
            max_size=len(given_colors),
            unique=True,
        )
    )
    givens = Placement(dict(zip(given_colors, given_cells, strict=True)))
    return puzzle(board, palette, clue_list, givens)


@settings(max_examples=150, deadline=None)
@given(small_puzzles())
def test_the_solver_agrees_with_brute_force(p: Puzzle) -> None:
    expected = brute_force(p)
    result = solve(p, limit=1000)
    assert set(result.solutions) == expected
    assert result.count == len(expected)
    assert not result.truncated
