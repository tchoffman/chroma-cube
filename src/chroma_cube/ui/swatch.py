"""How cube colors and clue states are drawn: text contrast and status markers."""

from __future__ import annotations

from chroma_cube.core import LIGHT_LUMINANCE, Truth, luminance

__all__ = ["STATUS_MARKERS", "is_dark", "luminance", "text_color"]

STATUS_MARKERS = {Truth.UNKNOWN: "·", Truth.SATISFIED: "✓", Truth.VIOLATED: "✗"}


def is_dark(hex_color: str) -> bool:
    """Dark enough that light text, and a light outline on a dark screen, are needed."""
    return luminance(hex_color) < LIGHT_LUMINANCE


def text_color(hex_color: str) -> str:
    """Black or white, whichever contrasts more with `hex_color`."""
    return "#ffffff" if is_dark(hex_color) else "#000000"
