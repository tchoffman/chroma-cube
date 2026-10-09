"""The generator: deterministic, unique, minimal puzzles that follow their difficulty profile."""

import json
import os
import subprocess
import sys
from collections import Counter
from dataclasses import replace

import pytest

from chroma_cube.core import CLASSIC_PALETTE, Board, Palette, Puzzle, puzzle_to_dict
from chroma_cube.generator import DIFFICULTIES, PROFILES, Difficulty, clue_features, generate
from chroma_cube.generator.build import primary_kind
from chroma_cube.generator.candidates import clue_colors
from chroma_cube.solver import is_unique
from tests.generator.helpers import SAMPLE_SEEDS, generated


def _sample() -> list[Puzzle]:
    return [generated(seed, level) for level in DIFFICULTIES for seed in SAMPLE_SEEDS]


def test_same_seed_gives_the_same_puzzle() -> None:
    assert generate(7, "medium") == generated(7, "medium")


def test_same_seed_in_another_process_gives_the_same_puzzle() -> None:
    script = (
        "import json; from chroma_cube.generator import generate; "
        "from chroma_cube.core import puzzle_to_dict; "
        "print(json.dumps(puzzle_to_dict(generate(3, 'hard'))))"
    )
    outputs = set()
    for hash_seed in ("1", "2"):
        env = {**os.environ, "PYTHONHASHSEED": hash_seed}
        run = subprocess.run(
            [sys.executable, "-c", script], env=env, capture_output=True, text=True, check=True
        )
        outputs.add(run.stdout)
    assert len(outputs) == 1
    assert json.loads(outputs.pop()) == puzzle_to_dict(generated(3, "hard"))


def test_different_seeds_give_different_puzzles() -> None:
    for level in DIFFICULTIES:
        puzzles = [generated(seed, level) for seed in SAMPLE_SEEDS]
        assert len({(p.givens, p.clues) for p in puzzles}) == len(puzzles)


def test_puzzle_identity() -> None:
    puzzle = generated(5, "easy")
    assert puzzle.id == "gen-easy-5"
    assert puzzle.difficulty == "easy"
    assert puzzle.title


def test_default_difficulty_is_medium() -> None:
    assert generate(2) == generated(2, "medium")


def test_unknown_difficulty_is_rejected() -> None:
    with pytest.raises(ValueError, match="difficulty"):
        generate(1, "impossible")  # type: ignore[arg-type]


@pytest.mark.parametrize("difficulty", DIFFICULTIES)
def test_every_generated_puzzle_is_unique(difficulty: Difficulty) -> None:
    for seed in SAMPLE_SEEDS:
        assert is_unique(generated(seed, difficulty))


@pytest.mark.parametrize("difficulty", DIFFICULTIES)
def test_no_clue_is_redundant(difficulty: Difficulty) -> None:
    for seed in SAMPLE_SEEDS[:2]:
        puzzle = generated(seed, difficulty)
        for i in range(len(puzzle.clues)):
            fewer = replace(puzzle, clues=puzzle.clues[:i] + puzzle.clues[i + 1 :])
            assert not is_unique(fewer), (seed, puzzle.rendered_clues()[i])


@pytest.mark.parametrize("difficulty", DIFFICULTIES)
def test_difficulty_profile_is_honoured(difficulty: Difficulty) -> None:
    profile = PROFILES[difficulty]
    for seed in SAMPLE_SEEDS:
        puzzle = generated(seed, difficulty)
        low, high = profile.givens
        assert low <= len(puzzle.givens.assignments) <= high
        low, high = profile.clues
        assert low <= len(puzzle.clues) <= high
        used = frozenset().union(*(clue_features(clue) for clue in puzzle.clues))
        assert used <= profile.features
        if profile.signature:
            assert used & profile.signature, puzzle.rendered_clues()


def test_no_clue_is_only_about_given_cubes() -> None:
    for puzzle in _sample():
        for clue in puzzle.clues:
            colors = clue_colors(clue, puzzle.palette)
            if colors:
                assert not all(c in puzzle.givens.assignments for c in colors), clue


def test_no_single_kind_dominates() -> None:
    for puzzle in _sample():
        counts = Counter(primary_kind(clue) for clue in puzzle.clues)
        assert counts.most_common(1)[0][1] <= max(2, (len(puzzle.clues) + 1) // 2)


def test_clues_render_as_english() -> None:
    for puzzle in _sample():
        for text in puzzle.rendered_clues():
            assert isinstance(text, str)
            assert len(text) > 10
            assert "{" not in text


def test_other_boards_and_palettes() -> None:
    board = Board(2, 3)
    palette = Palette(CLASSIC_PALETTE.colors[:6])
    puzzle = generate(4, "hard", board=board, palette=palette)
    assert puzzle.board == board
    assert puzzle.palette == palette
    assert is_unique(puzzle)


def test_palette_must_fill_the_board() -> None:
    with pytest.raises(ValueError, match="board"):
        generate(1, "easy", board=Board(2, 2))


def test_generation_never_exceeds_the_solver_budget() -> None:
    for seed in range(20, 23):
        for level in DIFFICULTIES:
            assert is_unique(generate(seed, level))


def test_a_solver_that_always_gives_up_rejects_every_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import chroma_cube.generator.build as build

    monkeypatch.setattr(build, "_MAX_NODES", 1)
    monkeypatch.setattr(build, "_MAX_ATTEMPTS", 5)
    with pytest.raises(RuntimeError, match="no hard puzzle"):
        generate(1, "hard")
