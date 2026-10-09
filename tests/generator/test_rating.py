from statistics import mean

from chroma_cube.core import (
    CLASSIC_BOARD,
    CLASSIC_PALETTE,
    Clue,
    Placement,
    Puzzle,
    prop,
    relation,
)
from chroma_cube.generator import DIFFICULTIES, rate
from tests.generator.helpers import SAMPLE_SEEDS, generated


def _puzzle(clues: tuple[Clue, ...], givens: Placement | None = None) -> Puzzle:
    return Puzzle("t", "t", CLASSIC_BOARD, CLASSIC_PALETTE, givens or Placement(), clues)


def test_report_counts_givens_clues_and_features() -> None:
    black = CLASSIC_PALETTE.by_id("black")
    puzzle = _puzzle(
        (relation("next_to", "black", "white"), prop("in_corner", "B")),
        Placement({black: CLASSIC_BOARD.row(0)[0]}),
    )
    report = rate(puzzle)
    assert report.givens == 1
    assert report.clues == 2
    assert report.features == ("in_corner", "initial", "next_to")
    assert report.score > 0


def test_fewer_givens_and_cryptic_clues_score_higher() -> None:
    plain = _puzzle((relation("next_to", "black", "white"),))
    cryptic = _puzzle((relation("knows", "B", "white"),))
    assert rate(cryptic).score > rate(plain).score


def test_generated_levels_rate_in_order() -> None:
    means = [
        mean(rate(generated(seed, level)).score for seed in SAMPLE_SEEDS) for level in DIFFICULTIES
    ]
    assert means == sorted(means)
    assert len(set(means)) == len(means)
