"""The classic set: 25 cards on the 3x4 tray with the twelve classic colors.

Each card is one JSON file under `data/classic/`, in the format of `puzzle_to_dict`.
"""

from __future__ import annotations

import json
from functools import cache
from importlib.resources import files

from chroma_cube.core import (
    And,
    AtLeast,
    BoardRule,
    Clue,
    Exactly,
    Not,
    Or,
    Property,
    Puzzle,
    Relation,
    puzzle_from_dict,
)

CARD_COUNT = 25

DIFFICULTIES = ("easy", "medium", "hard", "expert")
"""The difficulty labels, easiest first."""


@cache
def classic_puzzles() -> tuple[Puzzle, ...]:
    """The classic cards, easiest first."""
    folder = files(__package__).joinpath("data", "classic")
    return tuple(
        puzzle_from_dict(
            json.loads(folder.joinpath(f"classic-{n:02d}.json").read_text(encoding="utf-8"))
        )
        for n in range(1, CARD_COUNT + 1)
    )


def classic_puzzle(number: int) -> Puzzle:
    """Card `number`, counting from 1. Raises `ValueError` for a card that does not exist."""
    if not 1 <= number <= CARD_COUNT:
        raise ValueError(f"the classic set has cards 1 to {CARD_COUNT}, not {number}")
    return classic_puzzles()[number - 1]


def clue_kinds(clue: Clue) -> frozenset[str]:
    """The kinds of clue a player has to understand to read `clue`.

    Relation, property and board-rule kinds by name, plus "not", "or", "exactly",
    "at_least" and "initial" (a color named by its first letter). "and" is left out: it
    only groups statements the player already reads one by one.
    """
    match clue:
        case Relation(kind=kind, colors=refs):
            initial = {"initial"} if any(r.by_initial for r in refs) else set()
            return frozenset({kind} | initial)
        case Property(kind=kind, color=color_ref):
            return frozenset({kind, "initial"} if color_ref.by_initial else {kind})
        case BoardRule(kind=kind):
            return frozenset({kind})
        case Not(clue=inner):
            return frozenset({"not"}) | clue_kinds(inner)
        case And(clues=subs):
            return _union(subs)
        case Or(clues=subs):
            return frozenset({"or"}) | _union(subs)
        case Exactly(clues=subs):
            return frozenset({"exactly"}) | _union(subs)
        case AtLeast(clues=subs):
            return frozenset({"at_least"}) | _union(subs)
    raise TypeError(f"not a clue: {clue!r}")


def _union(clues: tuple[Clue, ...]) -> frozenset[str]:
    return frozenset().union(*(clue_kinds(sub) for sub in clues))


def difficulty_score(puzzle: Puzzle) -> int:
    """A rough difficulty: cubes left to place plus distinct kinds of clue on the card."""
    unplaced = len(puzzle.givens.unplaced(puzzle.palette))
    kinds = frozenset().union(*(clue_kinds(clue) for clue in puzzle.clues))
    return unplaced + len(kinds)
