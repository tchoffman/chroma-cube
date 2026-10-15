"""The pieces of the play screen: tray cells, palette chips and clue rows."""

from __future__ import annotations

from typing import ClassVar

from textual.message import Message
from textual.strip import Strip
from textual.widget import Widget
from textual.widgets import Static

from chroma_cube.core import Cell, Color, Truth
from chroma_cube.ui.cube import chip_line, cube_cell, well_cell
from chroma_cube.ui.swatch import STATUS_MARKERS, cube_tints, is_dark, text_color

GIVEN_MARK = "▪"
"""Before a given cube's name, in the same contrasting text color."""
HELD_MARK = "▸"


class TrayCell(Widget):
    """One well of the tray, with the cube on it drawn as a block in its own colors.

    The frame around the well is drawn half a cell thick inside the cell, so neighbouring
    wells share one frame bar; its color (set in the stylesheet) shows the cursor, the
    held cube and a hint.
    """

    COMPONENT_CLASSES: ClassVar[set[str]] = {
        "tray-cell--frame",
        "tray-cell--floor",
        "tray-cell--shadow",
    }

    class Clicked(Message):
        def __init__(self, cell: Cell) -> None:
            super().__init__()
            self.cell = cell

    def __init__(self, cell: Cell) -> None:
        super().__init__(id=f"cell-{cell.row}-{cell.col}")
        self.cell = cell
        self.text = ""
        self.color: Color | None = None
        self.given = False

    def show(
        self, color: Color | None, *, given: bool, cursor: bool, held: bool, hinted: bool = False
    ) -> None:
        self.color = color
        self.given = given
        if color is None:
            self.text = ""
            self.styles.clear_rule("background")
            self.styles.clear_rule("color")
        else:
            mark = f"{GIVEN_MARK} " if given else f"{HELD_MARK} " if held else ""
            self.text = f"{mark}{color.name}"
            self.styles.background = color.hex
            self.styles.color = text_color(color.hex)
        self.set_class(color is None, "empty")
        self.set_class(color is not None and is_dark(color.hex), "dark")
        self.set_class(given, "given")
        self.set_class(cursor, "cursor")
        self.set_class(held, "held")
        self.set_class(hinted, "hinted")
        self.refresh()

    def render_line(self, y: int) -> Strip:
        width, height = self.size
        frame = _background(self, "tray-cell--frame")
        if self.color is None:
            lines = well_cell(
                width,
                height,
                frame=frame,
                floor=_background(self, "tray-cell--floor"),
                shadow=_background(self, "tray-cell--shadow"),
            )
        else:
            lines = cube_cell(
                width,
                height,
                frame=frame,
                face=self.color.hex,
                tints=cube_tints(self.color.hex, given=self.given),
                text=self.text,
                text_color=text_color(self.color.hex),
                style=self.rich_style.without_color,
            )
        return Strip(lines[y], width) if 0 <= y < len(lines) else Strip.blank(width)

    def on_click(self) -> None:
        self.post_message(self.Clicked(self.cell))


class PaletteChip(Widget):
    """A cube waiting in the palette strip, drawn as a one-line block."""

    class Clicked(Message):
        def __init__(self, color: Color) -> None:
            super().__init__()
            self.color = color

    def __init__(self, color: Color) -> None:
        super().__init__(id=f"chip-{color.id}")
        self.color = color
        self.text = color.name
        self.set_class(is_dark(color.hex), "dark")

    def show(self, slot: int | None, *, held: bool, hinted: bool = False) -> None:
        """`slot` is the chip's number key, or None when the cube is on the tray."""
        self.display = slot is not None
        self.set_class(held, "held")
        self.set_class(hinted, "hinted")
        key = "" if slot is None or slot > 10 else f"{slot % 10} "
        pointer = f"{HELD_MARK} " if held else ""
        self.text = f"{pointer}{key}{self.color.name}"
        self.refresh()

    def render_line(self, y: int) -> Strip:
        width = self.size.width
        if y != 0:
            return Strip.blank(width, self.rich_style)
        line = chip_line(
            width,
            outside=self.background_colors[1].hex6.lower(),
            face=self.color.hex,
            tints=cube_tints(self.color.hex),
            text=self.text,
            text_color=text_color(self.color.hex),
            style=self.rich_style.without_color,
        )
        return Strip(line, width)

    def on_click(self) -> None:
        self.post_message(self.Clicked(self.color))


def _background(widget: Widget, component: str) -> str:
    """The background a stylesheet component gives, as `#rrggbb`, over whatever is behind
    the widget (not over the widget's own background, which is its cube's color)."""
    parent = widget.parent
    assert isinstance(parent, Widget), widget
    behind = parent.background_colors[1]
    return (behind + widget.get_component_styles(component).background).hex6.lower()


class ClueRow(Static):
    """One clue with a marker saying whether it holds yet."""

    def __init__(self, sentence: str) -> None:
        super().__init__(markup=False, classes="clue")
        self.sentence = sentence
        self.truth = Truth.UNKNOWN
        self.text = ""
        self.show(Truth.UNKNOWN)

    def show(self, truth: Truth, *, hinted: bool = False) -> None:
        self.truth = truth
        self.text = f"{STATUS_MARKERS[truth]} {self.sentence}"
        for value in Truth:
            self.set_class(value is truth, value.value)
        self.set_class(hinted, "hinted")
        self.update(self.text)
