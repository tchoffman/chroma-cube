import pytest

from chroma_cube.core import CLASSIC_BOARD, Board, Cell

B = CLASSIC_BOARD


def test_classic_board_is_three_rows_by_four_columns() -> None:
    assert (B.rows, B.cols) == (3, 4)
    assert len(B) == 12


def test_cells_iterate_row_by_row_from_the_top_left() -> None:
    cells = list(B)
    assert cells[0] == Cell(0, 0)
    assert cells[1] == Cell(0, 1)
    assert cells[4] == Cell(1, 0)
    assert cells[-1] == Cell(2, 3)
    assert cells == sorted(cells)


def test_contains_only_cells_inside_the_board() -> None:
    assert Cell(2, 3) in B
    assert Cell(3, 0) not in B
    assert Cell(0, 4) not in B
    assert Cell(-1, 0) not in B


def test_board_size_is_a_parameter() -> None:
    board = Board(5, 5)
    assert len(board) == 25
    assert board.is_center(Cell(2, 2))


@pytest.mark.parametrize(("rows", "cols"), [(0, 4), (3, 0), (-1, 2)])
def test_board_needs_at_least_one_row_and_column(rows: int, cols: int) -> None:
    with pytest.raises(ValueError):
        Board(rows, cols)


def test_corners() -> None:
    corners = {cell for cell in B if B.is_corner(cell)}
    assert corners == {Cell(0, 0), Cell(0, 3), Cell(2, 0), Cell(2, 3)}


def test_edge_is_every_border_cell() -> None:
    edge = {cell for cell in B if B.is_edge(cell)}
    assert len(edge) == 10
    assert Cell(0, 1) in edge
    assert Cell(1, 0) in edge
    assert Cell(1, 3) in edge


def test_center_is_every_cell_off_the_border() -> None:
    center = {cell for cell in B if B.is_center(cell)}
    assert center == {Cell(1, 1), Cell(1, 2)}


def test_row_and_column_cells() -> None:
    assert B.row(1) == (Cell(1, 0), Cell(1, 1), Cell(1, 2), Cell(1, 3))
    assert B.column(2) == (Cell(0, 2), Cell(1, 2), Cell(2, 2))


@pytest.mark.parametrize("index", [-1, 3])
def test_row_outside_the_board_is_rejected(index: int) -> None:
    with pytest.raises(ValueError):
        B.row(index)


@pytest.mark.parametrize("index", [-1, 4])
def test_column_outside_the_board_is_rejected(index: int) -> None:
    with pytest.raises(ValueError):
        B.column(index)


def test_orthogonal_neighbours_of_a_corner_and_the_center() -> None:
    assert B.orthogonal_neighbours(Cell(0, 0)) == (Cell(0, 1), Cell(1, 0))
    assert B.orthogonal_neighbours(Cell(1, 1)) == (Cell(0, 1), Cell(1, 0), Cell(1, 2), Cell(2, 1))


def test_diagonal_neighbours_of_a_corner_and_the_center() -> None:
    assert B.diagonal_neighbours(Cell(0, 0)) == (Cell(1, 1),)
    assert B.diagonal_neighbours(Cell(1, 1)) == (Cell(0, 0), Cell(0, 2), Cell(2, 0), Cell(2, 2))


def test_neighbours_are_orthogonal_and_diagonal_together() -> None:
    for cell in B:
        expected = sorted(B.orthogonal_neighbours(cell) + B.diagonal_neighbours(cell))
        assert B.neighbours(cell) == tuple(expected)
    assert len(B.neighbours(Cell(1, 1))) == 8
    assert len(B.neighbours(Cell(0, 1))) == 5


def test_neighbour_relation_is_symmetric() -> None:
    for cell in B:
        for other in B.neighbours(cell):
            assert cell in B.neighbours(other)


def test_single_cell_board_has_no_neighbours() -> None:
    board = Board(1, 1)
    only = Cell(0, 0)
    assert board.is_corner(only) and board.is_edge(only)
    assert board.neighbours(only) == ()


def test_queries_reject_cells_off_the_board() -> None:
    off = Cell(5, 5)
    for query in (B.is_corner, B.is_edge, B.is_center, B.neighbours):
        with pytest.raises(ValueError):
            query(off)
