"""Three-valued evaluation of clues on a possibly partial placement."""

from __future__ import annotations

from collections.abc import Callable, Iterable
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


def _attribute(clue: AttributeClue, placement: Placement, board: Board, palette: Palette) -> Truth:
    """Count matching cubes next to the clue's color or in its region, over every completion.

    A region is decided directly. A color clue tries its color on every free cell when it
    is not placed yet; initials try each matching color and combine with Kleene "or".
    """
    kind = ATTRIBUTE_KINDS[clue.kind]

    def decide(cells: tuple[Cell, ...], trial: Placement) -> tuple[bool, bool]:
        free_cells = sum(1 for cell in board if trial.color_at(cell) is None)
        return _counts(
            cells, trial, palette, free_cells, clue.value, lambda m, o: kind.holds(m, o, clue.n)
        )

    if clue.region is not None:
        return _truth(*decide(clue.region.cells(board), placement))
    assert clue.color is not None
    free = [cell for cell in board if placement.color_at(cell) is None]
    truths = []
    for color in _candidates(clue.color, palette):
        placed = placement.cell_of(color)
        seen_true = seen_false = False
        for spot in (placed,) if placed is not None else tuple(free):
            trial = placement if placed is not None else placement.with_color(color, spot)
            can_true, can_false = decide(board.orthogonal_neighbours(spot), trial)
            seen_true, seen_false = seen_true or can_true, seen_false or can_false
        truths.append(_truth(seen_true, seen_false))
    return _any(truths)


def _counts(
    cells: tuple[Cell, ...],
    placement: Placement,
    palette: Palette,
    free_cells: int,
    value: str,
    holds: Callable[[int, int], bool],
) -> tuple[bool, bool]:
    """Whether some completion makes `holds(matching, others)` true over `cells`, and
    whether some makes it false.

    Placed cubes in the cells are counted as they are. Each unplaced color lands on one
    free cell, so what can vary is how many matching (`a`) and other (`b`) unplaced colors
    land in the empty cells here; any split is possible as long as the rest fit elsewhere.
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
    unplaced = placement.unplaced(palette)
    free_matching = sum(1 for color in unplaced if color.has(value))
    free_others = len(unplaced) - free_matching
    elsewhere = free_cells - empty
    can_true = can_false = False
    for a in range(min(free_matching, empty) + 1):
        for b in range(min(free_others, empty - a) + 1):
            if (free_matching - a) + (free_others - b) > elsewhere:
                continue
            if holds(matching + a, others + b):
                can_true = True
            else:
                can_false = True
    return can_true, can_false


def _truth(can_true: bool, can_false: bool) -> Truth:
    if can_true and can_false:
        return UNK
    return SAT if can_true else VIOL
