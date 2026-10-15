"""The card list, the play screen and the win dialog."""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any, ClassVar

from textual import events, on
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Grid, Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, Footer, Label, OptionList, Static
from textual.widgets.option_list import Option

from chroma_cube.core import Placement, Puzzle
from chroma_cube.ui.card import ClueCard, ClueRow
from chroma_cube.ui.play import PlayState
from chroma_cube.ui.widgets import PaletteChip, TrayCell

if TYPE_CHECKING:
    from chroma_cube.ui.app import ChromaCubeApp

CELL_MIN_HEIGHT = 3
"""A border and one line for the name."""
CELL_MAX_HEIGHT = 5
WIDE_FROM = 70
"""The narrowest terminal that puts the clues beside the tray, whatever the board."""
CLUES_MIN_WIDTH = 24
"""Columns the clue list needs beside the tray."""
_CELL_EXTRA = 4
"""A tray cell's two border columns and the two of a given or held mark."""


def tray_width(puzzle: Puzzle) -> int:
    """Columns the tray needs for every color name in full, with a mark, plus its padding."""
    longest = max(len(color.name) for color in puzzle.palette)
    return puzzle.board.cols * (longest + _CELL_EXTRA) + 2


def game(screen: Screen[Any]) -> ChromaCubeApp:
    """The running app, typed as ours."""
    from chroma_cube.ui.app import ChromaCubeApp

    app = screen.app
    assert isinstance(app, ChromaCubeApp)
    return app


HINT = "Type a color's first letter or its number to take it, then Enter on a cell."


class CardListScreen(Screen[None]):
    """Every card, with a tick on the ones ever solved."""

    def compose(self) -> ComposeResult:
        yield Label("Chroma Cube: choose a card", id="list-title")
        yield OptionList(*self._options(), id="cards")
        yield Footer()

    def _options(self) -> list[Option]:
        app = self._game
        return [
            Option(self._prompt(index, puzzle), id=str(index))
            for index, puzzle in enumerate(app.puzzles)
        ]

    def _prompt(self, index: int, puzzle: Puzzle) -> str:
        tick = "✓" if self._game.is_solved(puzzle) else " "
        return f"{index + 1:>2}  {tick}  {puzzle.title}"

    @property
    def _game(self) -> ChromaCubeApp:
        return game(self)

    def on_screen_resume(self) -> None:
        cards = self.query_one(OptionList)
        for index, puzzle in enumerate(self._game.puzzles):
            cards.replace_option_prompt_at_index(index, self._prompt(index, puzzle))
        cards.focus()

    @on(OptionList.OptionSelected)
    def open_card(self, event: OptionList.OptionSelected) -> None:
        self._game.open_card(event.option_index)


class PlayScreen(Screen[None]):
    """One card: the tray, the palette strip, the clues and a status line."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("up", "cursor(-1, 0)", "Move", show=False, priority=True),
        Binding("down", "cursor(1, 0)", "Move", show=False, priority=True),
        Binding("left", "cursor(0, -1)", "Move", show=False, priority=True),
        Binding("right", "cursor(0, 1)", "Move", show=False, priority=True),
        Binding("enter,space", "activate", "Place", key_display="⏎"),
        Binding("x,backspace,delete", "return_cube", "Return", priority=True),
        Binding("r", "reset", "Reset", priority=True),
        Binding("h", "hint", "Hint", priority=True),
        Binding("escape", "back", "Back"),
        Binding("pageup", "scroll_clues(-1)", "Clues", show=False),
        Binding("pagedown", "scroll_clues(1)", "Clues", key_display="PgDn"),
    ]

    def __init__(
        self, index: int, puzzle: Puzzle, placement: Placement | None = None, hints: int = 0
    ) -> None:
        super().__init__()
        self.index = index
        self.state = PlayState(puzzle, placement, hints)
        self.tray_width = tray_width(puzzle)
        """Columns the tray needs to show every name in full, marks included."""
        self.wide_from = max(WIDE_FROM, self.tray_width + CLUES_MIN_WIDTH)
        """From this terminal width the clues sit beside the tray, below it under the tray."""

    def compose(self) -> ComposeResult:
        puzzle = self.state.puzzle
        board = puzzle.board
        with Horizontal(id="play"):
            with Vertical(id="left"):
                tray = Grid(*(TrayCell(cell) for cell in board), id="tray")
                tray.styles.grid_size_columns = board.cols
                tray.styles.grid_size_rows = board.rows
                tray.styles.min_height = board.rows * CELL_MIN_HEIGHT
                tray.styles.max_height = board.rows * CELL_MAX_HEIGHT
                yield tray
                yield Label("Palette", classes="heading")
                palette = Grid(*(PaletteChip(color) for color in puzzle.palette), id="palette")
                palette.styles.grid_size_columns = board.cols
                yield palette
            yield ClueCard(self.heading(), puzzle)
        yield Static(HINT, id="message", markup=False)
        yield Footer()

    def heading(self) -> str:
        """The name in the top edge of the clue card."""
        return f"Card {self.index + 1} · {self.state.puzzle.title}"

    def on_mount(self) -> None:
        self._fit(self.app.size.width)
        self.refresh_view()

    def on_resize(self, event: events.Resize) -> None:
        self._fit(event.size.width)

    def _fit(self, width: int) -> None:
        """Clues beside the tray when both fit, else under it (the -narrow layout)."""
        narrow = width < self.wide_from
        self.set_class(narrow, "-narrow")
        self.set_class(not narrow, "-wide")
        self.query_one("#left").styles.min_width = None if narrow else self.tray_width

    # ------------------------------------------------------------------ drawing

    def refresh_view(self, message: str | None = None) -> None:
        state = self.state
        hint = state.hint
        for widget in self.query(TrayCell):
            color = state.placement.color_at(widget.cell)
            widget.show(
                color,
                given=color is not None and state.is_given(color),
                cursor=widget.cell == state.cursor,
                held=color is not None and color == state.held,
                hinted=hint is not None and widget.cell == hint.cell,
            )
        slots = {color: slot for slot, color in enumerate(state.palette_cubes(), start=1)}
        for chip in self.query(PaletteChip):
            chip.show(
                slots.get(chip.color),
                held=chip.color == state.held,
                hinted=hint is not None and chip.color == hint.color,
            )
        hinted_clues = set(hint.clues) if hint is not None else set()
        rows = zip(self.query(ClueRow), state.statuses(), strict=True)
        for index, (row, truth) in enumerate(rows):
            row.show(truth, hinted=index in hinted_clues)
        if message is not None:
            self.query_one("#message", Static).update(message)

    def _after_change(self, message: str) -> None:
        self.refresh_view(message)
        if self.state.solved:
            self.won()
        else:
            self._save_board()

    def won(self) -> None:
        self._game.card_solved(self.index, self.state.hints_used)

    def _save_board(self) -> None:
        self._game.board_changed(self.index, self.state.placement, self.state.hints_used)

    @property
    def _game(self) -> ChromaCubeApp:
        return game(self)

    # ------------------------------------------------------------------ input

    def action_cursor(self, drow: int, dcol: int) -> None:
        self.state.move_cursor(drow, dcol)
        self.refresh_view()

    def action_activate(self) -> None:
        self._after_change(self.state.activate(self.state.cursor))

    def action_scroll_clues(self, pages: int) -> None:
        clues = self.query_one("#clues", VerticalScroll)
        if pages > 0:
            clues.scroll_page_down()
        else:
            clues.scroll_page_up()

    def action_return_cube(self) -> None:
        returned = self.state.return_held()
        self._after_change("Back in the palette." if returned else "Nothing to return there.")

    def action_hint(self) -> None:
        self.refresh_view(self.state.take_hint())
        self._save_board()

    def action_reset(self) -> None:
        self.state.reset()
        self._after_change("Card reset.")

    def action_back(self) -> None:
        if self.state.held is not None:
            self.state.held = None
            self.refresh_view("Let go.")
        else:
            self.app.pop_screen()

    def on_key(self, event: events.Key) -> None:
        character = event.character
        if character is None or len(character) != 1:
            return
        if character.isdigit():
            color = self.state.select_slot(int(character) or 10)
        elif character.isalpha():
            color = self.state.select_initial(character)
        else:
            return
        event.stop()
        self.refresh_view(
            f"Holding {color.name}. Enter or click a cell to place it."
            if color is not None
            else f"No cube in the palette for {character!r}."
        )

    @on(TrayCell.Clicked)
    def cell_clicked(self, event: TrayCell.Clicked) -> None:
        self.state.cursor = event.cell
        self._after_change(self.state.activate(event.cell))

    @on(PaletteChip.Clicked)
    def chip_clicked(self, event: PaletteChip.Clicked) -> None:
        if self.state.held == event.color:
            self.state.held = None
            self.refresh_view("Let go.")
            return
        self.state.select(event.color)
        self.refresh_view(f"Holding {event.color.name}. Click a cell to place it.")


class WinScreen(ModalScreen[str]):
    """Shown when a card is solved; dismisses with "next" or "back"."""

    BINDINGS: ClassVar[list[BindingType]] = [Binding("escape", "dismiss('back')", "Back")]

    def __init__(self, title: str, has_next: bool, hints: int = 0) -> None:
        super().__init__()
        self.card_title = title
        self.has_next = has_next
        self.hints = hints

    def compose(self) -> ComposeResult:
        with Vertical(id="win"):
            yield Label(f"Solved! {self.card_title}", id="win-title")
            yield Label("Every cube is placed and every clue holds.")
            yield Label(_hint_count(self.hints), id="win-hints")
            with Horizontal(id="win-buttons"):
                yield from self.buttons()

    def buttons(self) -> Iterable[Button]:
        """The choices under the message; each button's id is what the dialog dismisses with."""
        yield Button("Next card", id="next", variant="success", disabled=not self.has_next)
        yield Button("Back to list", id="back")

    def on_mount(self) -> None:
        self.query_one("#next" if self.has_next else "#back", Button).focus()

    @on(Button.Pressed)
    def choose(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id)


def _hint_count(hints: int) -> str:
    if hints == 0:
        return "Solved without hints."
    return f"Solved with {hints} hint{'' if hints == 1 else 's'}."
