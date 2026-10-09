"""The classic set: 25 cards on the 3x4 tray with the twelve classic colors.

Each card is one JSON file under `data/classic/`, in the format of `puzzle_to_dict`.
"""

from __future__ import annotations

import json
from functools import cache
from importlib.resources import files

from chroma_cube.core import (
    And,
    AtLeast,
    BoardRule,
    Cell,
    Clue,
    Color,
    ColorRef,
    Exactly,
    Not,
    Or,
    Palette,
    Placement,
    Property,
    Puzzle,
    Relation,
    Truth,
    evaluate,
    puzzle_from_dict,
)
from chroma_cube.solver import solve

CARD_COUNT = 25

DIFFICULTIES = ("easy", "medium", "hard", "expert")
"""The difficulty labels, easiest first."""


@cache
def classic_puzzles() -> tuple[Puzzle, ...]:
    """The classic cards, easiest first."""
    folder = files(__package__).joinpath("data", "classic")
    return tuple(
        puzzle_from_dict(
            json.loads(folder.joinpath(f"classic-{n:02d}.json").read_text(encoding="utf-8"))
        )
        for n in range(1, CARD_COUNT + 1)
    )


def classic_puzzle(number: int) -> Puzzle:
    """Card `number`, counting from 1. Raises `ValueError` for a card that does not exist."""
    if not 1 <= number <= CARD_COUNT:
        raise ValueError(f"the classic set has cards 1 to {CARD_COUNT}, not {number}")
    return classic_puzzles()[number - 1]


def clue_kinds(clue: Clue) -> frozenset[str]:
    """The kinds of clue a player has to understand to read `clue`.

    Relation, property and board-rule kinds by name, plus "not", "or", "exactly",
    "at_least" and "initial" (a color named by its first letter). "and" is left out: it
    only groups statements the player already reads one by one.
    """
    match clue:
        case Relation(kind=kind, colors=refs):
            initial = {"initial"} if any(r.by_initial for r in refs) else set()
            return frozenset({kind} | initial)
        case Property(kind=kind, color=color_ref):
            return frozenset({kind, "initial"} if color_ref.by_initial else {kind})
        case BoardRule(kind=kind):
            return frozenset({kind})
        case Not(clue=inner):
            return frozenset({"not"}) | clue_kinds(inner)
        case And(clues=subs):
            return _union(subs)
        case Or(clues=subs):
            return frozenset({"or"}) | _union(subs)
        case Exactly(clues=subs):
            return frozenset({"exactly"}) | _union(subs)
        case AtLeast(clues=subs):
            return frozenset({"at_least"}) | _union(subs)
    raise TypeError(f"not a clue: {clue!r}")


def _union(clues: tuple[Clue, ...]) -> frozenset[str]:
    return frozenset().union(*(clue_kinds(sub) for sub in clues))


def difficulty_score(puzzle: Puzzle) -> int:
    """A rough difficulty: cubes left to place plus distinct kinds of clue on the card."""
    unplaced = len(puzzle.givens.unplaced(puzzle.palette))
    kinds = frozenset().union(*(clue_kinds(clue) for clue in puzzle.clues))
    return unplaced + len(kinds)


def rate_card(puzzle: Puzzle) -> int:
    """How much trial and error a careful player needs: the number of one-step trials.

    The player places a cube whenever the clues leave it one cell, or leave a cell one
    cube. When nothing is forced they try each remaining cube-and-cell option one step
    ahead, and every try counts. A try that leaves some cube or cell with no option rules
    that option out. If no try rules anything out, the player guesses right: the most
    constrained cube goes to its cell in the solution. A card that falls out by plain
    deduction scores 0. Raises `ValueError` for a card without exactly one solution.
    """
    result = solve(puzzle, limit=1)
    if result.count != 1 or result.truncated or result.gave_up:
        raise ValueError(f"{puzzle.id} does not have exactly one solution")
    solution = result.solutions[0]
    mentions = _mentions(puzzle)
    placement = puzzle.givens
    ruled_out: set[tuple[Color, Cell]] = set()
    trials = 0
    while not placement.is_complete(puzzle.palette):
        options = _options(puzzle, mentions, placement, ruled_out)
        forced = _forced(puzzle, placement, options)
        if forced is not None:
            placement = placement.with_color(*forced)
            continue
        progress = False
        for color, cells in options.items():
            for cell in cells:
                trials += 1
                child = placement.with_color(color, cell)
                if _stuck(puzzle, child, _options(puzzle, mentions, child, ruled_out)):
                    ruled_out.add((color, cell))
                    progress = True
        if not progress:
            color = min(options, key=lambda c: (len(options[c]), c.id))
            target = solution.cell_of(color)
            assert target is not None
            placement = placement.with_color(color, target)
    return trials


Options = dict[Color, tuple[Cell, ...]]


def _mentions(puzzle: Puzzle) -> dict[Color, tuple[Clue, ...]]:
    found: dict[Color, list[Clue]] = {color: [] for color in puzzle.palette}
    for clue in puzzle.clues:
        for color in _colors_named(clue, puzzle.palette):
            found[color].append(clue)
    return {color: tuple(clues) for color, clues in found.items()}


def _colors_named(clue: Clue, palette: Palette) -> set[Color]:
    match clue:
        case Relation(colors=refs):
            return set().union(*(_resolve(r, palette) for r in refs))
        case Property(color=color_ref):
            return _resolve(color_ref, palette)
        case BoardRule():
            return set(palette)
        case Not(clue=inner):
            return _colors_named(inner, palette)
        case And(clues=subs) | Or(clues=subs) | Exactly(clues=subs) | AtLeast(clues=subs):
            return set().union(*(_colors_named(sub, palette) for sub in subs))
    raise TypeError(f"not a clue: {clue!r}")


def _resolve(color_ref: ColorRef, palette: Palette) -> set[Color]:
    if color_ref.by_initial:
        return set(palette.by_initial(color_ref.key))
    return {palette.by_id(color_ref.key)}


def _options(
    puzzle: Puzzle,
    mentions: dict[Color, tuple[Clue, ...]],
    placement: Placement,
    ruled_out: set[tuple[Color, Cell]],
) -> Options:
    """For each unplaced cube, the free cells where it breaks no clue."""
    free = [cell for cell in puzzle.board if placement.color_at(cell) is None]
    options: Options = {}
    for color in placement.unplaced(puzzle.palette):
        options[color] = tuple(
            cell
            for cell in free
            if (color, cell) not in ruled_out
            and all(
                evaluate(clue, placement.with_color(color, cell), puzzle.board, puzzle.palette)
                is not Truth.VIOLATED
                for clue in mentions[color]
            )
        )
    return options


def _forced(puzzle: Puzzle, placement: Placement, options: Options) -> tuple[Color, Cell] | None:
    """A cube with one cell left, or a cell with one cube left."""
    for color, cells in options.items():
        if len(cells) == 1:
            return color, cells[0]
    for cell in puzzle.board:
        if placement.color_at(cell) is None:
            takers = [color for color, cells in options.items() if cell in cells]
            if len(takers) == 1:
                return takers[0], cell
    return None


def _stuck(puzzle: Puzzle, placement: Placement, options: Options) -> bool:
    """Some cube has no cell left, or some free cell no cube."""
    if any(not cells for cells in options.values()):
        return True
    taken = {cell for cells in options.values() for cell in cells}
    return any(placement.color_at(cell) is None and cell not in taken for cell in puzzle.board)
