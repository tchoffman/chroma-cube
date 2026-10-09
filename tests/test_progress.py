import json
import os
from pathlib import Path

import pytest

from chroma_cube.core import Cell, Color, Placement, Puzzle
from chroma_cube.progress import Progress, SolveRecord, default_data_dir
from chroma_cube.puzzles import classic_puzzles

DEMO = classic_puzzles()[0]
OTHER = Puzzle(
    id="other",
    title="Other",
    board=DEMO.board,
    palette=DEMO.palette,
    givens=DEMO.givens,
    clues=DEMO.clues,
)


def magenta_at(row: int, col: int) -> Placement:
    return DEMO.givens.with_color(DEMO.palette.by_id("magenta"), Cell(row, col))


# ------------------------------------------------------------------ solves


def test_a_fresh_store_has_nothing_solved_and_no_board(tmp_path: Path) -> None:
    progress = Progress(tmp_path)
    assert not progress.is_solved(DEMO.id)
    assert progress.record(DEMO.id) is None
    assert progress.saved_board(DEMO) is None


def test_solves_are_counted_and_survive_a_reload(tmp_path: Path) -> None:
    progress = Progress(tmp_path)
    progress.record_solve(DEMO.id)
    progress.record_solve(DEMO.id)
    reloaded = Progress(tmp_path)
    assert reloaded.is_solved(DEMO.id)
    assert not reloaded.is_solved(OTHER.id)
    assert reloaded.record(DEMO.id) == SolveRecord(solves=2, best_hints=None)


def test_best_hints_keeps_the_fewest(tmp_path: Path) -> None:
    progress = Progress(tmp_path)
    progress.record_solve(DEMO.id, hints=3)
    progress.record_solve(DEMO.id, hints=1)
    progress.record_solve(DEMO.id, hints=2)
    progress.record_solve(DEMO.id)
    assert Progress(tmp_path).record(DEMO.id) == SolveRecord(solves=4, best_hints=1)


# ------------------------------------------------------------------ in-progress board


def test_a_board_round_trips_for_its_own_card_only(tmp_path: Path) -> None:
    Progress(tmp_path).save_board(DEMO, magenta_at(2, 1))
    reloaded = Progress(tmp_path)
    assert reloaded.saved_board(DEMO) == magenta_at(2, 1)
    assert reloaded.saved_board(OTHER) is None


def test_only_the_last_card_played_is_kept(tmp_path: Path) -> None:
    progress = Progress(tmp_path)
    progress.save_board(DEMO, magenta_at(2, 1))
    progress.save_board(OTHER, OTHER.givens.with_color(*first_free(OTHER)))
    assert Progress(tmp_path).saved_board(DEMO) is None
    assert Progress(tmp_path).saved_board(OTHER) is not None


def first_free(puzzle: Puzzle) -> tuple[Color, Cell]:
    color = puzzle.givens.unplaced(puzzle.palette)[0]
    cell = next(cell for cell in puzzle.board if puzzle.givens.color_at(cell) is None)
    return color, cell


def test_the_file_lists_only_the_cubes_the_player_placed(tmp_path: Path) -> None:
    Progress(tmp_path).save_board(DEMO, magenta_at(2, 1))
    data = json.loads((tmp_path / "progress.json").read_text())
    assert data["current"] == {
        "puzzle": DEMO.id,
        "cubes": [{"color": "magenta", "row": 2, "col": 1}],
    }


def test_a_board_back_at_the_givens_is_forgotten(tmp_path: Path) -> None:
    progress = Progress(tmp_path)
    progress.save_board(DEMO, magenta_at(2, 1))
    progress.save_board(DEMO, DEMO.givens)
    assert Progress(tmp_path).saved_board(DEMO) is None


def test_clear_board_forgets_it(tmp_path: Path) -> None:
    progress = Progress(tmp_path)
    progress.save_board(DEMO, magenta_at(2, 1))
    progress.clear_board()
    assert Progress(tmp_path).saved_board(DEMO) is None


@pytest.mark.parametrize(
    "cubes",
    [
        [{"color": "nope", "row": 0, "col": 0}],
        [{"color": "magenta", "row": 9, "col": 0}],
        [{"color": "magenta", "row": 1, "col": 1}],
        [{"color": "magenta", "row": 0, "col": 0}, {"color": "teal", "row": 0, "col": 0}],
        [{"color": "magenta", "row": 0, "col": 0}, {"color": "magenta", "row": 0, "col": 1}],
        [{"color": "magenta", "row": "0", "col": 0}],
        [{"color": "magenta", "row": True, "col": 0}],
        "magenta",
    ],
)
def test_a_board_that_no_longer_fits_the_card_is_ignored(tmp_path: Path, cubes: object) -> None:
    """Unknown colors, off-board or occupied cells, givens and bad types all mean no board."""
    write(tmp_path, {"current": {"puzzle": DEMO.id, "cubes": cubes}})
    assert Progress(tmp_path).saved_board(DEMO) is None


# ------------------------------------------------------------------ bad files


def write(directory: Path, data: object) -> None:
    (directory / "progress.json").write_text(json.dumps(data))


@pytest.mark.parametrize(
    "content",
    ["", "{not json", "[]", "null", '"text"', "\xff\xfe", '{"solved": []}'],
)
def test_a_corrupt_file_starts_fresh(tmp_path: Path, content: str) -> None:
    (tmp_path / "progress.json").write_text(content, encoding="latin-1")
    progress = Progress(tmp_path)
    assert not progress.is_solved(DEMO.id)
    assert progress.saved_board(DEMO) is None
    progress.record_solve(DEMO.id)
    assert Progress(tmp_path).is_solved(DEMO.id)


@pytest.mark.parametrize(
    "solved",
    [
        {"x": "yes"},
        {"x": {"solves": "2"}},
        {"x": {"solves": 0}},
        {"x": {"solves": 1, "best_hints": -1}},
        {"x": {"solves": 1, "best_hints": 1.5}},
    ],
)
def test_bad_solve_entries_are_dropped_and_good_ones_kept(tmp_path: Path, solved: object) -> None:
    assert isinstance(solved, dict)
    write(tmp_path, {"solved": {**solved, DEMO.id: {"solves": 1, "best_hints": None}}})
    progress = Progress(tmp_path)
    assert not progress.is_solved("x")
    assert progress.is_solved(DEMO.id)


def test_a_bad_board_does_not_cost_the_solves(tmp_path: Path) -> None:
    write(tmp_path, {"solved": {DEMO.id: {"solves": 1}}, "current": 7})
    progress = Progress(tmp_path)
    assert progress.is_solved(DEMO.id)
    assert progress.saved_board(DEMO) is None


def test_a_directory_in_place_of_the_file_starts_fresh(tmp_path: Path) -> None:
    (tmp_path / "progress.json").mkdir()
    progress = Progress(tmp_path)
    assert not progress.is_solved(DEMO.id)
    progress.record_solve(DEMO.id)  # cannot save, but must not raise
    assert progress.is_solved(DEMO.id)


def test_the_data_dir_is_created_on_first_save(tmp_path: Path) -> None:
    directory = tmp_path / "a" / "b"
    Progress(directory).record_solve(DEMO.id)
    assert Progress(directory).is_solved(DEMO.id)


# ------------------------------------------------------------------ atomic save


def test_a_failed_save_leaves_the_old_file_and_no_temp_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    progress = Progress(tmp_path)
    progress.record_solve(DEMO.id)
    before = (tmp_path / "progress.json").read_bytes()

    def broken_replace(src: object, dst: object) -> None:
        raise OSError("disk on fire")

    monkeypatch.setattr(os, "replace", broken_replace)
    progress.record_solve(OTHER.id)
    assert (tmp_path / "progress.json").read_bytes() == before
    assert [path.name for path in tmp_path.iterdir()] == ["progress.json"]


def test_save_writes_through_a_temp_file_and_rename(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    renames: list[tuple[Path, Path]] = []
    real_replace = os.replace

    def spy(src: str | Path, dst: str | Path) -> None:
        renames.append((Path(src), Path(dst)))
        real_replace(src, dst)

    monkeypatch.setattr(os, "replace", spy)
    Progress(tmp_path).record_solve(DEMO.id)
    [(src, dst)] = renames
    assert dst == tmp_path / "progress.json"
    assert src.parent == tmp_path and src != dst


# ------------------------------------------------------------------ where the file lives


HOME = Path("/home/ada")


def test_the_env_override_wins_everywhere() -> None:
    env = {"CHROMA_CUBE_DATA_DIR": "/saves", "XDG_DATA_HOME": "/xdg", "APPDATA": "C:/AppData"}
    for platform in ("linux", "darwin", "win32"):
        assert default_data_dir(env, platform, HOME) == Path("/saves")


def test_linux_uses_xdg_data_home() -> None:
    assert default_data_dir({"XDG_DATA_HOME": "/xdg"}, "linux", HOME) == Path("/xdg/chroma-cube")


def test_linux_falls_back_to_local_share() -> None:
    expected = HOME / ".local" / "share" / "chroma-cube"
    assert default_data_dir({}, "linux", HOME) == expected
    assert default_data_dir({"XDG_DATA_HOME": ""}, "linux", HOME) == expected
    assert default_data_dir({"XDG_DATA_HOME": "relative"}, "linux", HOME) == expected


def test_macos_uses_application_support() -> None:
    expected = HOME / "Library" / "Application Support" / "chroma-cube"
    assert default_data_dir({"XDG_DATA_HOME": "/xdg"}, "darwin", HOME) == expected


def test_windows_uses_appdata() -> None:
    assert default_data_dir({"APPDATA": "/appdata"}, "win32", HOME) == Path("/appdata/chroma-cube")
    assert default_data_dir({}, "win32", HOME) == HOME / "AppData" / "Roaming" / "chroma-cube"


def test_no_argument_uses_the_default_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CHROMA_CUBE_DATA_DIR", str(tmp_path))
    Progress().record_solve(DEMO.id)
    assert (tmp_path / "progress.json").exists()
    assert Progress().path == tmp_path / "progress.json"
