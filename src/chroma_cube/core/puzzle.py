"""A puzzle: a board, its colors, the cubes placed up front and the clues."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from chroma_cube.core.board import Board, Cell
from chroma_cube.core.clues import Clue
from chroma_cube.core.colors import Color, Palette
from chroma_cube.core.placement import Placement
from chroma_cube.core.render import render
from chroma_cube.core.serialize import clue_from_dict, clue_to_dict


@dataclass(frozen=True)
class Puzzle:
    """One puzzle. `givens` are the cubes already in the tray when play starts."""

    id: str
    title: str
    board: Board
    palette: Palette
    givens: Placement
    clues: tuple[Clue, ...]
    difficulty: str = ""
    notes: str = ""

    def __post_init__(self) -> None:
        for color, cell in self.givens.assignments.items():
            if color not in self.palette:
                raise ValueError(f"given {color.name} is not in the puzzle's palette")
            if cell not in self.board:
                raise ValueError(f"given {color.name} is on {cell}, off the board")

    def rendered_clues(self) -> tuple[str, ...]:
        """Every clue as an English sentence, in order."""
        return tuple(render(clue, self.palette, self.board) for clue in self.clues)


def puzzle_to_dict(puzzle: Puzzle) -> dict[str, Any]:
    """The puzzle as a plain JSON-compatible dict; givens are listed in reading order."""
    givens = sorted(puzzle.givens.assignments.items(), key=lambda item: item[1])
    return {
        "id": puzzle.id,
        "title": puzzle.title,
        "difficulty": puzzle.difficulty,
        "notes": puzzle.notes,
        "board": {"rows": puzzle.board.rows, "cols": puzzle.board.cols},
        "palette": [{"id": c.id, "name": c.name, "hex": c.hex} for c in puzzle.palette],
        "givens": [{"color": c.id, "row": cell.row, "col": cell.col} for c, cell in givens],
        "clues": [clue_to_dict(clue) for clue in puzzle.clues],
    }


def puzzle_from_dict(data: Mapping[str, Any]) -> Puzzle:
    """Rebuild a puzzle. Raises `ValueError` for anything that is not a well-formed puzzle."""
    try:
        board = Board(_int(data["board"]["rows"]), _int(data["board"]["cols"]))
        palette = Palette(
            tuple(Color(_str(c["id"]), _str(c["name"]), _str(c["hex"])) for c in data["palette"])
        )
        givens = Placement(
            {
                palette.by_id(_str(g["color"])): Cell(_int(g["row"]), _int(g["col"]))
                for g in data["givens"]
            }
        )
        return Puzzle(
            id=_str(data["id"]),
            title=_str(data["title"]),
            board=board,
            palette=palette,
            givens=givens,
            clues=tuple(clue_from_dict(clue) for clue in data["clues"]),
            difficulty=_str(data.get("difficulty", "")),
            notes=_str(data.get("notes", "")),
        )
    except (KeyError, TypeError, AttributeError) as error:
        raise ValueError(f"malformed puzzle data: {error!r}") from error


def _str(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError(value)
    return value


def _int(value: object) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(value)
    return value
