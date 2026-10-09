"""A simple difficulty rating that the UI can show next to a puzzle."""

from __future__ import annotations

from dataclasses import dataclass

from chroma_cube.core.puzzle import Puzzle
from chroma_cube.generator.candidates import clue_features

_WEIGHTS = {
    "in_corner": 2, "on_edge": 2, "in_center": 2, "in_row": 2, "in_col": 2,
    "not": 2, "or": 2,
    "knows": 3, "diagonal": 3, "between": 3, "and": 3, "initial": 3,
    "exactly": 4, "at_least": 4, "rows_alphabetical": 4, "columns_alphabetical": 4,
}  # fmt: skip
"""Extra effort a feature asks of the player; anything not listed (positions) weighs 1."""
_FREE_CUBE = 3


@dataclass(frozen=True)
class DifficultyReport:
    """How hard a puzzle looks.

    `score` is three points per cube the player must place, plus, for every clue, the
    weight of its hardest feature. It is a rough guide, not a measure of solving time.
    """

    givens: int
    clues: int
    features: tuple[str, ...]
    score: int


def rate(puzzle: Puzzle) -> DifficultyReport:
    """Rate a puzzle from its givens and the clue features it uses."""
    givens = len(puzzle.givens.assignments)
    features = [clue_features(clue) for clue in puzzle.clues]
    score = _FREE_CUBE * (len(puzzle.palette) - givens) + sum(
        max(_WEIGHTS.get(feature, 1) for feature in used) for used in features
    )
    return DifficultyReport(
        givens=givens,
        clues=len(puzzle.clues),
        features=tuple(sorted(frozenset().union(*features))),
        score=score,
    )
