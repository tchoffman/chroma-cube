"""Backtracking search with forward checking, pruned by three-valued clue evaluation.

The search keeps, for every unplaced color, the cells it could still go on. Attribute
clues about a region or about a color named by id (and their negations) are read as
counts over a group of cells, with each unplaced color limited to its candidates, so they
rule cells out before their group fills up; that reasoning, and probing a color on each
of its cells with it, lives in `counts`. Every other clue is checked by trial: a cell
stays a candidate only while putting the color there leaves every such clue that
mentions the color not VIOLATED. A branch ends when a color has no candidates left or the
colors cannot each have their own cell. Each step tries every cell of the color with the
fewest candidates, or every color of the cell with the fewest, whichever is fewer.

This is sound because VIOLATED from the evaluator always means no completion can satisfy
the clue, so a cell ruled out on a partial board stays ruled out below it, and the count
reasoning only drops cells that no arrangement within the candidates could use. Every
node and every solution is still checked with the evaluator, which stays the definition
of what a clue means.

Colors that no clue can tell apart (not given, not named, same attributes) are searched
in one order only, and each solution found is returned with every swap of them.

Before searching, the clues are simplified (see `simplify`) so a clue that contradicts
another is caught up front. The search also has a budget: it counts every trial
placement of a color on a cell, probes included, and gives up once the count passes
`max_nodes`.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from itertools import permutations, product

from chroma_cube.core.board import Board, Cell
from chroma_cube.core.clues import (
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
from chroma_cube.core.evaluate import Truth, evaluate
from chroma_cube.core.placement import Placement
from chroma_cube.core.puzzle import Puzzle
from chroma_cube.solver.counts import CountPropagator
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
    search = _Search(board, palette, simplified, givens, max_nodes)
    try:
        for solution in search.run():
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
        self,
        board: Board,
        palette: Palette,
        clues: tuple[Clue, ...],
        givens: Placement,
        max_nodes: int | None,
    ) -> None:
        self.board = board
        self.palette = palette
        self.clues = clues
        self.budget = max_nodes
        mentions: dict[Color, list[int]] = {color: [] for color in palette}
        for index, clue in enumerate(clues):
            for color in colors_in(clue, palette):
                mentions[color].append(index)
        self.mentions = {color: tuple(found) for color, found in mentions.items()}
        self.twins = _twins(palette, clues, givens)
        self.counter = CountPropagator(board, palette, clues, self.twins)
        # Trials skip count clues: `_propagate_counts` narrows by them with the candidates
        # in view, and every node and solution is still checked against the evaluator.
        self.counted = self.counter.indices
        self.givens = givens

    def run(self) -> Iterator[Placement]:
        givens = self.givens
        live = self._live(givens, tuple(range(len(self.clues))))
        if live is None:
            return
        free = tuple(cell for cell in self.board if givens.color_at(cell) is None)
        candidates = self._narrow(
            givens, {c: free for c in givens.unplaced(self.palette)}, live, root=True
        )
        if candidates is not None:
            for solution in self._extend(givens, candidates, live):
                yield from _rearrangements(solution, self.twins)

    def _extend(
        self, placement: Placement, candidates: Candidates, live: tuple[int, ...]
    ) -> Iterator[Placement]:
        if not candidates:
            if not live:
                yield placement
            return
        for color, cell in self._branches(candidates):
            child = placement.with_color(color, cell)
            child_live = self._live(child, live)
            if child_live is None:
                continue
            rest = {c: cells for c, cells in candidates.items() if c != color}
            narrowed = self._narrow(child, rest, child_live)
            if narrowed is not None:
                yield from self._extend(child, narrowed, child_live)

    def _branches(self, candidates: Candidates) -> list[tuple[Color, Cell]]:
        """The placements to try next: every cell of the color with the fewest candidates,
        or every color of the cell with the fewest, whichever is shorter. Every cell takes
        exactly one color, so branching on a cell misses no solution."""
        color = min(candidates, key=lambda c: len(candidates[c]))
        holders = _holders(candidates)
        cell = min(holders, key=lambda x: len(holders[x]))
        if len(holders[cell]) < len(candidates[color]):
            return [(holder, cell) for holder in holders[cell]]
        return [(color, spot) for spot in candidates[color]]

    def _live(self, placement: Placement, live: tuple[int, ...]) -> tuple[int, ...] | None:
        """The clues in `live` still undecided on `placement`; None if one is VIOLATED.

        A satisfied clue holds on every completion, so it can never rule anything out
        further down and is not checked again."""
        undecided: list[int] = []
        for index in live:
            truth = self._evaluate(self.clues[index], placement)
            if truth is Truth.VIOLATED:
                return None
            if truth is Truth.UNKNOWN:
                undecided.append(index)
        return tuple(undecided)

    def _narrow(
        self,
        placement: Placement,
        candidates: Candidates,
        live: tuple[int, ...],
        *,
        root: bool = False,
    ) -> dict[Color, tuple[Cell, ...]] | None:
        """Each color's candidates that are still free and break no clue; None on a dead end.

        A dead end is a color with no cell left, or no way to give every color its own
        cell from its candidates (which includes a free cell no color can take).

        The attribute clues' counts then narrow further (see `counts`). At the root every
        color is probed on every cell, since what that rules out holds for the whole
        search; below it only colors with at most half the board's cells left are, as one
        that could still go almost anywhere rarely loses a cell to a probe."""
        alive = set(live)
        narrowed: dict[Color, tuple[Cell, ...]] = {}
        for color, cells in candidates.items():
            checks = tuple(
                self.clues[i] for i in self.mentions[color] if i in alive and i not in self.counted
            )
            kept = tuple(
                cell
                for cell in cells
                if placement.color_at(cell) is None and self._allows(placement, color, cell, checks)
            )
            if not kept:
                return None
            narrowed[color] = kept
        widest = len(self.board) if root else len(self.board) // 2
        if not self.counter.narrow(placement, narrowed, alive, self._charge, widest=widest):
            return None
        if not _has_matching(narrowed):
            return None
        return narrowed

    def _charge(self, trials: int) -> None:
        if self.budget is not None:
            if self.budget < trials:
                raise _OutOfBudget
            self.budget -= trials

    def _allows(
        self, placement: Placement, color: Color, cell: Cell, checks: tuple[Clue, ...]
    ) -> bool:
        if self.budget is not None:
            if self.budget == 0:
                raise _OutOfBudget
            self.budget -= 1
        if not checks:
            return True
        trial = placement.with_color(color, cell)
        return all(self._evaluate(clue, trial) is not Truth.VIOLATED for clue in checks)

    def _evaluate(self, clue: Clue, placement: Placement) -> Truth:
        return evaluate(clue, placement, self.board, self.palette)


def _twins(
    palette: Palette, clues: Sequence[Clue], givens: Placement
) -> tuple[tuple[Color, ...], ...]:
    """Groups of unplaced colors no clue can tell apart: no clue names them (by name or
    initial, and a board rule names every color), and they share every attribute. Swapping
    two of them in a solution gives another solution, so the search only looks for
    solutions that keep each group in palette order across the board, and
    `_rearrangements` adds the others."""
    named = set().union(*(colors_named(clue, palette) for clue in clues))
    groups: dict[tuple[str, str, str], list[Color]] = {}
    for color in givens.unplaced(palette):
        if color not in named:
            groups.setdefault((color.temperature, color.tone, color.family), []).append(color)
    return tuple(tuple(group) for group in groups.values() if len(group) > 1)


def _rearrangements(
    solution: Placement, twins: tuple[tuple[Color, ...], ...]
) -> Iterator[Placement]:
    """`solution` and every solution made from it by swapping colors within a group."""
    fixed = {c: cell for c, cell in solution.assignments.items() if not any(c in g for g in twins)}
    orders = [permutations([solution.assignments[c] for c in group]) for group in twins]
    for choice in product(*orders):
        assignments = dict(fixed)
        for group, cells in zip(twins, choice, strict=True):
            assignments.update(zip(group, cells, strict=True))
        yield Placement(assignments)


def _holders(candidates: Candidates) -> dict[Cell, list[Color]]:
    """For each cell some color could take, the colors that could take it."""
    holders: dict[Cell, list[Color]] = {}
    for color, cells in candidates.items():
        for cell in cells:
            holders.setdefault(cell, []).append(color)
    return holders


def _has_matching(candidates: Candidates) -> bool:
    """Whether every color can have its own cell from its candidates (and so, with as many
    colors as free cells, every free cell gets a color). Augmenting paths, as in Kuhn's
    algorithm; the sizes here are at most a board's cells."""
    owner: dict[Cell, Color] = {}

    def assign(color: Color, seen: set[Cell]) -> bool:
        for cell in candidates[color]:
            if cell in seen:
                continue
            seen.add(cell)
            current = owner.get(cell)
            if current is None or assign(current, seen):
                owner[cell] = color
                return True
        return False

    return all(assign(color, set()) for color in candidates)


def colors_in(clue: Clue, palette: Palette) -> set[Color]:
    """Every palette color the clue depends on: placing one of them can change its truth.

    A board rule depends on all of them, and so does an attribute clue: whether it holds
    depends on whichever cubes land next to its color or in its region, not only on the
    colors it names. The search re-checks a clue whenever one of these colors is placed.
    """
    match clue:
        case BoardRule() | AttributeClue():
            return set(palette)
    return _colors(clue, palette, colors_in)


def colors_named(clue: Clue, palette: Palette) -> set[Color]:
    """Every palette color the clue's sentence names, which is what a player reads as
    being about that cube. An attribute clue names its subject color, a region clue none;
    a board rule counts as naming all of them."""
    match clue:
        case AttributeClue(color=color_ref):
            return set() if color_ref is None else _resolve((color_ref,), palette)
        case BoardRule():
            return set(palette)
    return _colors(clue, palette, colors_named)


def _colors(
    clue: Clue, palette: Palette, recurse: Callable[[Clue, Palette], set[Color]]
) -> set[Color]:
    match clue:
        case Relation(colors=refs):
            return _resolve(refs, palette)
        case Property(color=color_ref):
            return _resolve((color_ref,), palette)
        case Not(clue=inner):
            return recurse(inner, palette)
        case And(clues=subs) | Or(clues=subs) | Exactly(clues=subs) | AtLeast(clues=subs):
            return set().union(*(recurse(sub, palette) for sub in subs))
    raise TypeError(f"not a clue: {clue!r}")


def _resolve(refs: Iterable[ColorRef], palette: Palette) -> set[Color]:
    colors: set[Color] = set()
    for color_ref in refs:
        if color_ref.by_initial:
            colors.update(palette.by_initial(color_ref.key))
        else:
            colors.add(palette.by_id(color_ref.key))
    return colors
