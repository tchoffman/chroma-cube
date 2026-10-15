"""The pieces of the play screen: tray cells and palette chips (clue rows live on the card)."""

from __future__ import annotations

from textual.message import Message
from textual.widgets import Static

from chroma_cube.core import Cell, Color
from chroma_cube.ui.card import ClueRow as ClueRow
from chroma_cube.ui.swatch import is_dark, text_color

GIVEN_MARK = "▪"
"""Before a given cube's name, in the same contrasting text color."""
HELD_MARK = "▸"


class TrayCell(Static):
    """One position in the tray, painted in the color of the cube on it."""

    class Clicked(Message):
        def __init__(self, cell: Cell) -> None:
            super().__init__()
            self.cell = cell

    def __init__(self, cell: Cell) -> None:
        super().__init__(id=f"cell-{cell.row}-{cell.col}", markup=False)
        self.cell = cell
        self.text = ""

    def show(
        self, color: Color | None, *, given: bool, cursor: bool, held: bool, hinted: bool = False
    ) -> None:
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
        self.update(self.text)

    def on_click(self) -> None:
        self.post_message(self.Clicked(self.cell))


class PaletteChip(Static):
    """A cube waiting in the palette strip."""

    class Clicked(Message):
        def __init__(self, color: Color) -> None:
            super().__init__()
            self.color = color

    def __init__(self, color: Color) -> None:
        super().__init__(id=f"chip-{color.id}", markup=False)
        self.color = color
        self.styles.background = color.hex
        self.styles.color = text_color(color.hex)
        self.set_class(is_dark(color.hex), "dark")

    def show(self, slot: int | None, *, held: bool, hinted: bool = False) -> None:
        """`slot` is the chip's number key, or None when the cube is on the tray."""
        self.display = slot is not None
        self.set_class(held, "held")
        self.set_class(hinted, "hinted")
        key = "" if slot is None or slot > 10 else f"{slot % 10} "
        pointer = f"{HELD_MARK} " if held else ""
        self.update(f"{pointer}{key}{self.color.name}")

    def on_click(self) -> None:
        self.post_message(self.Clicked(self.color))
