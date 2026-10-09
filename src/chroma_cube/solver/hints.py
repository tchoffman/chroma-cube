"""Hints: the next move a player can be sure of, and which clues make it sure.

`next_hint` tries, in order:

1. a cube the player put in the wrong place (it breaks a clue, or the card has one
   solution and that solution has the cube elsewhere);
2. a cube with only one free cell left where no clue breaks ("only cell");
3. a free cell that only one cube left can take ("only color");
4. on a card with one solution, a cube straight from that solution, choosing the one that
   settles the most clues.

Steps 2 and 3 look one cube ahead with the same three-valued evaluation the clue list
shows, so every hint can be explained by naming clues the player can already see.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum

from chroma_cube.core.board import Cell
from chroma_cube.core.colors import Color
from chroma_cube.core.evaluate import Truth, evaluate
from chroma_cube.core.placement import Placement
from chroma_cube.core.puzzle import Puzzle
from chroma_cube.core.render import cell_name
from chroma_cube.solver.search import _colors_in, solve

__all__ = ["Hint", "HintReason", "explain", "next_hint"]


class HintReason(Enum):
    """Why a hint is sure."""

    MISPLACED = "misplaced"
    """The cube on `cell` is in the wrong place and should go back."""
    ONLY_CELL = "only cell"
    """`cell` is the only place left for the color."""
    ONLY_COLOR = "only color"
    """The color is the only cube left that fits `cell`."""
    REVEAL = "reveal"
    """Nothing is forced; the move comes from the card's solution."""


@dataclass(frozen=True)
class Hint:
    """One suggested move: put `color` on `cell`, or for MISPLACED take it off `cell`.

    `clues` are indices into the puzzle's clues, in order: the ones that force the move,
    the ones a misplaced cube breaks, or the ones a revealed cube settles.
    """

    color: Color
    cell: Cell
    reason: HintReason
    clues: tuple[int, ...] = ()


def next_hint(puzzle: Puzzle, placement: Placement) -> Hint | None:
    """The most useful sure move from `placement`, or None if there is none to give.

    None means the tray is complete, or the card has several solutions and no move is
    forced yet.
    """
    hinter = _Hinter(puzzle, placement)
    return hinter.misplaced() or hinter.only_cell() or hinter.only_color() or hinter.reveal()


def explain(hint: Hint, puzzle: Puzzle) -> str:
    """The hint as one English sentence, quoting the clues involved."""
    name = hint.color.name
    where = cell_name(hint.cell, puzzle.board)
    quoted = _quote(puzzle, hint.clues)
    match hint.reason:
        case HintReason.MISPLACED:
            why = f"it breaks {quoted}" if hint.clues else "the solution has it elsewhere"
            return f"{name} does not belong in {where}: {why}"
        case HintReason.ONLY_CELL:
            if not hint.clues:
                return f"{name} must go in {where}: it is the only free cell left"
            return (
                f"{name} must go in {where}: it is the only cell left where {quoted} can still hold"
            )
        case HintReason.ONLY_COLOR:
            if not hint.clues:
                return f"Only {name} can go in {where}: it is the only cube left"
            return f"Only {name} can go in {where}: any other cube left there would break {quoted}"
        case HintReason.REVEAL:
            settles = f", and it settles {quoted}" if hint.clues else ""
            return (
                f"{name} goes in {where}: nothing is forced yet, so this comes from the "
                f"solution{settles}"
            )
    raise ValueError(f"unknown hint reason {hint.reason!r}")


# --------------------------------------------------------------------------- search


class _Hinter:
    def __init__(self, puzzle: Puzzle, placement: Placement) -> None:
        self.puzzle = puzzle
        self.placement = placement
        self.free = tuple(cell for cell in puzzle.board if placement.color_at(cell) is None)
        self.unplaced = placement.unplaced(puzzle.palette)
        self._solution: Placement | None = None
        self._solved = False
        self._breaks: dict[tuple[Color, Cell], tuple[int, ...]] = {}
        self._violated_now = self._violated(placement)
        self._named = [_colors_in(clue, puzzle.palette) for clue in puzzle.clues]

    # ------------------------------------------------------------------ levels

    def misplaced(self) -> Hint | None:
        movable = [
            (color, cell)
            for color, cell in self.placement.assignments.items()
            if self.puzzle.givens.cell_of(color) is None
        ]
        movable.sort(key=lambda item: self._order(item[0]))
        violated = self._violated_now
        if violated:
            for color, cell in movable:
                fixed = violated - self._violated(self.placement.without(color))
                if fixed:
                    return Hint(color, cell, HintReason.MISPLACED, tuple(sorted(fixed)))
        solution = self.solution()
        if solution is not None:
            for color, cell in movable:
                if solution.cell_of(color) != cell:
                    return Hint(color, cell, HintReason.MISPLACED)
        return None

    def only_cell(self) -> Hint | None:
        found = []
        for color in self.unplaced:
            open_cells = [cell for cell in self.free if not self.breaks(color, cell)]
            if len(open_cells) == 1:
                ruled_out = self._union(self.breaks(color, cell) for cell in self.free)
                found.append(Hint(color, open_cells[0], HintReason.ONLY_CELL, ruled_out))
        return self._simplest(found)

    def only_color(self) -> Hint | None:
        found = []
        for cell in self.free:
            fitting = [color for color in self.unplaced if not self.breaks(color, cell)]
            if len(fitting) == 1:
                ruled_out = self._union(self.breaks(color, cell) for color in self.unplaced)
                found.append(Hint(fitting[0], cell, HintReason.ONLY_COLOR, ruled_out))
        return self._simplest(found)

    def reveal(self) -> Hint | None:
        solution = self.solution()
        if solution is None or not self.unplaced:
            return None
        open_now = self._open(self.placement)
        best: Hint | None = None
        for color in self.unplaced:
            cell = solution.cell_of(color)
            if cell is None or self.placement.color_at(cell) is not None:
                continue
            settled = tuple(sorted(open_now - self._open(self.placement.with_color(color, cell))))
            if best is None or len(settled) > len(best.clues):
                best = Hint(color, cell, HintReason.REVEAL, settled)
        return best

    # ------------------------------------------------------------------ helpers

    def solution(self) -> Placement | None:
        """The card's solution when it has exactly one, else None."""
        if not self._solved:
            result = solve(self.puzzle, limit=1)
            if result.count == 1 and not result.truncated:
                self._solution = result.solutions[0]
            self._solved = True
        return self._solution

    def breaks(self, color: Color, cell: Cell) -> tuple[int, ...]:
        """The clues that putting `color` on `cell` would newly violate."""
        key = (color, cell)
        if key not in self._breaks:
            trial = self.placement.with_color(color, cell)
            self._breaks[key] = tuple(sorted(self._violated(trial) - self._violated_now))
        return self._breaks[key]

    def _violated(self, placement: Placement) -> set[int]:
        return self._with_truth(placement, Truth.VIOLATED)

    def _open(self, placement: Placement) -> set[int]:
        return self._with_truth(placement, Truth.UNKNOWN)

    def _with_truth(self, placement: Placement, truth: Truth) -> set[int]:
        puzzle = self.puzzle
        return {
            index
            for index, clue in enumerate(puzzle.clues)
            if evaluate(clue, placement, puzzle.board, puzzle.palette) is truth
        }

    def _order(self, color: Color) -> int:
        return self.puzzle.palette.colors.index(color)

    def _simplest(self, hints: list[Hint]) -> Hint | None:
        """The hint a player is likeliest to see for themselves.

        First the one whose clues all name its color (a clue about Teal placing Teal beats
        the same clue crowding Mint out), then the one leaning on the fewest clues, then
        palette order.
        """
        if not hints:
            return None
        return min(
            hints,
            key=lambda hint: (
                sum(hint.color not in self._named[index] for index in hint.clues),
                len(hint.clues),
                self._order(hint.color),
            ),
        )

    @staticmethod
    def _union(groups: Iterable[tuple[int, ...]]) -> tuple[int, ...]:
        return tuple(sorted(set().union(*groups)))


def _quote(puzzle: Puzzle, indices: tuple[int, ...]) -> str:
    sentences = puzzle.rendered_clues()
    quoted = [f"'{sentences[index]}'" for index in indices]
    if len(quoted) <= 1:
        return "".join(quoted)
    return ", ".join(quoted[:-1]) + " and " + quoted[-1]
