"""Turn clues into English sentences, using the templates in the clue registries."""

from __future__ import annotations

from chroma_cube.core.board import CLASSIC_BOARD, Board
from chroma_cube.core.clues import (
    BOARD_RULE_KINDS,
    PROPERTY_KINDS,
    RELATION_KINDS,
    And,
    AtLeast,
    BoardRule,
    Clue,
    ColorRef,
    Exactly,
    Not,
    Or,
    Property,
    Relation,
)
from chroma_cube.core.colors import Palette

_ORDINALS = ("first", "second", "third", "fourth", "fifth", "sixth")
_NUMBERS = ("zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten")
_OPENERS = ("It's ", "Either ", "Exactly ", "At least ", "Every ")


def render(clue: Clue, palette: Palette, board: Board = CLASSIC_BOARD) -> str:
    """The clue as one English sentence, without a final full stop.

    The board is only needed to name rows ("top", "middle", "bottom").
    """
    return _Renderer(palette, board).sentence(clue)


class _Renderer:
    def __init__(self, palette: Palette, board: Board) -> None:
        self.palette = palette
        self.board = board

    def sentence(self, clue: Clue) -> str:
        match clue:
            case Relation(kind=kind, colors=refs):
                return RELATION_KINDS[kind].text.format(*self.names(refs))
            case Property():
                return self.prop(clue, negated=False)
            case BoardRule(kind=kind):
                return BOARD_RULE_KINDS[kind].text
            case Not(clue=Relation(kind=kind, colors=refs)):
                return RELATION_KINDS[kind].negated.format(*self.names(refs))
            case Not(clue=Property() as inner):
                return self.prop(inner, negated=True)
            case Not(clue=inner):
                return "It's not true that " + _lower_opener(self.sentence(inner))
            case And(clues=clues):
                return self.merged(clues) or _join(self.parts(clues), " and ")
            case Or(clues=(only,)):
                return self.sentence(only)
            case Or(clues=clues):
                return "Either " + _join(self.parts(clues), " or ")
            case Exactly(n=n, clues=clues):
                return f"Exactly {_number(n)} of these {_are(n)} true: " + self.listing(clues)
            case AtLeast(n=n, clues=clues):
                return f"At least {_number(n)} of these {_are(n)} true: " + self.listing(clues)
        raise TypeError(f"not a clue: {clue!r}")

    def name(self, color_ref: ColorRef) -> str:
        if color_ref.by_initial:
            return color_ref.key
        return self.palette.by_id(color_ref.key).name

    def names(self, refs: tuple[ColorRef, ...]) -> list[str]:
        return [self.name(color_ref) for color_ref in refs]

    def prop(self, clue: Property, *, negated: bool) -> str:
        kind = PROPERTY_KINDS[clue.kind]
        template = kind.negated if negated else kind.text
        line = ""
        if kind.index == "row" and clue.index is not None:
            line = f"the {self.row_name(clue.index)} row"
        elif kind.index == "column" and clue.index is not None:
            line = f"the {_ordinal(clue.index)} column"
        return template.format(self.name(clue.color), line=line)

    def row_name(self, index: int) -> str:
        if index == 0:
            return "top"
        if index == self.board.rows - 1:
            return "bottom"
        if self.board.rows == 3 and index == 1:
            return "middle"
        return _ordinal(index)

    def parts(self, clues: tuple[Clue, ...]) -> list[str]:
        """Sub-clue sentences for a list, bracketing the ones that are themselves compound."""
        parts = []
        for sub in clues:
            text = _lower_opener(self.sentence(sub))
            parts.append(f"({text})" if _is_compound(sub) else text)
        return parts

    def listing(self, clues: tuple[Clue, ...]) -> str:
        return "; ".join(self.parts(clues))

    def merged(self, clues: tuple[Clue, ...]) -> str | None:
        """Merge relations of one kind from one color: "Black knows White, Teal and Mint".

        Not for an initial: each part picks its own B color, so "B knows W and T" would
        claim that one B knows both.
        """
        if len(clues) < 2 or not all(isinstance(sub, Relation) for sub in clues):
            return None
        relations = [sub for sub in clues if isinstance(sub, Relation)]
        first = relations[0]
        template = RELATION_KINDS[first.kind].text
        if (
            len(first.colors) != 2
            or first.colors[0].by_initial
            or not template.endswith("{1}")
            or any(r.kind != first.kind or r.colors[0] != first.colors[0] for r in relations)
        ):
            return None
        others = _join([self.name(r.colors[1]) for r in relations], " and ")
        return template.format(self.name(first.colors[0]), others)


def _is_compound(clue: Clue) -> bool:
    if isinstance(clue, Not):
        return not isinstance(clue.clue, Relation | Property)
    return isinstance(clue, And | Or | Exactly | AtLeast)


def _join(parts: list[str], last: str) -> str:
    if len(parts) == 1:
        return parts[0]
    return ", ".join(parts[:-1]) + last + parts[-1]


def _lower_opener(text: str) -> str:
    """Lowercase a fixed opening phrase so the sentence can sit inside another."""
    if text.startswith(_OPENERS):
        return text[0].lower() + text[1:]
    return text


def _ordinal(index: int) -> str:
    if index < len(_ORDINALS):
        return _ORDINALS[index]
    number = index + 1
    suffix = {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")
    if 10 <= number % 100 <= 20:
        suffix = "th"
    return f"{number}{suffix}"


def _number(n: int) -> str:
    return _NUMBERS[n] if n < len(_NUMBERS) else str(n)


def _are(n: int) -> str:
    return "is" if n == 1 else "are"
