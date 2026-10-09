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

Relation and property kinds are registry entries (`RELATION_KINDS`, `PROPERTY_KINDS` in
`chroma_cube.core.clues`) holding the predicate and the English templates. Adding a kind
means adding one entry.

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
  `0 <= n <= len(clues)`.
- Board-wide rules: `rows_alphabetical` (every row reads in alphabetical order of color
  name, left to right) and `columns_alphabetical` (top to bottom). Names compare
  case-insensitively.

### English

| Clue                                    | English                                                 |
|-----------------------------------------|---------------------------------------------------------|
| `not` of a relation or property         | the negated template: "Black isn't in a corner", "Black doesn't know White" |
| `not` of anything else                  | "It's not true that ..."                                |
| `and`                                   | "X, Y and Z"                                            |
| `and` of one relation from one color    | "Black knows White, Teal and Mint" (when the template ends with the second color) |
| `or`                                    | "Either X or Y", "Either X, Y or Z"                     |
| `exactly(n)` / `at_least(n)`            | "Exactly one of these is true: X; Y; Z"                 |
| `rows_alphabetical`                     | "Every row is in alphabetical order from left to right" |
| `columns_alphabetical`                  | "Every column is in alphabetical order from top to bottom" |

A compound clue inside `and`, `or` or a count is wrapped in brackets.

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

## Evaluation on a partial board

For the live checker in the UI, each clue evaluates to one of three values:
`SATISFIED`, `VIOLATED`, or `UNKNOWN` (cannot be decided until more cubes are placed).
The solver uses the same three-valued evaluation to prune.

- **Relations and properties are exact.** They are `UNKNOWN` only if some way of putting
  the clue's unplaced colors on the free cells makes them true and another makes them
  false. So two placed cubes in different rows already violate `same_row`, and an
  unplaced cube whose only free cells are corners already satisfies `in_corner`.
- **Initials** take the three-valued "or" over every choice of distinct matching colors:
  satisfied if any choice is satisfied, violated only if every choice is violated.
- **Combinators** use Kleene logic (`and` is violated by any violated part, satisfied when
  all parts are; `or` the reverse). Counts are decided from how many sub-clues are
  satisfied and how many are still unknown. This can leave a combination `UNKNOWN` even
  when every completion would decide it the same way (for example `X or not X`).
- **Alphabetical rules** are violated as soon as a line's placed cubes are out of order,
  or a run of free cells cannot be filled because too few unplaced colors sort between its
  neighbours. They are satisfied once every line is full and in order. Lines are checked
  one at a time, so a board whose lines compete for the same few colors can stay
  `UNKNOWN` until it fills up.
