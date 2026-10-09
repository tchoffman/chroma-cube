"""The Textual application."""

from __future__ import annotations

from collections.abc import Sequence
from typing import ClassVar

from textual.app import App
from textual.binding import Binding, BindingType

from chroma_cube.core import Puzzle
from chroma_cube.ui.screens import CardListScreen, PlayScreen, WinScreen


class ChromaCubeApp(App[None]):
    """Pick a card from the list, then play it."""

    TITLE = "Chroma Cube"
    CSS_PATH = "chroma_cube.tcss"
    ENABLE_COMMAND_PALETTE = False
    BINDINGS: ClassVar[list[BindingType]] = [Binding("q", "quit", "Quit", priority=True)]

    def __init__(self, puzzles: Sequence[Puzzle]) -> None:
        super().__init__()
        self.puzzles = tuple(puzzles)
        self.solved: set[str] = set()
        """Ids of the cards solved this session."""

    def on_mount(self) -> None:
        self.push_screen(CardListScreen())

    def open_card(self, index: int) -> None:
        self.push_screen(PlayScreen(index, self.puzzles[index]))

    def card_solved(self, index: int) -> None:
        """Tick the card and offer the next one."""
        self.solved.add(self.puzzles[index].id)
        has_next = index + 1 < len(self.puzzles)

        def chosen(choice: str | None) -> None:
            self.pop_screen()
            if choice == "next" and has_next:
                self.open_card(index + 1)

        self.push_screen(WinScreen(self.puzzles[index].title, has_next), chosen)
