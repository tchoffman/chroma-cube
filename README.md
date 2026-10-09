# Chroma Cube

A digital version of **Chroma Cube**, the single-player color-cube deduction puzzle:
twelve colored cubes, a 3×4 tray, and a card of clues that pins down where every cube goes.

This project goes further than the physical game:

- a **clue language** that models every relationship a clue can express,
- a **solver** that checks any puzzle is solvable (and whether its answer is unique),
- a **generator** that produces endless new, verified puzzles,
- a terminal UI (Textual) you can also serve in a browser.

## Play

```bash
uv sync
uv run chroma-cube
```

## Develop

```bash
uv sync --all-groups
uv run pytest -q
uv run ruff check . && uv run ruff format --check . && uv run mypy
```

Design decisions are recorded in [docs/DECISIONS.md](docs/DECISIONS.md).
Feature work is tracked in GitHub Issues.
