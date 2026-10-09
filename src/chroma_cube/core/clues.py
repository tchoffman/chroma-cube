"""The clue language: an immutable AST of clues about where colors sit.

Relation, property, attribute and board-rule kinds live in registries (`RELATION_KINDS`,
`PROPERTY_KINDS`, `ATTRIBUTE_KINDS`, `BOARD_RULE_KINDS`).
Each entry carries everything the rest of the system needs to know about a kind: its
arity, the predicate over cells that the evaluator uses, and the English templates the
renderer uses. Adding a kind is one registry entry; no new node class is needed.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from itertools import product

from chroma_cube.core.board import Board, Cell
from chroma_cube.core.board_rules import columns_alphabetical, rows_alphabetical
from chroma_cube.core.colors import FAMILIES, QUALITIES, Palette
from chroma_cube.core.placement import Placement
from chroma_cube.core.truth import Truth

# --------------------------------------------------------------------------- color refs


@dataclass(frozen=True)
class ColorRef:
    """A reference to a color in a clue: by id (`black`) or by initial (`B`).

    An initial means "some palette color whose name starts with this letter". Ids may
    not be a single capital letter, so the two kinds of reference never look alike in
    puzzle data.
    """

    key: str
    by_initial: bool = False

    def __post_init__(self) -> None:
        if self.by_initial:
            if len(self.key) != 1 or not self.key.isalpha() or not self.key.isupper():
                raise ValueError(f"an initial is one capital letter, got {self.key!r}")
        elif not self.key or _looks_like_initial(self.key):
            raise ValueError(f"not a valid color id: {self.key!r}")

    @classmethod
    def named(cls, color_id: str) -> ColorRef:
        return cls(color_id)

    @classmethod
    def initial(cls, letter: str) -> ColorRef:
        return cls(letter.upper() if len(letter) == 1 else letter, by_initial=True)

    def __str__(self) -> str:
        return self.key


def _looks_like_initial(text: str) -> bool:
    return len(text) == 1 and text.isalpha() and text.isupper()


def ref(color: ColorRef | str) -> ColorRef:
    """Coerce a string to a reference: one capital letter is an initial, anything else an id."""
    if isinstance(color, ColorRef):
        return color
    return ColorRef.initial(color) if _looks_like_initial(color) else ColorRef.named(color)


# --------------------------------------------------------------------------- registries


@dataclass(frozen=True)
class RelationKind:
    """How a relation between colors is decided and said.

    `holds` gets the cells of the related colors in clue order. The templates use
    `{0}`, `{1}`, ... for the color names; `negated` is the sentence for `Not(...)`.
    """

    arity: int
    holds: Callable[[tuple[Cell, ...]], bool]
    text: str
    negated: str
    alternatives: str | None = None
    """The sentence with one color as its subject, for "Either Teal or Black ... {1}".
    Needed only when `text` does not start with "{0}" alone; defaults to `text`."""


@dataclass(frozen=True)
class PropertyKind:
    """How a property of one color is decided and said.

    `holds` gets the board, the color's cell and the property's index (or None).
    Templates use `{0}` for the color and `{line}` for the named row or column.
    """

    holds: Callable[[Board, Cell, int | None], bool]
    text: str
    negated: str
    index: str | None = None
    """"row" or "column" if the property takes an index naming one, else None."""


def _binary(test: Callable[[Cell, Cell], bool]) -> Callable[[tuple[Cell, ...]], bool]:
    return lambda cells: test(cells[0], cells[1])


def _between(cells: tuple[Cell, ...]) -> bool:
    a, b, c = cells
    if a.row == b.row == c.row:
        return {b.col, c.col} == {a.col - 1, a.col + 1}
    if a.col == b.col == c.col:
        return {b.row, c.row} == {a.row - 1, a.row + 1}
    return False


RELATION_KINDS: dict[str, RelationKind] = {
    "same_row": RelationKind(
        2,
        _binary(lambda a, b: a.row == b.row),
        "{0} and {1} are in the same row",
        "{0} and {1} aren't in the same row",
        alternatives="{0} is in the same row as {1}",
    ),
    "same_column": RelationKind(
        2,
        _binary(lambda a, b: a.col == b.col),
        "{0} and {1} are in the same column",
        "{0} and {1} aren't in the same column",
        alternatives="{0} is in the same column as {1}",
    ),
    "next_to": RelationKind(
        2,
        _binary(lambda a, b: abs(a.row - b.row) + abs(a.col - b.col) == 1),
        "{0} sits next to {1}",
        "{0} doesn't sit next to {1}",
    ),
    "knows": RelationKind(
        2,
        _binary(lambda a, b: a != b and max(abs(a.row - b.row), abs(a.col - b.col)) == 1),
        "{0} knows {1}",
        "{0} doesn't know {1}",
    ),
    "diagonal": RelationKind(
        2,
        _binary(lambda a, b: abs(a.row - b.row) == 1 and abs(a.col - b.col) == 1),
        "{0} is diagonal to {1}",
        "{0} isn't diagonal to {1}",
    ),
    "above": RelationKind(
        2,
        _binary(lambda a, b: a.col == b.col and a.row < b.row),
        "{0} is above {1}",
        "{0} isn't above {1}",
    ),
    "below": RelationKind(
        2,
        _binary(lambda a, b: a.col == b.col and a.row > b.row),
        "{0} is below {1}",
        "{0} isn't below {1}",
    ),
    "left_of": RelationKind(
        2,
        _binary(lambda a, b: a.row == b.row and a.col < b.col),
        "{0} is left of {1}",
        "{0} isn't left of {1}",
    ),
    "right_of": RelationKind(
        2,
        _binary(lambda a, b: a.row == b.row and a.col > b.col),
        "{0} is right of {1}",
        "{0} isn't right of {1}",
    ),
    "directly_above": RelationKind(
        2,
        _binary(lambda a, b: a.col == b.col and a.row == b.row - 1),
        "{0} is directly above {1}",
        "{0} isn't directly above {1}",
    ),
    "directly_below": RelationKind(
        2,
        _binary(lambda a, b: a.col == b.col and a.row == b.row + 1),
        "{0} is directly below {1}",
        "{0} isn't directly below {1}",
    ),
    "directly_left_of": RelationKind(
        2,
        _binary(lambda a, b: a.row == b.row and a.col == b.col - 1),
        "{0} is directly left of {1}",
        "{0} isn't directly left of {1}",
    ),
    "directly_right_of": RelationKind(
        2,
        _binary(lambda a, b: a.row == b.row and a.col == b.col + 1),
        "{0} is directly right of {1}",
        "{0} isn't directly right of {1}",
    ),
    "between": RelationKind(
        3,
        _between,
        "{0} is between {1} and {2}",
        "{0} isn't between {1} and {2}",
    ),
}
"""Every relation kind, by the name used in puzzle data."""


PROPERTY_KINDS: dict[str, PropertyKind] = {
    "in_corner": PropertyKind(
        lambda board, cell, _: board.is_corner(cell),
        "{0} is in a corner",
        "{0} isn't in a corner",
    ),
    "on_edge": PropertyKind(
        lambda board, cell, _: board.is_edge(cell),
        "{0} is on an edge",
        "{0} isn't on an edge",
    ),
    "in_center": PropertyKind(
        lambda board, cell, _: board.is_center(cell),
        "{0} is in the center",
        "{0} isn't in the center",
    ),
    "in_row": PropertyKind(
        lambda board, cell, index: cell.row == index,
        "{0} is in {line}",
        "{0} isn't in {line}",
        index="row",
    ),
    "in_col": PropertyKind(
        lambda board, cell, index: cell.col == index,
        "{0} is in {line}",
        "{0} isn't in {line}",
        index="column",
    ),
}
"""Every property kind, by the name used in puzzle data."""


@dataclass(frozen=True)
class BoardRuleKind:
    """How a board-wide rule is decided and said.

    `evaluate` decides the rule three-valued on a possibly partial placement, since a
    whole-board rule has no small set of colors to try out like a relation does.
    """

    evaluate: Callable[[Placement, Board, Palette], Truth]
    text: str


BOARD_RULE_KINDS: dict[str, BoardRuleKind] = {
    "rows_alphabetical": BoardRuleKind(
        rows_alphabetical, "Every row is in alphabetical order from left to right"
    ),
    "columns_alphabetical": BoardRuleKind(
        columns_alphabetical, "Every column is in alphabetical order from top to bottom"
    ),
}
"""Every board-wide rule, by the name used in puzzle data."""


# --------------------------------------------------------------------------- attributes

REGION_KINDS = ("corners", "edge", "center", "row", "column")
"""The parts of the board a region clue can talk about. Rows and columns take an index."""


@dataclass(frozen=True)
class Region:
    """A set of cells named in a clue: `Region("corners")`, `Region("row", 0)`."""

    kind: str
    index: int | None = None

    def __post_init__(self) -> None:
        if self.kind not in REGION_KINDS:
            raise ValueError(f"unknown region {self.kind!r}")
        lined = self.kind in ("row", "column")
        if lined and (self.index is None or self.index < 0):
            raise ValueError(f"a {self.kind} region needs an index >= 0")
        if not lined and self.index is not None:
            raise ValueError(f"the {self.kind} region takes no index")

    def cells(self, board: Board) -> tuple[Cell, ...]:
        """The region's cells in row-major order. Raises `ValueError` for a line off the board."""
        match self.kind:
            case "corners":
                return tuple(cell for cell in board if board.is_corner(cell))
            case "edge":
                return tuple(cell for cell in board if board.is_edge(cell))
            case "center":
                return tuple(cell for cell in board if board.is_center(cell))
            case "row":
                assert self.index is not None
                return board.row(self.index)
        assert self.index is not None
        return board.column(self.index)


@dataclass(frozen=True)
class AttributeKind:
    """How a clue about color attributes is decided and said.

    The clue looks at a group of cells: the cells next to its color (`subject` "color")
    or a named region (`subject` "region"). `holds(matching, others, n)` decides it from
    how many cubes in those cells have the clue's value and how many do not; `n` is the
    clue's count for `counted` kinds, else None. `values` lists the values the clue may
    name. Templates use `{0}` for the color, `{value}`, `{region}` ("in the corners"),
    `{n}`, and `{colors}` / `{is}`, which agree with `n`. A `negated` of None means
    `Not(...)` is said as "It's not true that ...".
    """

    subject: str
    values: tuple[str, ...]
    holds: Callable[[int, int, int | None], bool]
    text: str
    negated: str | None = None
    counted: bool = False


ATTRIBUTE_KINDS: dict[str, AttributeKind] = {
    "neighbours_all": AttributeKind(
        "color",
        QUALITIES,
        lambda matching, others, _: others == 0,
        "Every cube next to {0} is a {value} color",
        "Not every cube next to {0} is a {value} color",
    ),
    "neighbours_some": AttributeKind(
        "color",
        QUALITIES,
        lambda matching, others, _: matching > 0,
        "{0} sits next to a {value} color",
        "{0} doesn't sit next to a {value} color",
    ),
    "next_to_family": AttributeKind(
        "color",
        FAMILIES,
        lambda matching, others, _: matching > 0,
        "{0} sits next to a shade of {value}",
        "{0} doesn't sit next to a shade of {value}",
    ),
    "region_all": AttributeKind(
        "region",
        QUALITIES,
        lambda matching, others, _: others == 0,
        "Every cube {region} is a {value} color",
        "Not every cube {region} is a {value} color",
    ),
    "region_count": AttributeKind(
        "region",
        QUALITIES,
        lambda matching, others, n: matching == n,
        "Exactly {n} {value} {colors} {is} {region}",
        counted=True,
    ),
}
"""Every attribute kind, by the name used in puzzle data. "Next to" means sharing a side.

There is no "none" kind: "No cube next to Mint is a warm color" is
`Not(neighbours_some(mint, warm))`, said "Mint doesn't sit next to a warm color"."""


# --------------------------------------------------------------------------- nodes


@dataclass(frozen=True)
class Relation:
    """A relation between colors, e.g. `Relation("next_to", (black, white))`."""

    kind: str
    colors: tuple[ColorRef, ...]

    def __post_init__(self) -> None:
        if self.kind not in RELATION_KINDS:
            raise ValueError(f"unknown relation kind {self.kind!r}")
        arity = RELATION_KINDS[self.kind].arity
        if len(self.colors) != arity:
            raise ValueError(f"{self.kind} relates {arity} colors, got {len(self.colors)}")


@dataclass(frozen=True)
class Property:
    """A property of one color, e.g. `Property("in_row", black, 0)` for the top row."""

    kind: str
    color: ColorRef
    index: int | None = None

    def __post_init__(self) -> None:
        if self.kind not in PROPERTY_KINDS:
            raise ValueError(f"unknown property kind {self.kind!r}")
        takes_index = PROPERTY_KINDS[self.kind].index is not None
        if takes_index and (self.index is None or self.index < 0):
            raise ValueError(f"{self.kind} needs a row or column index >= 0")
        if not takes_index and self.index is not None:
            raise ValueError(f"{self.kind} takes no index")


@dataclass(frozen=True)
class BoardRule:
    """A rule about the whole board, e.g. `BoardRule("rows_alphabetical")`."""

    kind: str

    def __post_init__(self) -> None:
        if self.kind not in BOARD_RULE_KINDS:
            raise ValueError(f"unknown board rule {self.kind!r}")


@dataclass(frozen=True)
class AttributeClue:
    """A clue about the attributes of the cubes next to a color or in a region, e.g.
    `AttributeClue("neighbours_all", "cool", color=mint)` or
    `AttributeClue("region_count", "light", region=Region("row", 0), n=2)`."""

    kind: str
    value: str
    color: ColorRef | None = None
    region: Region | None = None
    n: int | None = None

    def __post_init__(self) -> None:
        if self.kind not in ATTRIBUTE_KINDS:
            raise ValueError(f"unknown attribute kind {self.kind!r}")
        kind = ATTRIBUTE_KINDS[self.kind]
        if self.value not in kind.values:
            raise ValueError(f"{self.kind} takes one of {kind.values}, got {self.value!r}")
        if (self.color is not None) != (kind.subject == "color"):
            raise ValueError(
                f"{self.kind} {'needs' if kind.subject == 'color' else 'takes no'} color"
            )
        if (self.region is not None) != (kind.subject == "region"):
            raise ValueError(
                f"{self.kind} {'needs' if kind.subject == 'region' else 'takes no'} region"
            )
        if kind.counted and (self.n is None or self.n < 0):
            raise ValueError(f"{self.kind} needs a count >= 0")
        if not kind.counted and self.n is not None:
            raise ValueError(f"{self.kind} takes no count")


@dataclass(frozen=True)
class Not:
    clue: Clue


@dataclass(frozen=True)
class And:
    clues: tuple[Clue, ...]

    def __post_init__(self) -> None:
        if not self.clues:
            raise ValueError("And needs at least one clue")


@dataclass(frozen=True)
class Or:
    clues: tuple[Clue, ...]

    def __post_init__(self) -> None:
        if not self.clues:
            raise ValueError("Or needs at least one clue")


@dataclass(frozen=True)
class Exactly:
    """Exactly `n` of the sub-clues hold."""

    n: int
    clues: tuple[Clue, ...]

    def __post_init__(self) -> None:
        _check_count(self.n, self.clues)


@dataclass(frozen=True)
class AtLeast:
    """At least `n` of the sub-clues hold. `n` is at least 1; "at least zero" says nothing."""

    n: int
    clues: tuple[Clue, ...]

    def __post_init__(self) -> None:
        _check_count(self.n, self.clues)
        if self.n == 0:
            raise ValueError("AtLeast(0, ...) is always true; use n >= 1")


def _check_count(n: int, clues: tuple[Clue, ...]) -> None:
    if not clues:
        raise ValueError("a counting clue needs at least one sub-clue")
    if not 0 <= n <= len(clues):
        raise ValueError(f"cannot count {n} of {len(clues)} clues")


Clue = Relation | Property | AttributeClue | BoardRule | Not | And | Or | Exactly | AtLeast
"""Any clue."""


# --------------------------------------------------------------------------- factories


def relation(kind: str, *colors: ColorRef | str) -> Relation:
    """`relation("next_to", "black", "M")`: strings are coerced with `ref`."""
    return Relation(kind, tuple(ref(color) for color in colors))


def prop(kind: str, color: ColorRef | str, index: int | None = None) -> Property:
    """`prop("in_row", "black", 0)`: the string is coerced with `ref`."""
    return Property(kind, ref(color), index)


def attribute(
    kind: str,
    value: str,
    *,
    color: ColorRef | str | None = None,
    region: Region | None = None,
    n: int | None = None,
) -> AttributeClue:
    """`attribute("neighbours_all", "cool", color="mint")`: a string color is coerced with `ref`."""
    return AttributeClue(kind, value, None if color is None else ref(color), region, n)


def regions(board: Board) -> tuple[Region, ...]:
    """Every region of the board: corners, edge, center (if any), each row and column."""
    found = [Region("corners"), Region("edge")]
    if any(board.is_center(cell) for cell in board):
        found.append(Region("center"))
    found += [Region("row", i) for i in range(board.rows)]
    found += [Region("column", i) for i in range(board.cols)]
    return tuple(found)


def attribute_clues(board: Board, palette: Palette) -> tuple[AttributeClue, ...]:
    """Every attribute clue that names palette colors by id and fits the board.

    Values no palette color has are left out, since a clue about them says nothing a
    player could use. Counts run from zero to the region's size. On a full board,
    `region_all(value, region)` holds exactly when `region_count(value, region, n=size)`
    does, so a generator can skip one of each such pair. This is the list a
    puzzle generator draws attribute clues from, so a new kind in `ATTRIBUTE_KINDS` shows
    up here without changes.
    """
    found: list[AttributeClue] = []
    for name, kind in ATTRIBUTE_KINDS.items():
        values = [v for v in kind.values if any(color.has(v) for color in palette)]
        if kind.subject == "color":
            for color, value in product(palette, values):
                found.append(AttributeClue(name, value, color=ColorRef(color.id)))
            continue
        for region, value in product(regions(board), values):
            counts: list[int | None] = (
                list(range(len(region.cells(board)) + 1)) if kind.counted else [None]
            )
            for n in counts:
                found.append(AttributeClue(name, value, region=region, n=n))
    return tuple(found)
