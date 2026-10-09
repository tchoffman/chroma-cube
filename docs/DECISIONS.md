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

## D11: Relation, property and board-rule kinds are registry entries, not classes (2026-10-08)
One `Relation(kind, colors)` node, one `Property(kind, color, index)` node and one
`BoardRule(kind)` node, with a registry entry per kind that holds how it is decided and its
English. Board rules are decided by a three-valued function in their entry, since they
have no small set of colors to try out. The ternary
`between` is a relation with arity 3. Adding a kind (color-attribute clues are planned) is
one entry and touches no evaluator, renderer or serializer code. We gave up per-kind
classes that a type checker could tell apart; kinds are validated when a node is built.

## D12: Initials pick distinct colors, and `not` negates the whole choice (2026-10-08)
"B knows B" asks about two different B colors; a cube cannot be related to itself. A clue
with no valid choice (no Z colors, or "T knows T" with one T color) is false. `not` applied
to an initial clue means no choice works, which is how the sentence reads ("B isn't in a
corner"). The alternative, "some B color isn't in a corner", reads wrongly in English.

## D13: Partial evaluation is exact for named leaves, Kleene elsewhere (2026-10-08)
A relation or property naming its colors by id tries every placement of its own unplaced
colors on the free cells, which is at most a few hundred cases, and so is exact. With
initials, each choice of matching colors is decided on its own and the answers are
combined with a three-valued "or"; combinators combine their parts with Kleene logic; and
alphabetical rules check each line on its own. All three are sound (a decided answer holds
on every completion) but can stay UNKNOWN where a joint search would decide. That keeps
evaluation cheap and local (about a millisecond at worst on the classic board); the
solver does the global search. We gave up an exact live checker for initials and
combinations: it may show a clue as open a little longer than strictly needed.

## D14: Color references are bare strings in data (2026-10-08)
A reference is written `"black"` (an id) or `"B"` (an initial), so hand-written puzzle data
stays short. A single capital letter is always an initial, so a color id may never be one.
We gave up a fully explicit `{"id": ...}` / `{"initial": ...}` form.

## D15: The renderer takes the board, defaulting to the classic tray (2026-10-08)
"Top / middle / bottom row" needs the row count, so `render(clue, palette, board)` takes
an optional board. Compound clues nested in `and`, `or` or a count are bracketed so the
sentence cannot be misread; the price is some brackets in deeply nested generated clues.

## D16: A puzzle carries its own palette and board (2026-10-08)
Each stored puzzle lists its colors (id, name, hex) and board size instead of pointing at a
named palette, so generated puzzles on other boards or palettes need no lookup table and a
puzzle file stays readable on its own. Givens are written in reading order so files diff
cleanly. We gave up smaller files: the classic palette is repeated in every classic puzzle.

## D17: Picking up a cube leaves it on the tray until it is put down (2026-10-08)
Selecting a placed cube only marks it as held; it stays in its cell, so the clue markers do
not flicker while the player decides. Putting it on an empty cell moves it, on another
placed cube swaps the two, and on its own cell lets go. A palette cube put on a placed cube
sends that cube back to the palette. Returning a cube (`x`) acts on the held cube, or on
the cube under the cursor when nothing is held. All of this lives in a plain `PlayState`
class so it is tested without Textual; the screens only draw it and forward input.

## D18: Keyboard picks cubes by first letter, cycling, or by strip number (2026-10-08)
Typing a letter takes the next palette cube whose name starts with it (`m` cycles Magenta,
Mint, Mustard), which is faster to learn than numbers that shift as cubes leave the strip.
The digits `1`-`9` and `0` (tenth) take a cube by its place in the strip, as a fallback.
`q`, `r` and `x` are commands, so a color whose name starts with one of them is reachable
only by number or mouse; no classic color does. `Escape` first lets go of a held cube and
only leaves the card when nothing is held.

## D19: Cubes are drawn with their name, a contrast-picked text color and a border (2026-10-08)
Each cube cell is filled with its hex color and shows the color's name in black or white,
whichever has the higher WCAG contrast, so Teal, Mint and Emerald are never confused.
Every cube has a grey border and dark cubes (luminance below 0.18, e.g. Black, Cobalt,
Brown) a light one, so they stay visible on a dark theme without changing the core hex
values (see D10). Empty cells have a dashed border. Givens get a double border and a `▪`
before the name, and the held cube a thick border and a `▸`, both in the cube's own text
color: an emoji lock was hard to see on yellow and orange and its width varies by terminal.
Markers are text as well as border, since no single border color shows on every cube.

## D20: Solving is checked after every change and remembered only for the session (2026-10-08)
After each change, a card whose cubes are all placed and whose clues are all satisfied
opens a win dialog with "Next card" and "Back to list", and the card gets a tick in the
list. Solved cards are kept in memory only; persistence between runs is a separate feature.

## D21: The play screen sizes itself from the board and the terminal (2026-10-08)
The tray's rows and columns come from the puzzle's board, and every track is a fraction of
the space, so a 4x5 generated board fits as well as the classic 3x4. The palette strip has
as many columns as the board, one line per row of cubes. From 70 columns up the clues sit
beside the tray; below that they stack underneath with smaller cells, so 80x24 shows
everything and 60x20 still shows every cell and cube with a scrolling clue list. The clue
list never takes keyboard focus, so arrows always move the tray cursor; PageUp/PageDown or
the mouse wheel scroll it. Textual's command palette is off so its "palette" does not
collide with the game's.

## D22: The solver is backtracking with forward checking, on the evaluator as it is (2026-10-08)
The search keeps, for each unplaced color, the cells it could still take: a cell survives
while placing the color there leaves every clue that mentions the color not VIOLATED. It
places the color with the fewest candidates first and re-narrows the rest after every
placement. Clues are indexed by the colors they can name (an initial counts as every
matching color, a board rule as all of them), so only those clues are re-checked. Ruling a
cell out is safe because VIOLATED means no completion can satisfy the clue. The evaluator
in `core/` is unchanged: measured on the classic tray, a five-given puzzle proves unique in
about 2 ms, a ten-clue empty tray in about 25 ms, and the worst of roughly 1,800 random
clue sets took 0.25 s. We gave up cleverer propagation (all-different reasoning, clue
compilation) until a measurement asks for it.

## D23: `limit` counts solutions, and the solver looks one further (2026-10-08)
`solve(puzzle, limit=n)` returns up to `n` solutions and sets `truncated` when an `n + 1`th
exists, so one call can say "unique", "N solutions" or "more than N". The default limit is
1, which answers both "solvable?" and "unique?" with one search. `count_solutions(puzzle,
cap)` returns at most `cap`, so `cap` there means "at least `cap`".

## D24: The palette must fill the board exactly (2026-10-08)
A solution places every color and leaves no cell empty, matching the physical game. The
solver raises `ValueError` when the palette size differs from the cell count rather than
guessing what an empty cell means for the alphabetical rules.
