"""The three answers a clue can give on a possibly partial placement."""

from __future__ import annotations

from enum import Enum


class Truth(Enum):
    """What a clue says about a placement: decided either way, or not yet."""

    SATISFIED = "satisfied"
    VIOLATED = "violated"
    UNKNOWN = "unknown"
