"""The clue card: a bordered panel with the card's name, its numbered clues and its note."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.content import Content
from textual.css.styles import RulesMap
from textual.strip import Strip
from textual.style import Style
from textual.visual import RenderOptions, Visual
from textual.widgets import Static

from chroma_cube.core import Puzzle, Truth
from chroma_cube.ui.swatch import STATUS_MARKERS

MARK_STYLES = {Truth.UNKNOWN: "", Truth.SATISFIED: "bold $success", Truth.VIOLATED: "bold $error"}
"""The marker keeps its state's color even when the clue text is dimmed."""


class HangingIndent(Visual):
    """A gutter, then text that wraps under itself rather than under the gutter."""

    def __init__(self, gutter: Content, body: Content) -> None:
        self.gutter = gutter
        self.body = body

    def lines(self, width: int) -> list[Content]:
        indent = self.gutter.cell_length
        wrapped = self.body.wrap(max(1, width - indent)) or [Content("")]
        blank = Content(" " * indent)
        return [(self.gutter if index == 0 else blank) + line for index, line in enumerate(wrapped)]

    def render_strips(
        self, width: int, height: int | None, style: Style, options: RenderOptions
    ) -> list[Strip]:
        return Content("\n").join(self.lines(width)).render_strips(width, height, style, options)

    def get_optimal_width(self, rules: RulesMap, container_width: int) -> int:
        return self.gutter.cell_length + self.body.cell_length

    def get_height(self, rules: RulesMap, width: int) -> int:
        return len(self.lines(width))


class ClueRow(Static):
    """One numbered clue, with a marker in the gutter saying whether it holds yet."""

    def __init__(self, number: int, sentence: str) -> None:
        super().__init__(classes="clue")
        self.number = number
        self.sentence = sentence
        self.truth = Truth.UNKNOWN
        self.text = ""
        self.show(Truth.UNKNOWN)

    def show(self, truth: Truth, *, hinted: bool = False) -> None:
        self.truth = truth
        mark = STATUS_MARKERS[truth]
        number = f" {self.number:>2}  "
        self.text = f"{mark}{number}{self.sentence}"
        for value in Truth:
            self.set_class(value is truth, value.value)
        self.set_class(hinted, "hinted")
        gutter = Content.assemble((mark, MARK_STYLES[truth]), (number, "$text-muted"))
        self.update(HangingIndent(gutter, Content(self.sentence)))


class ClueCard(Vertical):
    """The clues on a card: its name in the top edge, its tier and a clue count in the bottom.

    The clues and the note scroll inside; while some clues are out of sight the bottom edge
    says which are showing ("Clues 1–3 of 13"), and while the note is, "note ↓".
    """

    def __init__(self, heading: str, puzzle: Puzzle) -> None:
        super().__init__(id="card")
        self.border_title = heading
        self.tier = puzzle.difficulty.capitalize()
        self.sentences = puzzle.rendered_clues()
        self.note = puzzle.notes

    def compose(self) -> ComposeResult:
        clues = VerticalScroll(id="clues")
        clues.can_focus = False
        with clues:
            for number, sentence in enumerate(self.sentences, start=1):
                yield ClueRow(number, sentence)
            if self.note:
                yield Static(self.note, id="card-note", markup=False)

    def on_mount(self) -> None:
        self.watch(self.query_one("#clues"), "scroll_y", self.count_clues, init=False)
        self.call_after_refresh(self.count_clues)

    def on_resize(self) -> None:
        self.call_after_refresh(self.count_clues)

    def count_clues(self) -> None:
        clues = self.query_one("#clues", VerticalScroll)
        rows = list(self.query(ClueRow))
        top = clues.scroll_y
        bottom = top + clues.scrollable_content_region.height
        shown = [
            row.number
            for row in rows
            if row.virtual_region.y >= top and row.virtual_region.y < bottom
        ]
        total = len(rows)
        parts = [self.tier]
        if shown and len(shown) < total:
            parts.append(f"Clues {shown[0]}–{shown[-1]} of {total}")
        else:
            parts.append(f"{total} clue{'' if total == 1 else 's'}")
        notes = self.query("#card-note")
        if notes and notes.first().virtual_region.bottom > bottom:
            parts.append("note ↓")
        self.border_subtitle = " · ".join(part for part in parts if part)
