"""How cube colors and clue states are drawn: text contrast and status markers."""

from __future__ import annotations

from chroma_cube.core import Truth

STATUS_MARKERS = {Truth.UNKNOWN: "·", Truth.SATISFIED: "✓", Truth.VIOLATED: "✗"}

_DARK_BELOW = 0.18
"""Relative luminance under which white text reads better than black (the crossover)."""


def luminance(hex_color: str) -> float:
    """WCAG relative luminance of a `#rrggbb` color, from 0 (black) to 1 (white)."""

    def channel(offset: int) -> float:
        value = int(hex_color[offset : offset + 2], 16) / 255
        return value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4

    return 0.2126 * channel(1) + 0.7152 * channel(3) + 0.0722 * channel(5)


def is_dark(hex_color: str) -> bool:
    """Dark enough that light text, and a light outline on a dark screen, are needed."""
    return luminance(hex_color) < _DARK_BELOW


def text_color(hex_color: str) -> str:
    """Black or white, whichever contrasts more with `hex_color`."""
    return "#ffffff" if is_dark(hex_color) else "#000000"
