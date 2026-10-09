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

## Properties (unary, about one color)

| Property   | True when                              | English                   |
|------------|----------------------------------------|---------------------------|
| `in_corner`| the cell is a corner                   | "A is in a corner"        |
| `on_edge`  | the cell is on the border              | "A is on an edge"         |
| `in_center`| the cell is not on the border          | "A is in the center"      |
| `in_row r` | the cell is in row r                   | "A is in the top row"     |
| `in_col c` | the cell is in column c                | "A is in the second column" |

## Color references

A clue refers to a color by name (`black`) or by **initial** (`B`). An initial means
"some color in the palette whose name starts with this letter". A clue with initials is
true if there is *some* choice of matching colors that makes it true.

## Combinators

- `not(clue)`, `and(clues...)`, `or(clues...)`.
- `exactly(n, clues...)`, `at_least(n, clues...)`: counting over sub-clues.
- Board-wide rules: `rows_alphabetical`, `columns_alphabetical`.

## Evaluation on a partial board

For the live checker in the UI, each clue evaluates to one of three values:
`SATISFIED`, `VIOLATED`, or `UNKNOWN` (cannot be decided until more cubes are placed).
The solver uses the same three-valued evaluation to prune.
