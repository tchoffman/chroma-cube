"""Attribute clues in the generator, and puzzles on the larger boards."""

import hashlib
import json
import random
from dataclasses import replace

import pytest

from chroma_cube.core import (
    BOARD_4X4,
    BOARD_4X5,
    CLASSIC_BOARD,
    CLASSIC_PALETTE,
    EXTENDED_16,
    EXTENDED_20,
    Board,
    Not,
    Palette,
    Placement,
    Puzzle,
    attribute_clues,
    evaluate,
    puzzle_to_dict,
)
from chroma_cube.core.clues import ATTRIBUTE_KINDS, AttributeClue, Clue, Region, attribute
from chroma_cube.core.evaluate import Truth
from chroma_cube.core.parse import parse_clue
from chroma_cube.generator import DIFFICULTIES, LAYOUTS, Difficulty, clue_features, generate
from chroma_cube.generator.candidates import (
    attribute_meaning,
    candidate_pool,
    cells_of,
    compile_clue,
    disguised_by_givens,
    random_solution,
)
from chroma_cube.generator.profiles import PROFILES
from chroma_cube.solver import is_unique
from tests.generator.helpers import BUILD_SECONDS, SAMPLE_SEEDS, extended, generated

ATTRIBUTES = frozenset(ATTRIBUTE_KINDS)
EXTENDED = [(BOARD_4X4, EXTENDED_16), (BOARD_4X5, EXTENDED_20)]


def _attribute_clues(puzzle: Puzzle) -> list[Clue]:
    return [clue for clue in puzzle.clues if clue_features(clue) & ATTRIBUTES]


def _pool(seed: int, board: Board, palette: Palette, level: Difficulty = "expert") -> list[Clue]:
    rng = random.Random(seed)
    solution = random_solution(rng, board, palette)
    return candidate_pool(rng, solution, board, palette, PROFILES[level].features)


# --------------------------------------------------------------------------- truth


@pytest.mark.parametrize(("board", "palette"), [(CLASSIC_BOARD, CLASSIC_PALETTE), *EXTENDED])
def test_compiled_attribute_clues_agree_with_the_evaluator(board: Board, palette: Palette) -> None:
    rng = random.Random(len(board))
    placements = [random_solution(rng, board, palette) for _ in range(6)]
    for clue in attribute_clues(board, palette):
        check = compile_clue(clue, board, palette)
        for placement in placements:
            expected = evaluate(clue, placement, board, palette) is Truth.SATISFIED
            assert check(cells_of(placement, palette)) == expected, clue


def test_attribute_clues_with_an_initial_subject_compile() -> None:
    clue = attribute("neighbours_some", "dark", color="M")
    placement = random_solution(random.Random(3), CLASSIC_BOARD, CLASSIC_PALETTE)
    expected = evaluate(clue, placement, CLASSIC_BOARD, CLASSIC_PALETTE) is Truth.SATISFIED
    check = compile_clue(clue, CLASSIC_BOARD, CLASSIC_PALETTE)
    assert check(cells_of(placement, CLASSIC_PALETTE)) == expected


def test_attribute_features() -> None:
    clue = attribute("region_count", "light", region=Region("row", 0), n=2)
    assert clue_features(clue) == {"region_count"}
    assert clue_features(Not(attribute("neighbours_some", "warm", color="mint"))) == {
        "not",
        "neighbours_some",
    }
    assert clue_features(attribute("next_to_family", "green", color="C")) == {
        "next_to_family",
        "initial",
    }


# --------------------------------------------------------------------------- the pool


@pytest.mark.parametrize("seed", range(3))
def test_the_pool_offers_attribute_clues_only_at_hard_and_expert(seed: int) -> None:
    for level in DIFFICULTIES:
        pool = _pool(seed, CLASSIC_BOARD, CLASSIC_PALETTE, level)
        has = any(clue_features(clue) & ATTRIBUTES for clue in pool)
        assert has == (level in ("hard", "expert")), level


@pytest.mark.parametrize(("board", "palette"), [(CLASSIC_BOARD, CLASSIC_PALETTE), *EXTENDED])
@pytest.mark.parametrize("seed", range(3))
def test_pooled_attribute_clues_are_true_and_never_equivalent(
    board: Board, palette: Palette, seed: int
) -> None:
    rng = random.Random(seed)
    solution = random_solution(rng, board, palette)
    pool = candidate_pool(rng, solution, board, palette, PROFILES["expert"].features)
    meanings = []
    for clue in pool:
        if clue_features(clue) & ATTRIBUTES:
            assert evaluate(clue, solution, board, palette) is Truth.SATISFIED, clue
            meaning = attribute_meaning(clue, board, palette)
            assert meaning is not None, clue
            meanings.append(meaning)
    assert meanings
    assert len(meanings) == len(set(meanings))


def test_known_equivalent_pairs_share_a_meaning() -> None:
    board, palette = CLASSIC_BOARD, CLASSIC_PALETTE
    corners = Region("corners")
    pairs: list[tuple[Clue, Clue]] = [
        (
            attribute("region_all", "warm", region=corners),
            attribute("region_count", "warm", region=corners, n=4),
        ),
        (
            attribute("neighbours_all", "light", color="mint"),
            Not(attribute("neighbours_some", "dark", color="mint")),
        ),
        (
            attribute("next_to_family", "grey", color="mint"),
            attribute("neighbours_some", "neutral", color="mint"),
        ),
        (
            attribute("region_count", "dark", region=Region("center"), n=1),
            attribute("region_count", "dark", region=Region("edge"), n=4),
        ),
        (
            attribute("region_count", "light", region=Region("row", 0), n=3),
            attribute("region_count", "dark", region=Region("row", 0), n=1),
        ),
    ]
    for first, second in pairs:
        meaning = attribute_meaning(first, board, palette)
        assert meaning is not None
        assert meaning == attribute_meaning(second, board, palette), (first, second)


def test_clues_that_are_plainer_clues_in_disguise_have_no_meaning() -> None:
    board, palette = CLASSIC_BOARD, CLASSIC_PALETTE
    disguised = [
        # Orange is the only orange color: this is "Mint sits next to Orange".
        attribute("next_to_family", "orange", color="mint"),
        # Black is the only neutral color other than White: "White sits next to Black".
        attribute("neighbours_some", "neutral", color="white"),
        # Black and White are both neutral, so this one is a real attribute clue.
        AttributeClue("region_count", "neutral", region=Region("row", 0), n=0),
    ]
    assert attribute_meaning(disguised[0], board, palette) is None
    assert attribute_meaning(disguised[1], board, palette) is None
    # Two neutral colors in a region: not a disguise.
    assert attribute_meaning(disguised[2], board, palette) is not None


def test_a_count_that_cannot_hold_has_no_meaning() -> None:
    # Ten edge cells and seven light colors: some edge cube is always dark.
    never = attribute("region_all", "light", region=Region("edge"))
    assert attribute_meaning(never, CLASSIC_BOARD, CLASSIC_PALETTE) is None
    assert attribute_meaning(Not(never), CLASSIC_BOARD, CLASSIC_PALETTE) is None


def test_givens_can_turn_an_attribute_clue_into_a_plain_one() -> None:
    board, palette = BOARD_4X4, EXTENDED_16
    coral, purple = palette.by_id("coral"), palette.by_id("purple")
    apart = Placement({coral: board.row(0)[0], purple: board.row(3)[3]})
    beside = Placement({coral: board.row(0)[0], purple: board.row(0)[1]})
    # Purple and Lavender are the purples; with Purple given far away, only Lavender is left.
    clue = attribute("next_to_family", "purple", color="coral")
    assert attribute_meaning(clue, board, palette) is not None
    assert disguised_by_givens(clue, apart, board, palette)
    assert not disguised_by_givens(clue, beside, board, palette)
    assert not disguised_by_givens(clue, Placement(), board, palette)
    # The subject not given: nothing is known about its neighbours.
    assert not disguised_by_givens(
        attribute("next_to_family", "purple", color="mint"), apart, board, palette
    )


def test_givens_can_leave_a_region_count_about_one_cube() -> None:
    board, palette = CLASSIC_BOARD, CLASSIC_PALETTE
    black = palette.by_id("black")
    corners = Region("corners")
    # Black and White are the neutral colors; with Black given, the count is about White.
    clue = attribute("region_count", "neutral", region=corners, n=1)
    given = Placement({black: board.row(0)[0]})
    assert disguised_by_givens(clue, given, board, palette)
    assert not disguised_by_givens(clue, Placement(), board, palette)


def test_generated_puzzles_hold_no_clue_the_givens_disguise() -> None:
    puzzles = [
        extended(seed, level, *shape)
        for shape in [(4, 4), (4, 5)]
        for level in ("hard", "expert")
        for seed in range(2)
    ]
    for puzzle in puzzles:
        for clue in puzzle.clues:
            assert not disguised_by_givens(clue, puzzle.givens, puzzle.board, puzzle.palette)


# --------------------------------------------------------------------------- generated


def test_some_hard_and_expert_puzzles_use_an_attribute_clue() -> None:
    puzzles = [generated(seed, level) for level in ("hard", "expert") for seed in SAMPLE_SEEDS]
    with_attribute = [p for p in puzzles if _attribute_clues(p)]
    assert len(with_attribute) >= len(puzzles) // 4, len(with_attribute)


def test_easy_and_medium_classic_puzzles_never_use_an_attribute_clue() -> None:
    for level in ("easy", "medium"):
        for seed in SAMPLE_SEEDS:
            assert not _attribute_clues(generated(seed, level))


def test_no_puzzle_offers_two_equivalent_attribute_clues() -> None:
    puzzles = [generated(seed, level) for level in ("hard", "expert") for seed in SAMPLE_SEEDS]
    puzzles += [extended(seed, "hard", 4, 4) for seed in range(3)]
    for puzzle in puzzles:
        meanings = [attribute_meaning(c, puzzle.board, puzzle.palette) for c in puzzle.clues]
        found = [m for m in meanings if m is not None]
        assert len(found) == len(set(found)), puzzle.id


CLASSIC_HASHES = {
    "easy-1": "078319856aa1be41",
    "easy-20261008": "ffe3284c0cdb2269",
    "medium-1": "633a0439ef58ebf1",
    "medium-2": "aa33bae5f66df840",
    "medium-20261008": "f6b42989a78dcefd",
    "medium-20261014": "c087848741f9a664",
}
"""Puzzles generated before attribute clues reached the generator. Daily puzzles are
medium on the classic tray, so these must never change."""


@pytest.mark.parametrize("key", sorted(CLASSIC_HASHES))
def test_easy_and_medium_classic_puzzles_are_unchanged(key: str) -> None:
    level, seed = key.split("-")
    puzzle = generate(int(seed), level)  # type: ignore[arg-type]
    digest = hashlib.sha256(json.dumps(puzzle_to_dict(puzzle), sort_keys=True).encode())
    assert digest.hexdigest()[:16] == CLASSIC_HASHES[key]
    assert puzzle.id == f"gen-{level}-{seed}"


# --------------------------------------------------------------------------- larger boards


def test_layouts() -> None:
    assert [layout.key for layout in LAYOUTS] == ["classic", "4x4", "4x5"]
    assert [(layout.board, layout.palette) for layout in LAYOUTS] == [
        (CLASSIC_BOARD, CLASSIC_PALETTE),
        (BOARD_4X4, EXTENDED_16),
        (BOARD_4X5, EXTENDED_20),
    ]


@pytest.mark.parametrize("shape", [(4, 4), (4, 5)])
@pytest.mark.parametrize("difficulty", DIFFICULTIES)
def test_larger_boards_generate_unique_puzzles_that_read_back(
    shape: tuple[int, int], difficulty: Difficulty
) -> None:
    for seed in range(2):
        puzzle = extended(seed, difficulty, *shape)
        assert puzzle.id == f"gen-{shape[0]}x{shape[1]}-{difficulty}-{seed}"
        assert is_unique(puzzle)
        for clue, text in zip(puzzle.clues, puzzle.rendered_clues(), strict=True):
            assert parse_clue(text, puzzle.palette, puzzle.board) == clue, text


def test_larger_boards_are_minimal() -> None:
    for shape in [(4, 4), (4, 5)]:
        for level in ("hard", "expert"):
            puzzle = extended(0, level, *shape)
            for i in range(len(puzzle.clues)):
                fewer = replace(puzzle, clues=puzzle.clues[:i] + puzzle.clues[i + 1 :])
                assert not is_unique(fewer), (puzzle.id, puzzle.rendered_clues()[i])


def test_a_palette_other_than_the_boards_own_is_named_in_the_id() -> None:
    palette = Palette(tuple(reversed(EXTENDED_16.colors)))
    puzzle = generate(1, "easy", board=BOARD_4X4, palette=palette)
    assert puzzle.id.startswith("gen-4x4-")
    assert puzzle.id.endswith("-easy-1")
    assert puzzle.id != "gen-4x4-easy-1"


def test_larger_board_puzzles_use_attribute_clues() -> None:
    puzzles = [
        extended(seed, level, *shape)
        for shape in [(4, 4), (4, 5)]
        for level in ("hard", "expert")
        for seed in range(2)
    ]
    assert any(_attribute_clues(p) for p in puzzles)


@pytest.mark.parametrize("shape", [(4, 4), (4, 5)], ids=["4x4", "4x5"])
def test_larger_boards_are_fast_enough(shape: tuple[int, int]) -> None:
    """Eight puzzles, two per level, inside the per-board bar (see the decisions log).

    These are the puzzles the uniqueness tests check, timed when first built.
    """
    for seed in range(2):
        for level in DIFFICULTIES:
            extended(seed, level, *shape)
    assert BUILD_SECONDS[shape] < 40, f"8 puzzles took {BUILD_SECONDS[shape]:.1f}s"
