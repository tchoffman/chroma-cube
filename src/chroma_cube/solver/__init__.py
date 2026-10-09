"""Solution search: find a puzzle's solutions, count them and report uniqueness; hints."""

from chroma_cube.solver.hints import Hint, HintReason, explain, next_hint
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
    "Hint",
    "HintReason",
    "SearchBudgetExceeded",
    "SolveResult",
    "count_solutions",
    "explain",
    "first_solution",
    "is_solvable",
    "is_unique",
    "next_hint",
    "solve",
    "solve_clues",
]
