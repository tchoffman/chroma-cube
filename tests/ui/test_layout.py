"""The play screen fits common terminal sizes and keeps the keyboard on the tray."""

import textwrap

import pytest
from textual.app import App
from textual.widget import Widget
from textual.widgets import Footer, Static

from chroma_cube.core import (
    CLASSIC_PALETTE,
    Board,
    Cell,
    Color,
    Palette,
    Placement,
    Puzzle,
    relation,
)
from chroma_cube.ui import ChromaCubeApp
from chroma_cube.ui.screens import PlayScreen
from chroma_cube.ui.widgets import ClueRow, PaletteChip, TrayCell
from tests.conftest import DEMO

LONG = Puzzle(
    id="long",
    title="Empty tray, many clues",
    board=DEMO.board,
    palette=DEMO.palette,
    givens=Placement(),
    clues=tuple(
        relation("next_to", a.id, b.id)
        for a, b in zip(CLASSIC_PALETTE.colors, CLASSIC_PALETTE.colors[1:], strict=False)
    )
    * 2,
)
"""Every cube in the palette and more clues than any screen shows at once."""


def wide_puzzle(rows: int, cols: int) -> Puzzle:
    palette = Palette(
        tuple(
            Color(f"c{index}", f"Hue{index}", f"#{(index * 12) % 256:02x}8040")
            for index in range(rows * cols)
        )
    )
    return Puzzle(
        id=f"board-{rows}x{cols}",
        title="Generated",
        board=Board(rows, cols),
        palette=palette,
        givens=Placement({palette.colors[0]: Cell(0, 0)}),
        clues=(relation("next_to", "c1", "c2"),),
    )


def assert_reachable(app: App[None], widget: Widget) -> None:
    """The widget is on screen, above the status line, and a click on it lands on it."""
    width, height = app.size
    region = widget.region
    assert region.width > 0 and region.height > 0, widget
    assert region.x >= 0 and region.right <= width, widget
    assert region.y >= 0 and region.bottom <= height - 2, widget
    hit, _ = app.screen.get_widget_at(region.x + region.width // 2, region.y + region.height // 2)
    assert hit is widget, (widget, hit)


@pytest.mark.parametrize("size", [(80, 24), (120, 40), (60, 20)])
@pytest.mark.parametrize("puzzle", [DEMO, LONG], ids=["demo", "empty-tray"])
async def test_every_cell_and_palette_cube_is_reachable(
    size: tuple[int, int], puzzle: Puzzle
) -> None:
    async with ChromaCubeApp((puzzle,), start_on_cards=True).run_test(size=size) as pilot:
        await pilot.press("enter")
        await pilot.pause()
        for cell in pilot.app.screen.query(TrayCell):
            assert_reachable(pilot.app, cell)
        for chip in pilot.app.screen.query(PaletteChip):
            if chip.display:
                assert_reachable(pilot.app, chip)
        first_clue = pilot.app.screen.query(ClueRow).first()
        assert_reachable(pilot.app, first_clue)


@pytest.mark.parametrize("shape", [(4, 4), (4, 5), (2, 3)])
async def test_other_board_sizes_fit(shape: tuple[int, int]) -> None:
    async with ChromaCubeApp((wide_puzzle(*shape),), start_on_cards=True).run_test(
        size=(100, 30)
    ) as pilot:
        await pilot.press("enter")
        await pilot.pause()
        cells = list(pilot.app.screen.query(TrayCell))
        assert len(cells) == shape[0] * shape[1]
        for cell in cells:
            assert_reachable(pilot.app, cell)
        for chip in pilot.app.screen.query(PaletteChip):
            if chip.display:
                assert_reachable(pilot.app, chip)


async def test_arrows_move_the_cursor_even_when_the_clues_overflow() -> None:
    async with ChromaCubeApp((LONG,), start_on_cards=True).run_test(size=(80, 24)) as pilot:
        await pilot.press("enter")
        screen = pilot.app.screen
        assert isinstance(screen, PlayScreen)
        await pilot.press("down", "right")
        assert screen.state.cursor == Cell(1, 1)
        await pilot.click(ClueRow)
        await pilot.press("down")
        assert screen.state.cursor == Cell(2, 1)


async def test_page_down_scrolls_the_clues() -> None:
    async with ChromaCubeApp((LONG,), start_on_cards=True).run_test(size=(80, 24)) as pilot:
        await pilot.press("enter")
        clues = pilot.app.screen.query_one("#clues")
        assert clues.scroll_y == 0
        await pilot.press("pagedown")
        await pilot.pause()
        assert clues.scroll_y > 0


@pytest.mark.parametrize("size", [(80, 24), (60, 20)])
@pytest.mark.parametrize(
    ("keys", "start", "end"),
    [
        ((), "Magenta must go", "can still hold."),
        (("c", "right", "enter", "m", "left", "enter"), "Magenta does not belong", "1 more."),
    ],
    ids=["first-hint", "misplaced-with-three-clues"],
)
async def test_a_long_hint_wraps_and_the_tray_still_fits(
    size: tuple[int, int], keys: tuple[str, ...], start: str, end: str
) -> None:
    async with ChromaCubeApp((DEMO,), start_on_cards=True).run_test(size=size) as pilot:
        await pilot.press("enter", *keys, "h")
        await pilot.pause()
        message = pilot.app.screen.query_one("#message", Static)
        text = str(message.render())
        assert text.startswith(start) and text.endswith(end), text
        lines = textwrap.wrap(text, width=message.content_size.width)
        assert len(lines) > 1
        assert len(lines) <= message.content_size.height, lines
        assert message.region.bottom <= pilot.app.screen.query_one(Footer).region.y
        for cell in pilot.app.screen.query(TrayCell):
            assert_reachable(pilot.app, cell)
