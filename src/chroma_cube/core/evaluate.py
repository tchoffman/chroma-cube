"""Three-valued evaluation of clues on a possibly partial placement."""

from __future__ import annotations

import functools
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from itertools import product

from chroma_cube.core.board import Board, Cell
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
from chroma_cube.core.colors import Color, Palette
from chroma_cube.core.placement import Placement
from chroma_cube.core.truth import Truth

__all__ = ["Truth", "evaluate"]


SAT, VIOL, UNK = Truth.SATISFIED, Truth.VIOLATED, Truth.UNKNOWN


def evaluate(clue: Clue, placement: Placement, board: Board, palette: Palette) -> Truth:
    """Decide `clue` on `placement`, as early as the placed cubes allow.

    Relations, properties and attribute clues are exact: they are UNKNOWN only if some
    way of filling the free cells makes them true and another makes them false.
    Initial-letter references hold if some choice of distinct matching colors holds.
    Combinators use Kleene's three-valued logic over their sub-clues, so a combination
    can stay UNKNOWN even when every completion would decide it the same way.
    """
    match clue:
        case Relation(kind=kind, colors=refs):
            holds = RELATION_KINDS[kind].holds
            return _primitive(refs, lambda cells: holds(cells), placement, board, palette)
        case Property(kind=kind, color=color_ref, index=index):
            prop_holds = PROPERTY_KINDS[kind].holds
            return _primitive(
                (color_ref,),
                lambda cells: prop_holds(board, cells[0], index),
                placement,
                board,
                palette,
            )
        case AttributeClue():
            return _attribute(clue, placement, board, palette)
        case BoardRule(kind=kind):
            return BOARD_RULE_KINDS[kind].evaluate(placement, board, palette)
        case Not(clue=inner):
            return _negate(evaluate(inner, placement, board, palette))
        case And(clues=clues):
            return _all(evaluate(sub, placement, board, palette) for sub in clues)
        case Or(clues=clues):
            return _any(evaluate(sub, placement, board, palette) for sub in clues)
        case Exactly(n=n, clues=clues):
            sat, unk = _count(clues, placement, board, palette)
            if sat > n or sat + unk < n:
                return VIOL
            return SAT if sat == n and unk == 0 else UNK
        case AtLeast(n=n, clues=clues):
            sat, unk = _count(clues, placement, board, palette)
            if sat >= n:
                return SAT
            return VIOL if sat + unk < n else UNK
    raise TypeError(f"not a clue: {clue!r}")


# --------------------------------------------------------------------------- logic


def _negate(truth: Truth) -> Truth:
    return {SAT: VIOL, VIOL: SAT, UNK: UNK}[truth]


def _all(truths: Iterable[Truth]) -> Truth:
    result = SAT
    for truth in truths:
        if truth is VIOL:
            return VIOL
        if truth is UNK:
            result = UNK
    return result


def _any(truths: Iterable[Truth]) -> Truth:
    return _negate(_all(_negate(truth) for truth in truths))


def _count(
    clues: tuple[Clue, ...], placement: Placement, board: Board, palette: Palette
) -> tuple[int, int]:
    """How many sub-clues are satisfied, and how many are still undecided."""
    truths = [evaluate(sub, placement, board, palette) for sub in clues]
    return truths.count(SAT), truths.count(UNK)


# --------------------------------------------------------------------------- primitives


def _candidates(color_ref: ColorRef, palette: Palette) -> tuple[Color, ...]:
    if color_ref.by_initial:
        return palette.by_initial(color_ref.key)
    return (palette.by_id(color_ref.key),)


def _primitive(
    refs: tuple[ColorRef, ...],
    holds: Callable[[tuple[Cell, ...]], bool],
    placement: Placement,
    board: Board,
    palette: Palette,
) -> Truth:
    """Some choice of distinct colors for the references holds (Kleene "or" over choices)."""
    choices = product(*(_candidates(color_ref, palette) for color_ref in refs))
    return _any(
        _decide(colors, holds, placement, board)
        for colors in choices
        if len(set(colors)) == len(colors)
    )


def _decide(
    colors: tuple[Color, ...],
    holds: Callable[[tuple[Cell, ...]], bool],
    placement: Placement,
    board: Board,
) -> Truth:
    """Try every way of putting the unplaced colors on free cells and see if they agree."""
    free = [cell for cell in board if placement.color_at(cell) is None]
    options = [
        (cell,) if (cell := placement.cell_of(color)) is not None else tuple(free)
        for color in colors
    ]
    seen_true = seen_false = False
    for cells in product(*options):
        if len(set(cells)) != len(cells):
            continue
        if holds(cells):
            seen_true = True
        else:
            seen_false = True
        if seen_true and seen_false:
            return UNK
    if seen_true:
        return SAT
    return VIOL


# --------------------------------------------------------------------------- attributes


@dataclass(frozen=True)
class _Pool:
    """What is left to place: how many free cells, and how many unplaced colors have the
    clue's value (`matching`) or not (`others`). Every unplaced color takes one free cell."""

    free: int
    matching: int
    others: int

    def without(self, matches: bool) -> _Pool:
        """The pool once one more color (matching the value or not) has taken a cell."""
        return _Pool(self.free - 1, self.matching - matches, self.others - (not matches))


def _attribute(clue: AttributeClue, placement: Placement, board: Board, palette: Palette) -> Truth:
    """Count matching cubes next to the clue's color or in its region, over every completion.

    Only counts matter, so the unplaced colors are a pool of so many matching and so many
    other colors rather than placements to try. A region is decided from its cells. A
    color clue whose color is not placed yet tries that color on every free cell; initials
    try each matching color and combine with Kleene "or".
    """
    kind = ATTRIBUTE_KINDS[clue.kind]
    value, n = clue.value, clue.n

    def holds(matching: int, others: int) -> bool:
        return kind.holds(matching, others, n)

    unplaced = placement.unplaced(palette)
    matching = sum(1 for color in unplaced if color.has(value))
    free = tuple(cell for cell in board if placement.color_at(cell) is None)
    pool = _Pool(len(free), matching, len(unplaced) - matching)

    if clue.region is not None:
        return _truth(*_split(_region_cells(clue.region, board), placement, pool, value, holds))
    assert clue.color is not None
    truths = []
    for color in _candidates(clue.color, palette):
        cell = placement.cell_of(color)
        if cell is not None:
            cells = _neighbours(board, cell)
            truths.append(_truth(*_split(cells, placement, pool, value, holds)))
            continue
        rest = pool.without(color.has(value))
        seen_true = seen_false = False
        for spot in free:
            can_true, can_false = _split(_neighbours(board, spot), placement, rest, value, holds)
            seen_true, seen_false = seen_true or can_true, seen_false or can_false
            if seen_true and seen_false:
                break
        truths.append(_truth(seen_true, seen_false))
    return _any(truths)


@functools.cache
def _neighbours(board: Board, cell: Cell) -> tuple[Cell, ...]:
    return board.orthogonal_neighbours(cell)


@functools.cache
def _region_cells(region: Region, board: Board) -> tuple[Cell, ...]:
    return region.cells(board)


def _split(
    cells: tuple[Cell, ...],
    placement: Placement,
    pool: _Pool,
    value: str,
    holds: Callable[[int, int], bool],
) -> tuple[bool, bool]:
    """Whether some completion makes `holds(matching, others)` true over `cells`, and
    whether some makes it false.

    Placed cubes in the cells are counted as they are. What can vary is how many matching
    (`a`) and other (`b`) colors from the pool land on the empty cells here. Any split is
    possible as long as the rest of the pool fits on the free cells elsewhere.
    """
    matching = others = empty = 0
    for cell in cells:
        color = placement.color_at(cell)
        if color is None:
            empty += 1
        elif color.has(value):
            matching += 1
        else:
            others += 1
    if pool.matching + pool.others > pool.free:
        return False, False
    must_land = pool.matching + pool.others - (pool.free - empty)
    can_true = can_false = False
    for a in range(min(pool.matching, empty) + 1):
        for b in range(max(0, must_land - a), min(pool.others, empty - a) + 1):
            if holds(matching + a, others + b):
                can_true = True
            else:
                can_false = True
            if can_true and can_false:
                return True, True
    return can_true, can_false


def _truth(can_true: bool, can_false: bool) -> Truth:
    if can_true and can_false:
        return UNK
    return SAT if can_true else VIOL
