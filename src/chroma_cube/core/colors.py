"""Cube colors and the palettes they come in."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass


@dataclass(frozen=True)
class Color:
    """One cube color.

    `id` is the stable lowercase key used in puzzle data, `name` is what players see,
    and `hex` is the `#rrggbb` value used to paint the cube.
    """

    id: str
    name: str
    hex: str

    @property
    def initial(self) -> str:
        """The capital first letter of the name, used by clues that name colors by initial."""
        return self.name[0].upper()


@dataclass(frozen=True)
class Palette:
    """An ordered set of colors with unique ids."""

    colors: tuple[Color, ...]

    def __post_init__(self) -> None:
        ids = [color.id for color in self.colors]
        if len(set(ids)) != len(ids):
            raise ValueError(f"palette has duplicate color ids: {ids}")

    def __iter__(self) -> Iterator[Color]:
        return iter(self.colors)

    def __len__(self) -> int:
        return len(self.colors)

    def __contains__(self, color: object) -> bool:
        return color in self.colors

    def by_id(self, color_id: str) -> Color:
        """The color with this id. Raises `KeyError` if there is none."""
        for color in self.colors:
            if color.id == color_id:
                return color
        raise KeyError(color_id)

    def by_initial(self, initial: str) -> tuple[Color, ...]:
        """Every color whose name starts with this letter, in palette order."""
        return tuple(color for color in self.colors if color.initial == initial.upper())


CLASSIC_PALETTE = Palette(
    (
        Color("black", "Black", "#1c1c1c"),
        Color("brown", "Brown", "#8b5a2b"),
        Color("cobalt", "Cobalt", "#0047ab"),
        Color("coral", "Coral", "#ff6f61"),
        Color("emerald", "Emerald", "#009b4d"),
        Color("magenta", "Magenta", "#e0218a"),
        Color("mint", "Mint", "#98ffb3"),
        Color("mustard", "Mustard", "#e1ad01"),
        Color("orange", "Orange", "#ff8c00"),
        Color("purple", "Purple", "#7b2fbe"),
        Color("teal", "Teal", "#008080"),
        Color("white", "White", "#f5f5f5"),
    )
)
"""The twelve colors of the physical game, in alphabetical order."""
