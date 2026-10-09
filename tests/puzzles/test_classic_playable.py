from itertools import permutations

from chroma_cube.core import Placement, Puzzle, Truth, evaluate
from chroma_cube.puzzles import classic_puzzles


def solutions(puzzle: Puzzle) -> list[Placement]:
    free = [cell for cell in puzzle.board if puzzle.givens.color_at(cell) is None]
    rest = puzzle.givens.unplaced(puzzle.palette)
    found = []
    for cells in permutations(free, len(rest)):
        placement = Placement({**puzzle.givens.assignments, **dict(zip(rest, cells, strict=True))})
        if all(
            evaluate(clue, placement, puzzle.board, puzzle.palette) is Truth.SATISFIED
            for clue in puzzle.clues
        ):
            found.append(placement)
    return found


def test_there_is_at_least_one_card() -> None:
    assert classic_puzzles()


def test_every_card_fills_its_board_and_can_be_solved() -> None:
    for puzzle in classic_puzzles():
        assert len(puzzle.palette) == len(puzzle.board)
        if len(puzzle.givens.unplaced(puzzle.palette)) <= 6:
            assert solutions(puzzle), puzzle.id
