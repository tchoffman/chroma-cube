"""The card list, the play screen and the win dialog."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from textual import events, on
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Grid, Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, Footer, Label, OptionList, Static
from textual.widgets.option_list import Option

from chroma_cube.core import Puzzle
from chroma_cube.ui.play import PlayState
from chroma_cube.ui.widgets import ClueRow, PaletteChip, TrayCell

if TYPE_CHECKING:
    from chroma_cube.ui.app import ChromaCubeApp

CELL_MIN_HEIGHT = 3
"""A border and one line for the name."""
CELL_MAX_HEIGHT = 5

HINT = "Type a color's first letter or its number to take it, then Enter on a cell."


class CardListScreen(Screen[None]):
    """Every card, with a tick on the ones solved this session."""

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
        tick = "✓" if puzzle.id in self._game.solved else " "
        return f"{index + 1:>2}  {tick}  {puzzle.title}"

    @property
    def _game(self) -> ChromaCubeApp:
        from chroma_cube.ui.app import ChromaCubeApp

        app = self.app
        assert isinstance(app, ChromaCubeApp)
        return app

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
        Binding("escape", "back", "Back"),
        Binding("pageup", "scroll_clues(-1)", "Clues", show=False),
        Binding("pagedown", "scroll_clues(1)", "Clues", key_display="PgDn"),
    ]
    HORIZONTAL_BREAKPOINTS = [
        (0, "-narrow"),
        (70, "-wide"),
    ]
    """Below 70 columns the clues go under the tray instead of beside it."""

    def __init__(self, index: int, puzzle: Puzzle) -> None:
        super().__init__()
        self.index = index
        self.state = PlayState(puzzle)

    def compose(self) -> ComposeResult:
        puzzle = self.state.puzzle
        board = puzzle.board
        yield Label(f"Card {self.index + 1}: {puzzle.title}", id="card-title")
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
            clues = VerticalScroll(id="clues")
            clues.can_focus = False
            with clues:
                yield Label("Clues", classes="heading")
                yield from (ClueRow(sentence) for sentence in puzzle.rendered_clues())
        yield Static(HINT, id="message", markup=False)
        yield Footer()

    def on_mount(self) -> None:
        self.refresh_view()

    # ------------------------------------------------------------------ drawing

    def refresh_view(self, message: str | None = None) -> None:
        state = self.state
        for widget in self.query(TrayCell):
            color = state.placement.color_at(widget.cell)
            widget.show(
                color,
                given=color is not None and state.is_given(color),
                cursor=widget.cell == state.cursor,
                held=color is not None and color == state.held,
            )
        slots = {color: slot for slot, color in enumerate(state.palette_cubes(), start=1)}
        for chip in self.query(PaletteChip):
            chip.show(slots.get(chip.color), held=chip.color == state.held)
        for row, truth in zip(self.query(ClueRow), state.statuses(), strict=True):
            row.show(truth)
        if message is not None:
            self.query_one("#message", Static).update(message)

    def _after_change(self, message: str) -> None:
        self.refresh_view(message)
        if self.state.solved:
            self._game.card_solved(self.index)

    @property
    def _game(self) -> ChromaCubeApp:
        from chroma_cube.ui.app import ChromaCubeApp

        app = self.app
        assert isinstance(app, ChromaCubeApp)
        return app

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

    def __init__(self, title: str, has_next: bool) -> None:
        super().__init__()
        self.card_title = title
        self.has_next = has_next

    def compose(self) -> ComposeResult:
        with Vertical(id="win"):
            yield Label(f"Solved! {self.card_title}", id="win-title")
            yield Label("Every cube is placed and every clue holds.")
            with Horizontal(id="win-buttons"):
                yield Button("Next card", id="next", variant="success", disabled=not self.has_next)
                yield Button("Back to list", id="back")

    def on_mount(self) -> None:
        self.query_one("#next" if self.has_next else "#back", Button).focus()

    @on(Button.Pressed)
    def choose(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id)
