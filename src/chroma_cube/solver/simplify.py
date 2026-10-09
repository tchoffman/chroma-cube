"""Rewrite a puzzle's clues using the fact that every one of them must hold.

Each top-level clue is true in every solution, so wherever a copy of it sits inside a
*different* clue, that copy can be read as true (and a copy of a clue whose negation is a
top-level clue as false). After the rewrite a clue may turn out always true (it is
dropped) or always false (the puzzle has no solutions). This catches contradictions the
three-valued evaluator only sees on a full board, such as "every column is alphabetical"
next to "not every column is alphabetical".

The rewrite keeps the set of solutions: a clue is only ever simplified using strictly
smaller clues, so the clues that remain imply the ones that were dropped.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from chroma_cube.core.clues import And, AtLeast, Clue, Exactly, Not, Or

Simplified = Clue | bool


_MAX_ROUNDS = 8


def simplify(clues: Sequence[Clue]) -> tuple[Clue, ...] | None:
    """Equivalent clues with known-true copies folded away, or None if they contradict."""
    current = tuple(clues)
    for _ in range(_MAX_ROUNDS):
        folded = _fold_all(tuple(_facts(current)))
        if folded is None or folded == current:
            return folded
        current = folded
    return current


def _fold_all(flat: tuple[Clue, ...]) -> tuple[Clue, ...] | None:
    true = set(flat)
    false = {clue.clue for clue in flat if isinstance(clue, Not)}
    kept: list[Clue] = []
    for clue in flat:
        result = _fold_root(clue, true, false)
        if result is False:
            return None
        if result is not True:
            kept.append(result)
    return tuple(kept)


def _facts(clues: Iterable[Clue]) -> Iterable[Clue]:
    """Split each clue into the separate clues it asserts, e.g. "not (A or B)" into
    "not A" and "not B". Together they say exactly what the original said."""
    for clue in clues:
        match clue:
            case And(clues=subs):
                yield from _facts(subs)
            case Or(clues=(only,)) | Exactly(n=1, clues=(only,)) | AtLeast(n=1, clues=(only,)):
                yield from _facts((only,))
            case Exactly(n=n, clues=subs) | AtLeast(n=n, clues=subs) if n == len(subs):
                yield from _facts(subs)
            case Exactly(n=0, clues=subs):
                yield from _facts(Not(sub) for sub in subs)
            case Not(clue=inner):
                yield from _negated_facts(inner)
            case _:
                yield clue


def _negated_facts(clue: Clue) -> Iterable[Clue]:
    """The facts asserted by "not `clue`"."""
    match clue:
        case Not(clue=inner):
            yield from _facts((inner,))
        case Or(clues=subs) | AtLeast(n=1, clues=subs):
            yield from _facts(Not(sub) for sub in subs)
        case And(clues=(only,)) | Exactly(n=1, clues=(only,)):
            yield from _negated_facts(only)
        case Exactly(n=0, clues=(only,)):
            yield from _facts((only,))
        case _:
            yield Not(clue)


def _fold_root(clue: Clue, true: set[Clue], false: set[Clue]) -> Simplified:
    """Fold a top-level clue without using what that same clue says about itself.

    A top-level `not X` is what put X in `false`, so X must not be read as false here.
    """
    if isinstance(clue, Not):
        if clue.clue in true:
            return False
        folded = _fold_children(clue.clue, true, false)
        return (not folded) if isinstance(folded, bool) else Not(folded)
    return _fold_children(clue, true, false)


def _fold(clue: Clue, true: set[Clue], false: set[Clue]) -> Simplified:
    if clue in true:
        return True
    if clue in false:
        return False
    return _fold_children(clue, true, false)


def _fold_children(clue: Clue, true: set[Clue], false: set[Clue]) -> Simplified:
    """Fold the sub-clues of `clue`, but never `clue` itself."""
    match clue:
        case Not(clue=inner):
            folded = _fold(inner, true, false)
            return (not folded) if isinstance(folded, bool) else Not(folded)
        case And(clues=subs):
            parts = [_fold(sub, true, false) for sub in subs]
            if False in parts:
                return False
            rest = tuple(part for part in parts if not isinstance(part, bool))
            return And(rest) if rest else True
        case Or(clues=subs):
            parts = [_fold(sub, true, false) for sub in subs]
            if True in parts:
                return True
            rest = tuple(part for part in parts if not isinstance(part, bool))
            return Or(rest) if rest else False
        case Exactly(n=n, clues=subs):
            need, rest = _count(n, subs, true, false)
            if not 0 <= need <= len(rest):
                return False
            return Exactly(need, rest) if rest else True
        case AtLeast(n=n, clues=subs):
            need, rest = _count(n, subs, true, false)
            if need <= 0:
                return True
            return AtLeast(need, rest) if need <= len(rest) else False
    return clue


def _count(
    n: int, subs: tuple[Clue, ...], true: set[Clue], false: set[Clue]
) -> tuple[int, tuple[Clue, ...]]:
    """How many of the undecided sub-clues still need to hold, and which they are."""
    parts = [_fold(sub, true, false) for sub in subs]
    decided_true = sum(1 for part in parts if part is True)
    return n - decided_true, tuple(part for part in parts if not isinstance(part, bool))
