"""Cubes, wells and palette chips drawn as blocks of half-cell color."""

import pytest
from rich.segment import Segment
from rich.style import Style
from textual.pilot import Pilot
from textual.widget import Widget

from chroma_cube.core import Puzzle
from chroma_cube.puzzles import classic_puzzles
from chroma_cube.ui import ChromaCubeApp
from chroma_cube.ui.cube import chip_line, cube_cell, well_cell
from chroma_cube.ui.screens import PlayScreen
from chroma_cube.ui.swatch import cube_tints
from chroma_cube.ui.widgets import PaletteChip, TrayCell
from tests.conftest import DEMO
from tests.ui.test_boards import real

FRAME = "#3a3a3a"
ORANGE = "#ff8c00"
TINTS = cube_tints(ORANGE)


def text_of(line: list[Segment]) -> str:
    return "".join(segment.text for segment in line)


def colors_of(line: list[Segment]) -> set[str]:
    found = set()
    for segment in line:
        style = segment.style or Style()
        for color in (style.color, style.bgcolor):
            if color is not None:
                found.add(color.get_truecolor().hex)
    return found


def orange(width: int, height: int, text: str = "▸ Orange") -> list[list[Segment]]:
    return cube_cell(
        width, height, frame=FRAME, face=ORANGE, tints=TINTS, text=text, text_color="#000000"
    )


@pytest.mark.parametrize("height", [3, 4, 5])
def test_a_cube_fills_its_cell_and_shows_its_name_on_the_front_face(height: int) -> None:
    lines = orange(12, height)
    assert len(lines) == height
    assert all(sum(len(segment.text) for segment in line) == 12 for line in lines)
    name_line = lines[height // 2]
    assert text_of(name_line)[1:-1] == " ▸ Orange "
    for segment in name_line[1:-1]:
        if segment.text.strip():
            assert segment.style is not None and segment.style.bgcolor is not None
            assert segment.style.bgcolor.get_truecolor().hex == ORANGE
            assert segment.style.color is not None
            assert segment.style.color.get_truecolor().hex == "#000000"


@pytest.mark.parametrize("height", [3, 4, 5])
def test_a_cube_is_lit_on_top_shaded_right_and_below_inside_the_frame(height: int) -> None:
    lines = orange(12, height)
    assert {FRAME, TINTS.top} <= colors_of(lines[0])
    assert {FRAME, TINTS.bottom} <= colors_of(lines[-1])
    assert {ORANGE, TINTS.side, FRAME} <= colors_of(lines[height // 2])
    assert text_of(lines[height // 2])[-1] == "▌"
    assert text_of(lines[height // 2])[0] == "▐"


def test_the_lit_top_and_shaded_bottom_thicken_on_a_taller_cell() -> None:
    short, tall = orange(12, 4), orange(12, 5)
    assert ORANGE not in colors_of(short[0]) and ORANGE in colors_of(short[1])
    assert TINTS.top in colors_of(tall[1]) and TINTS.bottom in colors_of(tall[3])


def test_a_name_too_long_for_the_face_spills_over_the_edges_then_is_cut() -> None:
    assert text_of(orange(8, 3)[1]) == "▸ Orange"
    assert text_of(orange(6, 3)[1]) == "▸ Ora…"


def test_an_empty_well_is_shaded_inside_and_shows_no_cube() -> None:
    lines = well_cell(12, 4, frame=FRAME, floor="#101010", shadow="#000000")
    assert len(lines) == 4
    assert {FRAME, "#000000"} <= colors_of(lines[0])
    assert "#101010" in colors_of(lines[2])
    assert not {ORANGE, TINTS.top, TINTS.side} & set().union(*map(colors_of, lines))
    assert all(not text_of(line).strip(" ▀▄▌▐▖▗▘▝▛▜▙▟") for line in lines)


def test_a_chip_is_one_line_with_a_lit_left_strip_and_a_shaded_right_one() -> None:
    line = chip_line(
        12, outside="#121212", face=ORANGE, tints=TINTS, text="1 Orange", text_color="#000000"
    )
    assert text_of(line) == "▐ 1 Orange ▌"
    assert line[0].style is not None and line[0].style.color is not None
    assert line[0].style.color.get_truecolor().hex == TINTS.top
    assert line[-1].style is not None and line[-1].style.color is not None
    assert line[-1].style.color.get_truecolor().hex == TINTS.side


def test_a_chip_drops_its_edges_before_cutting_a_name() -> None:
    line = chip_line(
        8, outside="#121212", face=ORANGE, tints=TINTS, text="1 Orange", text_color="#000000"
    )
    assert text_of(line) == "1 Orange"
    assert colors_of(line) == {ORANGE, "#000000"}


# --------------------------------------------------------------------------- on screen


def puzzle_named(name: str) -> Puzzle:
    return classic_puzzles()[0] if name == "card-1" else real("hard", "4x5")


def drawn(widget: Widget) -> list[list[Segment]]:
    return [list(widget.render_line(y)) for y in range(widget.size.height)]


def ring_color(cell: TrayCell) -> str:
    """The color of the frame at the cell's top-left corner."""
    first = drawn(cell)[0][0]
    assert first.style is not None and first.style.bgcolor is not None
    return first.style.bgcolor.get_truecolor().hex


async def open_card(pilot: Pilot[None], *keys: str) -> PlayScreen:
    await pilot.press("enter", *keys)
    await pilot.pause()
    screen = pilot.app.screen
    assert isinstance(screen, PlayScreen)
    return screen


SHOTS = [("card-1", (80, 24)), ("card-1", (100, 30)), ("4x5", (100, 30))]


@pytest.mark.parametrize("theme", ["textual-dark", "textual-light"])
@pytest.mark.parametrize(("name", "size"), SHOTS)
async def test_every_cube_shows_its_full_name_between_a_lit_top_and_a_shaded_bottom(
    name: str, size: tuple[int, int], theme: str
) -> None:
    puzzle = puzzle_named(name)
    async with ChromaCubeApp((puzzle,), start_on_cards=True).run_test(size=size) as pilot:
        pilot.app.theme = theme
        screen = await open_card(pilot, "1", "enter")
        cubes = [cell for cell in screen.query(TrayCell) if cell.text]
        placed = [cell for cell in puzzle.board if screen.state.placement.color_at(cell)]
        assert len(cubes) == len(placed) > 1
        for cell in cubes:
            color = screen.state.placement.color_at(cell.cell)
            assert color is not None
            tints = cube_tints(color.hex, given=screen.state.is_given(color))
            lines = drawn(cell)
            assert cell.text in text_of(lines[len(lines) // 2]), cell.text
            assert tints.top in colors_of(lines[0]), cell.text
            assert tints.bottom in colors_of(lines[-1]) or tints.bottom == color.hex
        for chip in screen.query(PaletteChip):
            if chip.display:
                assert chip.color.name in text_of(drawn(chip)[0])


@pytest.mark.parametrize("theme", ["textual-dark", "textual-light"])
async def test_empty_wells_and_the_frame_stand_out_from_the_page(theme: str) -> None:
    async with ChromaCubeApp((DEMO,), start_on_cards=True).run_test(size=(100, 30)) as pilot:
        pilot.app.theme = theme
        screen = await open_card(pilot, "right")
        page = screen.background_colors[1].hex6.lower()
        empty = screen.query_one("#cell-0-0", TrayCell)
        assert not empty.text
        frame = ring_color(empty)
        floor = colors_of(drawn(empty)[2]) - {frame}
        assert frame != page and page not in floor and floor
        for color in DEMO.palette:
            assert color.hex not in set().union(*map(colors_of, drawn(empty)))


async def test_cursor_held_and_hinted_cells_each_ring_in_their_own_color() -> None:
    async with ChromaCubeApp((DEMO,), start_on_cards=True).run_test(size=(100, 30)) as pilot:
        screen = await open_card(pilot)

        def ring(row: int, col: int) -> str:
            return ring_color(screen.query_one(f"#cell-{row}-{col}", TrayCell))

        plain = ring(0, 1)
        cursor = ring(0, 0)
        await pilot.press("h")
        await pilot.pause()
        hint = screen.state.hint
        assert hint is not None
        hinted = ring(hint.cell.row, hint.cell.col)
        await pilot.press("c", "enter", "enter", "right")
        await pilot.pause()
        assert screen.state.held is not None
        held = ring(0, 0)
        assert len({plain, cursor, hinted, held}) == 4, (plain, cursor, hinted, held)
