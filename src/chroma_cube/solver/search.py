"""Backtracking search with forward checking, pruned by three-valued clue evaluation.

The search keeps, for every unplaced color, the cells it could still go on. A cell stays
a candidate only while putting the color there leaves every clue that mentions the color
not VIOLATED. Attribute clues are also read as counts over a group of cells, with each
unplaced color limited to its candidates, so a region or neighbour clue rules cells out
before its group fills up. A branch ends when a color has no candidates left or the
colors cannot each have their own cell. Each step tries every cell of the color with the
fewest candidates, or every color of the cell with the fewest, whichever is fewer.

This is sound because VIOLATED from the evaluator always means no completion can satisfy
the clue, so a cell ruled out on a partial board stays ruled out below it, and the count
reasoning only drops cells that no arrangement within the candidates could use. Every
node and every solution is still checked with the evaluator, which stays the definition
of what a clue means.

Colors that no clue can tell apart (unnamed, same attributes) are searched in one order
only, and each solution found is returned with every swap of them.

Before searching, the clues are simplified (see `simplify`) so a clue that contradicts
another is caught up front. The search also has a budget: it counts every trial
placement of a color on a cell, and gives up once the count passes `max_nodes`.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from itertools import permutations, product

from chroma_cube.core.board import Board, Cell
from chroma_cube.core.clues import (
    ATTRIBUTE_KINDS,
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
        mentions: dict[Color, list[int]] = {color: [] for color in palette}
        for index, clue in enumerate(clues):
            for color in colors_in(clue, palette):
                mentions[color].append(index)
        self.mentions = {color: tuple(found) for color, found in mentions.items()}
        self.counts = tuple(
            fact
            for index, clue in enumerate(clues)
            if (fact := _CountFact.of(index, clue, board, palette)) is not None
        )
        # Trials skip count clues: `_propagate_counts` narrows by them with the candidates
        # in view, and every node and solution is still checked against the evaluator.
        self.counted = {fact.index for fact in self.counts}
        self.twins: tuple[tuple[Color, ...], ...] = ()

    def run(self, givens: Placement) -> Iterator[Placement]:
        self.twins = _twins(self.palette, self.clues, givens)
        live = self._live(givens, tuple(range(len(self.clues))))
        if live is None:
            return
        free = tuple(cell for cell in self.board if givens.color_at(cell) is None)
        candidates = self._narrow(givens, {c: free for c in givens.unplaced(self.palette)}, live)
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
        self, placement: Placement, candidates: Candidates, live: tuple[int, ...]
    ) -> dict[Color, tuple[Cell, ...]] | None:
        """Each color's candidates that are still free and break no clue; None on a dead end.

        A dead end is a color with no cell left, or no way to give every color its own
        cell from its candidates (which includes a free cell no color can take)."""
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
        if not self._propagate_counts(placement, narrowed, alive):
            return None
        if not _has_matching(narrowed):
            return None
        return narrowed

    def _propagate_counts(
        self, placement: Placement, candidates: dict[Color, tuple[Cell, ...]], alive: set[int]
    ) -> bool:
        """Narrow `candidates` with the attribute clues' counts until nothing changes.

        False when some count clue can no longer hold within the colors' candidates."""
        changed = True
        while changed:
            changed = False
            for fact in self.counts:
                if fact.index in alive:
                    outcome = fact.tighten(placement, self.board, candidates)
                    if outcome is None:
                        return False
                    changed = changed or outcome
            for group in self.twins:
                changed = _keep_in_order(group, placement, candidates) or changed
        return all(candidates.values())

    def _allows(
        self, placement: Placement, color: Color, cell: Cell, checks: tuple[Clue, ...]
    ) -> bool:
        if self.budget is not None:
            if self.budget == 0:
                raise _OutOfBudget
            self.budget -= 1
        trial = placement.with_color(color, cell)
        return all(self._evaluate(clue, trial) is not Truth.VIOLATED for clue in checks)

    def _evaluate(self, clue: Clue, placement: Placement) -> Truth:
        return evaluate(clue, placement, self.board, self.palette)


@dataclass(frozen=True)
class _CountFact:
    """An attribute clue (or its negation) the search decides from candidates.

    Such a clue holds or not depending on how many cubes with its value (`matching`) and
    without it (`others`) end up in a group of cells: a region, or the cells next to its
    color. The evaluator treats every unplaced color as free to go to any free cell; here
    each one is limited to its candidates, which lets the clue rule cells out before its
    group fills up. The palette fills the board, so every empty cell in the group ends up
    holding exactly one unplaced color, and that is the only thing assumed.
    """

    index: int
    value: str
    holds: Callable[[int, int], bool]
    region: tuple[Cell, ...] | None
    subject: Color | None

    @staticmethod
    def of(index: int, clue: Clue, board: Board, palette: Palette) -> _CountFact | None:
        """The fact for an attribute clue or its negation naming one color; else None."""
        positive = True
        if isinstance(clue, Not):
            positive, clue = False, clue.clue
        if not isinstance(clue, AttributeClue):
            return None
        kind_holds = ATTRIBUTE_KINDS[clue.kind].holds
        n = clue.n

        def holds(matching: int, others: int) -> bool:
            return kind_holds(matching, others, n) is positive

        if clue.region is not None:
            return _CountFact(index, clue.value, holds, clue.region.cells(board), None)
        assert clue.color is not None
        if clue.color.by_initial:
            return None
        return _CountFact(index, clue.value, holds, None, palette.by_id(clue.color.key))

    def tighten(
        self, placement: Placement, board: Board, candidates: dict[Color, tuple[Cell, ...]]
    ) -> bool | None:
        """Drop candidates that leave the clue no way to hold.

        Returns None if nothing within the candidates can satisfy the clue, else whether
        a candidate was dropped (one per call). Only counts are compared, so this may keep
        arrangements that fail for other reasons, but it never drops a possible one."""
        if self.region is not None:
            return self._tighten_group(self.region, placement, candidates)
        assert self.subject is not None
        cell = placement.cell_of(self.subject)
        if cell is not None:
            return self._tighten_group(board.orthogonal_neighbours(cell), placement, candidates)
        # The color is not placed yet: keep the cells where its neighbours could still
        # make the clue hold.
        spots = candidates[self.subject]
        others = {color: cells for color, cells in candidates.items() if color != self.subject}
        kept = tuple(
            spot
            for spot in spots
            if self._census(board.orthogonal_neighbours(spot), placement, others, spot).possible()
        )
        if not kept:
            return None
        candidates[self.subject] = kept
        return len(kept) < len(spots)

    def _tighten_group(
        self,
        cells: tuple[Cell, ...],
        placement: Placement,
        candidates: dict[Color, tuple[Cell, ...]],
    ) -> bool | None:
        census = self._census(cells, placement, candidates, None)
        if not census.possible():
            return None
        group = set(cells)
        for color in census.undecided:
            matches = color.has(self.value)
            if not census.possible(inside=color, matches=matches):
                candidates[color] = tuple(c for c in candidates[color] if c not in group)
            elif not census.possible(outside=color, matches=matches):
                candidates[color] = tuple(c for c in candidates[color] if c in group)
            else:
                continue
            return True
        return False

    def _census(
        self,
        cells: tuple[Cell, ...],
        placement: Placement,
        candidates: Mapping[Color, tuple[Cell, ...]],
        taken: Cell | None,
    ) -> _Census:
        """Count the group's cubes so far and the unplaced colors that must or may join it.
        `taken` is a cell treated as filled (by the clue's own color) though not placed."""
        group = set(cells)
        placed = [0, 0]
        empty = 0
        for cell in cells:
            color = placement.color_at(cell)
            if color is None:
                empty += 1
            else:
                placed[not color.has(self.value)] += 1
        must = [0, 0]
        may = [0, 0]
        undecided: list[Color] = []
        for color, spots in candidates.items():
            usable = [spot for spot in spots if spot != taken]
            inside = sum(1 for spot in usable if spot in group)
            if inside == 0:
                continue
            side = int(not color.has(self.value))
            if inside == len(usable):
                must[side] += 1
            else:
                may[side] += 1
                undecided.append(color)
        return _Census(self.holds, placed, empty, must, may, undecided)


@dataclass(frozen=True)
class _Census:
    """A group of cells for one count clue: how many matching and other cubes it holds
    (`placed`), how many empty cells it has, and how many unplaced matching and other
    colors must land in it (`must`) or may (`may`, the colors listed in `undecided`)."""

    holds: Callable[[int, int], bool]
    placed: list[int]
    empty: int
    must: list[int]
    may: list[int]
    undecided: list[Color]

    def possible(
        self, *, inside: Color | None = None, outside: Color | None = None, matches: bool = False
    ) -> bool:
        """Whether some way of filling the empty cells satisfies the clue, optionally with
        one undecided color moved inside or outside the group."""
        must, may = list(self.must), list(self.may)
        side = int(not matches)
        if inside is not None or outside is not None:
            may[side] -= 1
        if inside is not None:
            must[side] += 1
        for extra_matching in range(may[0] + 1):
            extra_others = self.empty - must[0] - must[1] - extra_matching
            if 0 <= extra_others <= may[1] and self.holds(
                self.placed[0] + must[0] + extra_matching,
                self.placed[1] + must[1] + extra_others,
            ):
                return True
        return False


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


def _keep_in_order(
    group: tuple[Color, ...], placement: Placement, candidates: dict[Color, tuple[Cell, ...]]
) -> bool:
    """Keep each color of `group` on a later cell (row by row) than the one before it.
    Returns whether a candidate was dropped."""

    def span(color: Color) -> tuple[Cell, Cell]:
        cell = placement.cell_of(color)
        if cell is not None:
            return cell, cell
        cells = candidates[color]
        return (min(cells), max(cells)) if cells else (_LAST, _FIRST)

    changed = False
    for before, after in zip(group, group[1:], strict=False):
        low, _ = span(before)
        _, high = span(after)
        if after in candidates:
            kept = tuple(c for c in candidates[after] if c > low)
            changed = changed or len(kept) < len(candidates[after])
            candidates[after] = kept
        if before in candidates:
            kept = tuple(c for c in candidates[before] if c < high)
            changed = changed or len(kept) < len(candidates[before])
            candidates[before] = kept
    return changed


_FIRST, _LAST = Cell(-1, -1), Cell(1 << 30, 1 << 30)


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
