"""Difficulty profiles: how many cubes are given, how many clues, and which clue kinds."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Difficulty = Literal["easy", "medium", "hard", "expert"]

DIFFICULTIES: tuple[Difficulty, ...] = ("easy", "medium", "hard", "expert")


@dataclass(frozen=True)
class Profile:
    """What a puzzle of one difficulty looks like.

    `givens` and `clues` are inclusive ranges. `features` are the clue features (see
    `clue_features`) a clue may use. A puzzle must use at least one of `signature`, the
    features that set this level apart from the one below; an empty signature asks
    for nothing.
    """

    givens: tuple[int, int]
    clues: tuple[int, int]
    features: frozenset[str]
    signature: frozenset[str] = frozenset()


_POSITIONS = frozenset(
    {
        "same_row",
        "same_column",
        "next_to",
        "above",
        "below",
        "left_of",
        "right_of",
        "directly_above",
        "directly_below",
        "directly_left_of",
        "directly_right_of",
    }
)
_REGIONS_AND_LOGIC = frozenset(
    {"in_corner", "on_edge", "in_center", "in_row", "in_col", "not", "or"}
)
_CRYPTIC = frozenset({"knows", "diagonal", "between", "initial", "and"})
_COUNTING_AND_RULES = frozenset(
    {"exactly", "at_least", "rows_alphabetical", "columns_alphabetical"}
)

PROFILES: dict[Difficulty, Profile] = {
    "easy": Profile(givens=(5, 7), clues=(3, 5), features=_POSITIONS),
    "medium": Profile(
        givens=(2, 4),
        clues=(4, 7),
        features=_POSITIONS | _REGIONS_AND_LOGIC,
        signature=_REGIONS_AND_LOGIC,
    ),
    "hard": Profile(
        givens=(0, 1),
        clues=(5, 8),
        features=_POSITIONS | _REGIONS_AND_LOGIC | _CRYPTIC,
        signature=_CRYPTIC - {"and"},
    ),
    "expert": Profile(
        givens=(0, 0),
        clues=(3, 7),
        features=_POSITIONS | _REGIONS_AND_LOGIC | _CRYPTIC | _COUNTING_AND_RULES,
        signature=_COUNTING_AND_RULES,
    ),
}
"""The four levels, easiest first."""
