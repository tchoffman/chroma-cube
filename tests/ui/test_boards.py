"""Infinite play on the larger boards: the board picker and the 4x4 and 4x5 play screens."""

from dataclasses import replace
from datetime import date
from functools import cache
from typing import Any

import pytest
from textual.pilot import Pilot
from textual.widgets import Label, OptionList, Static

from chroma_cube.core import BOARD_4X4, BOARD_4X5, EXTENDED_16, EXTENDED_20, Puzzle
from chroma_cube.generator import generate, layout
from chroma_cube.puzzles import classic_puzzles
from chroma_cube.ui import ChromaCubeApp
from chroma_cube.ui.home import DifficultyScreen
from chroma_cube.ui.infinite import GeneratedPlayScreen, SeedScreen
from chroma_cube.ui.screens import PlayScreen
from chroma_cube.ui.seeds import GameSpec
from chroma_cube.ui.widgets import ClueRow, PaletteChip, TrayCell
from tests.conftest import DEMO
from tests.ui.test_infinite import settle
from tests.ui.test_layout import assert_reachable

SIZE = (120, 40)
TODAY = date(2026, 10, 8)


@cache
def real(difficulty: str, key: str) -> Puzzle:
    chosen = layout(key)
    return generate(0, difficulty, board=chosen.board, palette=chosen.palette)  # type: ignore[arg-type]


class LayoutFake:
    """Hands out a real puzzle for the board asked for, and records every call."""

    def __init__(self) -> None:
        self.calls: list[tuple[int, str, str]] = []

    def __call__(self, seed: int, difficulty: str, **options: Any) -> Puzzle:
        board = options.get("board")
        key = {None: "classic", BOARD_4X4: "4x4", BOARD_4X5: "4x5"}[board]
        self.calls.append((seed, difficulty, key))
        if key == "classic":
            return replace(DEMO, id=f"gen-{difficulty}-{seed}")
        puzzle = real("easy", key)
        return replace(puzzle, id=f"gen-{key}-{difficulty}-{seed}")


def app(fake: LayoutFake) -> ChromaCubeApp:
    return ChromaCubeApp(classic_puzzles(), generate=fake, today=lambda: TODAY)


def boards(pilot: Pilot[None]) -> OptionList:
    return pilot.app.screen.query_one("#boards", OptionList)


def chosen_marks(pilot: Pilot[None]) -> list[bool]:
    options = boards(pilot)
    return [
        str(options.get_option_at_index(i).prompt).startswith("●")
        for i in range(options.option_count)
    ]


def title(pilot: Pilot[None]) -> str:
    return str(pilot.app.screen.query_one("#card-title", Label).content)


async def test_the_difficulty_screen_offers_the_three_boards() -> None:
    async with app(LayoutFake()).run_test(size=SIZE) as pilot:
        await pilot.press("down", "enter")
        assert isinstance(pilot.app.screen, DifficultyScreen)
        options = boards(pilot)
        prompts = [str(options.get_option_at_index(i).prompt) for i in range(3)]
        assert "3×4" in prompts[0] and "12" in prompts[0]
        assert "4×4" in prompts[1] and "16" in prompts[1]
        assert "4×5" in prompts[2] and "20" in prompts[2]
        assert chosen_marks(pilot) == [True, False, False]
        assert pilot.app.focused is pilot.app.screen.query_one("#difficulties")


async def test_a_board_is_picked_by_keyboard() -> None:
    fake = LayoutFake()
    async with app(fake).run_test(size=SIZE) as pilot:
        await pilot.press("down", "enter", "tab", "down", "down", "enter")
        assert chosen_marks(pilot) == [False, False, True]
        assert pilot.app.focused is pilot.app.screen.query_one("#difficulties")
        await pilot.press("down", "enter")
        await settle(pilot)
        screen = pilot.app.screen
        assert isinstance(screen, GeneratedPlayScreen)
        [(seed, difficulty, key)] = fake.calls
        assert (difficulty, key) == ("medium", "4x5")
        assert title(pilot) == f"Infinite · 4×5 · medium · seed {seed}"
        assert screen.state.puzzle.board == BOARD_4X5


async def test_a_board_and_a_difficulty_are_picked_by_mouse() -> None:
    fake = LayoutFake()
    async with app(fake).run_test(size=SIZE) as pilot:
        await pilot.press("down", "enter")
        options = boards(pilot)
        await pilot.click(options, offset=(4, options.region.height // 2))
        assert chosen_marks(pilot) == [False, True, False]
        difficulties = pilot.app.screen.query_one("#difficulties", OptionList)
        await pilot.click(difficulties, offset=(4, 3))
        await settle(pilot)
        assert isinstance(pilot.app.screen, GeneratedPlayScreen)
        assert fake.calls[0][1:] == ("hard", "4x4")


async def test_new_and_seed_keep_the_board_and_the_choice_is_remembered() -> None:
    fake = LayoutFake()
    async with app(fake).run_test(size=SIZE) as pilot:
        await pilot.press("down", "enter", "tab", "down", "enter", "enter")
        await settle(pilot)
        await pilot.press("n")
        await settle(pilot)
        assert fake.calls[-1][1:] == ("easy", "4x4")
        await pilot.press("s")
        assert isinstance(pilot.app.screen, SeedScreen)
        assert "4×4" in str(pilot.app.screen.query_one(Label).content)
        await pilot.press(*"77", "enter")
        await settle(pilot)
        assert fake.calls[-1] == (77, "easy", "4x4")
        await pilot.press("escape")
        assert isinstance(pilot.app.screen, DifficultyScreen)
        await pilot.press("escape", "enter")
        assert isinstance(pilot.app.screen, DifficultyScreen)
        assert chosen_marks(pilot) == [False, True, False]


async def test_the_daily_stays_on_the_classic_tray() -> None:
    fake = LayoutFake()
    async with app(fake).run_test(size=SIZE) as pilot:
        await pilot.press("down", "enter", "tab", "down", "enter", "escape")
        await pilot.press("down", "enter")
        await settle(pilot)
        assert fake.calls == [(20261008, "medium", "classic")]


def test_game_spec_names_the_board() -> None:
    spec = GameSpec.infinite("hard", 5, "4x5")
    assert spec.title == "Infinite · 4×5 · hard · seed 5"
    assert spec.with_seed(9).layout == "4x5"
    assert GameSpec.infinite("hard", 5).title == "Infinite · hard · seed 5"
    assert GameSpec.daily(TODAY).layout == "classic"


# --------------------------------------------------------------------------- layout


@pytest.mark.parametrize("size", [(80, 24), (100, 30)])
@pytest.mark.parametrize("key", ["4x4", "4x5"])
@pytest.mark.parametrize("difficulty", ["easy", "hard"])
async def test_larger_boards_are_legible(size: tuple[int, int], key: str, difficulty: str) -> None:
    puzzle = real(difficulty, key)
    async with ChromaCubeApp((puzzle,), start_on_cards=True).run_test(size=size) as pilot:
        await pilot.press("enter")
        await pilot.pause()
        screen = pilot.app.screen
        assert isinstance(screen, PlayScreen)
        cells = list(screen.query(TrayCell))
        assert len(cells) == len(puzzle.board)
        for cell in cells:
            assert_reachable(pilot.app, cell)
            if cell.text:
                assert cell.content_size.width >= len(cell.text), cell.text
        for chip in screen.query(PaletteChip):
            if chip.display:
                assert_reachable(pilot.app, chip)
                assert chip.content_size.width >= len(chip.color.name), chip.color.name
        assert_reachable(pilot.app, screen.query(ClueRow).first())
        await pilot.press("h")
        await pilot.pause()
        message = screen.query_one("#message", Static)
        assert message.region.height >= 1
        for cell in cells:
            assert_reachable(pilot.app, cell)


@pytest.mark.parametrize("key", ["4x4", "4x5"])
async def test_every_palette_cube_can_be_picked_up_on_larger_boards(key: str) -> None:
    puzzle = real("hard", key)
    async with ChromaCubeApp((puzzle,), start_on_cards=True).run_test(size=(80, 24)) as pilot:
        await pilot.press("enter")
        screen = pilot.app.screen
        assert isinstance(screen, PlayScreen)
        for chip in screen.query(PaletteChip):
            if chip.display:
                await pilot.click(f"#chip-{chip.color.id}")
                assert screen.state.held == chip.color


def test_palettes_used_here_are_the_extended_ones() -> None:
    assert real("easy", "4x4").palette == EXTENDED_16
    assert real("easy", "4x5").palette == EXTENDED_20


async def test_the_clues_move_under_a_wide_board_when_the_terminal_narrows() -> None:
    puzzle = real("easy", "4x5")
    async with ChromaCubeApp((puzzle,), start_on_cards=True).run_test(size=(100, 30)) as pilot:
        await pilot.press("enter")
        await pilot.pause()
        screen = pilot.app.screen
        assert not screen.has_class("-narrow")
        await pilot.resize_terminal(80, 24)
        await pilot.pause()
        assert screen.has_class("-narrow")
        await pilot.resize_terminal(100, 30)
        await pilot.pause()
        assert not screen.has_class("-narrow")


@pytest.mark.parametrize(("width", "narrow"), [(69, True), (70, False)])
async def test_the_classic_tray_still_goes_wide_from_70_columns(width: int, narrow: bool) -> None:
    async with ChromaCubeApp((DEMO,), start_on_cards=True).run_test(size=(width, 24)) as pilot:
        await pilot.press("enter")
        await pilot.pause()
        assert pilot.app.screen.has_class("-narrow") is narrow
