"""Which generated puzzle is being played: its difficulty, seed, board and title.

No Textual here, so the daily seed and typed seeds are tested on their own.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, replace
from datetime import date

from chroma_cube.generator import Difficulty, layout

DAILY_DIFFICULTY: Difficulty = "medium"
MAX_SEED_DIGITS = 18
RANDOM_SEEDS = 100_000
"""Fresh seeds stay under six digits so they are easy to read out and type back."""


def daily_seed(day: date) -> int:
    """The seed for `day`'s puzzle: the date as a number, 2026-10-08 -> 20261008."""
    return int(day.strftime("%Y%m%d"))


def parse_seed(text: str) -> int:
    """A seed typed by the player: a whole number of at most 18 digits.

    Spaces and underscores anywhere are ignored, so "48 213" and "48_213" both read 48213.
    """
    digits = "".join(text.split()).replace("_", "")
    if not digits.isascii() or not digits.isdigit():
        raise ValueError("A seed is a whole number, like 48213.")
    if len(digits) > MAX_SEED_DIGITS:
        raise ValueError(f"A seed has at most {MAX_SEED_DIGITS} digits.")
    return int(digits)


def random_seed(rng: random.Random, avoid: int | None = None) -> int:
    """A fresh seed from 1 to 99999, never `avoid`."""
    while True:
        seed = rng.randrange(1, RANDOM_SEEDS)
        if seed != avoid:
            return seed


@dataclass(frozen=True)
class GameSpec:
    """Everything needed to generate one puzzle again, and how to name it."""

    difficulty: Difficulty
    seed: int
    day: date | None = None
    """Set for the daily puzzle, whose seed comes from this date."""
    layout: str = "classic"
    """The key of the board and palette played on (see `chroma_cube.generator.LAYOUTS`)."""

    @classmethod
    def infinite(cls, difficulty: Difficulty, seed: int, layout: str = "classic") -> GameSpec:
        return cls(difficulty, seed, layout=layout)

    @classmethod
    def daily(cls, day: date) -> GameSpec:
        return cls(DAILY_DIFFICULTY, daily_seed(day), day)

    @property
    def is_daily(self) -> bool:
        return self.day is not None

    @property
    def title(self) -> str:
        if self.day is not None:
            return f"Daily · {self.day.isoformat()}"
        if self.layout == "classic":
            return f"Infinite · {self.difficulty} · seed {self.seed}"
        return f"Infinite · {self.shape} · {self.difficulty} · seed {self.seed}"

    @property
    def shape(self) -> str:
        """The board as rows × columns, e.g. "4×5"."""
        board = layout(self.layout).board
        return f"{board.rows}×{board.cols}"

    def another(self, rng: random.Random) -> GameSpec:
        """A fresh infinite puzzle of the same difficulty, on the same board."""
        return GameSpec.infinite(self.difficulty, random_seed(rng, avoid=self.seed), self.layout)

    def with_seed(self, seed: int) -> GameSpec:
        """The infinite puzzle with this seed, at the same difficulty and on the same board."""
        return replace(self, seed=seed, day=None)
