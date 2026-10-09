"""Progress carries over between runs of the app."""

from pathlib import Path

from textual.widgets import OptionList

from chroma_cube.core import CLASSIC_PALETTE, Cell
from chroma_cube.progress import Progress
from chroma_cube.ui import ChromaCubeApp
from chroma_cube.ui.screens import CardListScreen
from tests.ui.test_app import DEMO, SIZE, place_solution, play


def tick_shown(app: ChromaCubeApp) -> bool:
    screen = app.screen
    assert isinstance(screen, CardListScreen)
    return "✓" in str(screen.query_one(OptionList).get_option_at_index(0).prompt)


async def test_a_solved_card_shows_solved_after_a_restart(tmp_path: Path) -> None:
    async with ChromaCubeApp((DEMO,), Progress(tmp_path)).run_test(size=SIZE) as pilot:
        assert not tick_shown(pilot.app)
        await pilot.press("enter")
        await place_solution(pilot)
        await pilot.pause()
        await pilot.click("#back")
        await pilot.pause()
    async with ChromaCubeApp((DEMO,), Progress(tmp_path)).run_test(size=SIZE) as pilot:
        assert tick_shown(pilot.app)
        await pilot.press("enter")
        assert play(pilot.app).state.placement == DEMO.givens


async def test_placed_cubes_come_back_after_a_restart(tmp_path: Path) -> None:
    magenta = CLASSIC_PALETTE.by_id("magenta")
    white = CLASSIC_PALETTE.by_id("white")
    async with ChromaCubeApp((DEMO,), Progress(tmp_path)).run_test(size=SIZE) as pilot:
        await pilot.press("enter")
        await pilot.click("#chip-magenta")
        await pilot.click("#cell-2-1")
        await pilot.click("#chip-white")
        await pilot.click("#cell-0-0")
    async with ChromaCubeApp((DEMO,), Progress(tmp_path)).run_test(size=SIZE) as pilot:
        assert not tick_shown(pilot.app)
        await pilot.press("enter")
        placement = play(pilot.app).state.placement
        assert placement.cell_of(magenta) == Cell(2, 1)
        assert placement.cell_of(white) == Cell(0, 0)
        assert not pilot.app.screen.query_one("#chip-magenta").display


async def test_reset_is_saved_too(tmp_path: Path) -> None:
    async with ChromaCubeApp((DEMO,), Progress(tmp_path)).run_test(size=SIZE) as pilot:
        await pilot.press("enter")
        await pilot.click("#chip-magenta")
        await pilot.click("#cell-2-1")
        await pilot.press("r")
    assert Progress(tmp_path).saved_board(DEMO) is None


async def test_the_app_uses_the_default_store_without_an_argument(isolated_data_dir: Path) -> None:
    async with ChromaCubeApp((DEMO,)).run_test(size=SIZE) as pilot:
        await pilot.press("enter")
        await pilot.click("#chip-magenta")
        await pilot.click("#cell-2-1")
    assert Progress(isolated_data_dir).saved_board(DEMO) is not None
