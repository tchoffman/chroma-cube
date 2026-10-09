"""Seeds for generated puzzles: the daily seed, typed seeds and play titles."""

import random
from datetime import date

import pytest

from chroma_cube.ui.seeds import GameSpec, daily_seed, parse_seed, random_seed


def test_the_daily_seed_is_the_date_as_a_number() -> None:
    assert daily_seed(date(2026, 10, 8)) == 20261008


def test_different_days_get_different_seeds() -> None:
    assert daily_seed(date(2026, 10, 8)) != daily_seed(date(2026, 10, 9))


@pytest.mark.parametrize(
    ("text", "seed"),
    [("48213", 48213), ("  7 ", 7), ("0", 0), ("20261008", 20261008), ("48_213", 48213), ("48 213", 48213)],
)
def test_parse_seed_reads_whole_numbers(text: str, seed: int) -> None:
    assert parse_seed(text) == seed


@pytest.mark.parametrize("text", ["", "   ", "-4", "4.5", "abc", "1e5", "9" * 19])
def test_parse_seed_rejects_anything_else(text: str) -> None:
    with pytest.raises(ValueError):
        parse_seed(text)


def test_random_seed_is_typeable_and_avoids_the_current_one() -> None:
    rng = random.Random(1)
    seeds = {random_seed(rng, avoid=5) for _ in range(500)}
    assert 5 not in seeds
    assert all(0 < seed < 100_000 for seed in seeds)


def test_titles() -> None:
    assert GameSpec.infinite("hard", 48213).title == "Infinite · hard · seed 48213"
    daily = GameSpec.daily(date(2026, 10, 8))
    assert daily.title == "Daily · 2026-10-08"
    assert (daily.difficulty, daily.seed) == ("medium", 20261008)
    assert daily.is_daily and not GameSpec.infinite("easy", 1).is_daily


def test_another_keeps_the_difficulty_and_changes_the_seed() -> None:
    spec = GameSpec.infinite("expert", 3)
    other = spec.another(random.Random(0))
    assert other.difficulty == "expert" and other.seed != 3
    assert spec.with_seed(48213) == GameSpec.infinite("expert", 48213)
