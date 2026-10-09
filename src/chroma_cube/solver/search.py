"""Backtracking search with forward checking, pruned by three-valued clue evaluation.

The search keeps, for every unplaced color, the cells it could still go on. A cell stays
a candidate only while putting the color there leaves every clue that mentions the color
not VIOLATED. Each step places the color with the fewest candidates (most constrained
first) and narrows everyone else's candidates. A color with no candidates left ends the
branch.

This is sound because VIOLATED from the evaluator always means no completion can satisfy
the clue, so a cell ruled out on a partial board stays ruled out below it.
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


@dataclass(frozen=True)
class SolveResult:
    """What a search found.

    `solutions` holds up to `limit` complete placements, `count` is how many that is,
    and `truncated` is True when the puzzle has more solutions than `limit`.
    """

    solutions: tuple[Placement, ...]
    truncated: bool

    @property
    def count(self) -> int:
        return len(self.solutions)


def solve(puzzle: Puzzle, *, limit: int = 1) -> SolveResult:
    """Find up to `limit` solutions of `puzzle`, and whether there are more."""
    return solve_clues(
        puzzle.board, puzzle.palette, puzzle.clues, givens=puzzle.givens, limit=limit
    )


def solve_clues(
    board: Board,
    palette: Palette,
    clues: Sequence[Clue],
    *,
    givens: Placement | None = None,
    limit: int = 1,
) -> SolveResult:
    """`solve` for a board, palette, givens and clues that are not wrapped in a `Puzzle`.

    Every palette color must be placed, so the palette must have one color per cell.
    Raises `ValueError` if it does not, or if `limit` is below 1.
    """
    if limit < 1:
        raise ValueError(f"limit must be at least 1, got {limit}")
    if len(palette) != len(board):
        raise ValueError(
            f"a {board.rows}x{board.cols} board needs {len(board)} colors, "
            f"the palette has {len(palette)}"
        )
    found: list[Placement] = []
    for solution in _Search(board, palette, tuple(clues)).run(givens or Placement()):
        if len(found) == limit:
            return SolveResult(tuple(found), truncated=True)
        found.append(solution)
    return SolveResult(tuple(found), truncated=False)


def first_solution(puzzle: Puzzle) -> Placement | None:
    """One solution, or None if the puzzle has none."""
    result = solve(puzzle, limit=1)
    return result.solutions[0] if result.solutions else None


def is_solvable(puzzle: Puzzle) -> bool:
    return first_solution(puzzle) is not None


def is_unique(puzzle: Puzzle) -> bool:
    """Exactly one solution."""
    result = solve(puzzle, limit=1)
    return result.count == 1 and not result.truncated


def count_solutions(puzzle: Puzzle, cap: int) -> int:
    """How many solutions there are, counting no further than `cap`.

    A return of `cap` means "at least `cap`"; use `solve(...).truncated` to tell
    "exactly `cap`" from "more than `cap`".
    """
    return solve(puzzle, limit=cap).count


# --------------------------------------------------------------------------- search

Candidates = Mapping[Color, tuple[Cell, ...]]


class _Search:
    def __init__(self, board: Board, palette: Palette, clues: tuple[Clue, ...]) -> None:
        self.board = board
        self.palette = palette
        self.clues = clues
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
