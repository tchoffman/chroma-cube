"""Cube colors and the palettes they come in."""

from __future__ import annotations

import colorsys
import re
from collections.abc import Iterator
from dataclasses import dataclass

_HEX = re.compile(r"#[0-9a-fA-F]{6}")

TEMPERATURES = ("warm", "cool", "neutral")
"""How warm a color feels. Grey-ish colors are neutral."""
TONES = ("light", "dark")
"""Whether a color is light or dark."""
QUALITIES = TEMPERATURES + TONES
"""Every temperature and tone: the values attribute clues like "a cool color" use."""
FAMILIES = ("red", "orange", "yellow", "green", "blue", "purple", "pink", "brown", "grey")
"""Hue families: "a shade of green". Black, white and greys are the grey family."""

_GREY_CHROMA = 0.12
"""Below this spread between the strongest and weakest channel a color reads as grey."""
_LIGHT_LUMINANCE = 0.18
"""Relative luminance from which a color is light; black text reads better on it (see D19)."""


def attributes_from_hex(hex_value: str) -> tuple[str, str, str]:
    """The temperature, tone and family a `#rrggbb` color gets when none are given.

    Grey-ish colors are neutral and in the grey family. Otherwise the hue picks the family
    (dark oranges are brown, pale reds pink) and the family the temperature: reds, oranges,
    yellows, pinks and browns are warm, greens, blues and purples cool. Tone is light from
    a relative luminance of 0.18 up.
    """
    if not _HEX.fullmatch(hex_value):
        raise ValueError(f"color hex must look like #rrggbb, got {hex_value!r}")
    red, green, blue = (int(hex_value[i : i + 2], 16) / 255 for i in (1, 3, 5))
    tone = "light" if _luminance(red, green, blue) >= _LIGHT_LUMINANCE else "dark"
    if max(red, green, blue) - min(red, green, blue) < _GREY_CHROMA:
        return "neutral", tone, "grey"
    hue, _, value = colorsys.rgb_to_hsv(red, green, blue)
    family = _family(hue * 360, value, (max(red, green, blue) + min(red, green, blue)) / 2)
    temperature = "cool" if family in ("green", "blue", "purple") else "warm"
    return temperature, tone, family


def _family(hue: float, value: float, lightness: float) -> str:
    if hue < 15 or hue >= 345:
        return "pink" if lightness >= 0.75 else "red"
    if hue < 50 and value < 0.6:
        return "brown"
    for limit, family in ((45, "orange"), (70, "yellow"), (170, "green"), (260, "blue")):
        if hue < limit:
            return family
    return "purple" if hue < 290 else "pink"


def _luminance(red: float, green: float, blue: float) -> float:
    def linear(channel: float) -> float:
        return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4

    return 0.2126 * linear(red) + 0.7152 * linear(green) + 0.0722 * linear(blue)


@dataclass(frozen=True)
class Color:
    """One cube color.

    `id` is the stable lowercase key used in puzzle data, `name` is what players see,
    and `hex` is the `#rrggbb` value used to paint the cube.

    `temperature` (one of `TEMPERATURES`), `tone` (`TONES`) and `family` (`FAMILIES`) are
    what attribute clues talk about. Any left empty is derived from the hex with
    `attributes_from_hex`, so `Color(id, name, hex)` still works.
    """

    id: str
    name: str
    hex: str
    temperature: str = ""
    tone: str = ""
    family: str = ""

    def __post_init__(self) -> None:
        if not self.id or not self.name:
            raise ValueError(f"a color needs a non-empty id and name, got {self!r}")
        derived = attributes_from_hex(self.hex)
        for field, allowed, default in zip(
            ("temperature", "tone", "family"), (TEMPERATURES, TONES, FAMILIES), derived, strict=True
        ):
            value = getattr(self, field) or default
            if value not in allowed:
                raise ValueError(f"{field} must be one of {allowed}, got {value!r}")
            object.__setattr__(self, field, value)

    def has(self, value: str) -> bool:
        """Whether this color is `value`: a temperature, a tone or a family."""
        return value in (self.temperature, self.tone, self.family)

    @property
    def derived(self) -> bool:
        """Whether every attribute is the one its hex implies, so data may leave them out."""
        return attributes_from_hex(self.hex) == (self.temperature, self.tone, self.family)

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
        """Every color whose name starts with this letter, in palette order.

        Raises `ValueError` unless `initial` is a single letter.
        """
        if len(initial) != 1 or not initial.isalpha():
            raise ValueError(f"an initial is a single letter, got {initial!r}")
        return tuple(color for color in self.colors if color.initial == initial.upper())


CLASSIC_PALETTE = Palette(
    (
        Color("black", "Black", "#1c1c1c", "neutral", "dark", "grey"),
        Color("brown", "Brown", "#8b5a2b", "warm", "dark", "brown"),
        Color("cobalt", "Cobalt", "#0047ab", "cool", "dark", "blue"),
        Color("coral", "Coral", "#ff6f61", "warm", "light", "red"),
        Color("emerald", "Emerald", "#009b4d", "cool", "light", "green"),
        Color("magenta", "Magenta", "#e0218a", "warm", "light", "pink"),
        Color("mint", "Mint", "#98ffb3", "cool", "light", "green"),
        Color("mustard", "Mustard", "#ccb800", "warm", "light", "yellow"),
        Color("orange", "Orange", "#ff8c00", "warm", "light", "orange"),
        Color("purple", "Purple", "#9440d8", "cool", "dark", "purple"),
        Color("teal", "Teal", "#008080", "cool", "dark", "blue"),
        Color("white", "White", "#f5f5f5", "neutral", "light", "grey"),
    )
)
"""The twelve colors of the physical game, in alphabetical order.

Attributes are assigned by hand (see D24 in docs/DECISIONS.md); they agree with the hex."""

EXTENDED_16 = Palette(
    (
        *CLASSIC_PALETTE.colors,
        Color("azure", "Azure", "#5ec8ff", "cool", "light", "blue"),
        Color("garnet", "Garnet", "#b3121f", "warm", "dark", "red"),
        Color("lavender", "Lavender", "#d4a8ff", "cool", "light", "purple"),
        Color("silver", "Silver", "#999999", "neutral", "light", "grey"),
    )
)
"""The classic twelve plus four, for a 4x4 board (see D25 in docs/DECISIONS.md)."""

EXTENDED_20 = Palette(
    (
        *EXTENDED_16.colors,
        Color("cyan", "Cyan", "#00ffff", "cool", "light", "blue"),
        Color("denim", "Denim", "#5580ff", "cool", "light", "blue"),
        Color("forest", "Forest", "#335500", "cool", "dark", "green"),
        Color("indigo", "Indigo", "#330055", "cool", "dark", "purple"),
    )
)
"""The sixteen plus four more, for a 4x5 board."""

PALETTES: dict[str, Palette] = {
    "classic": CLASSIC_PALETTE,
    "extended-16": EXTENDED_16,
    "extended-20": EXTENDED_20,
}
"""Every built-in palette, by name."""
