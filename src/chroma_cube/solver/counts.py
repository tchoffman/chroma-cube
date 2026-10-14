"""Count reasoning for attribute clues, over each unplaced color's candidate cells.

An attribute clue about a region or about a color named by id, or its negation, holds or
not depending on how many cubes with its value (`matching`) and without it (`others`) end
up in a group of cells: the region, or the cells next to its color. The evaluator treats
every unplaced color as free to go to any free cell; here each one is limited to its
candidates, which lets the clue rule cells out before its group fills up. The palette
fills the board, so every empty cell in a group ends up holding exactly one unplaced
color, and that is the only thing assumed.

For a group, some unplaced colors must land in it (every candidate is inside), some may
(candidates inside and out). If no split of the "may" colors passes the clue's test the
branch is dead, and a color whose going in (or staying out) fails the test loses those
cells. For a neighbour clue whose color is unplaced, each of its candidate cells is kept
only if the cells around it could still pass, and another color keeps a cell only if
some kept cell of the clue's color lets the clue pass with that color there.

On top of that, `narrow` can *probe*: put one color on one of its cells (taking that cell
from every other color), run the reasoning above to a standstill, and drop the cell if
that ends in a dead branch. Every probe is a trial placement and is charged to the
search's budget.

Each step only drops a cell that no arrangement within the candidates could use, so it
never loses a solution. Colors are numbered by palette position and cells by row-major
position, and sets of either are bits of an int, which is what keeps this cheap enough
to run at every node.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from chroma_cube.core.board import Board, Cell
from chroma_cube.core.clues import ATTRIBUTE_KINDS, AttributeClue, Clue, Not
from chroma_cube.core.colors import Color, Palette
from chroma_cube.core.placement import Placement

Holds = Callable[[int, int], bool]


class CountPropagator:
    """The count clues of one puzzle, and the narrowing they allow."""

    def __init__(
        self,
        board: Board,
        palette: Palette,
        clues: Sequence[Clue],
        twins: Sequence[Sequence[Color]],
    ) -> None:
        self.cells = tuple(board)
        self.bit = {cell: 1 << i for i, cell in enumerate(self.cells)}
        self.near = tuple(self._mask(board.orthogonal_neighbours(cell)) for cell in self.cells)
        # Per cell, the cell numbers next to it, and those neither next to it nor it.
        self.near_cells = tuple(_numbers(mask) for mask in self.near)
        self.far_cells = tuple(
            _numbers(((1 << len(self.cells)) - 1) & ~(mask | 1 << at))
            for at, mask in enumerate(self.near)
        )
        self.colors = palette.colors
        self.number = {color: i for i, color in enumerate(self.colors)}
        self.facts = tuple(
            fact
            for index, clue in enumerate(clues)
            if (fact := self._fact(index, clue, board, palette)) is not None
        )
        self.indices = frozenset(fact.index for fact in self.facts)
        self.twins = tuple(tuple(self.number[c] for c in group) for group in twins)

    def _mask(self, cells: Sequence[Cell]) -> int:
        mask = 0
        for cell in cells:
            mask |= self.bit[cell]
        return mask

    def _fact(self, index: int, clue: Clue, board: Board, palette: Palette) -> _Fact | None:
        """The fact for an attribute clue, or its negation, about a region or a color named
        by id; None for any other clue, which the search leaves to the evaluator."""
        positive = True
        if isinstance(clue, Not):
            positive, clue = False, clue.clue
        if not isinstance(clue, AttributeClue):
            return None
        kind_holds = ATTRIBUTE_KINDS[clue.kind].holds
        n = clue.n

        def holds(matching: int, others: int) -> bool:
            return kind_holds(matching, others, n) is positive

        matching = 0
        for i, color in enumerate(self.colors):
            if color.has(clue.value):
                matching |= 1 << i
        if clue.region is not None:
            region = self._mask(clue.region.cells(board))
            return _Fact(index, clue.value, matching, holds, region, -1)
        assert clue.color is not None
        if clue.color.by_initial:
            return None
        subject = self.number[palette.by_id(clue.color.key)]
        return _Fact(index, clue.value, matching, holds, 0, subject)

    def narrow(
        self,
        placement: Placement,
        candidates: dict[Color, tuple[Cell, ...]],
        alive: set[int],
        charge: Callable[[int], None],
        *,
        widest: int,
    ) -> bool:
        """Narrow `candidates` in place by the count clues in `alive` (and the order kept
        among look-alike colors), then probe the colors with at most `widest` cells left;
        False when the branch is dead. Each probe is charged to `charge`, which may raise
        to stop the search."""
        facts = tuple(fact for fact in self.facts if fact.index in alive)
        if not facts and not self.twins:
            return True
        filled = _Filled(placement, self)
        masks = [0] * len(self.colors)
        for color, cells in candidates.items():
            masks[self.number[color]] = self._mask(cells)
        start = list(masks)
        unplaced = tuple(self.number[color] for color in candidates)
        state = _State(self, filled, facts, unplaced)
        if not state.settle(masks):
            return False
        if facts and not state.probe(masks, widest, charge):
            return False
        for i in unplaced:
            if masks[i] != start[i]:
                candidates[self.colors[i]] = self._cells_of(masks[i])
        return True

    def _cells_of(self, mask: int) -> tuple[Cell, ...]:
        found: list[Cell] = []
        while mask:
            low = mask & -mask
            found.append(self.cells[low.bit_length() - 1])
            mask ^= low
        return tuple(found)


class _Filled:
    """Which cells of a placement are filled, and, per attribute value, which of those
    hold a cube with the value; also where each placed color sits."""

    def __init__(self, placement: Placement, counts: CountPropagator) -> None:
        self.at: dict[int, int] = {
            counts.number[color]: counts.bit[cell] for color, cell in placement.assignments.items()
        }
        self.cells = 0
        for bit in self.at.values():
            self.cells |= bit
        self._colors = counts.colors
        self._matching: dict[str, int] = {}

    def matching(self, value: str) -> int:
        found = self._matching.get(value)
        if found is None:
            found = 0
            for i, bit in self.at.items():
                if self._colors[i].has(value):
                    found |= bit
            self._matching[value] = found
        return found


class _Fact:
    """One count clue: its value as a set of colors, its test, and its group (a region
    mask, or the subject color whose neighbours are the group)."""

    __slots__ = ("holds", "index", "matching", "memo", "region", "subject", "value")

    def __init__(
        self, index: int, value: str, matching: int, holds: Holds, region: int, subject: int
    ) -> None:
        self.index = index
        self.value = value
        self.matching = matching
        self.holds = holds
        self.region = region
        self.subject = subject
        self.memo: dict[tuple[int, ...], bool] = {}

    def possible(
        self,
        placed: int,
        placed_others: int,
        empty: int,
        must: int,
        must_others: int,
        may: int,
        may_others: int,
    ) -> bool:
        """Whether some split of the "may" colors fills the `empty` cells so the test
        passes, with `must` matching and `must_others` other colors certainly inside."""
        key = (placed, placed_others, empty, must, must_others, may, may_others)
        answer = self.memo.get(key)
        if answer is None:
            answer = False
            for extra in range(may + 1):
                extra_others = empty - must - must_others - extra
                if 0 <= extra_others <= may_others and self.holds(
                    placed + must + extra, placed_others + must_others + extra_others
                ):
                    answer = True
                    break
            self.memo[key] = answer
        return answer


class _Census:
    """One fact's group: the cubes already in it, and the unplaced colors (as bit sets of
    color numbers) that must land in it or may."""

    __slots__ = ("args", "fact")

    def __init__(self, fact: _Fact, group: int, filled: _Filled, must: int, may: int) -> None:
        placed = (group & filled.matching(fact.value)).bit_count()
        placed_others = (group & filled.cells).bit_count() - placed
        empty = group.bit_count() - placed - placed_others
        must_matching = (must & fact.matching).bit_count()
        may_matching = (may & fact.matching).bit_count()
        self.fact = fact
        self.args = (
            placed,
            placed_others,
            empty,
            must_matching,
            must.bit_count() - must_matching,
            may_matching,
            may.bit_count() - may_matching,
        )

    def possible(self) -> bool:
        return self.fact.possible(*self.args)

    def moves(self, matching: bool) -> tuple[bool, bool]:
        """Whether the fact can still hold with one "may" color, matching the value or
        not, moved inside the group, and whether with it kept outside."""
        placed, placed_others, empty, must, must_others, may, may_others = self.args
        possible = self.fact.possible
        if matching:
            return (
                possible(placed, placed_others, empty, must + 1, must_others, may - 1, may_others),
                possible(placed, placed_others, empty, must, must_others, may - 1, may_others),
            )
        return (
            possible(placed, placed_others, empty, must, must_others + 1, may, may_others - 1),
            possible(placed, placed_others, empty, must, must_others, may, may_others - 1),
        )


class _State:
    """The count clues still undecided at one node, applied to a list of masks (one per
    color number; only the unplaced ones are read)."""

    def __init__(
        self,
        counts: CountPropagator,
        filled: _Filled,
        facts: tuple[_Fact, ...],
        unplaced: tuple[int, ...],
    ) -> None:
        self.counts = counts
        self.filled = filled
        self.facts = facts
        self.unplaced = unplaced

    def settle(self, masks: list[int]) -> bool:
        """Apply the facts and the look-alike order, round and round, until a whole round
        changes nothing. False on a dead branch."""
        steps = len(self.facts) + len(self.counts.twins)
        quiet = 0
        step = 0
        while quiet < steps:
            if step < len(self.facts):
                outcome = self._tighten(self.facts[step], masks)
                if outcome is None:
                    return False
            else:
                outcome = self._keep_in_order(self.counts.twins[step - len(self.facts)], masks)
            if outcome:
                if not all(masks[i] for i in self.unplaced):
                    return False
                quiet = 0
            else:
                quiet += 1
            step = (step + 1) % steps
        return True

    def probe(self, masks: list[int], widest: int, charge: Callable[[int], None]) -> bool:
        """Drop each cell whose color, put there, settles into a dead branch, then settle
        what is left. False on a dead branch. One pass only, over the colors with at most
        `widest` cells left."""
        dropped = False
        for i in self.unplaced:
            rest = masks[i]
            if rest & (rest - 1) == 0 or rest.bit_count() > widest:
                continue
            while rest:
                bit = rest & -rest
                rest ^= bit
                charge(1)
                trial = [mask & ~bit for mask in masks]
                trial[i] = bit
                if not self.settle(trial):
                    masks[i] &= ~bit
                    dropped = True
            if not masks[i]:
                return False
        return not dropped or self.settle(masks)

    def _tighten(self, fact: _Fact, masks: list[int]) -> bool | None:
        """Drop candidates that leave `fact` no way to hold. None if nothing within the
        candidates can satisfy it, else whether any candidate was dropped."""
        if fact.subject < 0:
            return self._tighten_group(fact, fact.region, masks)
        at = self.filled.at.get(fact.subject)
        if at is not None:
            return self._tighten_group(fact, self.counts.near[at.bit_length() - 1], masks)
        return self._tighten_subject(fact, masks)

    def _tighten_group(self, fact: _Fact, group: int, masks: list[int]) -> bool | None:
        filled = self.filled
        outside = ~group
        must_set = may_set = 0
        for i in self.unplaced:
            mask = masks[i]
            if mask & group:
                if mask & outside:
                    may_set |= 1 << i
                else:
                    must_set |= 1 << i
        census = _Census(fact, group, filled, must_set, may_set)
        if not census.possible():
            return None
        # Each color is tested against the counts taken before any of them moved. A color
        # moved in or out only narrows what is possible, so the older counts are looser,
        # never stricter, and what they rule out is still ruled out.
        changed = False
        for side, matches in ((fact.matching, True), (~fact.matching, False)):
            movers = may_set & side
            if not movers:
                continue
            can_in, can_out = census.moves(matches)
            if can_in and can_out:
                continue
            keep = group if can_in else outside
            while movers:
                low = movers & -movers
                movers ^= low
                masks[low.bit_length() - 1] &= keep
            changed = True
        return changed

    def _tighten_subject(self, fact: _Fact, masks: list[int]) -> bool | None:
        """The fact's color is not placed: keep the cells where its neighbours could still
        make the fact hold, and keep another color on a cell only if some kept cell of the
        fact's color lets the fact hold with that color there."""
        counts = self.counts
        subject = fact.subject
        # For each cell, the other colors that could take it.
        holders = [0] * len(counts.cells)
        for i in self.unplaced:
            if i == subject:
                continue
            mask = masks[i]
            color = 1 << i
            while mask:
                low = mask & -mask
                mask ^= low
                holders[low.bit_length() - 1] |= color
        spots = masks[subject]
        kept = 0
        # Colors that may still lose cells: none of the kept spots so far lets them sit
        # anywhere, and `support` holds the cells some kept spot does allow.
        open_ = 0
        for i in self.unplaced:
            if i != subject:
                open_ |= 1 << i
        support = [0] * len(masks)
        rest = spots
        while rest:
            spot = rest & -rest
            rest ^= spot
            at = spot.bit_length() - 1
            group = counts.near[at]
            touch = 0
            for cell in counts.near_cells[at]:
                touch |= holders[cell]
            elsewhere = 0
            for cell in counts.far_cells[at]:
                elsewhere |= holders[cell]
            may_set = touch & elsewhere
            census = _Census(fact, group, self.filled, touch & ~elsewhere, may_set)
            if not census.possible():
                continue
            kept |= spot
            # A color that cannot reach the group, or must land in it, sits anywhere it
            # can with the fact holding here.
            open_ &= may_set
            for side, matches in ((fact.matching, True), (~fact.matching, False)):
                movers = open_ & side
                if not movers:
                    continue
                can_in, can_out = census.moves(matches)
                if can_in and can_out:
                    open_ &= ~movers
                    continue
                keep = group if can_in else ~(group | spot)
                while movers:
                    low = movers & -movers
                    movers ^= low
                    i = low.bit_length() - 1
                    support[i] |= masks[i] & keep
        if not kept:
            return None
        changed = kept != spots
        masks[subject] = kept
        while open_:
            low = open_ & -open_
            open_ ^= low
            i = low.bit_length() - 1
            if support[i] != masks[i]:
                masks[i] = support[i]
                changed = True
        return changed

    def _keep_in_order(self, group: tuple[int, ...], masks: list[int]) -> bool:
        """Keep each color of a look-alike `group` on a later cell (row by row) than the
        one before it. Returns whether a candidate was dropped."""
        at = self.filled.at

        def cells(i: int) -> int:
            placed = at.get(i)
            return masks[i] if placed is None else placed

        changed = False
        for before, after in zip(group, group[1:], strict=False):
            first = cells(before)
            last = cells(after)
            # Cells after the first of `before`, and before the last of `after`.
            later = ~((first & -first) * 2 - 1) if first else 0
            earlier = (1 << (last.bit_length() - 1)) - 1 if last else 0
            if after not in at and masks[after] & ~later:
                masks[after] &= later
                changed = True
            if before not in at and masks[before] & ~earlier:
                masks[before] &= earlier
                changed = True
        return changed


def _numbers(mask: int) -> tuple[int, ...]:
    """The positions of the set bits of `mask`, lowest first."""
    return tuple(i for i in range(mask.bit_length()) if mask >> i & 1)
