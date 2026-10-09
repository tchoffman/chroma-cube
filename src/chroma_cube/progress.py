"""What the player has done, kept between runs in a small JSON file.

The store remembers which cards were solved (how often, and the fewest hints used) and
the cubes the player had placed on the last card they played, with the hints taken on it.
Reading never raises: a missing, empty or damaged file, or entries of the wrong shape, are
treated as no progress.
Writing goes through a temporary file and a rename, so a crash mid-save leaves the old
file whole, and a save that fails is dropped rather than interrupting the game.
"""

from __future__ import annotations

import contextlib
import json
import os
import sys
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeGuard

from chroma_cube.core import Cell, Placement, Puzzle

APP_DIR = "chroma-cube"
FILE_NAME = "progress.json"
ENV_OVERRIDE = "CHROMA_CUBE_DATA_DIR"
FORMAT_VERSION = 1


def default_data_dir(
    env: Mapping[str, str] | None = None,
    platform: str | None = None,
    home: Path | None = None,
) -> Path:
    """The per-user directory for saves.

    `CHROMA_CUBE_DATA_DIR` wins if set. Otherwise `%APPDATA%` on Windows,
    `~/Library/Application Support` on macOS, and `$XDG_DATA_HOME` (or `~/.local/share`)
    elsewhere, each with a `chroma-cube` subdirectory.
    """
    env = os.environ if env is None else env
    platform = sys.platform if platform is None else platform
    home = Path.home() if home is None else home
    if override := env.get(ENV_OVERRIDE):
        return Path(override)
    if platform == "win32":
        appdata = env.get("APPDATA")
        base = Path(appdata) if appdata else home / "AppData" / "Roaming"
    elif platform == "darwin":
        base = home / "Library" / "Application Support"
    else:
        xdg = env.get("XDG_DATA_HOME", "")
        # The XDG spec says relative paths are invalid and must be ignored.
        base = Path(xdg) if xdg and Path(xdg).is_absolute() else home / ".local" / "share"
    return base / APP_DIR


@dataclass(frozen=True)
class SolveRecord:
    """How often a card was solved, and the fewest hints used (None until hints exist)."""

    solves: int
    best_hints: int | None = None


@dataclass(frozen=True)
class SavedCube:
    """One cube the player placed: a color id and its cell."""

    color: str
    row: int
    col: int


@dataclass(frozen=True)
class SavedBoard:
    """The cubes the player had placed on one card, givens left out, and the hints taken."""

    puzzle_id: str
    cubes: tuple[SavedCube, ...]
    hints: int = 0


class Progress:
    """Solved cards and the last in-progress board, loaded once and saved on every change."""

    def __init__(self, data_dir: Path | None = None) -> None:
        self.path = (default_data_dir() if data_dir is None else data_dir) / FILE_NAME
        self._solved: dict[str, SolveRecord] = {}
        self._board: SavedBoard | None = None
        self._load()

    # ------------------------------------------------------------------ solves

    def is_solved(self, puzzle_id: str) -> bool:
        return puzzle_id in self._solved

    def record(self, puzzle_id: str) -> SolveRecord | None:
        return self._solved.get(puzzle_id)

    def record_solve(self, puzzle_id: str, hints: int | None = None) -> None:
        """Count one more solve, keeping the fewest hints seen."""
        old = self._solved.get(puzzle_id)
        best = old.best_hints if old is not None else None
        if hints is not None and (best is None or hints < best):
            best = hints
        self._solved[puzzle_id] = SolveRecord((old.solves if old else 0) + 1, best)
        self._save()

    # ------------------------------------------------------------------ in-progress board

    def saved_board(self, puzzle: Puzzle) -> Placement | None:
        """The board saved for `puzzle`, or None if there is none or it no longer fits."""
        board = self._board
        if board is None or board.puzzle_id != puzzle.id:
            return None
        placement = puzzle.givens
        for cube in board.cubes:
            try:
                color = puzzle.palette.by_id(cube.color)
            except KeyError:
                return None
            cell = Cell(cube.row, cube.col)
            if cell not in puzzle.board or placement.color_at(cell) is not None:
                return None
            if placement.cell_of(color) is not None:
                return None
            placement = placement.with_color(color, cell)
        return placement

    def saved_hints(self, puzzle_id: str) -> int:
        """The hints taken on the saved board of `puzzle_id`, or 0 if it has none."""
        board = self._board
        return board.hints if board is not None and board.puzzle_id == puzzle_id else 0

    def save_board(self, puzzle: Puzzle, placement: Placement, hints: int = 0) -> None:
        """Remember `placement` and the hints taken as the board of the last card played.

        A board with nothing beyond the givens and no hints is forgotten instead.
        """
        cubes = tuple(
            SavedCube(color.id, cell.row, cell.col)
            for color in puzzle.palette
            if (cell := placement.cell_of(color)) is not None
            and puzzle.givens.cell_of(color) is None
        )
        board = SavedBoard(puzzle.id, cubes, hints) if cubes or hints else None
        if board != self._board:
            self._board = board
            self._save()

    def clear_board(self, puzzle_id: str) -> None:
        """Forget the saved board if it belongs to `puzzle_id`; another card's is kept."""
        if self._board is not None and self._board.puzzle_id == puzzle_id:
            self._board = None
            self._save()

    # ------------------------------------------------------------------ file

    def _load(self) -> None:
        data = self._read()
        self._solved = _parse_solved(data.get("solved"))
        self._board = _parse_board(data.get("current"))

    def _read(self) -> dict[str, Any]:
        """The file's top-level object, or an empty one if it cannot be read."""
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError, RecursionError):
            return {}
        return data if isinstance(data, dict) else {}

    def _merge_from_disk(self) -> None:
        """Take in solves another running copy wrote since we loaded.

        Each card keeps the higher solve count and the fewer hints. The board is not
        merged: whoever saves last owns it.
        """
        for puzzle_id, theirs in _parse_solved(self._read().get("solved")).items():
            ours = self._solved.get(puzzle_id)
            if ours is None:
                self._solved[puzzle_id] = theirs
                continue
            hints = [h for h in (ours.best_hints, theirs.best_hints) if h is not None]
            self._solved[puzzle_id] = SolveRecord(
                max(ours.solves, theirs.solves), min(hints) if hints else None
            )

    def _save(self) -> None:
        self._merge_from_disk()
        data: dict[str, Any] = {
            "version": FORMAT_VERSION,
            "solved": {
                puzzle_id: {"solves": record.solves, "best_hints": record.best_hints}
                for puzzle_id, record in self._solved.items()
            },
            "current": None
            if self._board is None
            else {
                "puzzle": self._board.puzzle_id,
                "cubes": [
                    {"color": cube.color, "row": cube.row, "col": cube.col}
                    for cube in self._board.cubes
                ],
                **({"hints": self._board.hints} if self._board.hints else {}),
            },
        }
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            handle, temp_name = tempfile.mkstemp(
                prefix=f".{FILE_NAME}.", suffix=".tmp", dir=self.path.parent
            )
        except OSError:
            return
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as temp:
                json.dump(data, temp, indent=2)
                temp.flush()
                os.fsync(temp.fileno())
            os.replace(temp_name, self.path)
        except OSError:
            with contextlib.suppress(OSError):
                os.unlink(temp_name)


def _is_count(value: object, minimum: int) -> TypeGuard[int]:
    return isinstance(value, int) and not isinstance(value, bool) and value >= minimum


def _parse_solved(raw: object) -> dict[str, SolveRecord]:
    if not isinstance(raw, dict):
        return {}
    solved: dict[str, SolveRecord] = {}
    for puzzle_id, entry in raw.items():
        if not isinstance(entry, dict):
            continue
        solves, best = entry.get("solves"), entry.get("best_hints")
        if _is_count(solves, 1) and (best is None or _is_count(best, 0)):
            solved[puzzle_id] = SolveRecord(solves, best)
    return solved


def _parse_board(raw: object) -> SavedBoard | None:
    if not isinstance(raw, dict):
        return None
    puzzle_id, cubes = raw.get("puzzle"), raw.get("cubes")
    if not isinstance(puzzle_id, str) or not isinstance(cubes, list):
        return None
    parsed: list[SavedCube] = []
    for cube in cubes:
        if not isinstance(cube, dict):
            return None
        color, row, col = cube.get("color"), cube.get("row"), cube.get("col")
        if isinstance(color, str) and _is_count(row, 0) and _is_count(col, 0):
            parsed.append(SavedCube(color, row, col))
        else:
            return None
    hints = raw.get("hints")
    return SavedBoard(puzzle_id, tuple(parsed), hints if _is_count(hints, 0) else 0)
