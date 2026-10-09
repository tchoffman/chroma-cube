"""A speed check scaled from the target of 100 mixed puzzles in under a minute.

Twenty puzzles, five per level, must take under 18 s of wall-clock time: the rate of
100 puzzles in 90 s, which leaves headroom for a slow CI runner.
"""

import time

from chroma_cube.generator import DIFFICULTIES, generate


def test_mixed_batch_is_fast_enough() -> None:
    start = time.perf_counter()
    for seed in range(100, 105):
        for level in DIFFICULTIES:
            generate(seed, level)
    elapsed = time.perf_counter() - start
    assert elapsed < 18, f"20 puzzles took {elapsed:.1f}s"
