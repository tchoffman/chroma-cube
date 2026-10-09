"""The tray: a grid of cells with named regions and neighbourhoods."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass


@dataclass(frozen=True, order=True)
class Cell:
    """A position on a board. Row 0 is the top row, column 0 the leftmost column."""

    row: int
    col: int


_ORTHOGONAL = ((-1, 0), (0, -1), (0, 1), (1, 0))
_DIAGONAL = ((-1, -1), (-1, 1), (1, -1), (1, 1))


@dataclass(frozen=True)
class Board:
    """A `rows` x `cols` grid.

    Queries that return several cells return them in row-major order (top-left first),
    and every query raises `ValueError` for a cell that is not on the board.
    """

    rows: int
    cols: int

    def __post_init__(self) -> None:
        if self.rows < 1 or self.cols < 1:
            raise ValueError(f"a board needs at least one row and column, got {self}")

    def __iter__(self) -> Iterator[Cell]:
        for row in range(self.rows):
            for col in range(self.cols):
                yield Cell(row, col)

    def __len__(self) -> int:
        return self.rows * self.cols

    def __contains__(self, cell: object) -> bool:
        return isinstance(cell, Cell) and 0 <= cell.row < self.rows and 0 <= cell.col < self.cols

    def is_corner(self, cell: Cell) -> bool:
        self._check(cell)
        return cell.row in (0, self.rows - 1) and cell.col in (0, self.cols - 1)

    def is_edge(self, cell: Cell) -> bool:
        """True for any cell on the border, corners included."""
        self._check(cell)
        return cell.row in (0, self.rows - 1) or cell.col in (0, self.cols - 1)

    def is_center(self, cell: Cell) -> bool:
        """True for any cell not on the border."""
        return not self.is_edge(cell)

    def row(self, index: int) -> tuple[Cell, ...]:
        if not 0 <= index < self.rows:
            raise ValueError(f"row {index} is not on a board with {self.rows} rows")
        return tuple(Cell(index, col) for col in range(self.cols))

    def column(self, index: int) -> tuple[Cell, ...]:
        if not 0 <= index < self.cols:
            raise ValueError(f"column {index} is not on a board with {self.cols} columns")
        return tuple(Cell(row, index) for row in range(self.rows))

    def orthogonal_neighbours(self, cell: Cell) -> tuple[Cell, ...]:
        """Cells sharing a side with `cell`."""
        return self._offsets(cell, _ORTHOGONAL)

    def diagonal_neighbours(self, cell: Cell) -> tuple[Cell, ...]:
        """Cells sharing only a corner with `cell`."""
        return self._offsets(cell, _DIAGONAL)

    def neighbours(self, cell: Cell) -> tuple[Cell, ...]:
        """Cells sharing a side or a corner with `cell`."""
        return tuple(sorted(self._offsets(cell, _ORTHOGONAL + _DIAGONAL)))

    def _offsets(self, cell: Cell, offsets: tuple[tuple[int, int], ...]) -> tuple[Cell, ...]:
        self._check(cell)
        moved = (Cell(cell.row + dr, cell.col + dc) for dr, dc in offsets)
        return tuple(sorted(other for other in moved if other in self))

    def _check(self, cell: Cell) -> None:
        if cell not in self:
            raise ValueError(f"{cell} is not on a {self.rows}x{self.cols} board")


CLASSIC_BOARD = Board(3, 4)
"""The physical game's tray (see D3 in docs/DECISIONS.md)."""
