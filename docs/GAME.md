# Chroma Cube: how the game works

Research summary of the physical game (Project Genius, 2018). Sources are listed at the
bottom. Where the sources are silent we made a call; those calls are in `DECISIONS.md`.

## Components

- **12 cubes**, one per color: black, brown, cobalt, coral, emerald, magenta, mint, mustard,
  orange, purple, teal, white.
- **A tray** with 12 positions. Reviewers' walkthroughs place three cubes in one column
  (coral above orange, magenta below it), so the tray is **3 rows × 4 columns**.
- **25 puzzle cards**, numbered and increasing in difficulty. Each card shows some cubes
  already placed (the *givens*) and a list of clues. Card 8 starts with an empty tray.
  The back of a card shows one solution; other solutions may exist.

## Goal

Place all 12 cubes so that every clue on the card is true.

## Clue vocabulary seen in the physical game

- Same row / same column: "Coral and Magenta are in the same column."
- Adjacency: "Black sits next to Magenta."
- Either/or: "Either Teal or Black sits next to Cobalt." (Our card 1 adapts this to "Either
  Teal or Black is in the same row as Cobalt" so that every clue on it is needed.)
- Corners and negation: "White isn't in a corner, but Mustard is."
- A cryptic relation: "Mint knows Cobalt, Magenta, and Brown." The game never defines
  "knows"; the player works it out from earlier cards.
- First-letter references: a clue names colors only by initial ("B"), so the player has to
  consider Black and Brown.
- Whole-board rules: "the cubes in each row are in alphabetical order from left to right."
- A few clues rely on outside knowledge (the colors of the Irish flag).

## Card 1 walkthrough

The Timberdoodle review solves card 1 in this order: Coral and Magenta together first, then
Black, then Teal ("to the right of Cobalt"), and Mint last. Our card 1 keeps that layout and
those five cubes to place. A player follows the same order: clue 1 puts Coral and Magenta in
Orange's column, clue 4 puts Coral on top, then clue 2 places Black, clue 3 places Teal, and
Mint goes in the last free cell (`tests/puzzles/test_classic.py` checks each step). The hint
engine places Coral first, then Black before Magenta, because Black rests on fewer clues;
then Teal and Mint (`tests/solver/test_hints.py`).

## Sources

- The Board Game Family review: https://www.theboardgamefamily.com/2018/12/chroma-cube-is-a-colorful-puzzle-game/
- Timberdoodle review with a card 1 walkthrough: https://cumminslife.blogspot.com/2019/10/timberdoodles-chroma-cube-review.html
- PuzzleNation review: https://puzzculture.com/2018/11/08/puzzlenation-product-review-chroma-cube/
- Publisher page: https://projectgeniusinc.com/products/chroma-cube
