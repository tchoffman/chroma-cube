"""Read English clue sentences back into clues.

The parser accepts every sentence `render` produces plus common ways of saying the same
thing ("is next to", "is not", an Oxford comma). It is a hand-written tokenizer and a
backtracking recursive-descent parser: each rule yields every way it can match, and the
first reading that uses the whole sentence wins. Leaf sentences come from the templates in
the clue registries, so a new relation or property kind is parsed without touching this
module.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass

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


class ClueParseError(ValueError):
    """A clue sentence that could not be read. `position` is a character offset into the text."""

    def __init__(self, message: str, position: int) -> None:
        super().__init__(f"{message} (at character {position})")
        self.message = message
        self.position = position


def parse_clue(text: str, palette: Palette, board: Board = CLASSIC_BOARD) -> Clue:
    """The clue a sentence states. Raises `ClueParseError` if it cannot be read.

    Color names match the palette case-insensitively; a lone capital letter is an initial.
    The board is needed to read row names ("the bottom row") and to check row and column
    numbers.
    """
    return _Parser(text, palette, board).parse()


def parse_clues(text: str, palette: Palette, board: Board = CLASSIC_BOARD) -> tuple[Clue, ...]:
    """One clue per line. Blank lines and leading numbering ("1.", "2)") are ignored.

    Error positions are offsets into the whole text.
    """
    found: list[Clue] = []
    offset = 0
    for line in text.splitlines(keepends=True):
        numbering = _NUMBERING.match(line)
        start = numbering.end() if numbering else 0
        body = line[start:].rstrip("\r\n")
        if body.strip():
            try:
                found.append(parse_clue(body, palette, board))
            except ClueParseError as error:
                raise ClueParseError(error.message, offset + start + error.position) from None
        offset += len(line)
    return tuple(found)


_NUMBERING = re.compile(r"\s*\d+[.)]\s+")

# --------------------------------------------------------------------------- tokens


@dataclass(frozen=True)
class _Token:
    text: str
    """As written."""
    word: str
    """Lowercased, with contractions split into their words."""
    start: int


_TOKEN = re.compile(r"[A-Za-z0-9]+(?:['’][A-Za-z]+)?|[,;:().]|\S")
_CONTRACTIONS = {
    "isn't": ("is", "not"),
    "aren't": ("are", "not"),
    "doesn't": ("does", "not"),
    "don't": ("do", "not"),
    "it's": ("it", "is"),
}


def _tokenize(text: str) -> list[_Token]:
    tokens: list[_Token] = []
    for match in _TOKEN.finditer(text):
        piece, start = match.group(), match.start()
        if not (piece[0].isalnum() or piece in ",;:()."):
            raise ClueParseError(f"unexpected character {piece!r}", start)
        word = piece.lower().replace("’", "'")
        for part in _CONTRACTIONS.get(word, (word,)):
            tokens.append(_Token(piece, part, start))
    return tokens


def _words(template: str) -> tuple[str, ...]:
    """A template's words as tokens, keeping `{0}`-style slots whole."""
    words: list[str] = []
    for piece in template.split():
        if piece.startswith("{"):
            words.append(piece)
        else:
            words.extend(token.word for token in _tokenize(piece))
    return tuple(words)


# --------------------------------------------------------------------------- templates

_EXTRA_RELATION_TEXT: dict[str, list[tuple[str, str]]] = {
    "same_row": [("{0} is in the same row as {1}", "{0} isn't in the same row as {1}")],
    "same_column": [("{0} is in the same column as {1}", "{0} isn't in the same column as {1}")],
    "next_to": [
        ("{0} is next to {1}", "{0} isn't next to {1}"),
        ("{0} is beside {1}", "{0} isn't beside {1}"),
        ("{0} sits beside {1}", "{0} doesn't sit beside {1}"),
    ],
    "left_of": [("{0} is to the left of {1}", "{0} isn't to the left of {1}")],
    "right_of": [("{0} is to the right of {1}", "{0} isn't to the right of {1}")],
    "directly_left_of": [
        ("{0} is directly to the left of {1}", "{0} isn't directly to the left of {1}")
    ],
    "directly_right_of": [
        ("{0} is directly to the right of {1}", "{0} isn't directly to the right of {1}")
    ],
}
"""Other ways of saying a relation, beside the registry's own English."""

_EXTRA_PROPERTY_TEXT: dict[str, list[tuple[str, str]]] = {
    "in_corner": [("{0} is in the corner", "{0} isn't in the corner")],
    "on_edge": [("{0} is on the edge", "{0} isn't on the edge")],
    "in_center": [("{0} is in the middle", "{0} isn't in the middle")],
}
"""Other ways of saying a property, beside the registry's own English."""


@dataclass(frozen=True)
class _Template:
    words: tuple[str, ...]
    build: Callable[[tuple[ColorRef, ...], int | None], Clue]
    line: str | None = None
    """"row" or "column" if the template has a `{line}` slot."""

    @property
    def subject_first(self) -> bool:
        """Starts with one color as its subject ("{0} is ..."), not "{0} and {1} are"."""
        return len(self.words) > 1 and self.words[0] == "{0}" and self.words[1] != "and"


def _relation_builder(
    kind: str, negated: bool
) -> Callable[[tuple[ColorRef, ...], int | None], Clue]:
    def build(colors: tuple[ColorRef, ...], _: int | None) -> Clue:
        clue = Relation(kind, colors)
        return Not(clue) if negated else clue

    return build


def _property_builder(
    kind: str, negated: bool
) -> Callable[[tuple[ColorRef, ...], int | None], Clue]:
    def build(colors: tuple[ColorRef, ...], index: int | None) -> Clue:
        clue = Property(kind, colors[0], index)
        return Not(clue) if negated else clue

    return build


def _rule_builder(kind: str) -> Callable[[tuple[ColorRef, ...], int | None], Clue]:
    return lambda _colors, _index: BoardRule(kind)


def _templates() -> list[_Template]:
    templates: list[_Template] = []
    for kind, relation_kind in RELATION_KINDS.items():
        texts = [(relation_kind.text, relation_kind.negated), *_EXTRA_RELATION_TEXT.get(kind, [])]
        for text, negated in texts:
            templates.append(_Template(_words(text), _relation_builder(kind, False)))
            templates.append(_Template(_words(negated), _relation_builder(kind, True)))
    for kind, property_kind in PROPERTY_KINDS.items():
        texts = [(property_kind.text, property_kind.negated), *_EXTRA_PROPERTY_TEXT.get(kind, [])]
        for text, negated in texts:
            line = property_kind.index
            templates.append(_Template(_words(text), _property_builder(kind, False), line))
            templates.append(_Template(_words(negated), _property_builder(kind, True), line))
    for kind, rule_kind in BOARD_RULE_KINDS.items():
        templates.append(_Template(_words(rule_kind.text), _rule_builder(kind)))
    return templates


# --------------------------------------------------------------------------- vocabulary

_ORDINAL_WORDS = (
    "first",
    "second",
    "third",
    "fourth",
    "fifth",
    "sixth",
    "seventh",
    "eighth",
    "ninth",
    "tenth",
    "eleventh",
    "twelfth",
)
_NUMBER_WORDS = (
    "zero",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
    "eleven",
    "twelve",
)
_NUMERIC_ORDINAL = re.compile(r"(\d+)(?:st|nd|rd|th)")
_NOT_TRUE = (("it", "is", "not", "true", "that"), ("it", "is", "not", "the", "case", "that"))
_SEPARATORS = ((",", "and"), (",", "but"), (",", "or"), ("and",), ("but",), ("or",), (",",))
_CONNECTIVES = {"and": "and", "but": "and", "or": "or"}


def _ordinal_index(word: str) -> int | None:
    if word in _ORDINAL_WORDS:
        return _ORDINAL_WORDS.index(word)
    match = _NUMERIC_ORDINAL.fullmatch(word)
    if match and int(match.group(1)) >= 1:
        return int(match.group(1)) - 1
    return None


def _number(word: str) -> int | None:
    if word in _NUMBER_WORDS:
        return _NUMBER_WORDS.index(word)
    return int(word) if word.isdigit() else None


# --------------------------------------------------------------------------- parser

_Parses = Iterator[tuple[Clue, int]]
"""Every way a rule matches: the clue read and the index of the next token."""


class _Parser:
    def __init__(self, text: str, palette: Palette, board: Board) -> None:
        self.text = text
        self.board = board
        self.tokens = _tokenize(text)
        if self.tokens and self.tokens[-1].word == ".":
            self.tokens.pop()
        self.templates = _templates()
        self.names = sorted(
            ((tuple(t.word for t in _tokenize(color.name)), color.id) for color in palette),
            key=lambda entry: -len(entry[0]),
        )
        self.furthest = -1
        self.expected: set[str] = set()
        self.problem: tuple[int, str, int] | None = None
        """The furthest-reaching sentence that is well formed but says something impossible:
        how far it got, the message, and the character position to blame."""

    # ---- driver and error reporting

    def parse(self) -> Clue:
        if not self.tokens:
            raise ClueParseError("empty clue", 0)
        for clue, end in self.expr(0):
            if end == len(self.tokens):
                return clue
            self.fail(end, "the end of the clue")
        if self.problem and self.problem[0] >= self.furthest:
            raise ClueParseError(self.problem[1], self.problem[2])
        raise ClueParseError(self.syntax_message(), self.position(self.furthest))

    def fail(self, i: int, expected: str) -> None:
        if i > self.furthest:
            self.furthest, self.expected = i, set()
        if i == self.furthest:
            self.expected.add(expected)

    def impossible(self, reach: int, message: str, at: int) -> None:
        if self.problem is None or reach > self.problem[0]:
            self.problem = (reach, message, self.position(at))

    def position(self, i: int) -> int:
        return self.tokens[i].start if i < len(self.tokens) else len(self.text.rstrip())

    def syntax_message(self) -> str:
        i = self.furthest
        found = repr(self.tokens[i].text) if i < len(self.tokens) else "the end of the clue"
        if i < len(self.tokens) and "a color" in self.expected:
            text = self.tokens[i].text
            if text[0].isupper() and len(text) > 1:
                return f"unknown color {text!r}"
        described = sorted(e for e in self.expected if not e.startswith("'"))
        quoted = sorted(e for e in self.expected if e.startswith("'"))
        options = described + quoted
        listing = (
            options[0] if len(options) == 1 else ", ".join(options[:-1]) + " or " + options[-1]
        )
        return f"expected {listing}, found {found}"

    # ---- token helpers

    def word(self, i: int) -> str | None:
        return self.tokens[i].word if i < len(self.tokens) else None

    def at(self, i: int, *words: str) -> bool:
        return all(self.word(i + k) == w for k, w in enumerate(words))

    def expect(self, i: int, *words: str) -> int | None:
        """The index after `words` if they come next, else None (recording what was missing)."""
        for k, w in enumerate(words):
            if self.word(i + k) != w:
                self.fail(i + k, repr(w))
                return None
        return i + len(words)

    # ---- grammar

    def expr(self, i: int) -> _Parses:
        """A whole clue: a negation, an either/or, a count, or a list of units."""
        for phrase in _NOT_TRUE:
            if self.at(i, *phrase):
                for clue, end in self.expr(i + len(phrase)):
                    yield Not(clue), end
        if self.at(i, "either"):
            yield from self.either(i + 1)
        yield from self.count(i)
        yield from self.units(i)
        self.fail(i, "'it'")

    def unit(self, i: int) -> _Parses:
        """A bracketed clue, or one leaf sentence."""
        if self.at(i, "("):
            for clue, end in self.expr(i + 1):
                close = self.expect(end, ")")
                if close is not None:
                    yield clue, close
        else:
            self.fail(i, "'('")
        for template in self.templates:
            yield from self.leaf(template, i)

    def units(self, i: int) -> _Parses:
        for clue, end in self.unit(i):
            yield from self.more_units([clue], None, end)

    def more_units(self, items: list[Clue], connective: str | None, i: int) -> _Parses:
        """Continue a list "X, Y and Z" (or "or"); every connective in one list must agree."""
        for separator in _SEPARATORS:
            if not self.at(i, *separator):
                continue
            kind = _CONNECTIVES.get(separator[-1])
            if kind and connective and kind != connective:
                self.impossible(
                    i + 2,
                    f"found {separator[-1]!r} in a list joined by {connective!r}; "
                    "bracket one part to say which is meant",
                    i + len(separator) - 1,
                )
                continue
            joined = kind or connective
            for clue, end in self.next_unit(items[-1], i + len(separator)):
                yield from self.more_units([*items, clue], joined, end)
        for expected in ("','", "'and'", "'or'"):
            self.fail(i, expected)
        if len(items) == 1:
            yield items[0], i
        elif connective == "and":
            yield And(tuple(items)), i
        elif connective == "or":
            yield Or(tuple(items)), i

    def next_unit(self, previous: Clue, i: int) -> _Parses:
        """A list item: a unit, a bare color continuing "Black knows White, Teal", or a
        short "but Mustard is" repeating the previous clause for another color."""
        yield from self.unit(i)
        for color, end in self.color(i):
            if _mergeable(previous):
                assert isinstance(previous, Relation)
                yield Relation(previous.kind, (previous.colors[0], color)), end
            for verb in ("is", "does"):
                if self.at(end, verb):
                    negated = self.at(end + 1, "not")
                    repeated = _repeat(previous, color, negated)
                    if repeated is not None:
                        yield repeated, end + (2 if negated else 1)

    def either(self, i: int) -> _Parses:
        for clue, end in self.unit(i):
            yield from self.more_either([clue], False, end)

    def more_either(self, items: list[Clue], seen_or: bool, i: int) -> _Parses:
        for separator in ((",", "or"), ("or",), (",",)):
            if self.at(i, *separator):
                for clue, end in self.unit(i + len(separator)):
                    yield from self.more_either([*items, clue], seen_or or "or" in separator, end)
        if seen_or:
            yield Or(tuple(items)), i
        else:
            self.fail(i, "'or'")

    def count(self, i: int) -> _Parses:
        if self.at(i, "exactly"):
            build: type[Exactly] | type[AtLeast] = Exactly
            n_at = i + 1
        elif self.at(i, "at", "least"):
            build = AtLeast
            n_at = i + 2
        else:
            self.fail(i, "'exactly'")
            self.fail(i, "'at'")
            return
        n = _number(self.word(n_at) or "")
        if n is None:
            self.fail(n_at, "a number")
            return
        start = self.expect(n_at + 1, "of", "these")
        if start is None:
            return
        if not (self.at(start, "is") or self.at(start, "are")):
            self.fail(start, "'are'")
            return
        start = self.expect(start + 1, "true", ":")
        if start is not None:
            yield from self.count_items(build, n, n_at, [], start)

    def count_items(
        self,
        build: type[Exactly] | type[AtLeast],
        n: int,
        n_at: int,
        items: list[Clue],
        i: int,
    ) -> _Parses:
        for clue, end in self.expr(i):
            found = [*items, clue]
            if self.at(end, ";"):
                yield from self.count_items(build, n, n_at, found, end + 1)
            self.fail(end, "';'")
            if n > len(found):
                self.impossible(end, f"cannot count {n} of only {len(found)} clues", n_at)
            elif build is AtLeast and n == 0:
                self.impossible(end, "'at least zero' is always true; count from one", n_at)
            else:
                yield build(n, tuple(found)), end

    # ---- leaves

    def leaf(self, template: _Template, i: int) -> _Parses:
        if template.subject_first:
            for subjects, end in self.subjects(i):
                for clue, stop in self.slots(template, 1, end, (subjects[0],), None):
                    if len(subjects) == 1:
                        yield clue, stop
                    else:
                        yield Or(tuple(_with_subject(clue, s) for s in subjects)), stop
        else:
            yield from self.slots(template, 0, i, (), None)

    def slots(
        self,
        template: _Template,
        k: int,
        i: int,
        colors: tuple[ColorRef, ...],
        index: int | None,
    ) -> _Parses:
        """Match the template from word `k` on, filling color and line slots in order."""
        if k == len(template.words):
            yield template.build(colors, index), i
            return
        word = template.words[k]
        if word == "{line}":
            assert template.line is not None
            line = self.line(i, template.line)
            if line is not None:
                yield from self.slots(template, k + 1, line[1], colors, line[0])
        elif word.startswith("{"):
            for color, end in self.color(i):
                yield from self.slots(template, k + 1, end, (*colors, color), index)
        elif self.word(i) == word:
            yield from self.slots(template, k + 1, i + 1, colors, index)
        else:
            self.fail(i, repr(word))

    def subjects(self, i: int) -> Iterator[tuple[tuple[ColorRef, ...], int]]:
        """One color, or "either A or B" / "A, B or C" naming alternatives."""
        either = self.at(i, "either")
        start = i + 1 if either else i
        for first, end in self.color(start):
            if not either:
                yield (first,), end
            yield from self.more_subjects((first,), False, end)

    def more_subjects(
        self, found: tuple[ColorRef, ...], seen_or: bool, i: int
    ) -> Iterator[tuple[tuple[ColorRef, ...], int]]:
        for separator in ((",", "or"), ("or",), (",",)):
            if self.at(i, *separator):
                for color, end in self.color(i + len(separator)):
                    yield from self.more_subjects(
                        (*found, color), seen_or or "or" in separator, end
                    )
        if seen_or:
            yield found, i

    def color(self, i: int) -> Iterator[tuple[ColorRef, int]]:
        if i < len(self.tokens):
            text = self.tokens[i].text
            if len(text) == 1 and text.isalpha() and text.isupper():
                yield ColorRef.initial(text), i + 1
                return
            for words, color_id in self.names:
                if self.at(i, *words):
                    yield ColorRef.named(color_id), i + len(words)
                    return
        self.fail(i, "a color")

    def line(self, i: int, kind: str) -> tuple[int, int] | None:
        """A named row or column: "the top row", "the second column", "row 3"."""
        count = self.board.rows if kind == "row" else self.board.cols
        index: int | None
        if self.at(i, "the"):
            name = self.word(i + 1) or ""
            index = _ordinal_index(name)
            if kind == "row" and name == "top":
                index = 0
            elif kind == "row" and name == "bottom":
                index = count - 1
            elif kind == "row" and name == "middle" and count % 2 == 1:
                index = count // 2
            if index is None:
                self.fail(i + 1, f"a {kind} name")
                return None
            if self.expect(i + 2, kind) is None:
                return None
            name_at, end = i + 1, i + 3
        elif self.at(i, kind):
            index = _number(self.word(i + 1) or "")
            if index is None or index < 1:
                self.fail(i + 1, f"a {kind} number from 1")
                return None
            index -= 1
            name_at, end = i + 1, i + 2
        else:
            self.fail(i, "'the'")
            self.fail(i, repr(kind))
            return None
        if index >= count:
            self.impossible(end, f"the board has only {count} {kind}s", name_at)
            return None
        return index, end


# --------------------------------------------------------------------------- helpers


def _mergeable(clue: Clue) -> bool:
    """Whether "and Teal" can continue this clue, as in "Black knows White and Teal".

    Mirrors the renderer: a two-color relation whose sentence ends with its second color,
    from a named color (an initial would let each part pick its own color).
    """
    return (
        isinstance(clue, Relation)
        and len(clue.colors) == 2
        and not clue.colors[0].by_initial
        and RELATION_KINDS[clue.kind].text.endswith("{1}")
    )


def _repeat(previous: Clue, color: ColorRef, negated: bool) -> Clue | None:
    """The previous clause said of another color: "White isn't in a corner, but Mustard is"."""
    inner = previous.clue if isinstance(previous, Not) else previous
    if isinstance(inner, Relation) and RELATION_KINDS[inner.kind].text.startswith("{0} and"):
        return None
    if not isinstance(inner, Relation | Property):
        return None
    clue = _with_subject(inner, color)
    return Not(clue) if negated else clue


def _with_subject(clue: Clue, color: ColorRef) -> Clue:
    """The same leaf (or negated leaf) about `color` instead of its first color."""
    match clue:
        case Not(clue=inner):
            return Not(_with_subject(inner, color))
        case Relation(kind=kind, colors=colors):
            return Relation(kind, (color, *colors[1:]))
        case Property(kind=kind, index=index):
            return Property(kind, color, index)
    raise TypeError(f"no subject to replace in {clue!r}")
