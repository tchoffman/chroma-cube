"""Generated puzzles shared by the generator tests, so each is built once per run."""

from functools import cache

from chroma_cube.core import Puzzle
from chroma_cube.generator import Difficulty, generate

SAMPLE_SEEDS = range(7)
"""Seeds generated for every difficulty: 28 puzzles in all."""


@cache
def generated(seed: int, difficulty: Difficulty) -> Puzzle:
    return generate(seed, difficulty)
