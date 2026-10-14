"""The home screen (classic cards, infinite or daily) and the difficulty and board picker."""

from __future__ import annotations

from typing import ClassVar

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.screen import Screen
from textual.widgets import Footer, Label, OptionList
from textual.widgets.option_list import Option

from chroma_cube.generator import DIFFICULTIES, LAYOUTS
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
    """Pick how hard the infinite puzzles are, and the board they are played on.

    Choosing a difficulty starts a puzzle on the board marked with a dot. Tab moves to the
    board list; choosing a board there marks it and moves back to the difficulties.
    """

    BINDINGS: ClassVar[list[BindingType]] = [Binding("escape", "app.pop_screen", "Back")]

    def compose(self) -> ComposeResult:
        yield Label("Infinite: choose a difficulty", id="list-title")
        yield OptionList(
            *(Option(difficulty.capitalize(), id=difficulty) for difficulty in DIFFICULTIES),
            id="difficulties",
        )
        yield Label("Board (Tab to change)", classes="list-heading")
        yield OptionList(
            *(Option(self._prompt(i), id=lay.key) for i, lay in enumerate(LAYOUTS)), id="boards"
        )
        yield Footer()

    def _prompt(self, index: int) -> str:
        chosen = LAYOUTS[index].key == game(self).layout
        return f"{'●' if chosen else ' '} {LAYOUTS[index].label}"

    def on_mount(self) -> None:
        keys = [lay.key for lay in LAYOUTS]
        self.query_one("#boards", OptionList).highlighted = keys.index(game(self).layout)

    def on_screen_resume(self) -> None:
        self.query_one("#difficulties", OptionList).focus()

    @on(OptionList.OptionSelected, "#boards")
    def choose_board(self, event: OptionList.OptionSelected) -> None:
        event.stop()
        game(self).layout = LAYOUTS[event.option_index].key
        boards = self.query_one("#boards", OptionList)
        for index in range(len(LAYOUTS)):
            boards.replace_option_prompt_at_index(index, self._prompt(index))
        self.query_one("#difficulties", OptionList).focus()

    @on(OptionList.OptionSelected, "#difficulties")
    def choose(self, event: OptionList.OptionSelected) -> None:
        difficulty = DIFFICULTIES[event.option_index]
        app = game(self)
        play_generated(app, GameSpec.infinite(difficulty, random_seed(RNG), app.layout))
