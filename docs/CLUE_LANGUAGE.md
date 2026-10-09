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

Relation, property, attribute and board-rule kinds are registry entries (`RELATION_KINDS`,
`PROPERTY_KINDS`, `ATTRIBUTE_KINDS`, `BOARD_RULE_KINDS` in `chroma_cube.core.clues`) holding
how the kind is decided and its English. Adding a kind means adding one entry.

## Color attributes

Every color has a **temperature** (`warm`, `cool`, `neutral`), a **tone** (`light`,
`dark`) and a hue **family** (`red`, `orange`, `yellow`, `green`, `blue`, `purple`, `pink`,
`brown`, `grey`). The three vocabularies share no word, so "cool" or "green" names one
attribute on its own. A palette may set them; any it leaves out come from the hex
(`attributes_from_hex`): grey-ish colors are neutral and grey, otherwise the hue gives the
family and the family the temperature (reds, oranges, yellows, pinks and browns are warm),
and a color is light from a relative luminance of 0.18 up. The built-in palettes set every
attribute by hand, and their choices agree with the hex (see D35).

| Color    | Hex       | Temperature | Tone  | Family |
|----------|-----------|-------------|-------|--------|
| Black    | `#1c1c1c` | neutral     | dark  | grey   |
| Brown    | `#8b5a2b` | warm        | dark  | brown  |
| Cobalt   | `#0047ab` | cool        | dark  | blue   |
| Coral    | `#ff6f61` | warm        | light | red    |
| Emerald  | `#009b4d` | cool        | light | green  |
| Magenta  | `#e0218a` | warm        | light | pink   |
| Mint     | `#98ffb3` | cool        | light | green  |
| Mustard  | `#ccb800` | warm        | light | yellow |
| Orange   | `#ff8c00` | warm        | light | orange |
| Purple   | `#9440d8` | cool        | dark  | purple |
| Teal     | `#008080` | cool        | dark  | blue   |
| White    | `#f5f5f5` | neutral     | light | grey   |
| Azure    | `#5ec8ff` | cool        | light | blue   |
| Garnet   | `#b3121f` | warm        | dark  | red    |
| Lavender | `#d4a8ff` | cool        | light | purple |
| Silver   | `#999999` | neutral     | light | grey   |
| Cyan     | `#00ffff` | cool        | light | blue   |
| Denim    | `#5580ff` | cool        | light | blue   |
| Forest   | `#335500` | cool        | dark  | green  |
| Indigo   | `#330055` | cool        | dark  | purple |

Palettes (`PALETTES` in `chroma_cube.core.colors`): `classic` (the first twelve, for the
3 × 4 tray), `extended-16` (the first sixteen, for `BOARD_4X4`) and `extended-20` (all
twenty, for `BOARD_4X5`, four rows of five).

## Attribute clues (about the colors next to a color, or in a region)

An attribute clue counts how many cubes in a group of cells have a value. The group is the
cells **sharing a side** with a color (as in `next_to`), or a named region. A *quality* is a
temperature or tone (`warm`, `cool`, `neutral`, `light`, `dark`); a *family* is a hue family.

| Kind              | Takes                    | True when                                  | English |
|-------------------|--------------------------|--------------------------------------------|---------|
| `neighbours_all`  | color, quality           | every cube next to the color has it        | "Every cube next to Mint is a cool color" |
| `neighbours_none` | color, quality           | no cube next to the color has it           | "No cube next to Mint is a warm color" |
| `neighbours_some` | color, quality           | at least one cube next to the color has it | "Coral sits next to a dark color" |
| `next_to_family`  | color, family            | at least one cube next to it is in the family | "Coral sits next to a shade of green" |
| `region_all`      | region, quality          | every cube in the region has it            | "Every cube in the corners is a warm color" |
| `region_count`    | region, quality, count n | exactly n cubes in the region have it      | "Exactly two light colors are in the top row" |

Negated: "Not every cube next to Mint is a cool color", "Some cube next to Mint is a warm
color" (not `neighbours_none`), "Coral doesn't sit next to a dark color" / "a shade of
green", "Not every cube in the corners is a warm color". A negated `region_count` is "It's
not true that exactly two light colors are in the top row".

Regions are `corners` ("in the corners"), `edge` ("on the edge"), `center` ("in the
center"), `row` and `column` with an index ("in the top row", "in the second column"). A
region's empty cells count for nothing, so on a board with more cells than colors "every
cube in the corners" means every cube that is in a corner.

Properties like "Mint is a cool color" are true or false whatever the placement, so they
are not clues. Neither are "Mint and Teal are the same temperature" and the like.

`attribute_clues(board, palette)` lists every attribute clue that names colors by id and
fits the board, leaving out values no palette color has. A puzzle generator draws from it, so
a new attribute kind reaches the generator without changes there.

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
| `or` of 2–3 like clauses, first color differs | "Either Teal or Black is in the same row as Cobalt", "Either Teal, Mint or B is in a corner" |
| `exactly(n)` / `at_least(n)`            | "Exactly one of these is true: X; Y; Z"                 |
| `rows_alphabetical`                     | "Every row is in alphabetical order from left to right" |
| `columns_alphabetical`                  | "Every column is in alphabetical order from top to bottom" |

A compound clue inside `and`, `or` or a count is wrapped in brackets.

The short `or` form is used when every part is the same positive relation (two colors) or
property, the parts differ only in their first color, those colors are all different, and a
relation's second color is named rather than an initial. Colors are never swapped to make a
clue fit, even for symmetric kinds like `next_to`, because the sentence must read back as the
same clue. A relation whose `text` has two subjects ("{0} and {1} are in the same row") gives
a one-subject `alternatives` template in its registry entry ("{0} is in the same row as {1}").

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
- A short repeat takes the first clause's verb: "Black is in a corner, but Teal is";
  "Black knows White, but Teal doesn't".
- Limits: a leaf names at most three alternative colors, and brackets and "It's not true
  that" nest at most 16 deep.
- Color names may contain spaces and punctuation ("Sky Blue", "Off-White").
- Leaf sentences are the registry templates plus variants: "is next to", "is beside";
  "isn't" / "is not", "doesn't" / "does not"; "A is in the same row as B"; "is to the left
  of"; "in the corner"; "on the edge"; "in the middle" (center).
- Rows: "the top / middle / bottom row", "the third row", "row 3". Columns: "the second
  column", "the 7th column", "column 2". Numbers in text count from 1; indices in the AST
  from 0. A row or column off the board is an error.
- Attribute clues: "in the middle" for the center region; any number word or digits for
  a count; "color" / "colors" and "is" / "are" in either form ("Exactly one light colors
  is in column 2" reads fine). A family that is also a color name ("a shade of orange")
  reads as the family.
- A leaf may name alternatives as its subject: "Either Teal or Black is in the same row as
  Cobalt" reads as `or(same_row(teal, cobalt), same_row(black, cobalt))`, in that order. This
  is the renderer's short `or` form.

## Data format

`clue_to_dict` / `clue_from_dict` convert clues to plain JSON-compatible dicts:

```json
{"type": "relation", "kind": "next_to", "colors": ["black", "M"]}
{"type": "property", "kind": "in_row", "color": "black", "index": 0}
{"type": "attribute", "kind": "neighbours_all", "value": "cool", "color": "mint"}
{"type": "attribute", "kind": "region_count", "value": "light", "region": "row", "index": 0, "n": 2}
{"type": "board_rule", "kind": "rows_alphabetical"}
{"type": "not", "clue": {...}}
{"type": "and", "clues": [...]}          // also "or"
{"type": "exactly", "n": 2, "clues": [...]}  // also "at_least"
```

`index` is only present for `in_row` and `in_col`, and for `row` and `column` regions.
An attribute clue has `color` or `region` (never both), and `n` only for `region_count`.
Malformed data raises `ValueError`.

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
A palette entry may also carry `temperature`, `tone` and `family`; they are written only
when they differ from what the hex gives, and left-out ones are derived (D38). So puzzle
files written before colors had attributes load and save unchanged. A `region_count` may not
count more cubes than its region has cells.

## Evaluation on a partial board

For the live checker in the UI, each clue evaluates to one of three values:
`SATISFIED`, `VIOLATED`, or `UNKNOWN` (cannot be decided until more cubes are placed).
The solver uses the same three-valued evaluation to prune.

- **Relations and properties that name colors by id are exact.** They are `UNKNOWN` only
  if some way of putting the clue's unplaced colors on the free cells makes them true and
  another makes them false. So two placed cubes in different rows already violate
  `same_row`, and an unplaced cube whose only free cells are corners already satisfies
  `in_corner`.
- **Attribute clues that name colors by id, and region clues, are exact too.** The
  evaluator counts the matching and other cubes already in the cells, then checks every
  split of the unplaced colors between those cells' empty spots and the rest of the board;
  an unplaced subject color is tried on each free cell. With initials they follow the rule
  below.
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
