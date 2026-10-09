"""Type checks shared by the loaders of plain JSON-compatible data."""

from __future__ import annotations

from typing import Any


def as_str(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError(value)
    return value


def as_int(value: object) -> int:
    """An int, but not a bool (JSON `true` must not load as 1)."""
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(value)
    return value


def as_list(value: object) -> list[Any]:
    if not isinstance(value, list):
        raise TypeError(value)
    return value
