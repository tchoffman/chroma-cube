"""The 25 classic cards: they load, solve, read well and get harder as they go."""

import json
from importlib.resources import files

import pytest

from chroma_cube.core import Cell, Puzzle, puzzle_from_dict, puzzle_to_dict
from chroma_cube.puzzles import classic_puzzles
from chroma_cube.puzzles.classic import (
    DIFFICULTIES,
    classic_puzzle,
    clue_kinds,
    difficulty_score,
)
from chroma_cube.solver import solve
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


# ------------------------------------------------------------------ solving


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


def test_card_1_reads_like_the_published_card() -> None:
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
