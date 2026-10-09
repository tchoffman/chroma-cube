"""The Textual application."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import date
from typing import ClassVar

from textual.app import App
from textual.binding import Binding, BindingType

from chroma_cube.core import Placement, Puzzle
from chroma_cube.generator import generate as generate_puzzle
from chroma_cube.progress import Progress
from chroma_cube.ui.home import HomeScreen
from chroma_cube.ui.infinite import Generate
from chroma_cube.ui.screens import CardListScreen, PlayScreen, WinScreen


class ChromaCubeApp(App[None]):
    """Play the classic cards, generated puzzles or today's puzzle."""

    TITLE = "Chroma Cube"
    CSS_PATH = "chroma_cube.tcss"
    ENABLE_COMMAND_PALETTE = False
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("q", "quit", "Quit", priority=True),
        Binding("escape", "home", "Home"),
    ]

    def __init__(
        self,
        puzzles: Sequence[Puzzle],
        progress: Progress | None = None,
        *,
        generate: Generate = generate_puzzle,
        today: Callable[[], date] = date.today,
        start_on_cards: bool = False,
    ) -> None:
        super().__init__()
        self.puzzles = tuple(puzzles)
        self.progress = Progress() if progress is None else progress
        """Solved cards and the last board, saved in the per-user data directory."""
        self.generate = generate
        self.today = today
        """The player's local date, for the daily puzzle."""
        self.start_on_cards = start_on_cards

    def on_mount(self) -> None:
        self.push_screen(HomeScreen())
        if self.start_on_cards:
            self.push_screen(CardListScreen())

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        if action == "home":
            return isinstance(self.screen, CardListScreen)
        return True

    def action_home(self) -> None:
        """Escape on the card list goes back to the home screen."""
        self.pop_screen()

    def is_solved(self, puzzle: Puzzle) -> bool:
        return self.progress.is_solved(puzzle.id)

    def open_card(self, index: int) -> None:
        """Play a card, picking up where the player left it if its board was saved."""
        puzzle = self.puzzles[index]
        saved = self.progress.saved_board(puzzle)
        hints = 0 if saved is None else self.progress.saved_hints(puzzle.id)
        self.push_screen(PlayScreen(index, puzzle, saved, hints))

    def board_changed(self, index: int, placement: Placement, hints: int = 0) -> None:
        self.progress.save_board(self.puzzles[index], placement, hints)

    def card_solved(self, index: int, hints: int = 0) -> None:
        """Record the solve and its hints, forget its board, tick the card, offer the next."""
        puzzle_id = self.puzzles[index].id
        self.progress.record_solve(puzzle_id, hints=hints)
        self.progress.clear_board(puzzle_id)
        has_next = index + 1 < len(self.puzzles)

        def chosen(choice: str | None) -> None:
            self.pop_screen()
            if choice == "next" and has_next:
                self.open_card(index + 1)

        self.push_screen(WinScreen(self.puzzles[index].title, has_next, hints), chosen)
