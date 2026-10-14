"""The generation pipeline: solution, candidate clues, greedy choice, minimisation.

1. Draw a random full solution and pick the givens for the difficulty.
2. Build a pool of clues that are true on that solution (`candidate_pool`).
3. Greedily add the clue that rules out the most other solutions, judged on a sample of
   them, until the solver finds no solution but the real one.
4. Drop every clue the puzzle can do without, then check uniqueness one last time.

An attempt that misses the difficulty profile (too many clues, no signature clue, one
kind of clue everywhere) is thrown away and the next attempt draws a new solution from
the same random stream, so a seed still maps to exactly one puzzle. The solver is only
ever asked for every solution of a set of givens (`solver_rivals`), never for the first
few it meets, so a change to how it searches does not change the puzzle a seed builds.
"""

from __future__ import annotations

import hashlib
import itertools
import math
import random
from collections import Counter
from collections.abc import Sequence
from dataclasses import replace

from chroma_cube.core.board import CLASSIC_BOARD, Board, Cell
from chroma_cube.core.clues import (
    And,
    AtLeast,
    AttributeClue,
    BoardRule,
    Clue,
    Exactly,
    Not,
    Or,
    Property,
    Relation,
)
from chroma_cube.core.colors import CLASSIC_PALETTE, Color, Palette
from chroma_cube.core.placement import Placement
from chroma_cube.core.puzzle import Puzzle
from chroma_cube.generator.candidates import (
    ATTRIBUTE_FEATURES,
    Check,
    Order,
    candidate_pool,
    cells_of,
    clue_colors,
    clue_features,
    compile_clue,
    disguised_by_givens,
    random_solution,
)
from chroma_cube.generator.layouts import LAYOUTS
from chroma_cube.generator.profiles import PROFILES, Difficulty, Profile
from chroma_cube.solver import solve_clues

_POSITIONS = PROFILES["easy"].features
"""Every positional relation; easy uses only these."""

_MAX_ATTEMPTS = 200
_MAX_OTHER_BOARD_ATTEMPTS = 30
_MIN_CELLS = 4
_MAX_CELLS = 20
_CELLS_PER_EXTRA_GIVEN = 4
"""A board larger than the classic tray gets one more given for every this many extra
cells: with none, proving a 4x5 expert puzzle unique often runs out of solver budget."""
_FAMILY_DROP = 0.6
"""Chance that an attempt leaves out each non-positional clue family."""
_MAX_NODES = 200_000
"""Solver budget per call, the solver's own default. A clue set the solver cannot settle
within it is dropped and the next attempt starts from a fresh solution, so no seed can
stall on a hard search. It is set high enough that running out is rare: whether a call
runs out depends on how the solver searches, so a smaller budget would let solver
changes move seeds."""
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
_ATTRIBUTE_PENALTY = 0.4
"""Each attribute clue already picked costs any further one this factor."""
_MAX_ATTRIBUTE_CLUES = 2
"""Attribute clues rule out many random rivals but few close ones, and many of them slow
the solver, so a puzzle carries at most this many."""
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

    Raises `ValueError` for an unknown difficulty, a palette that does not fill the board,
    a board outside 4 to 20 cells, or a non-classic board on which no attempt fits the
    profile; `RuntimeError` if no attempt fits on the classic tray (not seen in practice).
    """
    if difficulty not in PROFILES:
        raise ValueError(f"unknown difficulty {difficulty!r}; pick one of {list(PROFILES)}")
    if len(palette) != len(board):
        raise ValueError(
            f"a {board.rows}x{board.cols} board needs {len(board)} colors, "
            f"the palette has {len(palette)}"
        )
    profile = fit_profile(PROFILES[difficulty], board)
    rng = random.Random(_seed_of(seed, difficulty, board, palette))
    classic = board == CLASSIC_BOARD
    for _ in range(_MAX_ATTEMPTS if classic else _MAX_OTHER_BOARD_ATTEMPTS):
        try:
            found = _attempt(rng, profile, difficulty, board, palette)
        except _GaveUp:
            found = None
        if found is not None:
            givens, clues = found
            return Puzzle(
                id=puzzle_id(seed, difficulty, board, palette),
                title=f"{rng.choice(_ADJECTIVES)} {rng.choice(_NOUNS)}",
                board=board,
                palette=palette,
                givens=givens,
                clues=clues,
                difficulty=difficulty,
            )
    if not classic:
        raise ValueError(
            f"no {difficulty} puzzle fits a {board.rows}x{board.cols} board for seed {seed}"
        )
    raise RuntimeError(f"no {difficulty} puzzle found for seed {seed}")


def puzzle_id(seed: int, difficulty: str, board: Board, palette: Palette) -> str:
    """`gen-<difficulty>-<seed>` on the classic tray; other boards add their shape, and a
    palette that is not the board's own adds a short digest of its color ids."""
    if board == CLASSIC_BOARD and palette == CLASSIC_PALETTE:
        return f"gen-{difficulty}-{seed}"
    tag = f"{board.rows}x{board.cols}"
    if not any(lay.board == board and lay.palette == palette for lay in LAYOUTS):
        ids = ",".join(color.id for color in palette)
        tag += "-" + hashlib.sha256(ids.encode()).hexdigest()[:6]
    return f"gen-{tag}-{difficulty}-{seed}"


def fit_profile(profile: Profile, board: Board) -> Profile:
    """The profile scaled to the board: givens grow with the cell count, plus one for
    every four cells past twelve, and clues with the information needed to pick one
    placement out of all of them (the log of cells!).

    The ranges are tuned for the classic twelve cells. Raises `ValueError` for a board
    with fewer than 4 or more than 20 cells, where the scaled profile stops making sense
    or the search gets too slow.
    """
    cells = len(board)
    if not _MIN_CELLS <= cells <= _MAX_CELLS:
        raise ValueError(
            f"a {board.rows}x{board.cols} board has {cells} cells; "
            f"the generator handles {_MIN_CELLS} to {_MAX_CELLS}"
        )
    if cells == len(CLASSIC_BOARD):
        return profile
    most_givens = cells - 2

    def scaled(low: int, high: int, scale: float, floor: int, cap: int) -> tuple[int, int]:
        new_low = min(max(floor, round(low * scale)), cap)
        return new_low, min(max(new_low, round(high * scale)), cap)

    # Clues must tell apart cells! placements, so they scale with its logarithm.
    information = math.lgamma(cells + 1) / math.lgamma(len(CLASSIC_BOARD) + 1)
    low, high = scaled(*profile.givens, cells / len(CLASSIC_BOARD), 0, most_givens)
    extra = max(0, cells - len(CLASSIC_BOARD)) // _CELLS_PER_EXTRA_GIVEN
    return replace(
        profile,
        givens=(min(low + extra, most_givens), min(high + extra, most_givens)),
        clues=scaled(*profile.clues, information, 1, cells),
    )


def _seed_of(seed: int, difficulty: str, board: Board, palette: Palette) -> int:
    """A stable seed for the random stream, different for every level, board and palette."""
    ids = ",".join(color.id for color in palette)
    key = f"{difficulty}:{seed}:{board.rows}x{board.cols}:{ids}"
    return int.from_bytes(hashlib.sha256(key.encode()).digest()[:8], "big")


def primary_kind(clue: Clue) -> str:
    """The family a clue belongs to, used to keep one family from crowding a puzzle."""
    match clue:
        case (
            Relation(kind=kind)
            | Property(kind=kind)
            | BoardRule(kind=kind)
            | AttributeClue(kind=kind)
        ):
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

    features = _families(rng, profile)
    if order is not None:
        features |= {f"{order}_alphabetical"}
    pool = [
        clue
        for clue in candidate_pool(rng, solution, board, palette, features)
        if not _only_about_givens(clue, givens, palette)
        and not _has_hollow_part(clue, givens, palette)
        and not disguised_by_givens(clue, givens, board, palette)
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


def _families(rng: random.Random, profile: Profile) -> frozenset[str]:
    """The features this attempt may use: every positional one, and a random share of the rest.

    Without this the strongest families (between, grouped "sits next to") would land on
    every hard card. At least one signature feature always survives.
    """
    optional = sorted(profile.features - _POSITIONS)
    kept = {feature for feature in optional if rng.random() >= _FAMILY_DROP}
    signature = sorted(profile.signature)
    if signature and not kept & profile.signature:
        kept.add(rng.choice(signature))
    return (profile.features & _POSITIONS) | frozenset(kept)


def _has_hollow_part(clue: Clue, givens: Placement, palette: Palette) -> bool:
    """A compound clue with a part only about given cubes: that part is settled already,
    so the clue is a plainer clue in disguise."""
    if not isinstance(clue, Or | And | Exactly | AtLeast):
        return False
    return any(_only_about_givens(part, givens, palette) for part in clue.clues)


def _only_about_givens(clue: Clue, givens: Placement, palette: Palette) -> bool:
    """A clue whose every possible color is already given tells the player nothing.

    Board rules and attribute clues also speak about cubes they do not name, so they are
    never only about the givens; one the givens already settle rules out no rival and is
    never picked."""
    if clue_features(clue) & ({"rows_alphabetical", "columns_alphabetical"} | ATTRIBUTE_FEATURES):
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


class _GaveUp(Exception):
    """The solver ran out of budget before it could answer."""


def _unique(board: Board, palette: Palette, clues: Sequence[Clue], givens: Placement) -> bool:
    """Exactly one solution. Raises `_GaveUp` if the solver's budget ran out first."""
    result = solve_clues(board, palette, clues, givens=givens, limit=1, max_nodes=_MAX_NODES)
    if result.count == 1 and not result.truncated and not result.gave_up:
        return True
    if result.count > 1 or result.truncated:
        return False
    if result.gave_up:
        raise _GaveUp
    return False


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
            return solver_rivals(
                self.rng,
                self.board,
                self.palette,
                self.chosen,
                self.givens,
                self.solution_cells,
                _SOLVER_SAMPLE,
            )
        return list(found)

    def walk(self) -> list[tuple[Cell, ...]]:
        """Other solutions found by local search: swap cubes while fewer clues break.

        Each restart starts from a random completion and keeps a swap unless it breaks
        more of the chosen clues than before, with an occasional uphill step to escape.
        It is cheap next to a solver call and finds solutions far from the real one.
        """
        found: list[tuple[Cell, ...]] = []
        free_cells = [self.solution_cells[i] for i in self.free]
        if len(self.free) < 2 or not self.chosen:
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

    def pins_a_cube(self, clue: Clue) -> bool:
        """A row clue for a cube that already has a column clue, or the other way round,
        would just be a given in disguise."""
        if not isinstance(clue, Property) or clue.kind not in ("in_row", "in_col"):
            return False
        other = "in_col" if clue.kind == "in_row" else "in_row"
        return any(
            isinstance(c, Property) and c.kind == other and c.color == clue.color
            for c in self.chosen
        )

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
        attributes = sum(bool(self.features[i] & ATTRIBUTE_FEATURES) for i in self.picked)
        want_signature = bool(self.profile.signature) and not have & self.profile.signature
        best: tuple[float, int] | None = None
        for i in range(len(self.pool)):
            cut = alive - (self.alive & self.masks[i]).bit_count()
            if cut == 0 or self.pins_a_cube(self.pool[i]):
                continue
            score = cut / alive
            if self.features[i] & ATTRIBUTE_FEATURES:
                if attributes == _MAX_ATTRIBUTE_CLUES:
                    continue
                score *= _ATTRIBUTE_PENALTY**attributes
            score *= _REPEAT_PENALTY ** used[self.kinds[i]]
            for feature in sorted(self.features[i] & _SPECIAL):
                score *= _SPECIAL_PENALTY ** special[feature]
            if want_signature and self.features[i] & self.profile.signature:
                score *= _SIGNATURE_BONUS
            score *= 1 - _JITTER + 2 * _JITTER * self.rng.random()
            if best is None or score > best[0]:
                best = (score, i)
        return None if best is None else best[1]


def solver_rivals(
    rng: random.Random,
    board: Board,
    palette: Palette,
    clues: Sequence[Clue],
    givens: Placement,
    solution: tuple[Cell, ...],
    cap: int,
) -> list[tuple[Cell, ...]]:
    """Up to `cap` solutions of the clues other than `solution`, as `cells_of` tuples;
    empty if there are none.

    Which ones depends only on `rng` and the puzzle data, never on the order the solver
    searches in: the solver is only ever asked for every solution of a set of givens,
    and a list that fits under `cap` is sorted. When there are more (or its budget runs
    out before it knows), more of the real solution is given, color by color in a random
    order. Bisection over how many of those to give stops at the first try that leaves
    a list that fits with a rival in it: rivals close to the real solution. If it ends
    with none (one color fewer is too many, one more leaves none), the last color added
    goes on each of its other cells in turn, splitting further the same way, until one
    of them has rivals.

    Raises `_GaveUp` if the budget runs out with a single color left to place.
    """
    colors = list(givens.unplaced(palette))
    real = {color: solution[palette.colors.index(color)] for color in colors}

    def listing(fixed: Placement) -> list[tuple[Cell, ...]] | None:
        """Every rival under `fixed`, sorted; None if there are too many to list."""
        result = solve_clues(board, palette, clues, givens=fixed, limit=cap, max_nodes=_MAX_NODES)
        if result.truncated or result.gave_up:
            return None
        others = (cells_of(s, palette) for s in result.solutions)
        return sorted(other for other in others if other != solution)

    def split(fixed: Placement, color: Color, cells: list[Cell]) -> list[tuple[Cell, ...]]:
        """The rivals with `color` on the first of `cells`, in a random order, that has any."""
        rng.shuffle(cells)
        for cell in cells:
            child = fixed.with_color(color, cell)
            found = listing(child)
            if found is None:
                rest = child.unplaced(palette)
                if not rest:
                    raise _GaveUp
                found = split(child, rest[0], [c for c in board if child.color_at(c) is None])
            if found:
                return found
        return []

    found = listing(givens)
    if found is not None:
        return found
    rng.shuffle(colors)

    def given(k: int) -> Placement:
        return Placement({**givens.assignments, **{c: real[c] for c in colors[:k]}})

    low, high = 0, len(colors)
    while high - low > 1:
        mid = (low + high) // 2
        found = listing(given(mid))
        if found:
            return found
        if found is None:
            low = mid
        else:
            high = mid
    color, fixed = colors[low], given(low)
    others = [cell for cell in board if fixed.color_at(cell) is None and cell != real[color]]
    return split(fixed, color, others)


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
        try:
            removable = _unique(
                greedy.board, greedy.palette, [clues[j] for j in trial], greedy.givens
            )
        except _GaveUp:
            removable = False
        if removable:
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
