"""Generated puzzles: the "Generating…" notice, the play screen, the seed box and the win."""

from __future__ import annotations

import random
from collections.abc import Callable
from typing import TYPE_CHECKING, ClassVar

from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label

from chroma_cube.core import Placement, Puzzle
from chroma_cube.generator import Difficulty
from chroma_cube.ui.screens import PlayScreen, WinScreen, _hint_count
from chroma_cube.ui.seeds import GameSpec, parse_seed

if TYPE_CHECKING:
    from chroma_cube.ui.app import ChromaCubeApp

Generate = Callable[[int, Difficulty], Puzzle]
"""Makes the puzzle for a seed and a difficulty; the same arguments give the same puzzle."""

RNG = random.Random()
"""Where fresh seeds come from."""

_MODAL_CSS = """
    align: center middle;

    #modal {
        width: 50;
        max-width: 100%;
        height: auto;
        padding: 1 2;
        border: thick $accent;
        background: $surface;
    }

    #seed-error {
        color: $error;
    }
"""


def play_generated(app: ChromaCubeApp, spec: GameSpec, *, replace: bool = False) -> None:
    """Generate `spec`'s puzzle off the UI thread, then play it.

    With `replace`, the new puzzle takes the place of the current play screen.
    """

    def ready(puzzle: Puzzle | None) -> None:
        if puzzle is None:
            return
        saved = app.progress.saved_board(puzzle)
        hints = 0 if saved is None else app.progress.saved_hints(puzzle.id)
        screen = GeneratedPlayScreen(spec, puzzle, saved, hints)
        if replace:
            app.switch_screen(screen)
        else:
            app.push_screen(screen)

    app.push_screen(GeneratingScreen(spec, app.generate), ready)


class GeneratingScreen(ModalScreen[Puzzle | None]):
    """Shown while the generator runs in a worker thread; dismisses with the puzzle."""

    DEFAULT_CSS = f"GeneratingScreen {{ {_MODAL_CSS} }}"
    BINDINGS: ClassVar[list[BindingType]] = [Binding("escape", "cancel", "Cancel")]

    def __init__(self, spec: GameSpec, generate: Generate) -> None:
        super().__init__()
        self.spec = spec
        self.generate = generate
        self.cancelled = False

    def compose(self) -> ComposeResult:
        with Vertical(id="modal"):
            yield Label(f"Generating {self.spec.title}…")

    def on_mount(self) -> None:
        self.run_generator()

    @work(thread=True, exit_on_error=False)
    def run_generator(self) -> None:
        spec = self.spec
        try:
            puzzle = self.generate(spec.seed, spec.difficulty)
        except (RuntimeError, ValueError) as error:
            self.app.call_from_thread(self.failed, error)
            return
        self.app.call_from_thread(self.finish, puzzle)

    def finish(self, puzzle: Puzzle) -> None:
        if not self.cancelled:
            self.dismiss(puzzle)

    def failed(self, error: Exception) -> None:
        if not self.cancelled:
            self.app.notify(f"Could not generate that puzzle: {error}", severity="error")
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.cancelled = True
        self.dismiss(None)


class GeneratedPlayScreen(PlayScreen):
    """A generated puzzle; infinite play adds a new puzzle (n) and replay by seed (s)."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("n", "another", "New", priority=True),
        Binding("s", "enter_seed", "Seed", priority=True),
    ]

    def __init__(
        self, spec: GameSpec, puzzle: Puzzle, placement: Placement | None = None, hints: int = 0
    ) -> None:
        super().__init__(0, puzzle, placement, hints)
        self.spec = spec

    def heading(self) -> str:
        return self.spec.title

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        if action in ("another", "enter_seed"):
            return not self.spec.is_daily
        return super().check_action(action, parameters)

    def action_another(self) -> None:
        play_generated(self._game, self.spec.another(RNG), replace=True)

    def action_enter_seed(self) -> None:
        def chosen(seed: int | None) -> None:
            if seed is not None:
                play_generated(self._game, self.spec.with_seed(seed), replace=True)

        self.app.push_screen(SeedScreen(self.spec.difficulty), chosen)

    def _save_board(self) -> None:
        state = self.state
        self._game.progress.save_board(state.puzzle, state.placement, state.hints_used)

    def won(self) -> None:
        state = self.state
        progress = self._game.progress
        progress.record_solve(state.puzzle.id, hints=state.hints_used)
        progress.clear_board(state.puzzle.id)

        def chosen(choice: str | None) -> None:
            if choice == "next":
                play_generated(self._game, self.spec.another(RNG), replace=True)
            else:
                self.app.pop_screen()

        offer_another = not self.spec.is_daily
        win = GeneratedWinScreen(self.spec.title, offer_another, state.hints_used)
        self.app.push_screen(win, chosen)


class SeedScreen(ModalScreen[int | None]):
    """A box to type a seed into; dismisses with the seed, or None on Escape."""

    DEFAULT_CSS = f"SeedScreen {{ {_MODAL_CSS} }}"
    BINDINGS: ClassVar[list[BindingType]] = [Binding("escape", "dismiss", "Cancel")]

    def __init__(self, difficulty: Difficulty) -> None:
        super().__init__()
        self.difficulty = difficulty

    def compose(self) -> ComposeResult:
        with Vertical(id="modal"):
            yield Label(f"Replay a {self.difficulty} puzzle by its seed")
            yield Input(placeholder="e.g. 48213", id="seed")
            yield Label("", id="seed-error")

    @on(Input.Submitted)
    def submit(self, event: Input.Submitted) -> None:
        try:
            seed = parse_seed(event.value)
        except ValueError as error:
            self.query_one("#seed-error", Label).update(str(error))
            return
        self.dismiss(seed)


class GeneratedWinScreen(WinScreen):
    """The win dialog for a generated puzzle: "Another" (infinite only) and "Back"."""

    def compose(self) -> ComposeResult:
        with Vertical(id="win"):
            yield Label(f"Solved! {self.card_title}", id="win-title")
            yield Label("Every cube is placed and every clue holds.")
            yield Label(_hint_count(self.hints), id="win-hints")
            with Horizontal(id="win-buttons"):
                if self.has_next:
                    yield Button("Another", id="next", variant="success")
                yield Button("Back", id="back")
