"""The home screen (classic cards, infinite or daily) and the difficulty picker."""

from __future__ import annotations

from typing import ClassVar

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.screen import Screen
from textual.widgets import Footer, Label, OptionList
from textual.widgets.option_list import Option

from chroma_cube.generator import DIFFICULTIES
from chroma_cube.ui.infinite import RNG, play_generated
from chroma_cube.ui.screens import CardListScreen, game
from chroma_cube.ui.seeds import DAILY_DIFFICULTY, GameSpec, random_seed


class HomeScreen(Screen[None]):
    """Where the app starts: the classic cards, an infinite puzzle or today's puzzle."""

    def compose(self) -> ComposeResult:
        cards = len(game(self).puzzles)
        yield Label("Chroma Cube", id="list-title")
        yield OptionList(
            Option(
                f"Classic cards    the {cards} hand-made card{'' if cards == 1 else 's'}",
                id="classic",
            ),
            Option("Infinite         a fresh puzzle at the difficulty you pick", id="infinite"),
            Option(
                f"Daily            today's {DAILY_DIFFICULTY} puzzle, the same for everyone",
                id="daily",
            ),
            id="modes",
        )
        yield Footer()

    def on_screen_resume(self) -> None:
        self.query_one(OptionList).focus()

    @on(OptionList.OptionSelected)
    def choose(self, event: OptionList.OptionSelected) -> None:
        app = game(self)
        match event.option.id:
            case "classic":
                app.push_screen(CardListScreen())
            case "infinite":
                app.push_screen(DifficultyScreen())
            case "daily":
                play_generated(app, GameSpec.daily(app.today()))


class DifficultyScreen(Screen[None]):
    """Pick how hard the infinite puzzles are."""

    BINDINGS: ClassVar[list[BindingType]] = [Binding("escape", "app.pop_screen", "Back")]

    def compose(self) -> ComposeResult:
        yield Label("Infinite: choose a difficulty", id="list-title")
        yield OptionList(
            *(Option(difficulty.capitalize(), id=difficulty) for difficulty in DIFFICULTIES),
            id="difficulties",
        )
        yield Footer()

    def on_screen_resume(self) -> None:
        self.query_one(OptionList).focus()

    @on(OptionList.OptionSelected)
    def choose(self, event: OptionList.OptionSelected) -> None:
        difficulty = DIFFICULTIES[event.option_index]
        play_generated(game(self), GameSpec.infinite(difficulty, random_seed(RNG)))
