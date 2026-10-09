"""Where cubes sit: an immutable, possibly partial map from colors to cells."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from chroma_cube.core.board import Cell
from chroma_cube.core.colors import Color, Palette


@dataclass(frozen=True)
class Placement:
    """Colors placed on cells, at most one color per cell and one cell per color.

    A placement does not know its board or palette; callers pass the palette to the
    queries that need it. Every change returns a new placement. Placing a color that
    is already placed, filling an occupied cell, or removing an unplaced color raises
    `ValueError`; to move a color, remove it and place it again.
    """

    assignments: Mapping[Color, Cell] = field(default_factory=dict)
    _colors_by_cell: Mapping[Cell, Color] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        by_color = dict(self.assignments)
        by_cell: dict[Cell, Color] = {}
        for color, cell in by_color.items():
            if cell in by_cell:
                raise ValueError(f"{color.name} and {by_cell[cell].name} are both on {cell}")
            by_cell[cell] = color
        object.__setattr__(self, "assignments", MappingProxyType(by_color))
        object.__setattr__(self, "_colors_by_cell", MappingProxyType(by_cell))

    def __hash__(self) -> int:
        return hash(frozenset(self.assignments.items()))

    def cell_of(self, color: Color) -> Cell | None:
        return self.assignments.get(color)

    def color_at(self, cell: Cell) -> Color | None:
        return self._colors_by_cell.get(cell)

    def with_color(self, color: Color, cell: Cell) -> Placement:
        if color in self.assignments:
            raise ValueError(f"{color.name} is already on {self.assignments[color]}")
        return Placement({**self.assignments, color: cell})

    def without(self, color: Color) -> Placement:
        if color not in self.assignments:
            raise ValueError(f"{color.name} is not placed")
        return Placement({c: cell for c, cell in self.assignments.items() if c != color})

    def unplaced(self, palette: Palette) -> tuple[Color, ...]:
        """The palette's colors that are not placed yet, in palette order."""
        return tuple(color for color in palette if color not in self.assignments)

    def is_complete(self, palette: Palette) -> bool:
        return not self.unplaced(palette)
