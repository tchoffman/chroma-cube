"""Solution search: find a puzzle's solutions, count them and report uniqueness."""

from chroma_cube.solver.search import (
    DEFAULT_MAX_NODES,
    SearchBudgetExceeded,
    SolveResult,
    count_solutions,
    first_solution,
    is_solvable,
    is_unique,
    solve,
    solve_clues,
)

__all__ = [
    "DEFAULT_MAX_NODES",
    "SearchBudgetExceeded",
    "SolveResult",
    "count_solutions",
    "first_solution",
    "is_solvable",
    "is_unique",
    "solve",
    "solve_clues",
]
