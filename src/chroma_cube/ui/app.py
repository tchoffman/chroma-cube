"""The Textual application."""

from __future__ import annotations

from collections.abc import Sequence
from typing import ClassVar

from textual.app import App
from textual.binding import Binding, BindingType

from chroma_cube.core import Placement, Puzzle
from chroma_cube.progress import Progress
from chroma_cube.ui.screens import CardListScreen, PlayScreen, WinScreen


class ChromaCubeApp(App[None]):
    """Pick a card from the list, then play it."""

    TITLE = "Chroma Cube"
    CSS_PATH = "chroma_cube.tcss"
    ENABLE_COMMAND_PALETTE = False
    BINDINGS: ClassVar[list[BindingType]] = [Binding("q", "quit", "Quit", priority=True)]

    def __init__(self, puzzles: Sequence[Puzzle], progress: Progress | None = None) -> None:
        super().__init__()
        self.puzzles = tuple(puzzles)
        self.progress = Progress() if progress is None else progress
        """Solved cards and the last board, saved in the per-user data directory."""

    def on_mount(self) -> None:
        self.push_screen(CardListScreen())

    def is_solved(self, puzzle: Puzzle) -> bool:
        return self.progress.is_solved(puzzle.id)

    def open_card(self, index: int) -> None:
        """Play a card, picking up where the player left it if its board was saved."""
        puzzle = self.puzzles[index]
        self.push_screen(PlayScreen(index, puzzle, self.progress.saved_board(puzzle)))

    def board_changed(self, index: int, placement: Placement) -> None:
        self.progress.save_board(self.puzzles[index], placement)

    def card_solved(self, index: int) -> None:
        """Record the solve, forget its board, tick the card and offer the next one."""
        puzzle_id = self.puzzles[index].id
        self.progress.record_solve(puzzle_id)
        self.progress.clear_board(puzzle_id)
        has_next = index + 1 < len(self.puzzles)

        def chosen(choice: str | None) -> None:
            self.pop_screen()
            if choice == "next" and has_next:
                self.open_card(index + 1)

        self.push_screen(WinScreen(self.puzzles[index].title, has_next), chosen)
