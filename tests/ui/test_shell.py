"""The shell screens around play: home, the card list, the infinite picker and the win."""

from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest
from textual.pilot import Pilot
from textual.widgets import Button, Label, OptionList

from chroma_cube.core import CLASSIC_PALETTE
from chroma_cube.progress import Progress
from chroma_cube.puzzles import classic_puzzles
from chroma_cube.ui import ChromaCubeApp
from chroma_cube.ui.home import DifficultyScreen, HomeScreen, Wordmark
from chroma_cube.ui.screens import TIER_COLORS, CardListScreen, PlayScreen, WinScreen, cheer
from tests.conftest import DEMO
from tests.ui.test_app import place_solution

SIZE = (80, 24)


def shell_app(progress: Progress, *, cards: bool = False) -> ChromaCubeApp:
    return ChromaCubeApp(
        classic_puzzles(), progress, today=lambda: date(2026, 10, 14), start_on_cards=cards
    )


def solved_progress(tmp_path: Path, count: int) -> Progress:
    progress = Progress(tmp_path)
    for puzzle in classic_puzzles()[:count]:
        progress.record_solve(puzzle.id, hints=0)
    return progress


def text_of(pilot: Pilot[None], selector: str) -> str:
    return str(pilot.app.screen.query_one(selector, Label).content)


def prompts(options: OptionList) -> list[str]:
    return [str(options.get_option_at_index(i).prompt) for i in range(options.option_count)]


# ---------------------------------------------------------------------- home


async def test_home_has_a_title_block(tmp_path: Path) -> None:
    async with shell_app(Progress(tmp_path)).run_test(size=SIZE) as pilot:
        assert isinstance(pilot.app.screen, HomeScreen)
        wordmark = pilot.app.screen.query_one(Wordmark)
        letters = "".join(ch for ch in str(wordmark.render()) if ch.isalpha())
        assert letters == "CHROMACUBE"
        assert text_of(pilot, "#tagline")


def test_the_wordmark_is_painted_in_classic_cube_colors() -> None:
    hexes = {color.hex.lower() for color in CLASSIC_PALETTE}
    assert {hex_color.lower() for hex_color in Wordmark.COLORS} <= hexes
    assert len(Wordmark.COLORS) == len("CHROMACUBE")


@pytest.mark.parametrize("size", [(80, 24), (60, 20), (40, 16)])
async def test_the_home_screen_fits_small_terminals(tmp_path: Path, size: tuple[int, int]) -> None:
    async with shell_app(Progress(tmp_path)).run_test(size=size) as pilot:
        modes = pilot.app.screen.query_one("#modes", OptionList)
        assert modes.region.bottom <= size[1] - 1
        assert modes.region.right <= size[0]


async def test_home_modes_open_by_mouse(tmp_path: Path) -> None:
    async with shell_app(Progress(tmp_path)).run_test(size=SIZE) as pilot:
        modes = pilot.app.screen.query_one("#modes", OptionList)
        await pilot.click(modes, offset=(4, 3))
        await pilot.pause()
        assert isinstance(pilot.app.screen, DifficultyScreen)


async def test_home_modes_name_and_describe_each_mode(tmp_path: Path) -> None:
    async with shell_app(Progress(tmp_path)).run_test(size=SIZE) as pilot:
        modes = prompts(pilot.app.screen.query_one("#modes", OptionList))
        assert modes[0].startswith("Classic cards") and "25 hand-made cards" in modes[0]
        assert modes[1].startswith("Infinite") and "difficulty" in modes[1]
        assert modes[2].startswith("Daily") and "medium" in modes[2]


# ---------------------------------------------------------------------- card list


async def test_every_card_row_shows_its_tier_and_solved_state(tmp_path: Path) -> None:
    async with shell_app(solved_progress(tmp_path, 7), cards=True).run_test(size=SIZE) as pilot:
        assert isinstance(pilot.app.screen, CardListScreen)
        rows = prompts(pilot.app.screen.query_one("#cards", OptionList))
        puzzles = classic_puzzles()
        assert len(rows) == len(puzzles)
        for index, (row, puzzle) in enumerate(zip(rows, puzzles, strict=True)):
            assert puzzle.title in row and puzzle.difficulty in row
            assert ("✓" in row) == (index < 7)
            assert row.lstrip().startswith(str(index + 1))


async def test_the_list_counts_solved_cards(tmp_path: Path) -> None:
    async with shell_app(solved_progress(tmp_path, 7), cards=True).run_test(size=SIZE) as pilot:
        assert text_of(pilot, "#solved-count") == "7 of 25 solved"


async def test_the_first_unsolved_card_is_preselected(tmp_path: Path) -> None:
    progress = solved_progress(tmp_path, 3)
    progress.record_solve(classic_puzzles()[4].id, hints=1)
    async with shell_app(progress, cards=True).run_test(size=SIZE) as pilot:
        assert pilot.app.screen.query_one("#cards", OptionList).highlighted == 3
        await pilot.press("enter")
        screen = pilot.app.screen
        assert isinstance(screen, PlayScreen) and screen.state.puzzle is classic_puzzles()[3]


async def test_with_every_card_solved_the_first_is_preselected(tmp_path: Path) -> None:
    async with shell_app(solved_progress(tmp_path, 25), cards=True).run_test(size=SIZE) as pilot:
        assert pilot.app.screen.query_one("#cards", OptionList).highlighted == 0
        assert text_of(pilot, "#solved-count") == "25 of 25 solved"


async def test_back_from_a_solve_moves_to_the_next_unsolved_card(tmp_path: Path) -> None:
    second = replace(DEMO, id="second", title="Second")
    third = replace(DEMO, id="third", title="Third", difficulty="hard")
    app = ChromaCubeApp((DEMO, second, third), Progress(tmp_path), start_on_cards=True)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("enter")
        await place_solution(pilot)
        await pilot.pause()
        await pilot.click("#back")
        await pilot.pause()
        cards = pilot.app.screen.query_one("#cards", OptionList)
        assert cards.highlighted == 1
        assert text_of(pilot, "#solved-count") == "1 of 3 solved"


async def test_a_card_without_a_tier_still_lists(tmp_path: Path) -> None:
    untiered = replace(DEMO, difficulty="")
    app = ChromaCubeApp((untiered,), Progress(tmp_path), start_on_cards=True)
    async with app.run_test(size=SIZE) as pilot:
        [row] = prompts(pilot.app.screen.query_one("#cards", OptionList))
        assert "Demo" in row


def test_every_tier_has_a_color() -> None:
    from chroma_cube.puzzles.classic import DIFFICULTIES

    assert set(TIER_COLORS) == set(DIFFICULTIES)


# ---------------------------------------------------------------------- infinite


async def test_the_infinite_pickers_sit_in_titled_panels(tmp_path: Path) -> None:
    async with shell_app(Progress(tmp_path)).run_test(size=SIZE) as pilot:
        await pilot.press("down", "enter")
        screen = pilot.app.screen
        assert isinstance(screen, DifficultyScreen)
        assert screen.query_one("#difficulties", OptionList).border_title == "Difficulty"
        assert screen.query_one("#boards", OptionList).border_title == "Board"


# ---------------------------------------------------------------------- win


async def test_the_win_names_the_card_and_cheers_by_hints(tmp_path: Path) -> None:
    async with shell_app(Progress(tmp_path)).run_test(size=SIZE) as pilot:
        pilot.app.push_screen(WinScreen("First Steps", True, 0))
        await pilot.pause()
        assert text_of(pilot, "#win-card") == "First Steps"
        assert text_of(pilot, "#win-hints") == "Solved without hints."
        assert text_of(pilot, "#win-cheer") == cheer(0)
        assert pilot.app.focused is pilot.app.screen.query_one("#next", Button)


def test_the_cheer_differs_with_and_without_hints() -> None:
    assert cheer(0) != cheer(1)
    assert cheer(1) == cheer(3)
    assert cheer(0) and cheer(2)
