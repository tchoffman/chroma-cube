"""The 25 classic cards: they load, solve, read well and get harder as they go."""

import json
import statistics
from functools import cache
from importlib.resources import files

import pytest

from chroma_cube.core import (
    CLASSIC_BOARD,
    CLASSIC_PALETTE,
    And,
    AtLeast,
    AttributeClue,
    BoardRule,
    Cell,
    Clue,
    Color,
    ColorRef,
    Exactly,
    Not,
    Or,
    Placement,
    Property,
    Puzzle,
    Relation,
    Truth,
    evaluate,
    puzzle_from_dict,
    puzzle_to_dict,
)
from chroma_cube.puzzles import classic_puzzles
from chroma_cube.puzzles.classic import (
    DIFFICULTIES,
    classic_puzzle,
    clue_kinds,
    clue_shape,
    difficulty_score,
    opening_move,
    rate_card,
)
from chroma_cube.solver import DEFAULT_MAX_NODES, solve
from chroma_cube.solver.search import colors_in
from tests.core.helpers import grid

CARDS = classic_puzzles()
NUMBERS = range(1, 26)

UNIQUE_CARDS = 25
"""How many cards have exactly one solution. The issue asks for at least 20."""

EVERY_CLUE_MATTERS: set[int] = set(NUMBERS)
"""Cards where dropping any one clue leaves more than one solution."""

FIRST_SEEN = {
    "same_row": (1, 1),
    "same_column": (1, 1),
    "next_to": (1, 1),
    "or": (1, 1),
    "directional": (2, 4),
    "in_corner": (5, 8),
    "edge_or_center": (5, 8),
    "line": (5, 8),
    "not": (5, 8),
    "knows": (12, 12),
    "diagonal": (15, 17),
    "between": (15, 17),
    "initial": (18, 18),
    "counting": (21, 22),
    "alphabetical": (23, 23),
}
"""Card range in which each kind of clue first appears."""

GROUPS = {
    "directional": {
        "above",
        "below",
        "left_of",
        "right_of",
        "directly_above",
        "directly_below",
        "directly_left_of",
        "directly_right_of",
    },
    "edge_or_center": {"on_edge", "in_center"},
    "line": {"in_row", "in_col"},
    "counting": {"exactly", "at_least"},
    "alphabetical": {"rows_alphabetical", "columns_alphabetical"},
}


def card(number: int) -> Puzzle:
    return CARDS[number - 1]


def kinds(puzzle: Puzzle) -> frozenset[str]:
    return frozenset().union(*(clue_kinds(clue) for clue in puzzle.clues))


def is_unique(puzzle: Puzzle) -> bool:
    result = solve(puzzle, limit=1)
    assert not result.gave_up, f"{puzzle.id} ran past the search budget"
    return result.count == 1 and not result.truncated


def without_clue(puzzle: Puzzle, index: int) -> Puzzle:
    clues = puzzle.clues[:index] + puzzle.clues[index + 1 :]
    return Puzzle(puzzle.id, puzzle.title, puzzle.board, puzzle.palette, puzzle.givens, clues)


# ------------------------------------------------------------------ the set


def test_there_are_25_cards_numbered_in_order() -> None:
    assert [puzzle.id for puzzle in CARDS] == [f"classic-{n:02d}" for n in NUMBERS]


def test_cards_load_by_number() -> None:
    assert classic_puzzle(1) is CARDS[0]
    assert classic_puzzle(25) is CARDS[24]
    with pytest.raises(ValueError):
        classic_puzzle(26)
    with pytest.raises(ValueError):
        classic_puzzle(0)


def test_titles_are_unique_and_present() -> None:
    titles = [puzzle.title for puzzle in CARDS]
    assert all(title.strip() for title in titles)
    assert len(set(titles)) == len(titles)


def test_every_card_uses_the_classic_tray_and_colors() -> None:
    from chroma_cube.core import CLASSIC_BOARD, CLASSIC_PALETTE

    for puzzle in CARDS:
        assert puzzle.board == CLASSIC_BOARD
        assert puzzle.palette == CLASSIC_PALETTE


def test_difficulty_labels_never_go_down() -> None:
    labels = [puzzle.difficulty for puzzle in CARDS]
    assert set(labels) <= set(DIFFICULTIES)
    ranks = [DIFFICULTIES.index(label) for label in labels]
    assert ranks == sorted(ranks)
    assert labels[0] == "easy"
    assert labels[-1] == "expert"
    assert set(labels) == set(DIFFICULTIES)


def test_difficulty_score_is_unplaced_cubes_plus_distinct_clue_kinds() -> None:
    first = card(1)
    # five cubes to place; same column, next to, either/or and same row
    assert difficulty_score(first) == 5 + 4


def test_clue_lists_are_short() -> None:
    for puzzle in CARDS:
        assert 3 <= len(puzzle.clues) <= 7, puzzle.id


def test_givens_taper_off() -> None:
    givens = [len(puzzle.givens.assignments) for puzzle in CARDS]
    assert 5 <= givens[0] <= 7
    assert givens[7] == 0
    assert sum(1 for count in givens[19:] if count == 0) >= 3
    assert max(givens[8:]) < givens[0]


@pytest.mark.parametrize(("group", "span"), FIRST_SEEN.items())
def test_clue_kinds_are_introduced_in_order(group: str, span: tuple[int, int]) -> None:
    members = GROUPS.get(group, {group})
    first = next(n for n in NUMBERS if kinds(card(n)) & members)
    assert span[0] <= first <= span[1]


def test_a_card_that_introduces_a_clue_kind_explains_it() -> None:
    seen: set[str] = set()
    for puzzle in CARDS:
        new = kinds(puzzle) - seen
        if new and puzzle.id != "classic-01":
            assert puzzle.notes.strip(), f"{puzzle.id} introduces {sorted(new)} without notes"
        seen |= new


@cache
def rating(number: int) -> int:
    return rate_card(card(number))


def test_measured_difficulty_climbs_by_tier() -> None:
    medians = [
        statistics.median(rating(n) for n in NUMBERS if card(n).difficulty == tier)
        for tier in DIFFICULTIES
    ]
    assert medians == sorted(medians), medians


def test_the_last_card_is_the_hardest() -> None:
    assert all(rating(25) > rating(n) for n in NUMBERS if n != 25)


def test_rate_card_is_zero_when_every_step_is_forced() -> None:
    assert rating(1) == 0


def fills_a_line(puzzle: Puzzle, clue: Clue) -> bool:
    """ "X is right of A, B and C" or "X is above A and B": one clue that fills a whole row
    or column around X."""
    if not isinstance(clue, And) or not all(isinstance(sub, Relation) for sub in clue.clues):
        return False
    relations = [sub for sub in clue.clues if isinstance(sub, Relation)]
    kinds = {r.kind for r in relations}
    subjects = {r.colors[0] for r in relations}
    if len(kinds) != 1 or len(subjects) != 1:
        return False
    span = {"left_of": puzzle.board.cols, "right_of": puzzle.board.cols}.get(
        relations[0].kind,
        puzzle.board.rows if relations[0].kind in ("above", "below") else 0,
    )
    return span > 0 and len(relations) >= span - 1


def test_line_filling_clues_are_rare() -> None:
    counts = {n: sum(fills_a_line(card(n), clue) for clue in card(n).clues) for n in NUMBERS}
    assert max(counts.values()) <= 1, counts
    late = [n for n in NUMBERS if card(n).difficulty in ("hard", "expert")]
    assert sum(1 for n in late if counts[n] == 0) * 2 >= len(late), counts


def diagonal_to_three(clue: Clue) -> bool:
    """ "X is diagonal to A, B and C": only the two middle cells touch three cells at a
    corner, so the clue alone puts X in the middle row."""
    if not isinstance(clue, And) or len(clue.clues) < 3:
        return False
    relations = [sub for sub in clue.clues if isinstance(sub, Relation)]
    return (
        len(relations) == len(clue.clues)
        and {r.kind for r in relations} == {"diagonal"}
        and len({r.colors[0] for r in relations}) == 1
    )


def test_diagonal_to_three_is_on_at_most_three_cards() -> None:
    found = [n for n in NUMBERS if any(diagonal_to_three(clue) for clue in card(n).clues)]
    assert len(found) <= 3, found


def test_opening_move_is_the_tightest_single_clue_narrowing() -> None:
    first = opening_move(card(1))
    assert first is not None
    assert (first.clue, first.color.id, first.cells) == (3, "coral", frozenset({Cell(0, 1)}))
    assert first.shape == "next_to"


def test_opening_move_of_diagonal_to_three_is_the_middle() -> None:
    puzzle = card(15)
    clue = next(i for i, c in enumerate(puzzle.clues) if diagonal_to_three(c))
    trimmed = Puzzle(
        puzzle.id, puzzle.title, puzzle.board, puzzle.palette, puzzle.givens, (puzzle.clues[clue],)
    )
    move = opening_move(trimmed)
    assert move is not None
    assert move.cells == frozenset({Cell(1, 1), Cell(1, 2)})
    assert move.shape == "and(diagonal,diagonal,diagonal)"


def test_clue_shape_hides_colors_but_keeps_structure() -> None:
    assert clue_shape(card(1).clues[2]) == "or(same_row,same_row)"
    assert clue_shape(card(18).clues[0]) == "next_to*"


def rel(kind: str, *colors: str) -> Relation:
    return Relation(kind, tuple(ColorRef(c) for c in colors))


def prop(kind: str, color: str, index: int | None = None) -> Property:
    return Property(kind, ColorRef(color), index)


def test_clue_shape_of_negations_counts_and_lines() -> None:
    assert clue_shape(Not(rel("knows", "black", "white"))) == "not(knows)"
    assert clue_shape(prop("in_row", "black", 2)) == "in_row2"
    assert clue_shape(prop("in_col", "black", 0)) == "in_col0"
    parts = (rel("next_to", "mint", "teal"), prop("in_corner", "coral"))
    assert clue_shape(Exactly(1, parts)) == "exactly1(in_corner,next_to)"
    assert clue_shape(AtLeast(2, parts)) == "at_least2(in_corner,next_to)"
    assert clue_shape(BoardRule("rows_alphabetical")) == "rows_alphabetical"


def test_clue_shape_of_an_attribute_clue() -> None:
    clue = AttributeClue("neighbours_all", "cool", color=ColorRef("mint"))
    assert clue_shape(clue) == "neighbours_all"


def puzzle_of(*clues: Clue, givens: Placement | None = None) -> Puzzle:
    return Puzzle(
        "test", "Test", CLASSIC_BOARD, CLASSIC_PALETTE, givens or Placement(), tuple(clues)
    )


def test_opening_move_tie_goes_to_the_earlier_clue_then_palette_order() -> None:
    corner_teal = prop("in_corner", "teal")
    corner_coral = prop("in_corner", "coral")
    move = opening_move(puzzle_of(corner_teal, corner_coral))
    assert move is not None and (move.clue, move.color.id) == (0, "teal")
    both = rel("same_column", "mint", "brown")
    edge_pair = And((prop("in_corner", "mint"), prop("in_corner", "brown")))
    move = opening_move(puzzle_of(both, edge_pair))
    assert move is not None and (move.clue, move.color.id) == (1, "brown")


def test_opening_move_is_none_when_no_clue_rules_out_half_the_cells() -> None:
    assert opening_move(puzzle_of(prop("on_edge", "coral"), rel("next_to", "mint", "teal"))) is None
    # the middle row leaves four of twelve cells: a real first step
    assert opening_move(puzzle_of(prop("in_row", "coral", 1))) is not None


def test_opening_move_judges_a_clue_about_many_cubes_one_cube_at_a_time() -> None:
    move = opening_move(puzzle_of(BoardRule("rows_alphabetical")))
    assert move is not None
    assert move.color.id == "black"
    assert move.cells == frozenset({Cell(0, 0), Cell(1, 0), Cell(2, 0)})


def opening_kind(puzzle: Puzzle) -> object:
    """What a player does first on the card. Every line-filling clue is one kind of
    opening, wherever the line is; a card with no single-clue opening starts by putting
    clues together."""
    move = opening_move(puzzle)
    if move is None:
        return "clues together"
    if fills_a_line(puzzle, puzzle.clues[move.clue]):
        return "fills a line"
    return (move.shape, move.cells)


def test_no_two_consecutive_cards_open_the_same_way() -> None:
    kinds = {n: opening_kind(card(n)) for n in NUMBERS}
    same = [(n - 1, n, kinds[n]) for n in NUMBERS[1:] if kinds[n - 1] == kinds[n]]
    assert not same, same


def sits_next_to_several(clue: Clue) -> bool:
    """ "X sits next to A and B" or "X sits next to A, B and C"."""
    if not isinstance(clue, And) or len(clue.clues) < 2:
        return False
    relations = [sub for sub in clue.clues if isinstance(sub, Relation)]
    return (
        len(relations) == len(clue.clues)
        and {r.kind for r in relations} == {"next_to"}
        and len({r.colors[0] for r in relations}) == 1
    )


SITS_NEXT_TO_SEVERAL_CAP = 16
"""Most cards that may carry an "X sits next to A, B (and C)" clue."""


def test_sits_next_to_several_is_capped() -> None:
    found = [n for n in NUMBERS if any(sits_next_to_several(clue) for clue in card(n).clues)]
    assert len(found) <= SITS_NEXT_TO_SEVERAL_CAP, found


MIRRORED = {
    "below": "above",
    "right_of": "left_of",
    "directly_below": "directly_above",
    "directly_right_of": "directly_left_of",
}


def broad_shape(clue: Clue) -> str:
    """A clue's shape with mirror images and group sizes merged: "X is left of A and B"
    and "X is right of A, B and C" read as the same kind of clue."""
    if isinstance(clue, Relation):
        return MIRRORED.get(clue.kind, clue.kind) + (
            "*" if any(r.by_initial for r in clue.colors) else ""
        )
    if isinstance(clue, And) and all(isinstance(sub, Relation) for sub in clue.clues):
        return "group:" + ",".join(sorted({broad_shape(sub) for sub in clue.clues}))
    return clue_shape(clue)


def test_cards_15_to_17_are_built_differently() -> None:
    shapes = {n: {broad_shape(clue) for clue in card(n).clues} for n in (15, 16, 17)}
    for a, b in ((15, 16), (15, 17), (16, 17)):
        assert len(shapes[a] & shapes[b]) <= 2, (a, b, shapes[a] & shapes[b])
    assert not shapes[15] & shapes[16] & shapes[17], shapes


Domains = dict[Color, set[Cell]]

PROPAGATED_COLORS = 4
"""Clues about more unplaced cubes than this are left out of the propagation."""


def propagate(puzzle: Puzzle) -> tuple[Placement, Domains]:
    """What a careful player knows before any guess: every cube's possible cells, cut
    down clue by clue (a cell stays only if the clue's other cubes can still sit
    somewhere in their own cells), placing a cube whenever one cell or one cube is left."""
    placement = puzzle.givens
    free = {cell for cell in puzzle.board if placement.color_at(cell) is None}
    domains: Domains = {color: set(free) for color in placement.unplaced(puzzle.palette)}
    changed = True
    while changed:
        changed = False
        for clue in puzzle.clues:
            involved = [c for c in colors_in(clue, puzzle.palette) if c in domains]
            if not involved or len(involved) > PROPAGATED_COLORS:
                continue
            for color in involved:
                others = [c for c in involved if c != color]
                keep = {
                    cell
                    for cell in domains[color]
                    if supported(puzzle, clue, placement.with_color(color, cell), others, domains)
                }
                if keep != domains[color]:
                    domains[color] = keep
                    changed = True
        forced = [(c, next(iter(cells))) for c, cells in domains.items() if len(cells) == 1]
        for cell in set().union(*domains.values()) if domains else set():
            takers = [c for c, cells in domains.items() if cell in cells]
            if len(takers) == 1 and len(domains[takers[0]]) > 1:
                forced.append((takers[0], cell))
        if forced:
            color, cell = forced[0]
            placement = placement.with_color(color, cell)
            del domains[color]
            for cells in domains.values():
                cells.discard(cell)
            changed = True
    return placement, domains


def supported(
    puzzle: Puzzle, clue: Clue, placement: Placement, rest: list[Color], domains: Domains
) -> bool:
    """Some placing of `rest`, each in its own cells, leaves `clue` not broken."""
    if not rest:
        return evaluate(clue, placement, puzzle.board, puzzle.palette) is not Truth.VIOLATED
    color, others = rest[0], rest[1:]
    return any(
        supported(puzzle, clue, placement.with_color(color, cell), others, domains)
        for cell in domains[color]
        if placement.color_at(cell) is None
    )


def can_be(puzzle: Puzzle, clue: Clue, placement: Placement, domains: Domains) -> set[Truth]:
    """The truth values `clue` can still take with every cube in its own cells."""
    involved = [c for c in colors_in(clue, puzzle.palette) if c in domains]

    def walk(trial: Placement, rest: list[Color]) -> set[Truth]:
        if not rest:
            return {evaluate(clue, trial, puzzle.board, puzzle.palette)}
        color, others = rest[0], rest[1:]
        found: set[Truth] = set()
        for cell in domains[color]:
            if trial.color_at(cell) is None:
                found |= walk(trial.with_color(color, cell), others)
        return found

    return walk(placement, involved)


@pytest.mark.parametrize("number", [9, 10])
def test_either_or_teaching_cards_leave_both_branches_open(number: int) -> None:
    """Both halves of the either/or can still be true or false once the player has made
    every deduction the other clues allow short of a guess."""
    puzzle = card(number)
    either_ors = [clue for clue in puzzle.clues if isinstance(clue, Or)]
    assert either_ors, f"{puzzle.id} has no either/or"
    others = tuple(clue for clue in puzzle.clues if not isinstance(clue, Or))
    placement, domains = propagate(
        Puzzle(puzzle.id, puzzle.title, puzzle.board, puzzle.palette, puzzle.givens, others)
    )
    for clue in either_ors:
        for part in clue.clues:
            assert evaluate(part, puzzle.givens, puzzle.board, puzzle.palette) is Truth.UNKNOWN
            truths = can_be(puzzle, part, placement, domains)
            assert {Truth.SATISFIED, Truth.VIOLATED} <= truths, (
                f"{puzzle.id}: '{part}' is settled before the either/or is needed"
            )


def test_card_8_warns_that_it_is_the_first_empty_tray() -> None:
    assert "first empty tray" in card(8).notes.lower()


# ------------------------------------------------------------------ solving


@pytest.mark.parametrize("number", NUMBERS)
def test_card_solves_within_the_default_search_budget(number: int) -> None:
    puzzle = card(number)
    result = solve(puzzle, limit=1, max_nodes=DEFAULT_MAX_NODES)
    assert not result.gave_up
    assert result.count == 1 and not result.truncated


@pytest.mark.parametrize("number", NUMBERS)
def test_card_is_solvable_and_agrees_with_its_givens(number: int) -> None:
    puzzle = card(number)
    result = solve(puzzle, limit=1)
    assert result.count == 1
    solution = result.solutions[0]
    for color, cell in puzzle.givens.assignments.items():
        assert solution.cell_of(color) == cell


def test_unique_cards() -> None:
    assert sum(is_unique(puzzle) for puzzle in CARDS) == UNIQUE_CARDS
    assert UNIQUE_CARDS >= 20


@pytest.mark.parametrize("number", sorted(EVERY_CLUE_MATTERS))
def test_every_clue_matters(number: int) -> None:
    puzzle = card(number)
    for index in range(len(puzzle.clues)):
        assert not is_unique(without_clue(puzzle, index)), (
            f"{puzzle.id}: clue {index + 1} ({puzzle.rendered_clues()[index]}) is not needed"
        )


# ------------------------------------------------------------------ reading


@pytest.mark.parametrize("number", NUMBERS)
def test_every_clue_renders_as_a_sentence(number: int) -> None:
    for text in card(number).rendered_clues():
        assert text[0].isupper()
        assert "{" not in text and "}" not in text
        assert "  " not in text
        assert not text.endswith((".", " "))


# ------------------------------------------------------------------ card 1


CARD_1_SOLUTION = grid(
    [
        ["mint", "coral", "white", "mustard"],
        ["cobalt", "orange", "brown", "teal"],
        ["emerald", "magenta", "black", "purple"],
    ]
)


def test_card_1_wording_adapts_the_published_walkthrough() -> None:
    assert card(1).rendered_clues() == (
        "Coral and Magenta are in the same column",
        "Black sits next to Magenta",
        "Either Teal or Black is in the same row as Cobalt",
        "Coral sits next to White",
    )


def test_card_1_has_the_walkthrough_solution() -> None:
    puzzle = card(1)
    assert solve(puzzle).solutions == (CARD_1_SOLUTION,)
    orange = CARD_1_SOLUTION.cell_of(puzzle.palette.by_id("orange"))
    assert orange is not None and orange.row == 1
    assert {c.id for c in puzzle.givens.unplaced(puzzle.palette)} == {
        "coral",
        "magenta",
        "black",
        "teal",
        "mint",
    }


def test_card_1_is_forced_one_clue_at_a_time() -> None:
    """Clue 1 picks orange's column, clue 4 sets coral on top, then clue 2, then clue 3."""
    puzzle = card(1)
    palette = puzzle.palette

    def cells(clue_numbers: list[int], color_id: str) -> set[Cell]:
        clues = tuple(puzzle.clues[n - 1] for n in clue_numbers)
        trimmed = Puzzle(puzzle.id, puzzle.title, puzzle.board, palette, puzzle.givens, clues)
        found = solve(trimmed, limit=1000).solutions
        return {cell for s in found if (cell := s.cell_of(palette.by_id(color_id))) is not None}

    assert cells([1], "coral") == cells([1], "magenta") == {Cell(0, 1), Cell(2, 1)}
    assert cells([1, 4], "coral") == {Cell(0, 1)}
    assert cells([1, 4], "magenta") == {Cell(2, 1)}
    assert len(cells([1, 4], "black")) > 1
    assert cells([1, 4, 2], "black") == {Cell(2, 2)}
    assert len(cells([1, 4, 2], "teal")) > 1
    assert cells([1, 4, 2, 3], "teal") == {Cell(1, 3)}
    assert cells([1, 4, 2, 3], "mint") == {Cell(0, 0)}


# ------------------------------------------------------------------ storage


def test_stored_cards_round_trip_through_json() -> None:
    folder = files("chroma_cube.puzzles").joinpath("data", "classic")
    stored = sorted(
        (entry for entry in folder.iterdir() if entry.name.endswith(".json")),
        key=lambda entry: entry.name,
    )
    assert [entry.name for entry in stored] == [f"classic-{n:02d}.json" for n in NUMBERS]
    for entry, puzzle in zip(stored, CARDS, strict=True):
        data = json.loads(entry.read_text(encoding="utf-8"))
        assert puzzle_to_dict(puzzle_from_dict(data)) == data
        assert puzzle_from_dict(data) == puzzle
