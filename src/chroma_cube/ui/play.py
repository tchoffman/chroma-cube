"""What the player is doing on one card, with no Textual in sight.

The play screen draws a `PlayState` and forwards clicks and keys to it, so every rule
about picking up, placing, swapping and returning cubes lives here and is tested on its own.
"""

from __future__ import annotations

from chroma_cube.core import Cell, Color, Placement, Puzzle, Truth, evaluate
from chroma_cube.solver import Hint, explain, next_hint


class PlayState:
    """The tray, the cube in hand and the keyboard cursor for one card.

    A held cube is either still in the palette (picked from the strip) or still on the
    tray (picked up from a cell); it only moves when it is put down somewhere.
    """

    def __init__(
        self, puzzle: Puzzle, placement: Placement | None = None, hints_used: int = 0
    ) -> None:
        """Start from `placement` (a board saved earlier), or else the card's givens.

        `hints_used` carries over the hints taken on a saved board.
        """
        self.puzzle = puzzle
        self.placement: Placement = puzzle.givens if placement is None else placement
        self.held: Color | None = None
        self.cursor = Cell(0, 0)
        self.hint: Hint | None = None
        """The hint on show; it goes away as soon as the tray changes."""
        self.hints_used = hints_used
        """Hints given on this card, kept through a reset and saved with the board."""

    # ------------------------------------------------------------------ queries

    def is_given(self, color: Color) -> bool:
        return self.puzzle.givens.cell_of(color) is not None

    def palette_cubes(self) -> tuple[Color, ...]:
        """The cubes not on the tray, in palette order."""
        return self.placement.unplaced(self.puzzle.palette)

    def statuses(self) -> tuple[Truth, ...]:
        """Each clue's truth on the current tray, in clue order."""
        puzzle = self.puzzle
        return tuple(
            evaluate(clue, self.placement, puzzle.board, puzzle.palette) for clue in puzzle.clues
        )

    @property
    def solved(self) -> bool:
        return self.placement.is_complete(self.puzzle.palette) and all(
            truth is Truth.SATISFIED for truth in self.statuses()
        )

    # ------------------------------------------------------------------ selecting

    def select(self, color: Color) -> None:
        """Take a cube from the palette strip into hand."""
        if color not in self.palette_cubes():
            raise ValueError(f"{color.name} is not in the palette")
        self.held = color

    def select_initial(self, letter: str) -> Color | None:
        """Take the next palette cube whose name starts with `letter`, cycling on repeats."""
        matches = [color for color in self.palette_cubes() if color.initial == letter.upper()]
        if not matches:
            return None
        index = matches.index(self.held) + 1 if self.held in matches else 0
        self.held = matches[index % len(matches)]
        return self.held

    def select_slot(self, slot: int) -> Color | None:
        """Take the palette cube at `slot`, counting from 1 along the strip."""
        cubes = self.palette_cubes()
        if not 1 <= slot <= len(cubes):
            return None
        self.held = cubes[slot - 1]
        return self.held

    # ------------------------------------------------------------------ acting

    def activate(self, cell: Cell) -> str:
        """Click or press Enter on `cell`; returns a short message for the status bar."""
        occupant = self.placement.color_at(cell)
        held = self.held
        if occupant is not None and self.is_given(occupant):
            return f"{occupant.name} is fixed on this card."
        if held is None:
            if occupant is None:
                return "Pick a cube from the palette first."
            self.held = occupant
            return f"Holding {occupant.name}. Choose a cell, or x to return it."
        self.held = None
        if occupant is held:
            return f"Put {held.name} down."
        from_cell = self.placement.cell_of(held)
        placement = self.placement if from_cell is None else self.placement.without(held)
        if occupant is not None:
            placement = placement.without(occupant)
            if from_cell is not None:
                placement = placement.with_color(occupant, from_cell)
        self._set_placement(placement.with_color(held, cell))
        if occupant is None:
            return f"Placed {held.name}."
        if from_cell is None:
            return f"Placed {held.name}; {occupant.name} went back to the palette."
        return f"Swapped {held.name} and {occupant.name}."

    def return_held(self) -> bool:
        """Send the held cube, or else the cube under the cursor, back to the palette.

        A cube held from the palette is simply let go. Returns whether anything changed.
        """
        held = self.held
        if held is None:
            under = self.placement.color_at(self.cursor)
            if under is None or self.is_given(under):
                return False
            held = under
        self.held = None
        if self.placement.cell_of(held) is not None:
            self._set_placement(self.placement.without(held))
        return True

    def move_cursor(self, drow: int, dcol: int) -> None:
        board = self.puzzle.board
        row = min(max(self.cursor.row + drow, 0), board.rows - 1)
        col = min(max(self.cursor.col + dcol, 0), board.cols - 1)
        self.cursor = Cell(row, col)

    def reset(self) -> None:
        """Back to the card's starting tray."""
        self._set_placement(self.puzzle.givens)
        self.held = None

    def take_hint(self) -> str:
        """Show the next sure move; returns its explanation for the status bar.

        Asking again before the tray changes shows the same hint and is not counted again.
        """
        hint = next_hint(self.puzzle, self.placement)
        if hint is None:
            self.hint = None
            return "No hint: nothing is forced yet."
        if hint != self.hint:
            self.hints_used += 1
        self.hint = hint
        return f"{explain(hint, self.puzzle)}."

    def _set_placement(self, placement: Placement) -> None:
        self.placement = placement
        self.hint = None
