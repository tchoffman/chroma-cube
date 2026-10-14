"""Generated puzzles shared by the generator tests, so each is built once per run."""

import time
from collections import Counter
from functools import cache

from chroma_cube.core import BOARD_4X4, BOARD_4X5, EXTENDED_16, EXTENDED_20, Puzzle
from chroma_cube.generator import Difficulty, generate

SAMPLE_SEEDS = range(7)
"""Seeds generated for every difficulty: 28 puzzles in all."""


@cache
def generated(seed: int, difficulty: Difficulty) -> Puzzle:
    return generate(seed, difficulty)


BUILD_SECONDS: Counter[tuple[int, int]] = Counter()
"""Time spent generating the cached larger-board puzzles, per board shape."""


@cache
def extended(seed: int, difficulty: Difficulty, rows: int, cols: int) -> Puzzle:
    board, palette = {(4, 4): (BOARD_4X4, EXTENDED_16), (4, 5): (BOARD_4X5, EXTENDED_20)}[
        (rows, cols)
    ]
    start = time.perf_counter()
    puzzle = generate(seed, difficulty, board=board, palette=palette)
    BUILD_SECONDS[(rows, cols)] += time.perf_counter() - start
    return puzzle
