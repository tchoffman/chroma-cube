# Decisions

A running log. Newest at the bottom. Each entry: what we decided, why, and what we gave up.

## D1: The whole app is Python (2026-10-08)
The owner asked for an all-Python app. Core, solver, generator and UI all live in one
`chroma_cube` package. No JavaScript.

## D2: Terminal UI with Textual (2026-10-08)
Textual gives a pure-Python UI with mouse and keyboard, truecolor for the twelve cube
colors, a first-class test harness (`App.run_test()`), and `textual serve` to play in a
browser. Alternatives: Pygame (weaker testing, no browser), NiceGUI (ships a JS front end).

## D3: The tray is 3 rows × 4 columns (2026-10-08)
No source states the dimensions. A card 1 walkthrough places coral above orange and magenta
below it in one column, so columns have three cells. Twelve cells therefore means 3 × 4.
The board model is parameterised so other sizes are possible for generated puzzles.

## D4: The "classic" 25 puzzles are original, in the physical game's style (2026-10-08)
The card texts are not published online and copying them wholesale would be a copyright
problem anyway. We ship 25 original cards that use the twelve physical colors and introduce
clue types in the same order the reviews describe (positions first, then corners and
negation, either/or, "knows", initials, whole-board rules). Card 1 is reconstructed from the
published walkthrough.

## D5: "knows" means touching on a side or a corner (2026-10-08)
The game never defines it. We pick the 8-neighbourhood so that "knows" differs from
"sits next to" (4-neighbourhood) and reads naturally when a cube "knows" three others.

## D6: Clues are an AST; English is rendered, never parsed, in the game (2026-10-08)
Puzzles are data (givens + clue AST). Rendering AST → English is a small template job and
cannot be ambiguous. A parser for a restricted English is a separate, later feature for
authoring convenience.

## D7: Tooling: uv, pytest, ruff, mypy --strict, Python 3.11+ (2026-10-08)
TDD is the working style: write the failing test first, then the code. CI runs on 3.11 and
3.13.

## D8: Puzzle validity means "at least one solution"; uniqueness is a quality flag (2026-10-08)
The physical game allows multiple solutions. The solver reports the solution count (capped),
and the generator aims for uniqueness because unique puzzles are more satisfying to deduce.

## D9: A placement is board-agnostic and never moves a cube implicitly (2026-10-08)
`Placement` only maps colors to cells; it does not check that a cell is on a given board or
a color is in a given palette. Callers that care pass the palette (`unplaced`, `is_complete`)
or check the board themselves. Placing an already-placed color raises instead of moving it,
so a move is `without(color).with_color(color, cell)` and a mistaken double placement never
passes silently. A color's initial is derived from its name so the two cannot disagree.
We gave up a one-call "move" and board validation inside the placement.

## D10: The twelve hex values are our own picks, tuned for the terminal (2026-10-08)
No source gives the physical cubes' exact colors, so `CLASSIC_PALETTE`'s hex values are
approximations chosen to be told apart in a truecolor terminal. A review scored every pair
with CIEDE2000; the two weakest pairs were Mustard/Orange (17.4) and Cobalt/Purple (17.7), so
Mustard moved to `#ccb800` and Purple to `#9440d8`, lifting the closest pair to about 21.
Black is near-invisible on a dark background; the UI should give cubes a border or a light
tray rather than change the core value. The UI may adjust these values for display.
