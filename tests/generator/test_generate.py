"""The generator: deterministic, unique, minimal puzzles that follow their difficulty profile."""

import json
import os
import subprocess
import sys
import time
from collections import Counter
from dataclasses import replace

import pytest

from chroma_cube.core import (
    CLASSIC_PALETTE,
    And,
    AtLeast,
    Board,
    Color,
    Exactly,
    Or,
    Palette,
    Property,
    Puzzle,
    puzzle_to_dict,
)
from chroma_cube.core.parse import parse_clue
from chroma_cube.generator import DIFFICULTIES, PROFILES, Difficulty, clue_features, generate
from chroma_cube.generator.build import primary_kind
from chroma_cube.generator.candidates import clue_colors
from chroma_cube.solver import is_unique, solve
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


def test_clues_render_as_english_that_parses_back() -> None:
    for puzzle in _sample():
        for clue, text in zip(puzzle.clues, puzzle.rendered_clues(), strict=True):
            assert parse_clue(text, puzzle.palette, puzzle.board) == clue, text


def test_compound_clues_have_no_part_only_about_given_cubes() -> None:
    for puzzle in _sample():
        for clue in puzzle.clues:
            if isinstance(clue, Or | Exactly | AtLeast | And):
                for part in clue.clues:
                    colors = clue_colors(part, puzzle.palette)
                    assert not all(c in puzzle.givens.assignments for c in colors), (
                        puzzle.id,
                        puzzle.rendered_clues(),
                    )


def test_each_level_has_its_own_solution_for_the_same_seed() -> None:
    solutions = {solve(generated(0, level)).solutions[0] for level in DIFFICULTIES}
    assert len(solutions) == len(DIFFICULTIES)


def test_hard_puzzles_vary_their_clue_families() -> None:
    puzzles = [generated(seed, "hard") for seed in range(20)]
    without_between = [
        p for p in puzzles if not any("between" in clue_features(c) for c in p.clues)
    ]
    assert len(without_between) >= 5


def test_no_cube_is_pinned_by_a_row_and_a_column_clue() -> None:
    for puzzle in _sample():
        rows = {c.color for c in puzzle.clues if isinstance(c, Property) and c.kind == "in_row"}
        cols = {c.color for c in puzzle.clues if isinstance(c, Property) and c.kind == "in_col"}
        assert not rows & cols, puzzle.id


def test_other_boards_and_palettes() -> None:
    board = Board(2, 3)
    palette = Palette(CLASSIC_PALETTE.colors[:6])
    puzzle = generate(4, "hard", board=board, palette=palette)
    assert puzzle.board == board
    assert puzzle.palette == palette
    assert is_unique(puzzle)


def _wide_palette(size: int) -> Palette:
    extra = [Color(f"extra{i}", f"Extra{i}", "#123456") for i in range(size - 12)]
    return Palette(CLASSIC_PALETTE.colors + tuple(extra))


@pytest.mark.parametrize(
    ("board", "palette"),
    [
        (Board(2, 2), Palette(CLASSIC_PALETTE.colors[:4])),
        (Board(4, 4), _wide_palette(16)),
    ],
)
@pytest.mark.parametrize("difficulty", DIFFICULTIES)
def test_small_and_large_boards_generate_or_refuse_quickly(
    board: Board, palette: Palette, difficulty: Difficulty
) -> None:
    start = time.perf_counter()
    try:
        puzzle = generate(3, difficulty, board=board, palette=palette)
    except ValueError:
        pass
    else:
        assert is_unique(puzzle)
    assert time.perf_counter() - start < 20


@pytest.mark.parametrize("board", [Board(1, 2), Board(1, 3), Board(5, 5)])
def test_boards_the_profiles_do_not_fit_are_refused(board: Board) -> None:
    palette = (
        _wide_palette(len(board))
        if len(board) > 12
        else Palette(CLASSIC_PALETTE.colors[: len(board)])
    )
    with pytest.raises(ValueError, match="board"):
        generate(1, "hard", board=board, palette=palette)


def test_palette_must_fill_the_board() -> None:
    with pytest.raises(ValueError, match="board"):
        generate(1, "easy", board=Board(2, 2))


def test_generation_never_exceeds_the_solver_budget() -> None:
    for puzzle in _sample():
        assert is_unique(puzzle)


def test_a_solver_that_always_gives_up_rejects_every_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import chroma_cube.generator.build as build

    monkeypatch.setattr(build, "_MAX_NODES", 1)
    monkeypatch.setattr(build, "_MAX_ATTEMPTS", 5)
    with pytest.raises(RuntimeError, match="no hard puzzle"):
        generate(1, "hard")


def test_some_expert_puzzles_use_an_alphabetical_rule() -> None:
    rules = {"rows_alphabetical", "columns_alphabetical"}
    expert = [generated(seed, "expert") for seed in SAMPLE_SEEDS]
    assert any(rules & clue_features(clue) for p in expert for clue in p.clues)
