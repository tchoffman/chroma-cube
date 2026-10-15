"""Cubes, empty wells and palette chips drawn as blocks of half-cell color.

Each terminal cell is split into four quadrants, so a cell of the tray is a grid of colors
twice as wide and twice as tall as the cell. Each 2 x 2 group of quadrants becomes one block
character (half blocks and quadrants) in at most two colors, so edges half a cell thick can
be drawn between the frame and a cube, and the lit and shaded edges scale with the cell.
"""

from __future__ import annotations

from rich.segment import Segment
from rich.style import Style

from chroma_cube.ui.swatch import CubeTints

__all__ = ["chip_line", "cube_cell", "well_cell"]

Line = list[Segment]
_Canvas = list[list[str]]

_BLOCKS = " ▘▝▀▖▌▞▛▗▚▐▜▄▙▟█"
"""A block character by which of its quadrants are in the foreground color, as bits:
upper left 1, upper right 2, lower left 4, lower right 8."""
ELLIPSIS = "…"


def cube_cell(
    width: int,
    height: int,
    *,
    frame: str,
    face: str,
    tints: CubeTints,
    text: str,
    text_color: str,
    style: Style | None = None,
) -> list[Line]:
    """A cube sitting in its well: a frame half a cell thick, then the cube's top, front face,
    right side and bottom, with `text` centred on the front face."""
    across, down = 2 * width, 2 * height
    edge = 1 if height < 5 else 2  # half-rows of lit top, and of shaded bottom
    canvas = [[frame] * across for _ in range(down)]
    for y in range(1, down - 1):
        row = canvas[y]
        for x in range(1, across - 1):
            if y <= edge:
                row[x] = tints.top
            elif y >= down - 1 - edge:
                row[x] = tints.bottom
            elif x == across - 2:
                row[x] = tints.side
            else:
                row[x] = face
    lines = [_blocks(canvas, row, frame) for row in range(height)]
    text_style = (style or Style()) + Style(color=text_color, bgcolor=face)
    middle = height // 2
    return [
        _with_text(line, width, text, text_style) if row == middle else _simple(line)
        for row, line in enumerate(lines)
    ]


def well_cell(width: int, height: int, *, frame: str, floor: str, shadow: str) -> list[Line]:
    """An empty well in the frame, its top and left inner walls in shadow."""
    across, down = 2 * width, 2 * height
    canvas = [[frame] * across for _ in range(down)]
    for y in range(1, down - 1):
        for x in range(1, across - 1):
            canvas[y][x] = shadow if y == 1 or x == 1 else floor
    return [_simple(_blocks(canvas, row, frame)) for row in range(height)]


def chip_line(
    width: int,
    *,
    outside: str,
    face: str,
    tints: CubeTints,
    text: str,
    text_color: str,
    style: Style | None = None,
) -> Line:
    """A cube one line tall: a lit strip on the left, the face, a shaded strip on the right.
    The strips go first when the text needs their room."""
    text_style = (style or Style()) + Style(color=text_color, bgcolor=face)
    if len(text) > width - 2:
        return [Segment(_fit(text, width).center(width), text_style)]
    canvas = [[tints.top, *[face] * (2 * width - 4), tints.side] for _ in range(2)]
    canvas = [[outside, *row, outside] for row in canvas]
    return _with_text(_blocks(canvas, 0, outside), width, text, text_style)


def _fit(text: str, width: int) -> str:
    return text if len(text) <= width else text[: max(width - 1, 0)] + ELLIPSIS


def _with_text(line: Line, width: int, text: str, style: Style) -> Line:
    """`line`, one segment per cell, with `text` over its middle, inside its edge columns
    when it fits there."""
    inner = width - 2
    if len(text) <= inner:
        start = 1 + (inner - len(text)) // 2
    else:
        text = _fit(text, width)
        start = (width - len(text)) // 2
    cells = [*line[:start], *(Segment(char, style) for char in text), *line[start + len(text) :]]
    return list(Segment.simplify(cells))


def _simple(line: Line) -> Line:
    return list(Segment.simplify(line))


def _blocks(canvas: _Canvas, row: int, ground: str) -> Line:
    """One terminal row of `canvas` as block characters, with `ground` (the frame, or the
    screen around a chip) as the background where a cell is half ground."""
    upper, lower = canvas[2 * row], canvas[2 * row + 1]
    line: Line = []
    for x in range(0, len(upper), 2):
        quads = [upper[x], upper[x + 1], lower[x], lower[x + 1]]
        line.append(_block(quads, ground))
    return line


def _block(quads: list[str], ground: str) -> Segment:
    counts: dict[str, int] = {}
    for color in quads:
        counts[color] = counts.get(color, 0) + 1
    if len(counts) == 1:
        return Segment(" ", Style(bgcolor=quads[0]))
    ranked = sorted(counts, key=lambda color: (-counts[color], color != ground))
    back, fore = ranked[0], ranked[1]
    mask = sum(1 << index for index, color in enumerate(quads) if color == fore)
    return Segment(_BLOCKS[mask], Style(color=fore, bgcolor=back))
