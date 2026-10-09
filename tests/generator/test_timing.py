"""A generous speed check: a mixed batch must not take seconds per puzzle."""

import time

from chroma_cube.generator import DIFFICULTIES, generate


def test_mixed_batch_is_fast_enough() -> None:
    start = time.process_time()
    for seed in range(100, 103):
        for level in DIFFICULTIES:
            generate(seed, level)
    elapsed = time.process_time() - start
    assert elapsed < 12 * 3, f"12 puzzles took {elapsed:.1f}s of CPU"
