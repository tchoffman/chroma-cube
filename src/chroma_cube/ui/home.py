"""The home screen (classic cards, infinite or daily) and the difficulty and board picker."""

from __future__ import annotations

from typing import ClassVar

from textual import events, on
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical
from textual.content import Content
from textual.geometry import Size
from textual.screen import Screen
from textual.widget import Widget
from textual.widgets import Footer, Label, OptionList
from textual.widgets.option_list import Option

from chroma_cube.generator import DIFFICULTIES, LAYOUTS
from chroma_cube.ui.infinite import RNG, play_generated
from chroma_cube.ui.screens import (
    CUBE_COLORS,
    TIER_WIDTH,
    CardListScreen,
    cube,
    game,
    tier_badge,
)
from chroma_cube.ui.seeds import DAILY_DIFFICULTY, GameSpec, random_seed

TAGLINE = "Twelve cubes, one tray, and every clue must hold."
SHORT_BELOW = 20
"""Terminals shorter than this leave out the tagline."""


class Wordmark(Widget):
    """ "CHROMA CUBE" spelled on a row of colored cubes, as big as the width allows.

    Cubes are five columns by three rows (about square on a terminal) where they fit,
    else three columns by one row, else one letter each.
    """

    COLORS = CUBE_COLORS
    WORDS = ("CHROMA", "CUBE")
    _SIZES = ((5, 3, 1, 3), (3, 1, 1, 3), (1, 1, 0, 1))
    """Cube width, cube height, the gap between cubes and the gap between the words."""

    def _cubes_for(self, width: int) -> tuple[int, int, int, int]:
        letters = sum(len(word) for word in self.WORDS)
        for size in self._SIZES:
            cube_width, _, gap, word_gap = size
            needed = letters * cube_width + (letters - len(self.WORDS)) * gap + word_gap
            if needed <= width:
                return size
        return self._SIZES[-1]

    def get_content_height(self, container: Size, viewport: Size, width: int) -> int:
        return self._cubes_for(width)[1]

    def render(self) -> Content:
        cube_width, height, gap, word_gap = self._cubes_for(self.size.width)
        colors = iter(self.COLORS)
        lines: list[list[Content]] = [[] for _ in range(height)]
        for number, word in enumerate(self.WORDS):
            if number:
                for line in lines:
                    line.append(Content(" " * word_gap))
            for position, letter in enumerate(word):
                color = next(colors)
                for row, line in enumerate(lines):
                    if position:
                        line.append(Content(" " * gap))
                    face = letter if row == height // 2 else " "
                    line.append(cube(face.center(cube_width), color))
        return Content("\n").join(Content("").join(line) for line in lines)


def _mode(name: str, description: str) -> Content:
    return Content.assemble((name, "bold"), "\n", (description, "dim"))


class HomeScreen(Screen[None]):
    """Where the app starts: the classic cards, an infinite puzzle or today's puzzle."""

    DEFAULT_CLASSES: ClassVar[str] = "shell"

    def compose(self) -> ComposeResult:
        cards = len(game(self).puzzles)
        with Vertical(id="home"):
            yield Wordmark()
            yield Label(TAGLINE, id="tagline")
            modes = OptionList(
                Option(
                    _mode(
                        "Classic cards", f"the {cards} hand-made card{'' if cards == 1 else 's'}"
                    ),
                    id="classic",
                ),
                Option(
                    _mode("Infinite", "a fresh puzzle at the difficulty you pick"), id="infinite"
                ),
                Option(
                    _mode("Daily", f"today's {DAILY_DIFFICULTY} puzzle, the same for everyone"),
                    id="daily",
                ),
                id="modes",
            )
            modes.border_title = "Play"
            yield modes
        yield Footer()

    def on_resize(self, event: events.Resize) -> None:
        """Short terminals drop the tagline, so the modes stay on screen."""
        self.set_class(event.size.height < SHORT_BELOW, "-short")

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

    DEFAULT_CLASSES: ClassVar[str] = "shell"
    BINDINGS: ClassVar[list[BindingType]] = [Binding("escape", "app.pop_screen", "Back")]

    def compose(self) -> ComposeResult:
        yield Label("Infinite", id="list-title")
        yield Label(
            "Enter on a difficulty starts a fresh puzzle on the marked board.",
            id="infinite-help",
        )
        with Horizontal(id="pickers"):
            difficulties = OptionList(
                *(
                    Option(tier_badge(difficulty, TIER_WIDTH), id=difficulty)
                    for difficulty in DIFFICULTIES
                ),
                id="difficulties",
            )
            difficulties.border_title = "Difficulty"
            yield difficulties
            boards = OptionList(
                *(Option(self._prompt(i), id=lay.key) for i, lay in enumerate(LAYOUTS)),
                id="boards",
            )
            boards.border_title = "Board"
            boards.border_subtitle = "Tab to change"
            yield boards
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
