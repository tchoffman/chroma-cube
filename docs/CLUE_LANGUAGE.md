# Clue language

The clue language is the heart of the project. Puzzles are *data*: a set of givens plus a
list of clues. Clues are structured values (an AST), not strings. English text is rendered
from the AST, and the solver and the live clue checker both evaluate the same AST.

## Board model

- A board is `rows × cols` cells (the classic tray is 3 × 4). Rows are numbered from the
  top starting at 0, columns from the left starting at 0.
- A *placement* maps colors to cells. A *partial* placement may leave colors unplaced.
- Named regions: `corner`, `edge` (any cell on the border), `center` (any cell not on the
  border), `top row`, `middle row`, `bottom row`, `column 1..4`.

## Relations (binary, between two colors A and B)

| Relation            | True when                                                   | English                               |
|---------------------|-------------------------------------------------------------|---------------------------------------|
| `same_row`          | A and B share a row                                         | "A and B are in the same row"         |
| `same_column`       | A and B share a column                                      | "A and B are in the same column"      |
| `next_to`           | A and B are orthogonally adjacent                           | "A sits next to B"                    |
| `knows`             | A and B touch on a side **or a corner** (8-neighbourhood)   | "A knows B"                           |
| `diagonal`          | A and B are diagonally adjacent                             | "A is diagonal to B"                  |
| `above`             | same column, A in a higher row (any distance)               | "A is above B"                        |
| `below`             | same column, A in a lower row                               | "A is below B"                        |
| `left_of`           | same row, A to the left (any distance)                      | "A is left of B"                      |
| `right_of`          | same row, A to the right                                    | "A is right of B"                     |
| `directly_above`    | A immediately above B                                       | "A is directly above B"               |
| `directly_below`    | A immediately below B                                       | "A is directly below B"               |
| `directly_left_of`  | A immediately left of B                                     | "A is directly left of B"             |
| `directly_right_of` | A immediately right of B                                    | "A is directly right of B"            |
| `between`           | ternary: A is directly between B and C in a line            | "A is between B and C"                |

`between(A, B, C)` means B and C sit on the two cells right next to A, on opposite sides,
in one row or one column. The order of B and C does not matter.

## Properties (unary, about one color)

| Property   | True when                              | English                   |
|------------|----------------------------------------|---------------------------|
| `in_corner`| the cell is a corner                   | "A is in a corner"        |
| `on_edge`  | the cell is on the border              | "A is on an edge"         |
| `in_center`| the cell is not on the border          | "A is in the center"      |
| `in_row r` | the cell is in row r                   | "A is in the top row"     |
| `in_col c` | the cell is in column c                | "A is in the second column" |

Rows are named top / middle / bottom on a 3-row board; on other boards the first and last
rows are top and bottom and the rest are ordinals ("the third row"). Columns are always
ordinals counted from the left ("the first column").

Relation, property and board-rule kinds are registry entries (`RELATION_KINDS`,
`PROPERTY_KINDS`, `BOARD_RULE_KINDS` in `chroma_cube.core.clues`) holding how the kind is
decided and its English. Adding a kind means adding one entry.

## Color references

A clue refers to a color by name (`black`) or by **initial** (`B`). An initial means
"some color in the palette whose name starts with this letter". A clue with initials is
true if there is *some* choice of matching colors that makes it true.

- The colors chosen for one clue must be different: "B knows B" asks whether Black and
  Brown touch, not whether Black touches itself. A clue with no valid choice is false.
- `not` negates the whole existential: "B isn't in a corner" means *no* B color is in a
  corner.
- In data and in code a reference is a string: one capital letter is an initial, anything
  else is a color id. Color ids are therefore never a single capital letter.
- Initials render as the bare letter: "B sits next to M".

## Combinators

- `not(clue)`, `and(clues...)`, `or(clues...)`. `and` and `or` need at least one clue.
- `exactly(n, clues...)`, `at_least(n, clues...)`: counting over sub-clues, with
  `0 <= n <= len(clues)` for `exactly` and `1 <= n <= len(clues)` for `at_least`
  ("at least zero" is always true, so it is rejected).
- Board-wide rules: `rows_alphabetical` (every row reads in alphabetical order of color
  name, left to right) and `columns_alphabetical` (top to bottom). Names compare
  case-insensitively.

### English

| Clue                                    | English                                                 |
|-----------------------------------------|---------------------------------------------------------|
| `not` of a relation or property         | the negated template: "Black isn't in a corner", "Black doesn't know White" |
| `not` of anything else                  | "It's not true that ..."                                |
| `and`                                   | "X, Y and Z"                                            |
| `and` of one relation from one color    | "Black knows White, Teal and Mint" (when the template ends with the second color and the shared color is named, not an initial) |
| `or`                                    | "Either X or Y", "Either X, Y or Z"; a one-clue `or` is just that clue |
| `exactly(n)` / `at_least(n)`            | "Exactly one of these is true: X; Y; Z"                 |
| `rows_alphabetical`                     | "Every row is in alphabetical order from left to right" |
| `columns_alphabetical`                  | "Every column is in alphabetical order from top to bottom" |

A compound clue inside `and`, `or` or a count is wrapped in brackets.

`and` never merges when the shared color is an initial: each part picks its own B color,
so `and(knows(B, White), knows(B, Teal))` reads "B knows White and B knows Teal", not
"B knows White and Teal" (which would say one B knows both).

## Reading clues from text

`parse_clue(text, palette, board)` reads one sentence back into a clue, and
`parse_clues(text, ...)` reads one clue per line (blank lines and "1." / "2)" numbering are
skipped). Every sentence `render` produces parses back to the same clue. A one-clue `and` or
`or` renders as its only clue, so it comes back as that clue. Unreadable text raises
`ClueParseError` with a message and the character offset of the problem.

The accepted grammar, informally (keywords are case-insensitive, the final full stop is
optional):

```
clue   := "It's not true that" clue | "Either" unit ("," | "or" | ", or") unit ...
        | ("Exactly" | "At least") N "of these is/are true:" clue ("; " clue)*
        | unit (("," | "and" | "but" | "or" | ", and" | ", or" | ", but") item)*
unit   := "(" clue ")" | board rule | leaf sentence | negated leaf sentence
item   := unit | color            (continues "Black knows White, Teal and Mint")
        | color "is"/"isn't"/"does"/"doesn't"   (repeats the last clause: "but Mustard is")
color  := a palette color name, any case | one capital letter (an initial)
```

- One list uses one connective: "A and B or C" is an error; bracket one side.
- Leaf sentences are the registry templates plus variants: "is next to", "is beside";
  "isn't" / "is not", "doesn't" / "does not"; "A is in the same row as B"; "is to the left
  of"; "in the corner"; "on the edge"; "in the middle" (center).
- Rows: "the top / middle / bottom row", "the third row", "row 3". Columns: "the second
  column", "the 7th column", "column 2". Numbers in text count from 1; indices in the AST
  from 0. A row or column off the board is an error.
- A leaf may name alternatives as its subject: "Either Teal or Black is in the same row as
  Cobalt" reads as `or(same_row(teal, cobalt), same_row(black, cobalt))`.

## Data format

`clue_to_dict` / `clue_from_dict` convert clues to plain JSON-compatible dicts:

```json
{"type": "relation", "kind": "next_to", "colors": ["black", "M"]}
{"type": "property", "kind": "in_row", "color": "black", "index": 0}
{"type": "board_rule", "kind": "rows_alphabetical"}
{"type": "not", "clue": {...}}
{"type": "and", "clues": [...]}          // also "or"
{"type": "exactly", "n": 2, "clues": [...]}  // also "at_least"
```

`index` is only present for `in_row` and `in_col`. Malformed data raises `ValueError`.

A whole puzzle (`Puzzle`, `puzzle_to_dict` / `puzzle_from_dict` in `chroma_cube.core.puzzle`)
is stored as:

```json
{"id": "classic-01", "title": "...", "difficulty": "", "notes": "",
 "board": {"rows": 3, "cols": 4},
 "palette": [{"id": "black", "name": "Black", "hex": "#1c1c1c"}, ...],
 "givens": [{"color": "black", "row": 0, "col": 0}],
 "clues": [...]}
```

`difficulty` and `notes` may be left out. Givens must use palette colors and on-board cells.

## Evaluation on a partial board

For the live checker in the UI, each clue evaluates to one of three values:
`SATISFIED`, `VIOLATED`, or `UNKNOWN` (cannot be decided until more cubes are placed).
The solver uses the same three-valued evaluation to prune.

- **Relations and properties that name colors by id are exact.** They are `UNKNOWN` only
  if some way of putting the clue's unplaced colors on the free cells makes them true and
  another makes them false. So two placed cubes in different rows already violate
  `same_row`, and an unplaced cube whose only free cells are corners already satisfies
  `in_corner`.
- **Initials** are decided one choice of colors at a time, then combined with the
  three-valued "or": satisfied if any choice is satisfied, violated only if every choice
  is violated. A decided answer is always right, but the clue can stay `UNKNOWN` longer
  than a joint search would. Example: with Black, Brown and White left for three free
  cells, two of them corners, some B always lands in a corner, yet `in_corner(B)` stays
  `UNKNOWN` because neither Black nor Brown is forced into one on its own.
- **Combinators** use Kleene logic (`and` is violated by any violated part, satisfied when
  all parts are; `or` the reverse). Counts are decided from how many sub-clues are
  satisfied and how many are still unknown. This can leave a combination `UNKNOWN` even
  when every completion would decide it the same way (for example `X or not X`).
- **Alphabetical rules** are violated as soon as a line's placed cubes are out of order,
  or a run of free cells cannot be filled because too few unplaced colors sort between its
  neighbours. They are satisfied once every line is full and in order. Lines are checked
  one at a time, so a board whose lines compete for the same few colors can stay
  `UNKNOWN` until it fills up.
