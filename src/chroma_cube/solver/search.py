"""Backtracking search with forward checking, pruned by three-valued clue evaluation.

The search keeps, for every unplaced color, the cells it could still go on. A cell stays
a candidate only while putting the color there leaves every clue that mentions the color
not VIOLATED. Each step places the color with the fewest candidates (most constrained
first) and narrows everyone else's candidates. A color with no candidates left ends the
branch.

This is sound because VIOLATED from the evaluator always means no completion can satisfy
the clue, so a cell ruled out on a partial board stays ruled out below it.

Before searching, the clues are simplified (see `simplify`) so a clue that contradicts
another is caught up front. The search also has a budget: it counts every trial
placement of a color on a cell, and gives up once the count passes `max_nodes`.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass

from chroma_cube.core.board import Board, Cell
from chroma_cube.core.clues import (
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
from chroma_cube.core.evaluate import Truth, evaluate
from chroma_cube.core.placement import Placement
from chroma_cube.core.puzzle import Puzzle
from chroma_cube.solver.simplify import simplify

DEFAULT_MAX_NODES = 200_000
"""The default search budget: trial placements before the search gives up."""


class SearchBudgetExceeded(Exception):
    """The search ran out of budget before it could answer the question asked."""


@dataclass(frozen=True)
class SolveResult:
    """What a search found.

    `solutions` holds up to `limit` complete placements, `count` is how many that is,
    and `truncated` is True when the puzzle has more solutions than `limit`. `gave_up`
    is True when the budget ran out first: the solutions found are real, but there may
    be others, so `count` is a lower bound and `truncated` is False.
    """

    solutions: tuple[Placement, ...]
    truncated: bool
    gave_up: bool = False

    @property
    def count(self) -> int:
        return len(self.solutions)


def solve(
    puzzle: Puzzle, *, limit: int = 1, max_nodes: int | None = DEFAULT_MAX_NODES
) -> SolveResult:
    """Find up to `limit` solutions of `puzzle`, and whether there are more.

    `max_nodes` caps the trial placements the search may make (None for no cap).
    """
    return solve_clues(
        puzzle.board,
        puzzle.palette,
        puzzle.clues,
        givens=puzzle.givens,
        limit=limit,
        max_nodes=max_nodes,
    )


def solve_clues(
    board: Board,
    palette: Palette,
    clues: Sequence[Clue],
    *,
    givens: Placement | None = None,
    limit: int = 1,
    max_nodes: int | None = DEFAULT_MAX_NODES,
) -> SolveResult:
    """`solve` for a board, palette, givens and clues that are not wrapped in a `Puzzle`.

    Every palette color must be placed, so the palette must have one color per cell.
    Raises `ValueError` if it does not, if a given is off the board or not in the
    palette, or if `limit` or `max_nodes` is below 1.
    """
    if limit < 1:
        raise ValueError(f"limit must be at least 1, got {limit}")
    if max_nodes is not None and max_nodes < 1:
        raise ValueError(f"max_nodes must be at least 1, got {max_nodes}")
    givens = givens or Placement()
    for color, cell in givens.assignments.items():
        if color not in palette:
            raise ValueError(f"given {color.name} is not in the palette")
        if cell not in board:
            raise ValueError(f"given {color.name} is on {cell}, off the board")
    if len(palette) != len(board):
        raise ValueError(
            f"a {board.rows}x{board.cols} board needs {len(board)} colors, "
            f"the palette has {len(palette)}"
        )
    found: list[Placement] = []
    simplified = simplify(clues)
    if simplified is None:
        return SolveResult((), truncated=False)
    search = _Search(board, palette, simplified, max_nodes)
    try:
        for solution in search.run(givens):
            if len(found) == limit:
                return SolveResult(tuple(found), truncated=True)
            found.append(solution)
    except _OutOfBudget:
        return SolveResult(tuple(found), truncated=False, gave_up=True)
    return SolveResult(tuple(found), truncated=False)


# The helpers below answer yes/no questions, so they raise `SearchBudgetExceeded` when the
# budget runs out before the answer is known, rather than guess.


def first_solution(
    puzzle: Puzzle, *, max_nodes: int | None = DEFAULT_MAX_NODES
) -> Placement | None:
    """One solution, or None if the puzzle has none."""
    result = solve(puzzle, limit=1, max_nodes=max_nodes)
    if result.solutions:
        return result.solutions[0]
    _check_finished(result)
    return None


def is_solvable(puzzle: Puzzle, *, max_nodes: int | None = DEFAULT_MAX_NODES) -> bool:
    return first_solution(puzzle, max_nodes=max_nodes) is not None


def is_unique(puzzle: Puzzle, *, max_nodes: int | None = DEFAULT_MAX_NODES) -> bool:
    """Exactly one solution."""
    result = solve(puzzle, limit=1, max_nodes=max_nodes)
    _check_finished(result)
    return result.count == 1 and not result.truncated


def count_solutions(puzzle: Puzzle, cap: int, *, max_nodes: int | None = DEFAULT_MAX_NODES) -> int:
    """How many solutions there are, counting no further than `cap`.

    A return of `cap` means "at least `cap`"; use `solve(...).truncated` to tell
    "exactly `cap`" from "more than `cap`".
    """
    result = solve(puzzle, limit=cap, max_nodes=max_nodes)
    _check_finished(result)
    return result.count


def _check_finished(result: SolveResult) -> None:
    if result.gave_up:
        raise SearchBudgetExceeded(f"the search gave up after finding {result.count} solution(s)")


# --------------------------------------------------------------------------- search

Candidates = Mapping[Color, tuple[Cell, ...]]


class _OutOfBudget(Exception):
    pass


class _Search:
    def __init__(
        self, board: Board, palette: Palette, clues: tuple[Clue, ...], max_nodes: int | None
    ) -> None:
        self.board = board
        self.palette = palette
        self.clues = clues
        self.budget = max_nodes
        mentions: dict[Color, list[Clue]] = {color: [] for color in palette}
        for clue in clues:
            for color in _colors_in(clue, palette):
                mentions[color].append(clue)
        self.mentions = {color: tuple(found) for color, found in mentions.items()}

    def run(self, givens: Placement) -> Iterator[Placement]:
        if any(self._evaluate(clue, givens) is Truth.VIOLATED for clue in self.clues):
            return
        free = tuple(cell for cell in self.board if givens.color_at(cell) is None)
        candidates = self._narrow(givens, {c: free for c in givens.unplaced(self.palette)})
        if candidates is not None:
            yield from self._extend(givens, candidates)

    def _extend(self, placement: Placement, candidates: Candidates) -> Iterator[Placement]:
        if not candidates:
            if all(self._evaluate(clue, placement) is Truth.SATISFIED for clue in self.clues):
                yield placement
            return
        color = min(candidates, key=lambda c: len(candidates[c]))
        rest = {c: cells for c, cells in candidates.items() if c != color}
        for cell in candidates[color]:
            child = placement.with_color(color, cell)
            narrowed = self._narrow(child, rest)
            if narrowed is not None:
                yield from self._extend(child, narrowed)

    def _narrow(
        self, placement: Placement, candidates: Candidates
    ) -> dict[Color, tuple[Cell, ...]] | None:
        """Each color's candidates that are still free and break no clue; None on a dead end."""
        narrowed: dict[Color, tuple[Cell, ...]] = {}
        for color, cells in candidates.items():
            kept = tuple(
                cell
                for cell in cells
                if placement.color_at(cell) is None and self._allows(placement, color, cell)
            )
            if not kept:
                return None
            narrowed[color] = kept
        return narrowed

    def _allows(self, placement: Placement, color: Color, cell: Cell) -> bool:
        if self.budget is not None:
            if self.budget == 0:
                raise _OutOfBudget
            self.budget -= 1
        trial = placement.with_color(color, cell)
        return all(
            self._evaluate(clue, trial) is not Truth.VIOLATED for clue in self.mentions[color]
        )

    def _evaluate(self, clue: Clue, placement: Placement) -> Truth:
        return evaluate(clue, placement, self.board, self.palette)


def _colors_in(clue: Clue, palette: Palette) -> set[Color]:
    """Every palette color the clue could be about; a board rule is about all of them."""
    match clue:
        case Relation(colors=refs):
            return _resolve(refs, palette)
        case Property(color=color_ref):
            return _resolve((color_ref,), palette)
        case BoardRule():
            return set(palette)
        case Not(clue=inner):
            return _colors_in(inner, palette)
        case And(clues=subs) | Or(clues=subs) | Exactly(clues=subs) | AtLeast(clues=subs):
            return set().union(*(_colors_in(sub, palette) for sub in subs))
    raise TypeError(f"not a clue: {clue!r}")


def _resolve(refs: Iterable[ColorRef], palette: Palette) -> set[Color]:
    colors: set[Color] = set()
    for color_ref in refs:
        if color_ref.by_initial:
            colors.update(palette.by_initial(color_ref.key))
        else:
            colors.add(palette.by_id(color_ref.key))
    return colors
