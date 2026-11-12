"""The clues sit on a card: a bordered panel with the card's name, tier, numbered clues and note."""

import re
from dataclasses import replace
from datetime import date

import pytest
from textual.app import App
from textual.content import Content
from textual.widgets import Static

from chroma_cube.core import Truth
from chroma_cube.puzzles import classic_puzzles
from chroma_cube.ui import ChromaCubeApp
from chroma_cube.ui.card import ClueCard, HangingIndent
from chroma_cube.ui.infinite import GeneratedPlayScreen
from chroma_cube.ui.seeds import GameSpec
from chroma_cube.ui.widgets import ClueRow
from tests.conftest import DEMO
from tests.ui.drawn import card_edges
from tests.ui.test_boards import real

CARDS = classic_puzzles()


def card(pilot_app: App[None]) -> ClueCard:
    return pilot_app.screen.query_one(ClueCard)


def footer(pilot_app: App[None]) -> str:
    return str(card(pilot_app).border_subtitle)


def test_a_hanging_indent_keeps_wrapped_lines_clear_of_the_gutter() -> None:
    visual = HangingIndent(Content("✓  1  "), Content("Coral sits next to White and Teal"))
    lines = [line.plain for line in visual.lines(20)]
    assert visual.get_height({}, 20) == len(lines) == 3
    assert lines[0].startswith("✓  1  Coral")
    assert all(line.startswith(" " * 6) and line[6] != " " for line in lines[1:])


async def test_a_classic_card_is_headed_by_its_number_and_title_and_footed_by_its_tier() -> None:
    puzzles = CARDS[:8]
    async with ChromaCubeApp(puzzles, start_on_cards=True).run_test(size=(100, 30)) as pilot:
        await pilot.press("end", "enter")
        await pilot.pause()
        assert card_edges(pilot.app) == ("8 · Empty Tray", "Medium · 6 clues")


async def test_clues_are_numbered_after_their_marker() -> None:
    async with ChromaCubeApp((DEMO,), start_on_cards=True).run_test(size=(120, 40)) as pilot:
        await pilot.press("enter")
        rows = list(pilot.app.screen.query(ClueRow))
        assert [row.text for row in rows] == [
            f"·  {number}  {text}" for number, text in enumerate(DEMO.rendered_clues(), start=1)
        ]


async def test_a_long_clue_wraps_under_its_text_not_under_its_marker() -> None:
    async with ChromaCubeApp((DEMO,), start_on_cards=True).run_test(size=(70, 24)) as pilot:
        await pilot.press("enter")
        await pilot.pause()
        row = next(row for row in pilot.app.screen.query(ClueRow) if row.size.height > 1)
        first, second = row.render_line(0).text, row.render_line(1).text
        assert first.startswith("·  ")
        assert second.startswith(" " * 6) and second.strip()


@pytest.mark.parametrize("truth", list(Truth))
def test_a_clue_row_keeps_one_class_per_state(truth: Truth) -> None:
    row = ClueRow(3, "Black sits next to Magenta")
    row.show(truth)
    assert [row.has_class(value.value) for value in Truth] == [value is truth for value in Truth]
    assert row.text.startswith(f"{row.text[0]}  3  Black")


async def test_the_note_sits_at_the_foot_of_the_card_when_there_is_one() -> None:
    with_note = CARDS[7]
    assert with_note.notes
    async with ChromaCubeApp((with_note,), start_on_cards=True).run_test(size=(100, 30)) as pilot:
        await pilot.press("enter")
        await pilot.pause()
        note = pilot.app.screen.query_one("#card-note", Static)
        assert str(note.render()).startswith(with_note.notes[:20])
        last_clue = list(pilot.app.screen.query(ClueRow))[-1]
        assert note.virtual_region.y > last_clue.virtual_region.y


async def test_a_card_without_a_note_has_no_note() -> None:
    plain = replace(DEMO, notes="")
    async with ChromaCubeApp((plain,), start_on_cards=True).run_test(size=(100, 30)) as pilot:
        await pilot.press("enter")
        assert not pilot.app.screen.query("#card-note")


async def test_the_footer_counts_the_clues_when_all_are_in_sight() -> None:
    puzzle = replace(DEMO, difficulty="easy")
    async with ChromaCubeApp((puzzle,), start_on_cards=True).run_test(size=(120, 40)) as pilot:
        await pilot.press("enter")
        await pilot.pause()
        assert footer(pilot.app) == f"Easy · {len(DEMO.clues)} clues"


async def test_the_footer_says_which_clues_are_in_sight_on_a_small_terminal() -> None:
    puzzle = real("hard", "4x5")
    total = len(puzzle.clues)
    async with ChromaCubeApp((puzzle,), start_on_cards=True).run_test(size=(80, 24)) as pilot:
        await pilot.press("enter")
        await pilot.pause()
        assert card_edges(pilot.app)[1] == f"Hard · Clues 1–3 of {total}"
        await pilot.press("pagedown")
        await pilot.pause()
        assert card_edges(pilot.app)[1] == f"Hard · Clues 4–6 of {total}"


async def test_the_footer_points_to_a_note_that_is_out_of_sight() -> None:
    with_note = CARDS[18]
    total = len(with_note.clues)
    async with ChromaCubeApp((with_note,), start_on_cards=True).run_test(size=(80, 24)) as pilot:
        await pilot.press("enter")
        await pilot.pause()
        assert card_edges(pilot.app)[1] == f"Hard · {total} clues · note ↓"
        await pilot.press("pagedown", "pagedown")
        await pilot.pause()
        bottom = card_edges(pilot.app)[1]
        assert re.fullmatch(rf"Hard · Clues [2-6]–{total} of {total}", bottom), bottom


@pytest.mark.parametrize("number", range(1, len(CARDS) + 1))
async def test_every_classic_card_shows_its_name_and_count_in_full_at_80x24(number: int) -> None:
    puzzle = CARDS[number - 1]
    clues = len(puzzle.clues)
    async with ChromaCubeApp(CARDS, start_on_cards=True).run_test(size=(80, 24)) as pilot:
        pilot.app.open_card(number - 1)
        await pilot.pause()
        top, bottom = card_edges(pilot.app)
        assert top == f"{number} · {puzzle.title}"
        tier = puzzle.difficulty.capitalize()
        pattern = rf"({tier} · )?({clues} clues|Clues 1–\d+ of {clues})( · note ↓)?"
        assert re.fullmatch(pattern, bottom), bottom


async def test_a_long_footer_drops_the_tier_before_the_note_marker() -> None:
    puzzle = CARDS[20]
    async with ChromaCubeApp((puzzle,), start_on_cards=True).run_test(size=(80, 24)) as pilot:
        await pilot.press("enter")
        await pilot.pause()
        assert card_edges(pilot.app)[1] == "Clues 1–5 of 6 · note ↓"


@pytest.mark.parametrize(
    ("spec", "size", "name"),
    [
        (GameSpec.infinite("expert", 48213), (80, 24), "Seed 48213"),
        (GameSpec.daily(date(2026, 10, 8)), (80, 24), "Daily · 2026-10-08"),
        (GameSpec.infinite("hard", 99999, "4x5"), (100, 30), "Seed 99999 · 4×5"),
        (GameSpec.infinite("hard", 99999, "4x5"), (80, 24), "Seed 99999 · 4×5"),
    ],
    ids=["infinite", "daily", "4x5-wide", "4x5-narrow"],
)
async def test_generated_cards_show_the_seed_in_full(
    spec: GameSpec, size: tuple[int, int], name: str
) -> None:
    puzzle = real("hard", "4x5") if spec.layout == "4x5" else CARDS[0]
    async with ChromaCubeApp(CARDS, start_on_cards=True).run_test(size=size) as pilot:
        await pilot.app.push_screen(GeneratedPlayScreen(spec, puzzle))
        await pilot.pause()
        top, bottom = card_edges(pilot.app)
        assert top == name
        assert "…" not in bottom
