"""The generation pipeline: solution, candidate clues, greedy choice, minimisation.

1. Draw a random full solution and pick the givens for the difficulty.
2. Build a pool of clues that are true on that solution (`candidate_pool`).
3. Greedily add the clue that rules out the most other solutions, judged on a sample of
   them, until the solver finds no solution but the real one.
4. Drop every clue the puzzle can do without, then check uniqueness one last time.

An attempt that misses the difficulty profile (too many clues, no signature clue, one
kind of clue everywhere) is thrown away and the next attempt draws a new solution from
the same random stream, so a seed still maps to exactly one puzzle.
"""

from __future__ import annotations

import itertools
import random
from collections import Counter
from collections.abc import Sequence

from chroma_cube.core.board import CLASSIC_BOARD, Board, Cell
from chroma_cube.core.clues import (
    And,
    AtLeast,
    BoardRule,
    Clue,
    Exactly,
    Not,
    Or,
    Property,
    Relation,
)
from chroma_cube.core.colors import CLASSIC_PALETTE, Palette
from chroma_cube.core.placement import Placement
from chroma_cube.core.puzzle import Puzzle
from chroma_cube.generator.candidates import (
    Check,
    Order,
    candidate_pool,
    cells_of,
    clue_colors,
    clue_features,
    compile_clue,
    random_solution,
)
from chroma_cube.generator.profiles import PROFILES, Difficulty, Profile
from chroma_cube.solver import solve_clues

_MAX_ATTEMPTS = 200
_SLACK = 1
"""How far past the profile's clue limit greedy may run before the attempt is dropped."""
_RANDOM_DRAWS = 300
_MAX_SAMPLE = 64
_SOLVER_SAMPLE = 16
_WALK_RESTARTS = 4
_WALK_STEPS = 600
_WALK_UPHILL = 0.1
_SIGNATURE_BONUS = 1.6
_REPEAT_PENALTY = 0.45
_JITTER = 0.2
_SPECIAL = frozenset({"initial", "or", "not", "exactly", "at_least", "between"})
"""Features that make a clue slow for the solver or heavy to read; each reuse costs a factor."""
_SPECIAL_PENALTY = 0.4
_ALPHABETICAL_SHARE = 0.4
"""How often an expert puzzle starts from a solution whose rows or columns are sorted."""

_ADJECTIVES = (
    "Quiet", "Bright", "Hidden", "Tangled", "Hollow", "Silent", "Crooked", "Gentle",
    "Restless", "Folded", "Distant", "Patient", "Sudden", "Narrow", "Wandering", "Steady",
)  # fmt: skip
_NOUNS = (
    "Lantern", "Harbor", "Garden", "Crossing", "Orchard", "Mosaic", "Ladder", "Window",
    "Corridor", "Meadow", "Compass", "Quarry", "Tapestry", "Puzzle", "Signal", "Courtyard",
)  # fmt: skip


def generate(
    seed: int,
    difficulty: Difficulty = "medium",
    *,
    board: Board = CLASSIC_BOARD,
    palette: Palette = CLASSIC_PALETTE,
) -> Puzzle:
    """A new puzzle with exactly one solution. The same arguments always give the same puzzle.

    Raises `ValueError` for an unknown difficulty or a palette that does not fill the
    board, and `RuntimeError` if no attempt fits the profile (not seen on the classic tray).
    """
    if difficulty not in PROFILES:
        raise ValueError(f"unknown difficulty {difficulty!r}; pick one of {list(PROFILES)}")
    if len(palette) != len(board):
        raise ValueError(
            f"a {board.rows}x{board.cols} board needs {len(board)} colors, "
            f"the palette has {len(palette)}"
        )
    rng = random.Random(seed)
    profile = PROFILES[difficulty]
    for _ in range(_MAX_ATTEMPTS):
        found = _attempt(rng, profile, difficulty, board, palette)
        if found is not None:
            givens, clues = found
            return Puzzle(
                id=f"gen-{difficulty}-{seed}",
                title=f"{rng.choice(_ADJECTIVES)} {rng.choice(_NOUNS)}",
                board=board,
                palette=palette,
                givens=givens,
                clues=clues,
                difficulty=difficulty,
            )
    raise RuntimeError(f"no {difficulty} puzzle found for seed {seed}")


def primary_kind(clue: Clue) -> str:
    """The family a clue belongs to, used to keep one family from crowding a puzzle."""
    match clue:
        case Relation(kind=kind) | Property(kind=kind) | BoardRule(kind=kind):
            return kind.removeprefix("directly_")
        case Not():
            return "not"
        case Or():
            return "or"
        case And():
            return "and"
        case Exactly() | AtLeast():
            return "count"
    raise TypeError(f"not a clue: {clue!r}")


# --------------------------------------------------------------------------- one attempt


def _attempt(
    rng: random.Random, profile: Profile, difficulty: Difficulty, board: Board, palette: Palette
) -> tuple[Placement, tuple[Clue, ...]] | None:
    order: Order | None = None
    if difficulty == "expert" and rng.random() < _ALPHABETICAL_SHARE:
        order = rng.choice(("rows", "columns"))
    solution = random_solution(rng, board, palette, order)
    low, high = profile.givens
    given_count = min(rng.randint(low, high), len(board) - 1)
    given_colors = rng.sample(list(palette), given_count)
    givens = Placement({color: solution.assignments[color] for color in given_colors})

    pool = [
        clue
        for clue in candidate_pool(rng, solution, board, palette, profile.features)
        if not _only_about_givens(clue, givens, palette)
    ]
    greedy = _Greedy(rng, profile, solution, givens, pool, board, palette)
    chosen = greedy.run()
    if chosen is None:
        return None
    clues = _minimise(rng, profile, greedy, chosen)
    if not _fits(profile, clues):
        return None
    if not _unique(board, palette, clues, givens):
        return None
    return givens, clues


def _only_about_givens(clue: Clue, givens: Placement, palette: Palette) -> bool:
    """A clue whose every possible color is already given tells the player nothing."""
    if clue_features(clue) & {"rows_alphabetical", "columns_alphabetical"}:
        return False
    return all(color in givens.assignments for color in clue_colors(clue, palette))


def _fits(profile: Profile, clues: Sequence[Clue]) -> bool:
    low, high = profile.clues
    if not low <= len(clues) <= high:
        return False
    used = frozenset().union(*(clue_features(clue) for clue in clues))
    if profile.signature and not used & profile.signature:
        return False
    most = Counter(primary_kind(clue) for clue in clues).most_common(1)[0][1]
    return most <= max(2, (len(clues) + 1) // 2)


def _unique(board: Board, palette: Palette, clues: Sequence[Clue], givens: Placement) -> bool:
    result = solve_clues(board, palette, clues, givens=givens, limit=1)
    return result.count == 1 and not result.truncated


# --------------------------------------------------------------------------- greedy


class _Greedy:
    """Adds clues until the solution is the only one.

    Which clue to add is judged on a sample of the other solutions still allowed: random
    completions of the givens that the chosen clues accept, or, once those run dry, the
    solver's next solutions. Each candidate's truth on the sample is a bit mask, so
    adding a clue just narrows the set of sample solutions still alive.
    """

    def __init__(
        self,
        rng: random.Random,
        profile: Profile,
        solution: Placement,
        givens: Placement,
        pool: list[Clue],
        board: Board,
        palette: Palette,
    ) -> None:
        self.rng = rng
        self.profile = profile
        self.solution = solution
        self.givens = givens
        self.pool = pool
        self.board = board
        self.palette = palette
        self.checks = [compile_clue(clue, board, palette) for clue in pool]
        self.solution_cells = cells_of(solution, palette)
        self.free = [i for i, color in enumerate(palette) if color not in givens.assignments]
        self.near = _reshuffles(self.solution_cells, self.free)
        self.features = [clue_features(clue) for clue in pool]
        self.kinds = [primary_kind(clue) for clue in pool]
        self.picked: list[int] = []
        self.chosen: list[Clue] = []
        self.chosen_checks: list[Check] = []
        self.chosen_colors: list[list[int]] = []
        self.witnesses: list[tuple[Cell, ...]] = []
        """Every other solution sampled along the way, to rule out removals cheaply later."""
        self.masks: list[int] = []
        self.alive = 0

    def run(self) -> list[Clue] | None:
        limit = self.profile.clues[1] + _SLACK
        while True:
            if not self.alive and not self.resample():
                return self.chosen
            pick = self.best()
            if pick is None or len(self.chosen) == limit:
                return None
            self.picked.append(pick)
            self.chosen.append(self.pool[pick])
            self.chosen_checks.append(self.checks[pick])
            self.chosen_colors.append(
                [
                    i
                    for i in self.free
                    if self.palette.colors[i] in clue_colors(self.pool[pick], self.palette)
                ]
            )
            self.alive &= self.masks[pick]

    def resample(self) -> bool:
        """Draw a fresh sample of other solutions; False if there are none."""
        sample = self.alternatives()
        if not sample:
            return False
        self.witnesses += sample
        self.masks = [
            sum(1 << i for i, other in enumerate(sample) if check(other)) for check in self.checks
        ]
        self.alive = (1 << len(sample)) - 1
        return True

    def alternatives(self) -> list[tuple[Cell, ...]]:
        """Other solutions of the clues chosen so far, as `cells_of` tuples.

        Random completions find them while the clues are loose; small reshuffles of the
        real solution find the close calls once they are tight; the solver is asked only
        when neither finds any.
        """
        found: dict[tuple[Cell, ...], None] = {}
        free_cells = [self.solution_cells[i] for i in self.free]
        for draw in range(_RANDOM_DRAWS):
            if draw == _RANDOM_DRAWS // 5 and not found:
                break
            self.rng.shuffle(free_cells)
            cells = list(self.solution_cells)
            for i, cell in zip(self.free, free_cells, strict=True):
                cells[i] = cell
            other = tuple(cells)
            if other != self.solution_cells and self.allowed(other):
                found[other] = None
                if len(found) == _MAX_SAMPLE:
                    return list(found)
        for other in self.near:
            if self.allowed(other):
                found[other] = None
                if len(found) == _MAX_SAMPLE:
                    return list(found)
        if len(found) < _MAX_SAMPLE // 8:
            for other in self.walk():
                found[other] = None
        if not found:
            result = solve_clues(
                self.board, self.palette, self.chosen, givens=self.givens, limit=_SOLVER_SAMPLE
            )
            for solution in result.solutions:
                other = cells_of(solution, self.palette)
                if other != self.solution_cells:
                    found[other] = None
        return list(found)

    def walk(self) -> list[tuple[Cell, ...]]:
        """Other solutions found by local search: swap cubes while fewer clues break.

        Each restart starts from a random completion and keeps a swap unless it breaks
        more of the chosen clues than before, with an occasional uphill step to escape.
        It is cheap next to a solver call and finds solutions far from the real one.
        """
        found: list[tuple[Cell, ...]] = []
        free_cells = [self.solution_cells[i] for i in self.free]
        if len(self.free) < 2:
            return found
        for _ in range(_WALK_RESTARTS):
            self.rng.shuffle(free_cells)
            cells = list(self.solution_cells)
            for i, cell in zip(self.free, free_cells, strict=True):
                cells[i] = cell
            broken = self.broken(cells)
            for _ in range(_WALK_STEPS):
                if not broken:
                    other = tuple(cells)
                    if other != self.solution_cells:
                        found.append(other)
                        break
                    broken = list(range(len(self.chosen)))
                culprits = self.chosen_colors[self.rng.choice(broken)] or self.free
                a = self.rng.choice(culprits)
                b = self.rng.choice(self.free)
                if a == b:
                    continue
                cells[a], cells[b] = cells[b], cells[a]
                now = self.broken(cells)
                if len(now) <= len(broken) or self.rng.random() < _WALK_UPHILL:
                    broken = now
                else:
                    cells[a], cells[b] = cells[b], cells[a]
        return found

    def broken(self, cells: Sequence[Cell]) -> list[int]:
        """Which chosen clues `cells` breaks, by position."""
        return [i for i, check in enumerate(self.chosen_checks) if not check(cells)]

    def allowed(self, cells: tuple[Cell, ...]) -> bool:
        return all(check(cells) for check in self.chosen_checks)

    def best(self) -> int | None:
        """The candidate that rules out the most sample solutions still alive, weighted.

        Repeating a family of clue, or reusing one of the slow-to-solve features, costs
        a factor each time; the first clue to carry the level's signature gets a bonus.
        """
        alive = self.alive.bit_count()
        used = Counter(self.kinds[i] for i in self.picked)
        special = Counter(f for i in self.picked for f in self.features[i] & _SPECIAL)
        have = frozenset().union(*(self.features[i] for i in self.picked))
        want_signature = bool(self.profile.signature) and not have & self.profile.signature
        best: tuple[float, int] | None = None
        for i in range(len(self.pool)):
            cut = alive - (self.alive & self.masks[i]).bit_count()
            if cut == 0:
                continue
            score = cut / alive
            score *= _REPEAT_PENALTY ** used[self.kinds[i]]
            for feature in self.features[i] & _SPECIAL:
                score *= _SPECIAL_PENALTY ** special[feature]
            if want_signature and self.features[i] & self.profile.signature:
                score *= _SIGNATURE_BONUS
            score *= 1 - _JITTER + 2 * _JITTER * self.rng.random()
            if best is None or score > best[0]:
                best = (score, i)
        return None if best is None else best[1]


# --------------------------------------------------------------------------- minimise


def _minimise(
    rng: random.Random, profile: Profile, greedy: _Greedy, clues: list[Clue]
) -> tuple[Clue, ...]:
    """Drop each clue the puzzle stays unique without. Signature clues are tried last.

    A removal is ruled out without the solver when another solution seen during the
    greedy step, or a small reshuffle of the real one, satisfies every remaining clue.
    """
    checks = [compile_clue(clue, greedy.board, greedy.palette) for clue in clues]
    order = list(range(len(clues)))
    rng.shuffle(order)
    order.sort(key=lambda i: bool(clue_features(clues[i]) & profile.signature))
    kept = set(range(len(clues)))
    for i in order:
        trial = sorted(kept - {i})
        if any(
            all(checks[j](other) for j in trial)
            for other in itertools.chain(greedy.witnesses, greedy.near)
        ):
            continue
        if _unique(greedy.board, greedy.palette, [clues[j] for j in trial], greedy.givens):
            kept.remove(i)
    return tuple(clues[j] for j in sorted(kept))


def _reshuffles(cells: tuple[Cell, ...], free: Sequence[int]) -> list[tuple[Cell, ...]]:
    """Every swap of two free colors' cells, and every rotation of three."""
    found = []
    pairs = list(itertools.combinations(free, 2))
    for a, b in pairs:
        swapped = list(cells)
        swapped[a], swapped[b] = cells[b], cells[a]
        found.append(tuple(swapped))
    for a, b, c in itertools.combinations(free, 3):
        for x, y, z in ((b, c, a), (c, a, b)):
            rotated = list(cells)
            rotated[a], rotated[b], rotated[c] = cells[x], cells[y], cells[z]
            found.append(tuple(rotated))
    return found
