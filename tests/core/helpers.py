from chroma_cube.core import CLASSIC_PALETTE, Cell, Palette, Placement


def grid(rows: list[list[str | None]], palette: Palette = CLASSIC_PALETTE) -> Placement:
    """A placement drawn as rows of color ids; None leaves a cell empty."""
    return Placement(
        {
            palette.by_id(color_id): Cell(r, c)
            for r, row in enumerate(rows)
            for c, color_id in enumerate(row)
            if color_id is not None
        }
    )


FULL = grid(
    [
        ["black", "brown", "cobalt", "coral"],
        ["emerald", "magenta", "mint", "mustard"],
        ["orange", "purple", "teal", "white"],
    ]
)
"""A complete classic board in which every row and column is alphabetical."""
