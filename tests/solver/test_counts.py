"""Count reasoning over candidates: what it rules out, and what it charges."""

from chroma_cube.core import EXTENDED_16, Board, Cell, Clue, Color, Palette, Placement
from chroma_cube.core.clues import Region, attribute
from chroma_cube.solver.counts import CountPropagator

BOARD = Board(2, 3)
SIX = Palette(
    tuple(EXTENDED_16.by_id(i) for i in ("purple", "lavender", "black", "brown", "coral", "white"))
)
PURPLE, LAVENDER, BLACK, BROWN, CORAL, WHITE = SIX.colors


def narrow(
    clues: list[Clue], candidates: dict[Color, tuple[Cell, ...]], widest: int = 0
) -> tuple[bool, dict[Color, tuple[Cell, ...]], int]:
    counts = CountPropagator(BOARD, SIX, clues, ())
    charged = [0]

    def charge(trials: int) -> None:
        charged[0] += trials

    narrowed = dict(candidates)
    alive = set(range(len(clues)))
    ok = counts.narrow(Placement(), narrowed, alive, charge, widest=widest)
    return ok, narrowed, charged[0]


def everywhere(**fixed: tuple[Cell, ...]) -> dict[Color, tuple[Cell, ...]]:
    return {color: fixed.get(color.id, tuple(BOARD)) for color in SIX}


def test_a_neighbour_clue_keeps_the_only_matching_color_next_to_its_subject() -> None:
    # Lavender is the only other purple, so it must sit next to wherever Purple can go.
    ok, narrowed, _ = narrow(
        [attribute("next_to_family", "purple", color="purple")],
        everywhere(purple=(Cell(0, 0),)),
    )
    assert ok
    assert narrowed[LAVENDER] == (Cell(0, 1), Cell(1, 0))


def test_a_neighbour_clue_keeps_its_subject_where_a_match_can_reach() -> None:
    ok, narrowed, _ = narrow(
        [attribute("next_to_family", "purple", color="purple")],
        everywhere(lavender=(Cell(1, 2),)),
    )
    assert ok
    assert narrowed[PURPLE] == (Cell(0, 2), Cell(1, 1))


def test_a_region_count_with_no_room_left_ends_the_branch() -> None:
    # Two dark colors in the top row, but every dark color is kept in the bottom row.
    bottom = tuple(BOARD.row(1))
    ok, _, _ = narrow(
        [attribute("region_count", "dark", region=Region("row", 0), n=2)],
        everywhere(purple=bottom, black=bottom, brown=bottom),
    )
    assert not ok


def test_probing_drops_a_cell_that_settles_into_a_dead_end_and_is_charged() -> None:
    # Every cube in the right column is light, so dark Purple must take the top-left
    # cell. The counts alone leave Coral that cell too; putting Coral there leaves Purple
    # nowhere, so a probe rules it out.
    clues = [attribute("region_all", "light", region=Region("column", 2))]
    start = everywhere(purple=(Cell(0, 0), Cell(1, 2)), coral=(Cell(0, 0), Cell(0, 2)))
    _, without, nothing = narrow(clues, start, widest=0)
    ok, probed, charged = narrow(clues, start, widest=len(BOARD))
    assert ok
    assert without[PURPLE] == probed[PURPLE] == (Cell(0, 0),)
    assert without[CORAL] == (Cell(0, 0), Cell(0, 2))
    assert probed[CORAL] == (Cell(0, 2),)
    assert nothing == 0 and charged > 0
