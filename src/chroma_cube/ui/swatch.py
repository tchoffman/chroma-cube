"""How cube colors and clue states are drawn: text contrast, cube tints and status markers."""

from __future__ import annotations

from dataclasses import dataclass

from chroma_cube.core import LIGHT_LUMINANCE, Truth, luminance

__all__ = [
    "STATUS_MARKERS",
    "CubeTints",
    "cube_tints",
    "darken",
    "is_dark",
    "lighten",
    "luminance",
    "text_color",
]

STATUS_MARKERS = {Truth.UNKNOWN: "·", Truth.SATISFIED: "✓", Truth.VIOLATED: "✗"}

TOP_LIGHT = 0.45
"""How far a loose cube's top is mixed toward white."""
SIDE_SHADE = 0.4
"""How far its right side is mixed toward black."""
BOTTOM_SHADE = 0.55
"""How far its bottom edge, the face furthest from the light, is mixed toward black."""
PRESSED_SHADE = 0.3
"""How far a given cube's top edge is shadowed by the rim of the well it sits down in."""


def is_dark(hex_color: str) -> bool:
    """Dark enough that light text, and a light outline on a dark screen, are needed."""
    return luminance(hex_color) < LIGHT_LUMINANCE


def text_color(hex_color: str) -> str:
    """Black or white, whichever contrasts more with `hex_color`."""
    return "#ffffff" if is_dark(hex_color) else "#000000"


def _mix(hex_color: str, target: int, amount: float) -> str:
    channels = (int(hex_color[offset : offset + 2], 16) for offset in (1, 3, 5))
    mixed = (int(value + (target - value) * amount + 0.5) for value in channels)
    return "#" + "".join(f"{value:02x}" for value in mixed)


def lighten(hex_color: str, amount: float) -> str:
    """`hex_color` mixed toward white: 0 leaves it, 1 is white."""
    return _mix(hex_color, 255, amount)


def darken(hex_color: str, amount: float) -> str:
    """`hex_color` mixed toward black: 0 leaves it, 1 is black."""
    return _mix(hex_color, 0, amount)


@dataclass(frozen=True)
class CubeTints:
    """The colors of a cube's edges around its front face, which is the cube's own color."""

    top: str
    side: str
    bottom: str


def cube_tints(hex_color: str, *, given: bool = False) -> CubeTints:
    """A loose cube is lit from above; a given one sits pressed into its well, flat."""
    if given:
        return CubeTints(darken(hex_color, PRESSED_SHADE), hex_color, hex_color)
    return CubeTints(
        lighten(hex_color, TOP_LIGHT),
        darken(hex_color, SIDE_SHADE),
        darken(hex_color, BOTTOM_SHADE),
    )
