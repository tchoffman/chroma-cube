"""A puzzle: a board, its colors, the cubes placed up front and the clues."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from chroma_cube.core._data import as_int, as_list, as_str
from chroma_cube.core.board import Board, Cell
from chroma_cube.core.clues import (
    PROPERTY_KINDS,
    And,
    AtLeast,
    Clue,
    ColorRef,
    Exactly,
    Not,
    Or,
    Property,
    Relation,
)
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

        for clue in self.clues:
            _check_clue(clue, self.board, self.palette)

    def rendered_clues(self) -> tuple[str, ...]:
        """Every clue as an English sentence, in order."""
        return tuple(render(clue, self.palette, self.board) for clue in self.clues)


def _check_clue(clue: Clue, board: Board, palette: Palette) -> None:
    """Every named color is in the palette and every row or column index is on the board."""
    match clue:
        case Relation(colors=refs):
            for color_ref in refs:
                _check_ref(color_ref, palette)
        case Property(kind=kind, color=color_ref, index=index):
            _check_ref(color_ref, palette)
            line = PROPERTY_KINDS[kind].index
            size = board.rows if line == "row" else board.cols
            if line is not None and index is not None and index >= size:
                raise ValueError(f"{line} {index} is not on a {board.rows}x{board.cols} board")
        case Not(clue=inner):
            _check_clue(inner, board, palette)
        case And(clues=clues) | Or(clues=clues) | Exactly(clues=clues) | AtLeast(clues=clues):
            for sub in clues:
                _check_clue(sub, board, palette)


def _check_ref(color_ref: ColorRef, palette: Palette) -> None:
    if color_ref.by_initial:
        return
    try:
        palette.by_id(color_ref.key)
    except KeyError:
        raise ValueError(f"clue names {color_ref.key!r}, which is not in the palette") from None


def puzzle_to_dict(puzzle: Puzzle) -> dict[str, Any]:
    """The puzzle as a plain JSON-compatible dict; givens are listed in reading order."""
    givens = sorted(puzzle.givens.assignments.items(), key=lambda item: item[1])
    return {
        "id": puzzle.id,
        "title": puzzle.title,
        "difficulty": puzzle.difficulty,
        "notes": puzzle.notes,
        "board": {"rows": puzzle.board.rows, "cols": puzzle.board.cols},
        "palette": [_color_to_dict(color) for color in puzzle.palette],
        "givens": [{"color": c.id, "row": cell.row, "col": cell.col} for c, cell in givens],
        "clues": [clue_to_dict(clue) for clue in puzzle.clues],
    }


def puzzle_from_dict(data: Mapping[str, Any]) -> Puzzle:
    """Rebuild a puzzle. Raises `ValueError` for anything that is not a well-formed puzzle."""
    try:
        board = Board(as_int(data["board"]["rows"]), as_int(data["board"]["cols"]))
        palette = Palette(tuple(_color_from_dict(entry) for entry in as_list(data["palette"])))
        givens: dict[Color, Cell] = {}
        for given in as_list(data["givens"]):
            color = palette.by_id(as_str(given["color"]))
            if color in givens:
                raise ValueError(f"{color.name} is given twice")
            givens[color] = Cell(as_int(given["row"]), as_int(given["col"]))
        return Puzzle(
            id=as_str(data["id"]),
            title=as_str(data["title"]),
            board=board,
            palette=palette,
            givens=Placement(givens),
            clues=tuple(clue_from_dict(clue) for clue in data["clues"]),
            difficulty=as_str(data.get("difficulty", "")),
            notes=as_str(data.get("notes", "")),
        )
    except (KeyError, TypeError, AttributeError) as error:
        raise ValueError(f"malformed puzzle data: {error!r}") from error


_ATTRIBUTES = ("temperature", "tone", "family")


def _color_to_dict(color: Color) -> dict[str, str]:
    """A color's id, name and hex, plus its attributes only if they differ from the hex's."""
    data = {"id": color.id, "name": color.name, "hex": color.hex}
    if not color.derived:
        data.update({field: getattr(color, field) for field in _ATTRIBUTES})
    return data


def _color_from_dict(data: Mapping[str, Any]) -> Color:
    """A color; attributes left out (as in older data) are derived from the hex."""
    attributes = {field: as_str(data[field]) for field in _ATTRIBUTES if field in data}
    return Color(as_str(data["id"]), as_str(data["name"]), as_str(data["hex"]), **attributes)
