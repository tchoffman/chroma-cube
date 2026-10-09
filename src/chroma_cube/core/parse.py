"""Read English clue sentences back into clues.

The parser accepts every sentence `render` produces plus common ways of saying the same
thing ("is next to", "is not", an Oxford comma). It is a hand-written tokenizer and a
backtracking recursive-descent parser: each rule yields every way it can match, and the
first reading that uses the whole sentence wins. Leaf sentences come from the templates in
the clue registries, so a new relation or property kind is parsed without touching this
module.
"""

from __future__ import annotations

import functools
import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass, replace
from typing import TypeVar

from chroma_cube.core.board import CLASSIC_BOARD, Board
from chroma_cube.core.clues import (
    ATTRIBUTE_KINDS,
    BOARD_RULE_KINDS,
    PROPERTY_KINDS,
    RELATION_KINDS,
    And,
    AtLeast,
    AttributeClue,
    BoardRule,
    Clue,
    ColorRef,
    Exactly,
    Not,
    Or,
    Property,
    Region,
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


_TOKEN = r"[A-Za-z0-9]+(?:['’][A-Za-z]+)?|[,;:().]|\S"
_WORDS = re.compile(_TOKEN)
_CONTRACTIONS = {
    "isn't": ("is", "not"),
    "aren't": ("are", "not"),
    "doesn't": ("does", "not"),
    "don't": ("do", "not"),
    "it's": ("it", "is"),
}


def _tokenize(text: str, pattern: re.Pattern[str] = _WORDS) -> list[_Token]:
    """Split text into tokens. A pattern from `_tokens_for` also reads each palette color
    name, spaces and punctuation included, as one token."""
    tokens: list[_Token] = []
    for match in pattern.finditer(text):
        piece, start = match.group(), match.start()
        if match.lastgroup == "name":
            tokens.append(_Token(piece, _name_key(piece), start))
            continue
        if not (piece[0].isalnum() or piece in ",;:()."):
            raise ClueParseError(f"unexpected character {piece!r}", start)
        word = piece.lower().replace("’", "'")
        for part in _CONTRACTIONS.get(word, (word,)):
            tokens.append(_Token(piece, part, start))
    return tokens


def _name_key(name: str) -> str:
    return " ".join(name.lower().split())


@functools.cache
def _tokens_for(palette: Palette) -> re.Pattern[str]:
    """A token pattern that reads each color name of the palette as one token."""
    names = sorted({_name_key(color.name) for color in palette}, key=len, reverse=True)
    spelled = "|".join(r"\s+".join(re.escape(part) for part in name.split()) for name in names)
    return re.compile(
        rf"(?P<name>(?<![A-Za-z0-9])(?:{spelled})(?![A-Za-z0-9]))|{_TOKEN}", re.IGNORECASE
    )


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
"""Other ways of saying a relation, beside the registry's own English (its `text`,
`negated` and `alternatives`)."""

_EXTRA_PROPERTY_TEXT: dict[str, list[tuple[str, str]]] = {
    "in_corner": [("{0} is in the corner", "{0} isn't in the corner")],
    "on_edge": [("{0} is on the edge", "{0} isn't on the edge")],
    "in_center": [("{0} is in the middle", "{0} isn't in the middle")],
}
"""Other ways of saying a property, beside the registry's own English."""


@dataclass(frozen=True)
class _Filled:
    """What a template's slots were filled with so far."""

    colors: tuple[ColorRef, ...] = ()
    index: int | None = None
    region: Region | None = None
    value: str | None = None
    n: int | None = None


_Builder = Callable[[_Filled], Clue]


@dataclass(frozen=True)
class _Template:
    words: tuple[str, ...]
    build: _Builder
    line: str | None = None
    """"row" or "column" if the template has a `{line}` slot."""
    values: tuple[str, ...] = ()
    """The words a `{value}` slot accepts."""

    @property
    def subject_first(self) -> bool:
        """Starts with one color as its subject ("{0} is ..."), not "{0} and {1} are"."""
        return len(self.words) > 1 and self.words[0] == "{0}" and self.words[1] != "and"

    @property
    def verb(self) -> str | None:
        """The verb a short repeat of this clause takes: "but Mustard is" / "does"."""
        if not self.subject_first:
            return None
        return "is" if self.words[1] == "is" else "does"


def _negatable(clue: Clue, negated: bool) -> Clue:
    return Not(clue) if negated else clue


def _relation_builder(kind: str, negated: bool) -> _Builder:
    return lambda filled: _negatable(Relation(kind, filled.colors), negated)


def _property_builder(kind: str, negated: bool) -> _Builder:
    return lambda filled: _negatable(Property(kind, filled.colors[0], filled.index), negated)


def _attribute_builder(kind: str, negated: bool) -> _Builder:
    def build(filled: _Filled) -> Clue:
        assert filled.value is not None
        color = filled.colors[0] if filled.colors else None
        clue = AttributeClue(kind, filled.value, color, filled.region, filled.n)
        return _negatable(clue, negated)

    return build


def _rule_builder(kind: str) -> _Builder:
    return lambda _filled: BoardRule(kind)


def _templates() -> list[_Template]:
    templates: list[_Template] = []
    for kind, relation_kind in RELATION_KINDS.items():
        texts = [(relation_kind.text, relation_kind.negated), *_EXTRA_RELATION_TEXT.get(kind, [])]
        positives = [text for text, _ in texts]
        if relation_kind.alternatives and relation_kind.alternatives not in positives:
            positives.append(relation_kind.alternatives)
        for text in positives:
            templates.append(_Template(_words(text), _relation_builder(kind, False)))
        for _, negated in texts:
            templates.append(_Template(_words(negated), _relation_builder(kind, True)))
    for kind, property_kind in PROPERTY_KINDS.items():
        texts = [(property_kind.text, property_kind.negated), *_EXTRA_PROPERTY_TEXT.get(kind, [])]
        for text, negated in texts:
            line = property_kind.index
            templates.append(_Template(_words(text), _property_builder(kind, False), line))
            templates.append(_Template(_words(negated), _property_builder(kind, True), line))
    for kind, attribute_kind in ATTRIBUTE_KINDS.items():
        values = attribute_kind.values
        sayings = ((attribute_kind.text, False), (attribute_kind.negated, True))
        for saying, is_negated in sayings:
            if saying is not None:
                build = _attribute_builder(kind, is_negated)
                templates.append(_Template(_words(saying), build, values=values))
    for kind, rule_kind in BOARD_RULE_KINDS.items():
        templates.append(_Template(_words(rule_kind.text), _rule_builder(kind)))
    return templates


_TEMPLATES = _templates()
"""Every leaf sentence the parser knows, built once from the registries at import."""

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
_AGREEING = {"{colors}": ("colors", "color"), "{is}": ("are", "is")}
"""Slots whose word agrees with a count; the parser takes either form."""
_MAX_DEPTH = 16
"""How deeply brackets and "it's not true that" may nest."""
_MAX_ALTERNATIVES = 3
"""How many colors "Either A, B or C ..." may name; the renderer never writes more."""


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

_Unit = tuple[Clue, int, str | None]
"""A unit read: the clue, the index of the next token, and the verb a short repeat of it
takes ("is" / "does"), or None if it cannot be repeated."""

_Subjects = list[tuple[tuple[ColorRef, ...], int]]

_State = TypeVar("_State")
_ListState = tuple[tuple[Clue, ...], str | None, int, str | None]
"""A list read so far: its items, its connective, the next token, the last item's verb."""
_EitherState = tuple[tuple[Clue, ...], bool, int]
"""An either/or read so far: its items, whether an "or" was seen, the next token."""
_CountState = tuple[tuple[Clue, ...], int]
"""A count's clues read so far and the next token."""


def _post_order(
    start: _State,
    children: Callable[[_State], Iterator[_State]],
    finish: Callable[[_State], _Parses],
) -> _Parses:
    """Depth-first over list states, longest list first, without deep recursion: a long
    list ("A, B, C, ...") would otherwise nest one generator per item."""
    stack = [(start, children(start))]
    while stack:
        state, pending = stack[-1]
        child = next(pending, None)
        if child is not None:
            stack.append((child, children(child)))
            continue
        stack.pop()
        yield from finish(state)


class _Parser:
    def __init__(self, text: str, palette: Palette, board: Board) -> None:
        self.text = text
        self.board = board
        self.tokens = _tokenize(text, _tokens_for(palette))
        if self.tokens and self.tokens[-1].word == ".":
            self.tokens.pop()
        self.names = {_name_key(color.name): color.id for color in palette}
        self.units_at: dict[int, list[_Unit]] = {}
        self.subjects_at: dict[int, _Subjects] = {}
        self.furthest = -1
        self.expected: set[str] = set()
        self.problem: tuple[int, str, int] | None = None
        """The furthest-reaching sentence that is well formed but says something impossible:
        how far it got, the message, and the character position to blame."""

    # ---- driver and error reporting

    def parse(self) -> Clue:
        if not self.tokens:
            raise ClueParseError("empty clue", 0)
        try:
            for clue, end in self.expr(0, 0):
                if end == len(self.tokens):
                    return clue
                self.fail(end, "the end of the clue")
        except RecursionError:
            raise ClueParseError("clue is nested too deeply to read", 0) from None
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

    def deeper(self, i: int, depth: int) -> int:
        if depth >= _MAX_DEPTH:
            raise ClueParseError(
                f"brackets and negations are nested more than {_MAX_DEPTH} deep",
                self.position(i),
            )
        return depth + 1

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

    def expr(self, i: int, depth: int) -> _Parses:
        """A whole clue: a negation, an either/or, a count, or a list of units."""
        for phrase in _NOT_TRUE:
            if self.at(i, *phrase):
                inner = self.deeper(i, depth)
                for clue, end in self.expr(i + len(phrase), inner):
                    yield Not(clue), end
        if self.at(i, "either"):
            yield from self.either(i + 1, depth)
        yield from self.count(i, depth)
        yield from self.units(i, depth)
        self.fail(i, "'it'")

    def unit(self, i: int, depth: int) -> list[_Unit]:
        """A bracketed clue, or one leaf sentence. Each position is read once."""
        if i not in self.units_at:
            self.units_at[i] = list(self.read_unit(i, depth))
        return self.units_at[i]

    def read_unit(self, i: int, depth: int) -> Iterator[_Unit]:
        if self.at(i, "("):
            inner = self.deeper(i, depth)
            for clue, end in self.expr(i + 1, inner):
                close = self.expect(end, ")")
                if close is not None:
                    yield clue, close, None
        else:
            self.fail(i, "'('")
        yield from self.leaves(i)

    def units(self, i: int, depth: int) -> _Parses:
        for clue, end, verb in self.unit(i, depth):
            yield from self.unit_list(((clue,), None, end, verb), depth)

    def unit_list(self, start: _ListState, depth: int) -> _Parses:
        """Continue a list "X, Y and Z" (or "or"); every connective in one list must agree."""

        def children(
            state: _ListState,
        ) -> Iterator[_ListState]:
            items, connective, i, verb = state
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
                for clue, end, next_verb in self.next_unit(
                    items[-1], verb, i + len(separator), depth
                ):
                    yield (*items, clue), kind or connective, end, next_verb

        def finish(state: _ListState) -> _Parses:
            items, connective, i, _ = state
            for expected in ("','", "'and'", "'or'"):
                self.fail(i, expected)
            if len(items) == 1:
                yield items[0], i
            elif connective == "and":
                yield And(items), i
            elif connective == "or":
                yield Or(items), i

        yield from _post_order(start, children, finish)

    def next_unit(self, previous: Clue, verb: str | None, i: int, depth: int) -> Iterator[_Unit]:
        """A list item: a unit, a bare color continuing "Black knows White, Teal", or a
        short "but Mustard is" repeating the previous clause for another color with the
        same verb."""
        yield from self.unit(i, depth)
        for color, end in self.color(i):
            if _mergeable(previous):
                assert isinstance(previous, Relation)
                yield Relation(previous.kind, (previous.colors[0], color)), end, verb
            if verb is not None and self.at(end, verb):
                negated = self.at(end + 1, "not")
                repeated = _repeat(previous, color, negated)
                if repeated is not None:
                    yield repeated, end + (2 if negated else 1), verb
            elif verb is not None:
                self.fail(end, repr(verb))

    def either(self, i: int, depth: int) -> _Parses:
        def children(
            state: _EitherState,
        ) -> Iterator[_EitherState]:
            items, seen_or, at = state
            for separator in ((",", "or"), ("or",), (",",)):
                if self.at(at, *separator):
                    for clue, end, _ in self.unit(at + len(separator), depth):
                        yield (*items, clue), seen_or or "or" in separator, end

        def finish(state: _EitherState) -> _Parses:
            items, seen_or, at = state
            if seen_or:
                yield Or(items), at
            else:
                self.fail(at, "'or'")

        for clue, end, _ in self.unit(i, depth):
            first: _EitherState = ((clue,), False, end)
            yield from _post_order(first, children, finish)

    def count(self, i: int, depth: int) -> _Parses:
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
        if start is None:
            return

        def children(state: _CountState) -> Iterator[_CountState]:
            items, at = state
            if items and not self.at(at, ";"):
                self.fail(at, "';'")
                return
            for clue, end in self.expr(at + 1 if items else at, depth):
                yield (*items, clue), end

        def finish(state: _CountState) -> _Parses:
            items, at = state
            if not items:
                return
            if n > len(items):
                self.impossible(at, f"cannot count {n} of only {len(items)} clues", n_at)
            elif build is AtLeast and n == 0:
                self.impossible(at, "'at least zero' is always true; count from one", n_at)
            else:
                yield build(n, items), at

        empty: _CountState = ((), start)
        yield from _post_order(empty, children, finish)

    # ---- leaves

    def leaves(self, i: int) -> Iterator[_Unit]:
        """Every leaf sentence from the templates that matches at `i`."""
        subjects = self.subjects(i)
        for template in _TEMPLATES:
            if not template.subject_first:
                for clue, stop in self.slots(template, 0, i, _Filled()):
                    yield clue, stop, None
                continue
            for found, end in subjects:
                for clue, stop in self.slots(template, 1, end, _Filled((found[0],))):
                    if len(found) == 1:
                        yield clue, stop, template.verb
                    else:
                        yield Or(tuple(_with_subject(clue, s) for s in found)), stop, None

    def slots(self, template: _Template, k: int, i: int, filled: _Filled) -> _Parses:
        """Match the template from word `k` on, filling its slots in order."""
        if k == len(template.words):
            yield template.build(filled), i
            return
        word = template.words[k]
        word_here = self.word(i)
        if word == "{line}":
            assert template.line is not None
            line = self.line(i, template.line)
            if line is not None:
                yield from self.slots(template, k + 1, line[1], replace(filled, index=line[0]))
        elif word == "{region}":
            for region, end in self.region(i):
                yield from self.slots(template, k + 1, end, replace(filled, region=region))
        elif word == "{value}":
            if word_here in template.values:
                yield from self.slots(template, k + 1, i + 1, replace(filled, value=word_here))
            else:
                self.fail(i, "a color attribute")
        elif word == "{n}":
            n = _number(word_here or "")
            if n is not None:
                yield from self.slots(template, k + 1, i + 1, replace(filled, n=n))
            else:
                self.fail(i, "a number")
        elif word in _AGREEING:
            if word_here in _AGREEING[word]:
                yield from self.slots(template, k + 1, i + 1, filled)
            else:
                self.fail(i, repr(_AGREEING[word][0]))
        elif word.startswith("{"):
            for color, end in self.color(i):
                colors = (*filled.colors, color)
                yield from self.slots(template, k + 1, end, replace(filled, colors=colors))
        elif word_here == word:
            yield from self.slots(template, k + 1, i + 1, filled)
        else:
            self.fail(i, repr(word))

    def region(self, i: int) -> Iterator[tuple[Region, int]]:
        """A region with its preposition: "in the corners", "on the edge", "in row 2"."""
        if self.at(i, "on", "the", "edge"):
            yield Region("edge"), i + 3
            return
        if not self.at(i, "in"):
            self.fail(i, "'in'")
            self.fail(i, "'on'")
            return
        middle = self.at(i + 1, "the", "middle") and not self.at(i + 3, "row")
        if middle or self.at(i + 1, "the", "center"):
            yield Region("center"), i + 3
            return
        if self.at(i + 1, "the", "corners"):
            yield Region("corners"), i + 3
            return
        for kind in ("row", "column"):
            line = self.line(i + 1, kind)
            if line is not None:
                yield Region(kind, line[0]), line[1]

    def subjects(self, i: int) -> _Subjects:
        """One color, or "either A or B" / "A, B or C" naming up to three alternatives.
        Each position is read once."""
        if i in self.subjects_at:
            return self.subjects_at[i]
        found: _Subjects = []
        either = self.at(i, "either")
        start = i + 1 if either else i
        for first, end in self.color(start):
            if not either:
                found.append(((first,), end))
            stack: list[tuple[tuple[ColorRef, ...], bool, int]] = [((first,), False, end)]
            while stack:
                colors, seen_or, at = stack.pop()
                if seen_or:
                    found.append((colors, at))
                if len(colors) == _MAX_ALTERNATIVES:
                    continue
                for separator in ((",", "or"), ("or",), (",",)):
                    if self.at(at, *separator):
                        for color, stop in self.color(at + len(separator)):
                            stack.append(((*colors, color), seen_or or "or" in separator, stop))
        found.sort(key=lambda entry: (len(entry[0]) != 1, -len(entry[0])))
        self.subjects_at[i] = found
        return found

    def color(self, i: int) -> Iterator[tuple[ColorRef, int]]:
        if i < len(self.tokens):
            token = self.tokens[i]
            if len(token.text) == 1 and token.text.isalpha() and token.text.isupper():
                yield ColorRef.initial(token.text), i + 1
                return
            if token.word in self.names:
                yield ColorRef.named(self.names[token.word]), i + 1
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
    if isinstance(inner, AttributeClue) and inner.color is None:
        return None
    if not isinstance(inner, Relation | Property | AttributeClue):
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
        case AttributeClue():
            return replace(clue, color=color)
    raise TypeError(f"no subject to replace in {clue!r}")
