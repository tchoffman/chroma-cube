"""The hint engine: forced moves first, a cube from the solution as a last resort."""

from typing import Any

import pytest

from chroma_cube.core import Board, Cell, Not, Placement, Puzzle, prop, relation
from chroma_cube.puzzles import classic_puzzles
from chroma_cube.solver import hints
from chroma_cube.solver.hints import Hint, HintReason, explain, next_hint
from tests.solver.helpers import puzzle, small_palette

CARD_1 = classic_puzzles()[0]
PALETTE = CARD_1.palette
ROW = Board(1, 3)
THREE = small_palette(3)
"""Black, Brown, Cobalt."""


def card_1_with(**cells: Cell) -> Placement:
    placement = CARD_1.givens
    for color_id, cell in cells.items():
        placement = placement.with_color(PALETTE.by_id(color_id), cell)
    return placement


def play_hints(p: Puzzle) -> tuple[list[Hint], Placement]:
    """Follow hints from the givens until there are none, placing each hinted cube."""
    placement = p.givens
    taken: list[Hint] = []
    while (hint := next_hint(p, placement)) is not None:
        assert hint.reason is not HintReason.MISPLACED
        placement = placement.with_color(hint.color, hint.cell)
        taken.append(hint)
        assert len(taken) <= len(p.palette)
    return taken, placement


# ------------------------------------------------------------------ card 1


def test_card_1_hints_follow_the_walkthrough_to_the_solution() -> None:
    hints, final = play_hints(CARD_1)
    assert [hint.color.id for hint in hints] == ["magenta", "coral", "white", "teal", "mint"]
    assert all(hint.reason is HintReason.ONLY_CELL for hint in hints)
    assert final == card_1_with(
        white=Cell(0, 0), coral=Cell(0, 1), teal=Cell(0, 3), mint=Cell(2, 0), magenta=Cell(2, 1)
    )


def test_the_first_hint_names_the_cell_and_the_clues_that_force_it() -> None:
    hint = next_hint(CARD_1, CARD_1.givens)
    assert hint == Hint(PALETTE.by_id("magenta"), Cell(2, 1), HintReason.ONLY_CELL, (0, 1))
    assert explain(hint, CARD_1) == (
        "Magenta must go in the bottom row, second column: it is the only cell left where "
        "'Coral and Magenta are in the same column' and 'Black sits next to Magenta' can "
        "still hold"
    )


def test_coral_follows_magenta_because_of_the_column_clue() -> None:
    hint = next_hint(CARD_1, card_1_with(magenta=Cell(2, 1)))
    assert hint is not None
    assert (hint.color.id, hint.cell, hint.clues) == ("coral", Cell(0, 1), (0, 3))
    assert explain(hint, CARD_1) == (
        "Coral must go in the top row, second column: it is the only cell left where "
        "'Coral and Magenta are in the same column' and 'Coral sits next to White' can "
        "still hold"
    )


def test_the_last_cube_has_one_free_cell_and_no_clue() -> None:
    placement = card_1_with(white=Cell(0, 0), coral=Cell(0, 1), teal=Cell(0, 3), magenta=Cell(2, 1))
    hint = next_hint(CARD_1, placement)
    assert hint == Hint(PALETTE.by_id("mint"), Cell(2, 0), HintReason.ONLY_CELL, ())
    assert explain(hint, CARD_1) == (
        "Mint must go in the bottom row, first column: it is the only free cell left"
    )


def test_a_solved_card_has_no_hint() -> None:
    _, final = play_hints(CARD_1)
    assert next_hint(CARD_1, final) is None


# ------------------------------------------------------------------ misplaced cubes


def test_a_cube_that_breaks_a_clue_is_pointed_out_first() -> None:
    placement = card_1_with(magenta=Cell(0, 0))
    hint = next_hint(CARD_1, placement)
    assert hint == Hint(PALETTE.by_id("magenta"), Cell(0, 0), HintReason.MISPLACED, (1,))
    assert explain(hint, CARD_1) == (
        "Magenta does not belong in the top row, first column: it breaks "
        "'Black sits next to Magenta'"
    )


def test_a_cube_off_the_unique_solution_is_pointed_out_even_if_no_clue_breaks() -> None:
    placement = card_1_with(mint=Cell(0, 0))
    hint = next_hint(CARD_1, placement)
    assert hint == Hint(PALETTE.by_id("mint"), Cell(0, 0), HintReason.MISPLACED, ())
    assert explain(hint, CARD_1) == (
        "Mint does not belong in the top row, first column: the solution has it elsewhere"
    )


def test_a_correct_cube_is_not_blamed_for_a_clue_a_wrong_one_breaks() -> None:
    placement = card_1_with(coral=Cell(0, 1), magenta=Cell(0, 0))
    hint = next_hint(CARD_1, placement)
    assert hint == Hint(PALETTE.by_id("magenta"), Cell(0, 0), HintReason.MISPLACED, (0, 1, 3))
    assert explain(hint, CARD_1) == (
        "Magenta does not belong in the top row, first column: it breaks "
        "'Coral and Magenta are in the same column', 'Black sits next to Magenta' and 1 more"
    )


def test_without_a_known_solution_the_first_cube_that_breaks_a_clue_is_blamed() -> None:
    placement = card_1_with(coral=Cell(0, 1), magenta=Cell(0, 0))
    hint = next_hint(CARD_1, placement, max_nodes=1)
    assert hint is not None
    assert (hint.color.id, hint.reason) == ("coral", HintReason.MISPLACED)


def test_the_solution_is_searched_once_per_card(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []
    real_solve = hints.solve

    def counting_solve(*args: Any, **kwargs: Any) -> Any:
        calls.append(1)
        return real_solve(*args, **kwargs)

    monkeypatch.setattr(hints, "solve", counting_solve)
    hints.clear_solution_cache()
    next_hint(CARD_1, card_1_with(mint=Cell(0, 0)))
    next_hint(CARD_1, card_1_with(mint=Cell(0, 0)))
    next_hint(CARD_1, card_1_with(teal=Cell(0, 0)))
    assert len(calls) == 1


def test_givens_are_never_blamed() -> None:
    givens = Placement({THREE.by_id("black"): Cell(0, 1)})
    p = puzzle(ROW, THREE, [prop("in_col", "black", 0)], givens)
    assert next_hint(p, p.givens) is None


# ------------------------------------------------------------------ only color


def test_a_cell_only_one_cube_can_take() -> None:
    p = puzzle(
        ROW,
        THREE,
        [Not(prop("in_col", "brown", 0)), Not(prop("in_col", "cobalt", 0))],
    )
    hint = next_hint(p, p.givens)
    assert hint == Hint(THREE.by_id("black"), Cell(0, 0), HintReason.ONLY_COLOR, (0, 1))
    assert explain(hint, p) == (
        "Only Black can go in the top row, first column: any other cube left there would "
        "break 'Brown isn't in the first column' and 'Cobalt isn't in the first column'"
    )


def test_no_forced_move_on_a_puzzle_with_several_solutions_gives_no_hint() -> None:
    p = puzzle(
        ROW,
        THREE,
        [Not(prop("in_col", "brown", 0)), Not(prop("in_col", "cobalt", 0))],
    )
    assert next_hint(p, p.givens.with_color(THREE.by_id("black"), Cell(0, 0))) is None


# ------------------------------------------------------------------ revealing


def needs_a_reveal() -> Puzzle:
    """Unique on a 2x2 tray, but no cube or cell is forced one step ahead."""
    return puzzle(
        Board(2, 2),
        small_palette(4),
        [
            prop("in_row", "cobalt", 0),
            Not(relation("next_to", "brown", "coral")),
            relation("left_of", "black", "coral"),
        ],
    )


def test_with_nothing_forced_a_unique_puzzle_reveals_the_most_decisive_cube() -> None:
    p = needs_a_reveal()
    hint = next_hint(p, p.givens)
    assert hint == Hint(p.palette.by_id("cobalt"), Cell(0, 1), HintReason.REVEAL, (0,))
    assert explain(hint, p) == (
        "Cobalt goes in the top row, second column: nothing is forced yet, so this comes "
        "from the solution, and it settles 'Cobalt is in the top row'"
    )


def test_hints_finish_a_puzzle_that_needs_a_reveal() -> None:
    p = needs_a_reveal()
    hints, final = play_hints(p)
    assert hints[0].reason is HintReason.REVEAL
    assert final.is_complete(p.palette)


def test_a_search_that_runs_out_of_budget_means_no_reveal() -> None:
    p = needs_a_reveal()
    assert next_hint(p, p.givens, max_nodes=1) is None


def test_running_out_of_budget_never_flags_a_cube_off_the_solution() -> None:
    hint = next_hint(CARD_1, card_1_with(mint=Cell(0, 0)), max_nodes=1)
    assert hint is not None
    assert hint.reason is not HintReason.MISPLACED
