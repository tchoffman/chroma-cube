"""Drive the whole app through Textual's pilot, as a player would."""

from collections.abc import Sequence
from typing import Any

from textual.app import App
from textual.pilot import Pilot
from textual.screen import Screen
from textual.widgets import OptionList

from chroma_cube.core import CLASSIC_BOARD, CLASSIC_PALETTE, Cell, Puzzle, Truth
from chroma_cube.puzzles import classic_puzzles
from chroma_cube.ui import ChromaCubeApp
from chroma_cube.ui.screens import CardListScreen, PlayScreen, WinScreen
from chroma_cube.ui.widgets import ClueRow, PaletteChip, TrayCell

SIZE = (120, 40)
DEMO = classic_puzzles()[0]
SOLUTION = {
    "white": Cell(0, 0),
    "coral": Cell(0, 1),
    "teal": Cell(0, 3),
    "mint": Cell(2, 0),
    "magenta": Cell(2, 1),
}
"""Where the demo card's free cubes go."""


def app(puzzles: Sequence[Puzzle] = (DEMO,)) -> ChromaCubeApp:
    return ChromaCubeApp(puzzles)


def play(pilot_app: App[None]) -> PlayScreen:
    screen = pilot_app.screen
    assert isinstance(screen, PlayScreen)
    return screen


def cell_widget(pilot_app: App[None], cell: Cell) -> TrayCell:
    return pilot_app.screen.query_one(f"#cell-{cell.row}-{cell.col}", TrayCell)


def clue_truths(screen: Screen[Any]) -> list[Truth]:
    return [row.truth for row in screen.query(ClueRow)]


async def test_the_list_shows_every_card_and_enter_opens_one() -> None:
    second = Puzzle(
        id="other",
        title="Second",
        board=DEMO.board,
        palette=DEMO.palette,
        givens=DEMO.givens,
        clues=DEMO.clues,
    )
    async with app((DEMO, second)).run_test(size=SIZE) as pilot:
        assert isinstance(pilot.app.screen, CardListScreen)
        options = pilot.app.screen.query_one(OptionList)
        assert options.option_count == 2
        prompt = str(options.get_option_at_index(1).prompt)
        assert "2" in prompt and "Second" in prompt
        await pilot.press("down", "enter")
        assert play(pilot.app).state.puzzle is second


async def test_the_card_shows_givens_palette_and_clues() -> None:
    async with app().run_test(size=SIZE) as pilot:
        await pilot.press("enter")
        orange = cell_widget(pilot.app, Cell(1, 1))
        assert orange.text == "▪ Orange"
        assert orange.has_class("given")
        assert orange.styles.background.hex.lower() == "#ff8c00"
        chips = [chip for chip in pilot.app.screen.query(PaletteChip) if chip.display]
        assert sorted(chip.color.id for chip in chips) == sorted(SOLUTION)
        rows = list(pilot.app.screen.query(ClueRow))
        assert [row.text for row in rows] == [f"· {text}" for text in DEMO.rendered_clues()]


async def test_place_a_cube_by_keyboard_and_see_a_clue_flip() -> None:
    async with app().run_test(size=SIZE) as pilot:
        await pilot.press("enter")
        assert clue_truths(pilot.app.screen)[1] is Truth.UNKNOWN
        await pilot.press("m")
        assert play(pilot.app).state.held == CLASSIC_PALETTE.by_id("magenta")
        await pilot.press("down", "down", "right", "enter")
        assert cell_widget(pilot.app, Cell(2, 1)).text.startswith("Magenta")
        assert clue_truths(pilot.app.screen)[1] is Truth.SATISFIED
        assert pilot.app.screen.query_one(ClueRow).text.startswith("·")
        assert list(pilot.app.screen.query(ClueRow))[1].text.startswith("✓")


async def test_a_wrong_move_shows_a_violated_clue() -> None:
    async with app().run_test(size=SIZE) as pilot:
        await pilot.press("enter", "m", "enter")
        assert clue_truths(pilot.app.screen)[1] is Truth.VIOLATED
        assert list(pilot.app.screen.query(ClueRow))[1].text.startswith("✗")


async def test_place_and_move_a_cube_with_the_mouse() -> None:
    async with app().run_test(size=SIZE) as pilot:
        await pilot.press("enter")
        await pilot.click("#chip-magenta")
        await pilot.click("#cell-0-0")
        state = play(pilot.app).state
        magenta = CLASSIC_PALETTE.by_id("magenta")
        assert state.placement.cell_of(magenta) == Cell(0, 0)
        assert not pilot.app.screen.query_one("#chip-magenta").display
        await pilot.click("#cell-0-0")
        await pilot.click("#cell-2-1")
        assert state.placement.cell_of(magenta) == Cell(2, 1)
        assert cell_widget(pilot.app, Cell(0, 0)).text.strip() in ("", "·")
        assert clue_truths(pilot.app.screen)[1] is Truth.SATISFIED


async def test_return_a_placed_cube_to_the_palette() -> None:
    async with app().run_test(size=SIZE) as pilot:
        await pilot.press("enter", "m", "enter", "x")
        assert play(pilot.app).state.placement == DEMO.givens
        assert pilot.app.screen.query_one("#chip-magenta").display


async def test_givens_cannot_be_moved() -> None:
    async with app().run_test(size=SIZE) as pilot:
        await pilot.press("enter")
        await pilot.click("#cell-1-1")
        await pilot.click("#cell-0-0")
        state = play(pilot.app).state
        assert state.placement == DEMO.givens
        await pilot.press("right", "down", "x")
        assert state.placement == DEMO.givens


async def test_reset_puts_the_card_back() -> None:
    async with app().run_test(size=SIZE) as pilot:
        await pilot.press("enter", "m", "enter", "w", "right", "enter")
        assert play(pilot.app).state.placement != DEMO.givens
        await pilot.press("r")
        assert play(pilot.app).state.placement == DEMO.givens
        assert clue_truths(pilot.app.screen) == [Truth.UNKNOWN] * 4


async def place_solution(pilot: Pilot[None]) -> None:
    for color_id, cell in SOLUTION.items():
        await pilot.click(f"#chip-{color_id}")
        await pilot.click(f"#cell-{cell.row}-{cell.col}")


async def test_completing_the_card_shows_the_win_and_marks_it_solved() -> None:
    async with app().run_test(size=SIZE) as pilot:
        await pilot.press("enter")
        await place_solution(pilot)
        await pilot.pause()
        assert clue_truths(pilot.app.screen_stack[-2]) == [Truth.SATISFIED] * 4
        assert isinstance(pilot.app.screen, WinScreen)
        await pilot.click("#back")
        await pilot.pause()
        assert isinstance(pilot.app.screen, CardListScreen)
        prompt = str(pilot.app.screen.query_one(OptionList).get_option_at_index(0).prompt)
        assert "✓" in prompt


async def test_next_card_opens_the_following_card() -> None:
    second = Puzzle(
        id="other",
        title="Second",
        board=CLASSIC_BOARD,
        palette=CLASSIC_PALETTE,
        givens=DEMO.givens,
        clues=DEMO.clues,
    )
    async with app((DEMO, second)).run_test(size=SIZE) as pilot:
        await pilot.press("enter")
        await place_solution(pilot)
        await pilot.pause()
        await pilot.click("#next")
        await pilot.pause()
        assert play(pilot.app).state.puzzle is second
        await pilot.press("escape")
        assert isinstance(pilot.app.screen, CardListScreen)


async def test_escape_drops_the_held_cube_before_leaving() -> None:
    async with app().run_test(size=SIZE) as pilot:
        await pilot.press("enter", "m", "escape")
        assert play(pilot.app).state.held is None
        await pilot.press("escape")
        assert isinstance(pilot.app.screen, CardListScreen)


async def test_q_quits() -> None:
    async with app().run_test(size=SIZE) as pilot:
        await pilot.press("q")
        assert not pilot.app.is_running
