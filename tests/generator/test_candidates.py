"""The candidate pool: clues that are true on a solution, drawn from the whole vocabulary."""

import random

import pytest

from chroma_cube.core import (
    CLASSIC_BOARD,
    CLASSIC_PALETTE,
    AtLeast,
    BoardRule,
    Exactly,
    Not,
    Or,
    Placement,
    Property,
    Relation,
    evaluate,
    prop,
    relation,
)
from chroma_cube.core.evaluate import Truth
from chroma_cube.generator.candidates import candidate_pool, clue_features, holds, random_solution
from chroma_cube.generator.profiles import PROFILES
from tests.core.helpers import FULL


def _solution(seed: int) -> Placement:
    return random_solution(random.Random(seed), CLASSIC_BOARD, CLASSIC_PALETTE)


def test_random_solution_fills_the_board() -> None:
    solution = _solution(1)
    assert solution.is_complete(CLASSIC_PALETTE)
    assert set(solution.assignments.values()) == set(CLASSIC_BOARD)


def test_random_solution_is_deterministic_per_seed() -> None:
    assert _solution(5) == _solution(5)
    assert _solution(5) != _solution(6)


@pytest.mark.parametrize("seed", range(5))
def test_every_candidate_is_true_on_the_solution(seed: int) -> None:
    solution = _solution(seed)
    pool = candidate_pool(
        random.Random(seed), solution, CLASSIC_BOARD, CLASSIC_PALETTE, PROFILES["expert"].features
    )
    assert len(pool) > 100
    for clue in pool:
        assert evaluate(clue, solution, CLASSIC_BOARD, CLASSIC_PALETTE) is Truth.SATISFIED, clue


@pytest.mark.parametrize("seed", range(5))
def test_fast_holds_agrees_with_the_evaluator(seed: int) -> None:
    rng = random.Random(seed)
    pool = candidate_pool(
        rng, _solution(seed), CLASSIC_BOARD, CLASSIC_PALETTE, PROFILES["expert"].features
    )
    others = [_solution(1000 + i) for i in range(10)] + [FULL]
    for other in others:
        for clue in pool:
            expected = evaluate(clue, other, CLASSIC_BOARD, CLASSIC_PALETTE) is Truth.SATISFIED
            assert holds(clue, other, CLASSIC_BOARD, CLASSIC_PALETTE) == expected, clue


@pytest.mark.parametrize("difficulty", ["easy", "medium", "hard", "expert"])
def test_pool_only_uses_allowed_features(difficulty: str) -> None:
    allowed = PROFILES[difficulty].features
    pool = candidate_pool(random.Random(3), _solution(3), CLASSIC_BOARD, CLASSIC_PALETTE, allowed)
    for clue in pool:
        assert clue_features(clue) <= allowed, clue


def test_expert_pool_covers_the_vocabulary() -> None:
    solution = _solution(2)
    pool = candidate_pool(
        random.Random(2), solution, CLASSIC_BOARD, CLASSIC_PALETTE, PROFILES["expert"].features
    )
    seen = set().union(*(clue_features(clue) for clue in pool))
    for feature in ("between", "knows", "diagonal", "directly_above", "in_corner", "initial"):
        assert feature in seen
    for feature in ("not", "or", "exactly", "at_least"):
        assert feature in seen


def test_or_candidates_join_one_true_and_one_false_clue() -> None:
    solution = _solution(4)
    pool = candidate_pool(
        random.Random(4), solution, CLASSIC_BOARD, CLASSIC_PALETTE, PROFILES["medium"].features
    )
    ors = [clue for clue in pool if isinstance(clue, Or)]
    assert ors
    for clue in ors:
        truths = [holds(sub, solution, CLASSIC_BOARD, CLASSIC_PALETTE) for sub in clue.clues]
        assert sorted(truths) == [False, True]


def test_not_candidates_negate_false_clues() -> None:
    solution = _solution(4)
    pool = candidate_pool(
        random.Random(4), solution, CLASSIC_BOARD, CLASSIC_PALETTE, PROFILES["medium"].features
    )
    nots = [clue for clue in pool if isinstance(clue, Not)]
    assert any(isinstance(clue.clue, Property) for clue in nots)


def test_initials_only_where_two_colors_share_the_letter() -> None:
    pool = candidate_pool(
        random.Random(8), _solution(8), CLASSIC_BOARD, CLASSIC_PALETTE, PROFILES["hard"].features
    )
    letters = set()
    for clue in pool:
        if isinstance(clue, Relation):
            letters |= {r.key for r in clue.colors if r.by_initial}
        if isinstance(clue, Property) and clue.color.by_initial:
            letters.add(clue.color.key)
    assert letters
    assert letters <= {"B", "C", "M"}


def test_board_rules_only_when_they_hold() -> None:
    expert = PROFILES["expert"].features
    pool = candidate_pool(random.Random(1), FULL, CLASSIC_BOARD, CLASSIC_PALETTE, expert)
    assert BoardRule("rows_alphabetical") in pool
    assert BoardRule("columns_alphabetical") in pool
    for seed in range(5):
        other = candidate_pool(
            random.Random(seed), _solution(seed), CLASSIC_BOARD, CLASSIC_PALETTE, expert
        )
        for clue in other:
            if isinstance(clue, BoardRule):
                assert holds(clue, _solution(seed), CLASSIC_BOARD, CLASSIC_PALETTE)


def test_counting_candidates_count_correctly() -> None:
    solution = _solution(6)
    pool = candidate_pool(
        random.Random(6), solution, CLASSIC_BOARD, CLASSIC_PALETTE, PROFILES["expert"].features
    )
    counts = [clue for clue in pool if isinstance(clue, Exactly | AtLeast)]
    assert counts
    assert any(
        not all(holds(sub, solution, CLASSIC_BOARD, CLASSIC_PALETTE) for sub in clue.clues)
        for clue in counts
    )


def test_features_of_compound_clues() -> None:
    clue = Or((Not(prop("in_corner", "B")), relation("knows", "black", "white")))
    assert clue_features(clue) == {"or", "not", "in_corner", "initial", "knows"}
    assert clue_features(BoardRule("rows_alphabetical")) == {"rows_alphabetical"}
