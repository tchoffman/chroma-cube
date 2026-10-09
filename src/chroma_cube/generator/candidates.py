"""Clues that are true on a known solution, drawn from the whole clue vocabulary.

The generator starts from a full solution and needs a large, varied pool of clues that
solution satisfies. Everything here is about complete placements, so truth is a plain
yes or no (`holds`), which is much cheaper than the three-valued evaluator.
"""

from __future__ import annotations

import random
from collections.abc import Iterable, Sequence
from itertools import combinations, product
from typing import Literal

from chroma_cube.core.board import Board, Cell
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
from chroma_cube.core.colors import Color, Palette
from chroma_cube.core.placement import Placement
from chroma_cube.core.truth import Truth

Order = Literal["rows", "columns"]

_SYMMETRIC = ("same_row", "same_column", "next_to", "knows", "diagonal")
_MIRRORED = (
    ("above", "below"),
    ("left_of", "right_of"),
    ("directly_above", "directly_below"),
    ("directly_left_of", "directly_right_of"),
)
_NEGATABLE_RELATIONS = ("same_row", "same_column", "next_to", "knows")
_GROUPABLE = ("knows", "next_to")

_OR_SAMPLES = 40
_NOT_RELATION_SAMPLES = 30
_INITIAL_SAMPLES = 40
_COUNT_SAMPLES = 25
_BETWEEN_FALSE_SAMPLES = 20


def random_solution(
    rng: random.Random, board: Board, palette: Palette, order: Order | None = None
) -> Placement:
    """A random full placement. With `order`, every row (or column) reads alphabetically."""
    colors = list(palette)
    rng.shuffle(colors)
    if order is None:
        return Placement(dict(zip(colors, board, strict=True)))
    lines = (
        [board.row(i) for i in range(board.rows)]
        if order == "rows"
        else [board.column(i) for i in range(board.cols)]
    )
    assignments: dict[Color, Cell] = {}
    start = 0
    for line in lines:
        chunk = sorted(colors[start : start + len(line)], key=lambda c: c.name.casefold())
        assignments.update(zip(chunk, line, strict=True))
        start += len(line)
    return Placement(assignments)


# --------------------------------------------------------------------------- truth


def holds(clue: Clue, placement: Placement, board: Board, palette: Palette) -> bool:
    """Whether `clue` is true on a complete `placement`."""
    match clue:
        case Relation(kind=kind, colors=refs):
            test = RELATION_KINDS[kind].holds
            return any(test(cells) for cells in _choices(refs, placement, palette))
        case Property(kind=kind, color=color_ref, index=index):
            prop_test = PROPERTY_KINDS[kind].holds
            return any(
                prop_test(board, cells[0], index)
                for cells in _choices((color_ref,), placement, palette)
            )
        case BoardRule(kind=kind):
            return BOARD_RULE_KINDS[kind].evaluate(placement, board, palette) is Truth.SATISFIED
        case Not(clue=inner):
            return not holds(inner, placement, board, palette)
        case And(clues=subs):
            return all(holds(sub, placement, board, palette) for sub in subs)
        case Or(clues=subs):
            return any(holds(sub, placement, board, palette) for sub in subs)
        case Exactly(n=n, clues=subs):
            return sum(holds(sub, placement, board, palette) for sub in subs) == n
        case AtLeast(n=n, clues=subs):
            return sum(holds(sub, placement, board, palette) for sub in subs) >= n
    raise TypeError(f"not a clue: {clue!r}")


def _choices(
    refs: tuple[ColorRef, ...], placement: Placement, palette: Palette
) -> Iterable[tuple[Cell, ...]]:
    """The cells of every choice of distinct colors the references can stand for."""
    options = [palette.by_initial(r.key) if r.by_initial else (palette.by_id(r.key),) for r in refs]
    for colors in product(*options):
        if len(set(colors)) != len(colors):
            continue
        cells = tuple(placement.cell_of(color) for color in colors)
        if all(cell is not None for cell in cells):
            yield tuple(cell for cell in cells if cell is not None)


# --------------------------------------------------------------------------- features


def clue_features(clue: Clue) -> frozenset[str]:
    """Every kind and combinator a clue uses, plus "initial" if it names a color by letter."""
    match clue:
        case Relation(kind=kind, colors=refs):
            return frozenset({kind}) | _initial(refs)
        case Property(kind=kind, color=color_ref):
            return frozenset({kind}) | _initial((color_ref,))
        case BoardRule(kind=kind):
            return frozenset({kind})
        case Not(clue=inner):
            return frozenset({"not"}) | clue_features(inner)
        case And(clues=subs):
            return _combined("and", subs)
        case Or(clues=subs):
            return _combined("or", subs)
        case Exactly(clues=subs):
            return _combined("exactly", subs)
        case AtLeast(clues=subs):
            return _combined("at_least", subs)
    raise TypeError(f"not a clue: {clue!r}")


def _initial(refs: Iterable[ColorRef]) -> frozenset[str]:
    return frozenset({"initial"}) if any(r.by_initial for r in refs) else frozenset()


def _combined(name: str, subs: Iterable[Clue]) -> frozenset[str]:
    return frozenset({name}).union(*(clue_features(sub) for sub in subs))


# --------------------------------------------------------------------------- pool


def candidate_pool(
    rng: random.Random,
    solution: Placement,
    board: Board,
    palette: Palette,
    features: frozenset[str],
) -> list[Clue]:
    """Clues true on `solution` that use only `features`, without duplicates.

    Positional relations and properties come first, then negations of false ones,
    either/or clues joining one true and one false clue, initial-letter versions,
    counting clues, grouped relations ("Black knows White and Teal") and board rules
    that happen to hold.
    """
    return _PoolBuilder(rng, solution, board, palette, features).build()


class _PoolBuilder:
    def __init__(
        self,
        rng: random.Random,
        solution: Placement,
        board: Board,
        palette: Palette,
        features: frozenset[str],
    ) -> None:
        self.rng = rng
        self.solution = solution
        self.board = board
        self.palette = palette
        self.features = features
        self.true_leaves: list[Clue] = []
        self.false_leaves: list[Clue] = []

    def build(self) -> list[Clue]:
        self.relations()
        self.properties()
        pool: list[Clue] = list(self.true_leaves)
        pool += self.negations()
        pool += self.either_ors()
        pool += self.initials()
        pool += self.counts()
        pool += self.groups()
        pool += [
            BoardRule(kind)
            for kind in BOARD_RULE_KINDS
            if kind in self.features and self.holds(BoardRule(kind))
        ]
        unique = list(dict.fromkeys(pool))
        return [clue for clue in unique if clue_features(clue) <= self.features]

    def holds(self, clue: Clue) -> bool:
        return holds(clue, self.solution, self.board, self.palette)

    def allowed(self, *kinds: str) -> list[str]:
        return [kind for kind in kinds if kind in self.features]

    def leaf(self, clue: Clue) -> None:
        (self.true_leaves if self.holds(clue) else self.false_leaves).append(clue)

    def relations(self) -> None:
        colors = list(self.palette)
        for a, b in combinations(colors, 2):
            for kind in self.allowed(*_SYMMETRIC):
                first, second = (a, b) if self.rng.random() < 0.5 else (b, a)
                self.leaf(Relation(kind, (ColorRef(first.id), ColorRef(second.id))))
            for forward, backward in _MIRRORED:
                kinds = self.allowed(forward, backward)
                if not kinds:
                    continue
                for x, y in ((a, b), (b, a)):
                    clue = Relation(forward, (ColorRef(x.id), ColorRef(y.id)))
                    if self.holds(clue):
                        kind = self.rng.choice(kinds)
                        pair = (x, y) if kind == forward else (y, x)
                        self.true_leaves.append(
                            Relation(kind, (ColorRef(pair[0].id), ColorRef(pair[1].id)))
                        )
        if "between" in self.features:
            false_between: list[Clue] = []
            for middle in colors:
                for b, c in combinations([c for c in colors if c != middle], 2):
                    ends = (b, c) if self.rng.random() < 0.5 else (c, b)
                    clue = Relation(
                        "between", (ColorRef(middle.id), ColorRef(ends[0].id), ColorRef(ends[1].id))
                    )
                    (self.true_leaves if self.holds(clue) else false_between).append(clue)
            self.false_leaves += _sample(self.rng, false_between, _BETWEEN_FALSE_SAMPLES)

    def properties(self) -> None:
        for color in self.palette:
            target = ColorRef(color.id)
            for kind in self.allowed("in_corner", "on_edge", "in_center"):
                self.leaf(Property(kind, target))
            if "in_row" in self.features:
                for row in range(self.board.rows):
                    self.leaf(Property("in_row", target, row))
            if "in_col" in self.features:
                for col in range(self.board.cols):
                    self.leaf(Property("in_col", target, col))

    def negations(self) -> list[Clue]:
        if "not" not in self.features:
            return []
        props = [Not(c) for c in self.false_leaves if isinstance(c, Property)]
        relations = [
            Not(c)
            for c in self.false_leaves
            if isinstance(c, Relation) and c.kind in _NEGATABLE_RELATIONS
        ]
        return props + _sample(self.rng, relations, _NOT_RELATION_SAMPLES)

    def either_ors(self) -> list[Clue]:
        if "or" not in self.features or not self.true_leaves or not self.false_leaves:
            return []
        found: list[Clue] = []
        for _ in range(_OR_SAMPLES):
            pair = [self.rng.choice(self.true_leaves), self.rng.choice(self.false_leaves)]
            self.rng.shuffle(pair)
            found.append(Or(tuple(pair)))
        return found

    def initials(self) -> list[Clue]:
        if "initial" not in self.features:
            return []
        shared = {
            color.id: color.initial
            for color in self.palette
            if len(self.palette.by_initial(color.initial)) >= 2
        }
        found: list[Clue] = []
        sources: list[Clue] = [c for c in self.true_leaves if isinstance(c, Relation | Property)]
        negatable: list[Clue] = [Not(c) for c in self.false_leaves if isinstance(c, Property)]
        for clue in _sample(self.rng, sources + negatable, 4 * _INITIAL_SAMPLES):
            swapped = _with_initial(self.rng, clue, shared)
            if swapped is not None and self.holds(swapped):
                found.append(swapped)
        return found[:_INITIAL_SAMPLES]

    def counts(self) -> list[Clue]:
        kinds = self.allowed("exactly", "at_least")
        if not kinds or len(self.true_leaves) < 2 or len(self.false_leaves) < 2:
            return []
        found: list[Clue] = []
        for _ in range(_COUNT_SAMPLES):
            true_count = self.rng.choice((1, 2))
            subs = self.rng.sample(self.true_leaves, true_count) + self.rng.sample(
                self.false_leaves, 3 - true_count
            )
            self.rng.shuffle(subs)
            kind = self.rng.choice(kinds)
            if kind == "exactly":
                found.append(Exactly(true_count, tuple(subs)))
            else:
                found.append(AtLeast(true_count, tuple(subs)))
        return found

    def groups(self) -> list[Clue]:
        if "and" not in self.features:
            return []
        found: list[Clue] = []
        for kind in self.allowed(*_GROUPABLE):
            for color in self.palette:
                partners = [
                    other
                    for other in self.palette
                    if other != color
                    and self.holds(Relation(kind, (ColorRef(color.id), ColorRef(other.id))))
                ]
                if len(partners) < 2:
                    continue
                size = self.rng.choice((2, 3)) if len(partners) >= 3 else 2
                chosen = self.rng.sample(partners, size)
                found.append(
                    And(
                        tuple(
                            Relation(kind, (ColorRef(color.id), ColorRef(other.id)))
                            for other in chosen
                        )
                    )
                )
        return found


def _with_initial(rng: random.Random, clue: Clue, shared: dict[str, str]) -> Clue | None:
    """The clue with one color whose initial is shared swapped for that initial."""
    match clue:
        case Relation(kind=kind, colors=refs):
            spots = [i for i, r in enumerate(refs) if r.key in shared]
            if not spots:
                return None
            i = rng.choice(spots)
            swapped = list(refs)
            swapped[i] = ColorRef.initial(shared[refs[i].key])
            return Relation(kind, tuple(swapped))
        case Property(kind=kind, color=color_ref, index=index):
            if color_ref.key not in shared:
                return None
            return Property(kind, ColorRef.initial(shared[color_ref.key]), index)
        case Not(clue=inner):
            swapped_inner = _with_initial(rng, inner, shared)
            return None if swapped_inner is None else Not(swapped_inner)
    return None


def _sample(rng: random.Random, items: Sequence[Clue], size: int) -> list[Clue]:
    return list(items) if len(items) <= size else rng.sample(list(items), size)
