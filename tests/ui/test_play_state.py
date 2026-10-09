import pytest

from chroma_cube.core import (
    CLASSIC_BOARD,
    CLASSIC_PALETTE,
    Cell,
    Clue,
    Placement,
    Puzzle,
    Truth,
    relation,
)
from chroma_cube.puzzles import classic_puzzles
from chroma_cube.ui.play import PlayState

P = CLASSIC_PALETTE
BLACK, BROWN, CORAL, MAGENTA, MINT, MUSTARD, ORANGE, TEAL = (
    P.by_id(c) for c in ("black", "brown", "coral", "magenta", "mint", "mustard", "orange", "teal")
)


def puzzle(*clues: Clue) -> Puzzle:
    return Puzzle(
        id="t",
        title="Test",
        board=CLASSIC_BOARD,
        palette=P,
        givens=Placement({ORANGE: Cell(1, 1)}),
        clues=tuple(clues) or (relation("next_to", "black", "brown"),),
    )


def test_starts_with_only_the_givens_and_nothing_held() -> None:
    state = PlayState(puzzle())
    assert state.placement == Placement({ORANGE: Cell(1, 1)})
    assert state.held is None
    assert state.cursor == Cell(0, 0)
    assert ORANGE not in state.palette_cubes()
    assert len(state.palette_cubes()) == 11


def test_select_from_palette_then_place_on_an_empty_cell() -> None:
    state = PlayState(puzzle())
    state.select(BLACK)
    assert state.held is BLACK
    state.activate(Cell(0, 0))
    assert state.placement.cell_of(BLACK) == Cell(0, 0)
    assert state.held is None
    assert BLACK not in state.palette_cubes()


def test_activating_an_empty_cell_with_nothing_held_does_nothing() -> None:
    state = PlayState(puzzle())
    message = state.activate(Cell(0, 0))
    assert state.placement == PlayState(puzzle()).placement
    assert message


def test_givens_cannot_be_picked_up_or_covered() -> None:
    state = PlayState(puzzle())
    assert "fixed" in state.activate(Cell(1, 1))
    assert state.held is None
    state.select(BLACK)
    assert "fixed" in state.activate(Cell(1, 1))
    assert state.placement.color_at(Cell(1, 1)) is ORANGE
    assert state.held is BLACK
    assert state.is_given(ORANGE)
    assert not state.is_given(BLACK)


def test_selecting_a_given_or_placed_color_from_the_palette_is_refused() -> None:
    state = PlayState(puzzle())
    with pytest.raises(ValueError):
        state.select(ORANGE)


def test_pick_up_a_placed_cube_and_move_it() -> None:
    state = PlayState(puzzle())
    state.select(BLACK)
    state.activate(Cell(0, 0))
    state.activate(Cell(0, 0))
    assert state.held is BLACK
    state.activate(Cell(2, 3))
    assert state.placement.cell_of(BLACK) == Cell(2, 3)
    assert state.placement.color_at(Cell(0, 0)) is None
    assert state.held is None


def test_activating_the_held_cube_again_puts_it_down() -> None:
    state = PlayState(puzzle())
    state.select(BLACK)
    state.activate(Cell(0, 0))
    state.activate(Cell(0, 0))
    state.activate(Cell(0, 0))
    assert state.held is None
    assert state.placement.cell_of(BLACK) == Cell(0, 0)


def test_moving_onto_a_placed_cube_swaps_them() -> None:
    state = PlayState(puzzle())
    state.select(BLACK)
    state.activate(Cell(0, 0))
    state.select(BROWN)
    state.activate(Cell(0, 1))
    state.activate(Cell(0, 0))
    state.activate(Cell(0, 1))
    assert state.placement.cell_of(BLACK) == Cell(0, 1)
    assert state.placement.cell_of(BROWN) == Cell(0, 0)


def test_placing_from_the_palette_onto_a_placed_cube_sends_it_back() -> None:
    state = PlayState(puzzle())
    state.select(BLACK)
    state.activate(Cell(0, 0))
    state.select(BROWN)
    state.activate(Cell(0, 0))
    assert state.placement.cell_of(BROWN) == Cell(0, 0)
    assert state.placement.cell_of(BLACK) is None
    assert BLACK in state.palette_cubes()


def test_return_a_held_placed_cube_to_the_palette() -> None:
    state = PlayState(puzzle())
    state.select(BLACK)
    state.activate(Cell(0, 0))
    state.activate(Cell(0, 0))
    assert state.return_held()
    assert state.placement.cell_of(BLACK) is None
    assert state.held is None


def test_return_with_a_palette_cube_held_just_lets_go() -> None:
    state = PlayState(puzzle())
    state.select(BLACK)
    assert state.return_held()
    assert state.held is None
    assert not state.return_held()


def test_return_a_cube_under_the_cursor_when_nothing_is_held() -> None:
    state = PlayState(puzzle())
    state.select(BLACK)
    state.activate(Cell(0, 0))
    assert state.return_held()
    assert state.placement.cell_of(BLACK) is None
    state.cursor = Cell(1, 1)
    assert not state.return_held()
    assert state.placement.cell_of(ORANGE) == Cell(1, 1)


def test_select_by_initial_cycles_through_unplaced_matches() -> None:
    state = PlayState(puzzle())
    assert state.select_initial("m") is MAGENTA
    assert state.select_initial("m") is MINT
    assert state.select_initial("M") is MUSTARD
    assert state.select_initial("m") is MAGENTA
    state.activate(Cell(0, 0))
    assert state.select_initial("m") is MINT
    assert state.select_initial("z") is None
    assert state.held is MINT


def test_select_by_initial_skips_the_given() -> None:
    state = PlayState(puzzle())
    assert state.select_initial("o") is None


def test_select_by_slot_counts_from_one_over_the_palette_strip() -> None:
    state = PlayState(puzzle())
    assert state.select_slot(1) is BLACK
    assert state.select_slot(4) is CORAL
    assert state.select_slot(12) is None


def test_cursor_moves_and_stays_on_the_board() -> None:
    state = PlayState(puzzle())
    state.move_cursor(-1, -1)
    assert state.cursor == Cell(0, 0)
    state.move_cursor(2, 3)
    assert state.cursor == Cell(2, 3)
    state.move_cursor(5, 5)
    assert state.cursor == Cell(2, 3)


def test_reset_restores_the_givens() -> None:
    state = PlayState(puzzle())
    state.select(BLACK)
    state.activate(Cell(0, 0))
    state.select(BROWN)
    state.reset()
    assert state.placement == Placement({ORANGE: Cell(1, 1)})
    assert state.held is None


def test_statuses_follow_the_placement() -> None:
    state = PlayState(puzzle(relation("next_to", "black", "brown")))
    assert state.statuses() == (Truth.UNKNOWN,)
    state.select(BLACK)
    state.activate(Cell(0, 0))
    state.select(BROWN)
    state.activate(Cell(0, 1))
    assert state.statuses() == (Truth.SATISFIED,)
    state.activate(Cell(0, 1))
    state.activate(Cell(2, 3))
    assert state.statuses() == (Truth.VIOLATED,)


def test_solved_needs_every_cube_placed_and_every_clue_satisfied() -> None:
    state = PlayState(puzzle(relation("next_to", "black", "brown")))
    cells = [cell for cell in CLASSIC_BOARD if cell != Cell(1, 1)]
    for color, cell in zip(state.palette_cubes(), cells, strict=True):
        assert not state.solved
        state.select(color)
        state.activate(cell)
    assert state.solved


# ------------------------------------------------------------------ hints

CARD_1 = classic_puzzles()[0]


def test_a_hint_is_remembered_explained_and_counted() -> None:
    state = PlayState(CARD_1)
    message = state.take_hint()
    assert state.hint is not None
    assert (state.hint.color, state.hint.cell) == (MAGENTA, Cell(2, 1))
    assert message.startswith("Magenta must go in the bottom row, second column")
    assert state.hints_used == 1


def test_asking_again_without_moving_does_not_count_twice() -> None:
    state = PlayState(CARD_1)
    state.take_hint()
    state.take_hint()
    assert state.hints_used == 1


def test_a_change_on_the_tray_clears_the_hint_but_keeps_the_count() -> None:
    state = PlayState(CARD_1)
    state.take_hint()
    state.select(MAGENTA)
    assert state.hint is not None
    state.activate(Cell(2, 1))
    assert state.hint is None
    state.take_hint()
    state.reset()
    assert state.hint is None
    assert state.hints_used == 2


def test_no_hint_when_nothing_is_forced() -> None:
    state = PlayState(puzzle())
    assert state.take_hint() == "No hint: nothing is forced yet."
    assert state.hint is None
    assert state.hints_used == 0
