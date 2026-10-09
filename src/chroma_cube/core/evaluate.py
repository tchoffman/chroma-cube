"""Three-valued evaluation of clues on a possibly partial placement."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from enum import Enum
from itertools import product

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


class Truth(Enum):
    """What a clue says about a placement: decided either way, or not yet."""

    SATISFIED = "satisfied"
    VIOLATED = "violated"
    UNKNOWN = "unknown"


SAT, VIOL, UNK = Truth.SATISFIED, Truth.VIOLATED, Truth.UNKNOWN


def evaluate(clue: Clue, placement: Placement, board: Board, palette: Palette) -> Truth:
    """Decide `clue` on `placement`, as early as the placed cubes allow.

    Relations and properties are exact: they are UNKNOWN only if some way of putting the
    clue's unplaced colors on free cells makes them true and another makes them false.
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
        case BoardRule(kind=kind):
            return _alphabetical(BOARD_RULE_KINDS[kind][0], placement, board, palette)
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


# --------------------------------------------------------------------------- board rules


def _alphabetical(lines: str, placement: Placement, board: Board, palette: Palette) -> Truth:
    """Every row (left to right) or column (top to bottom) is in alphabetical name order.

    VIOLATED as soon as a line's placed cubes are out of order, or a run of free cells
    in a line cannot be filled because too few unplaced colors sort between its ends.
    SATISFIED once every line is full and in order. The lines are checked one at a time,
    so a board whose lines compete for the same few colors can stay UNKNOWN.
    """
    cells_of = board.row if lines == "row" else board.column
    count = board.rows if lines == "row" else board.cols
    unplaced = sorted(_key(color) for color in placement.unplaced(palette))
    full = True
    for index in range(count):
        names: list[str | None] = [
            None if (color := placement.color_at(cell)) is None else _key(color)
            for cell in cells_of(index)
        ]
        if None in names:
            full = False
        if not _line_can_be_ordered(names, unplaced):
            return VIOL
    return SAT if full else UNK


def _key(color: Color) -> str:
    return color.name.casefold()


def _line_can_be_ordered(names: list[str | None], unplaced: list[str]) -> bool:
    """Placed names ascend, and every run of free cells has enough names to fit in it."""
    low: str | None = None
    gap = 0
    for name in names:
        if name is None:
            gap += 1
            continue
        if low is not None and name <= low:
            return False
        if not _enough_between(low, name, gap, unplaced):
            return False
        low, gap = name, 0
    return _enough_between(low, None, gap, unplaced)


def _enough_between(low: str | None, high: str | None, gap: int, unplaced: list[str]) -> bool:
    fits = [
        name for name in unplaced if (low is None or name > low) and (high is None or name < high)
    ]
    return len(fits) >= gap
