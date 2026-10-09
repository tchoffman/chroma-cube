# Working in this repo (for humans and agents)

## What this is
A Python digital version of the Chroma Cube logic puzzle. Read `docs/GAME.md` (rules),
`docs/CLUE_LANGUAGE.md` (the clue model), and `docs/DECISIONS.md` (why things are the way
they are) before changing anything.

## Layout
- `src/chroma_cube/core/`      colors, board, placement, clue AST, evaluation, rendering
- `src/chroma_cube/solver/`    solution search, uniqueness, deduction steps
- `src/chroma_cube/generator/` random puzzle generation and difficulty rating
- `src/chroma_cube/puzzles/`   the shipped puzzle sets (data + loader)
- `src/chroma_cube/progress.py` saved progress (solved cards, last board) as a JSON file
- `src/chroma_cube/ui/`        the Textual app
- `tests/`                     mirrors the package layout

## How we work
- **TDD.** Write the failing test first, make it pass, refactor. Every PR adds tests.
- **Pure core.** Nothing under `core/`, `solver/`, `generator/`, `puzzles/`, nor
  `progress.py`, imports Textual.
- **Type-checked.** `uv run mypy` is strict and must pass. `uv run ruff check .` and
  `uv run ruff format --check .` must pass. Format only the files you touched.
- **One issue per PR.** Branch `feat/<issue>-<slug>`, PR body starts with what it does in
  plain terms and ends with `Closes #<issue>`.
- **Decisions.** Any design call that is not forced by the issue goes into
  `docs/DECISIONS.md` as a new numbered entry in the same PR.
- **No issue numbers in code or comments.** They belong in branches, commits and PRs.

## Commands
```bash
uv sync --all-groups
uv run pytest -q
uv run ruff check . && uv run ruff format --check . && uv run mypy
uv run chroma-cube
```
