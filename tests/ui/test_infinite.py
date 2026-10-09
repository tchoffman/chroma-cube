"""Infinite and daily play through Textual's pilot, mostly with a stand-in generator."""

import threading
from dataclasses import replace
from datetime import date

import pytest
from textual.pilot import Pilot
from textual.widgets import Input, Label, OptionList

from chroma_cube.core import Placement, Puzzle
from chroma_cube.puzzles import classic_puzzles
from chroma_cube.solver import first_solution
from chroma_cube.ui import ChromaCubeApp
from chroma_cube.ui.home import DifficultyScreen, HomeScreen
from chroma_cube.ui.infinite import GeneratedPlayScreen, GeneratingScreen, SeedScreen
from chroma_cube.ui.screens import CardListScreen, WinScreen

SIZE = (120, 40)
DEMO = classic_puzzles()[0]
TODAY = date(2026, 10, 8)


class FakeGenerator:
    """Hands out the first classic card under a seeded id, and records every call."""

    def __init__(self) -> None:
        self.calls: list[tuple[int, str]] = []

    def __call__(self, seed: int, difficulty: str) -> Puzzle:
        self.calls.append((seed, difficulty))
        return replace(DEMO, id=f"gen-{difficulty}-{seed}", title=f"Puzzle {seed}")


def app(generate: object = None) -> ChromaCubeApp:
    return ChromaCubeApp(
        classic_puzzles(),
        generate=generate if generate is not None else FakeGenerator(),  # type: ignore[arg-type]
        today=lambda: TODAY,
    )


async def settle(pilot: Pilot[None]) -> None:
    """Let the generator thread finish and its result reach the screen."""
    await pilot.app.workers.wait_for_complete()
    await pilot.pause()
    await pilot.pause()


def playing(pilot: Pilot[None]) -> GeneratedPlayScreen:
    screen = pilot.app.screen
    assert isinstance(screen, GeneratedPlayScreen), screen
    return screen


def title(pilot: Pilot[None]) -> str:
    return str(pilot.app.screen.query_one("#card-title", Label).content)


async def start_infinite(pilot: Pilot[None], difficulty: str = "easy") -> None:
    """From the home screen, open Infinite and pick `difficulty`."""
    await pilot.press("down", "enter")
    assert isinstance(pilot.app.screen, DifficultyScreen)
    options = pilot.app.screen.query_one(OptionList)
    ids = [options.get_option_at_index(i).id for i in range(options.option_count)]
    options.highlighted = ids.index(difficulty)
    await pilot.press("enter")
    await settle(pilot)


async def solve(pilot: Pilot[None], puzzle: Puzzle, solution: Placement) -> None:
    for color, cell in solution.assignments.items():
        if puzzle.givens.cell_of(color) is None:
            await pilot.click(f"#chip-{color.id}")
            await pilot.click(f"#cell-{cell.row}-{cell.col}")
    await pilot.pause()


async def test_home_offers_classic_infinite_and_daily() -> None:
    async with app().run_test(size=SIZE) as pilot:
        assert isinstance(pilot.app.screen, HomeScreen)
        options = pilot.app.screen.query_one(OptionList)
        prompts = [str(options.get_option_at_index(i).prompt) for i in range(3)]
        assert prompts[0].startswith("Classic cards")
        assert prompts[1].startswith("Infinite")
        assert prompts[2].startswith("Daily")
        await pilot.press("enter")
        assert isinstance(pilot.app.screen, CardListScreen)
        await pilot.press("escape")
        assert isinstance(pilot.app.screen, HomeScreen)
        await pilot.press("down", "enter")
        assert isinstance(pilot.app.screen, DifficultyScreen)
        await pilot.press("escape")
        assert isinstance(pilot.app.screen, HomeScreen)


async def test_infinite_generates_a_puzzle_of_the_chosen_difficulty() -> None:
    generate = FakeGenerator()
    async with app(generate).run_test(size=SIZE) as pilot:
        await start_infinite(pilot, "hard")
        screen = playing(pilot)
        [(seed, difficulty)] = generate.calls
        assert difficulty == "hard"
        assert screen.spec.seed == seed
        assert title(pilot) == f"Infinite · hard · seed {seed}"
        await pilot.press("escape")
        assert isinstance(pilot.app.screen, DifficultyScreen)


async def test_n_gives_a_new_puzzle_with_another_seed() -> None:
    generate = FakeGenerator()
    async with app(generate).run_test(size=SIZE) as pilot:
        await start_infinite(pilot, "medium")
        first = playing(pilot).spec.seed
        await pilot.press("n")
        await settle(pilot)
        second = playing(pilot).spec
        assert second.difficulty == "medium" and second.seed != first
        assert generate.calls[-1] == (second.seed, "medium")
        await pilot.press("escape")
        assert isinstance(pilot.app.screen, DifficultyScreen)


async def test_a_typed_seed_replays_that_puzzle() -> None:
    generate = FakeGenerator()
    async with app(generate).run_test(size=SIZE) as pilot:
        await start_infinite(pilot, "easy")
        await pilot.press("s")
        assert isinstance(pilot.app.screen, SeedScreen)
        await pilot.press(*"48213", "enter")
        await settle(pilot)
        screen = playing(pilot)
        assert title(pilot) == "Infinite · easy · seed 48213"
        assert screen.state.puzzle == generate(48213, "easy")


async def test_a_bad_seed_is_explained_and_escape_keeps_the_puzzle() -> None:
    async with app().run_test(size=SIZE) as pilot:
        await start_infinite(pilot)
        before = playing(pilot).spec
        await pilot.press("s", "a", "b", "enter")
        assert isinstance(pilot.app.screen, SeedScreen)
        assert pilot.app.screen.query_one(Input).value == "ab"
        assert "whole number" in str(pilot.app.screen.query_one("#seed-error", Label).content)
        await pilot.press("escape")
        assert playing(pilot).spec == before


async def test_daily_uses_todays_date() -> None:
    generate = FakeGenerator()
    async with app(generate).run_test(size=SIZE) as pilot:
        await pilot.press("down", "down", "enter")
        await settle(pilot)
        playing(pilot)
        assert title(pilot) == "Daily · 2026-10-08"
        assert generate.calls == [(20261008, "medium")]
        await pilot.press("n")
        assert generate.calls == [(20261008, "medium")]
        await pilot.press("escape")
        assert isinstance(pilot.app.screen, HomeScreen)


async def test_winning_an_infinite_puzzle_offers_another() -> None:
    generate = FakeGenerator()
    async with app(generate).run_test(size=SIZE) as pilot:
        await start_infinite(pilot, "expert")
        first = playing(pilot)
        await solve(pilot, first.state.puzzle, _demo_solution())
        assert isinstance(pilot.app.screen, WinScreen)
        assert str(pilot.app.screen.query_one("#next").label) == "Another"
        await pilot.click("#next")
        await settle(pilot)
        second = playing(pilot)
        assert second is not first
        assert second.spec.difficulty == "expert" and second.spec.seed != first.spec.seed
        await solve(pilot, second.state.puzzle, _demo_solution())
        await pilot.click("#back")
        await pilot.pause()
        assert isinstance(pilot.app.screen, DifficultyScreen)


async def test_winning_the_daily_only_goes_back() -> None:
    async with app().run_test(size=SIZE) as pilot:
        await pilot.press("down", "down", "enter")
        await settle(pilot)
        await solve(pilot, playing(pilot).state.puzzle, _demo_solution())
        assert isinstance(pilot.app.screen, WinScreen)
        assert not pilot.app.screen.query("#next")
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(pilot.app.screen, HomeScreen)


async def test_generating_shows_a_notice_and_keeps_the_ui_live() -> None:
    release = threading.Event()
    fake = FakeGenerator()

    def slow(seed: int, difficulty: str) -> Puzzle:
        release.wait(5)
        return fake(seed, difficulty)

    async with app(slow).run_test(size=SIZE) as pilot:
        await pilot.press("down", "enter", "enter")
        await pilot.pause()
        assert isinstance(pilot.app.screen, GeneratingScreen)
        assert "Generating" in str(pilot.app.screen.query_one(Label).content)
        release.set()
        await settle(pilot)
        playing(pilot)


async def test_a_generator_failure_is_reported_and_play_continues() -> None:
    def broken(seed: int, difficulty: str) -> Puzzle:
        raise RuntimeError("no puzzle found")

    async with app(broken).run_test(size=SIZE) as pilot:
        await pilot.press("down", "enter", "enter")
        await settle(pilot)
        assert isinstance(pilot.app.screen, DifficultyScreen)
        assert any("no puzzle found" in str(n.message) for n in pilot.app._notifications)


def _demo_solution() -> Placement:
    solution = first_solution(DEMO)
    assert solution is not None
    return solution


async def test_a_generated_easy_puzzle_plays_to_a_win() -> None:
    generator = pytest.importorskip("chroma_cube.generator")
    generate = getattr(generator, "generate", None)
    if generate is None:
        pytest.skip("the generator is not on this branch yet")
    async with ChromaCubeApp(classic_puzzles(), today=lambda: TODAY).run_test(size=SIZE) as pilot:
        await pilot.press("down", "enter")
        await pilot.press("enter")  # easy is first
        await settle(pilot)
        screen = playing(pilot)
        puzzle = screen.state.puzzle
        assert puzzle == generate(screen.spec.seed, "easy")
        solution = first_solution(puzzle)
        assert solution is not None
        await solve(pilot, puzzle, solution)
        assert isinstance(pilot.app.screen, WinScreen)
