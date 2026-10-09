import pytest

from chroma_cube.core import CLASSIC_PALETTE, Cell, Placement

coral = CLASSIC_PALETTE.by_id("coral")
orange = CLASSIC_PALETTE.by_id("orange")
magenta = CLASSIC_PALETTE.by_id("magenta")


def test_empty_placement_has_nothing_placed() -> None:
    empty = Placement()
    assert empty.cell_of(coral) is None
    assert empty.color_at(Cell(0, 0)) is None
    assert empty.unplaced(CLASSIC_PALETTE) == CLASSIC_PALETTE.colors
    assert not empty.is_complete(CLASSIC_PALETTE)


def test_build_from_givens_and_query_both_ways() -> None:
    placement = Placement({coral: Cell(0, 1), orange: Cell(1, 1)})
    assert placement.cell_of(coral) == Cell(0, 1)
    assert placement.color_at(Cell(1, 1)) == orange
    assert placement.cell_of(magenta) is None
    assert placement.color_at(Cell(2, 1)) is None


def test_givens_may_not_share_a_cell() -> None:
    with pytest.raises(ValueError):
        Placement({coral: Cell(0, 0), orange: Cell(0, 0)})


def test_with_color_returns_a_new_placement() -> None:
    before = Placement({coral: Cell(0, 1)})
    after = before.with_color(magenta, Cell(2, 1))
    assert after.color_at(Cell(2, 1)) == magenta
    assert after.cell_of(coral) == Cell(0, 1)
    assert before.cell_of(magenta) is None


def test_with_color_rejects_placing_a_color_twice() -> None:
    placement = Placement({coral: Cell(0, 1)})
    with pytest.raises(ValueError):
        placement.with_color(coral, Cell(2, 2))
    with pytest.raises(ValueError):
        placement.with_color(coral, Cell(0, 1))


def test_with_color_rejects_an_occupied_cell() -> None:
    placement = Placement({coral: Cell(0, 1)})
    with pytest.raises(ValueError):
        placement.with_color(orange, Cell(0, 1))


def test_without_removes_a_color() -> None:
    placement = Placement({coral: Cell(0, 1), orange: Cell(1, 1)})
    after = placement.without(coral)
    assert after.cell_of(coral) is None
    assert after.color_at(Cell(0, 1)) is None
    assert after.cell_of(orange) == Cell(1, 1)
    assert placement.cell_of(coral) == Cell(0, 1)


def test_without_rejects_an_unplaced_color() -> None:
    with pytest.raises(ValueError):
        Placement().without(coral)


def test_moving_a_color_is_without_then_with_color() -> None:
    placement = Placement({coral: Cell(0, 1)})
    moved = placement.without(coral).with_color(coral, Cell(2, 3))
    assert moved.cell_of(coral) == Cell(2, 3)


def test_unplaced_keeps_palette_order() -> None:
    placement = Placement({coral: Cell(0, 1), CLASSIC_PALETTE.by_id("black"): Cell(0, 0)})
    unplaced = placement.unplaced(CLASSIC_PALETTE)
    assert [c.id for c in unplaced[:3]] == ["brown", "cobalt", "emerald"]
    assert len(unplaced) == 10


def test_complete_when_every_palette_color_is_placed() -> None:
    placement = Placement()
    cells = [Cell(r, c) for r in range(3) for c in range(4)]
    for color, cell in zip(CLASSIC_PALETTE, cells, strict=True):
        assert not placement.is_complete(CLASSIC_PALETTE)
        placement = placement.with_color(color, cell)
    assert placement.is_complete(CLASSIC_PALETTE)
    assert placement.unplaced(CLASSIC_PALETTE) == ()


def test_assignments_are_read_only() -> None:
    placement = Placement({coral: Cell(0, 1)})
    assert dict(placement.assignments) == {coral: Cell(0, 1)}
    with pytest.raises(TypeError):
        placement.assignments[orange] = Cell(1, 1)  # type: ignore[index]


def test_givens_are_copied_not_shared() -> None:
    givens = {coral: Cell(0, 1)}
    placement = Placement(givens)
    givens[orange] = Cell(1, 1)
    assert placement.cell_of(orange) is None


def test_equal_placements_are_equal_and_hash_alike() -> None:
    a = Placement({coral: Cell(0, 1)}).with_color(orange, Cell(1, 1))
    b = Placement({orange: Cell(1, 1), coral: Cell(0, 1)})
    assert a == b
    assert hash(a) == hash(b)
    assert a != Placement({coral: Cell(0, 1)})


def test_placement_survives_pickle_and_deepcopy() -> None:
    import copy
    import pickle

    placement = Placement({coral: Cell(0, 1), orange: Cell(1, 1)})
    for clone in (pickle.loads(pickle.dumps(placement)), copy.deepcopy(placement)):
        assert clone == placement
        assert clone.color_at(Cell(1, 1)) == orange
