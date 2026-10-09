import dataclasses
from itertools import combinations

import pytest

from chroma_cube.core import (
    BOARD_4X4,
    BOARD_4X5,
    CLASSIC_PALETTE,
    EXTENDED_16,
    EXTENDED_20,
    FAMILIES,
    PALETTES,
    QUALITIES,
    TEMPERATURES,
    TONES,
    Color,
    Palette,
    attributes_from_hex,
)
from tests.core.ciede2000 import ciede2000

CLASSIC_IDS = [
    "black",
    "brown",
    "cobalt",
    "coral",
    "emerald",
    "magenta",
    "mint",
    "mustard",
    "orange",
    "purple",
    "teal",
    "white",
]


def test_classic_palette_has_the_twelve_colors_in_order() -> None:
    assert [color.id for color in CLASSIC_PALETTE] == CLASSIC_IDS
    assert len(CLASSIC_PALETTE) == 12


def test_classic_colors_have_display_name_initial_and_hex() -> None:
    for color in CLASSIC_PALETTE:
        assert color.name == color.id.capitalize()
        assert color.initial == color.name[0]
        assert len(color.hex) == 7 and color.hex.startswith("#")
        int(color.hex[1:], 16)


def test_classic_hex_values_are_all_different() -> None:
    assert len({color.hex for color in CLASSIC_PALETTE}) == 12


def test_by_id_returns_the_color() -> None:
    coral = CLASSIC_PALETTE.by_id("coral")
    assert coral.name == "Coral"
    assert coral in CLASSIC_PALETTE


def test_by_id_rejects_an_unknown_id() -> None:
    with pytest.raises(KeyError):
        CLASSIC_PALETTE.by_id("chartreuse")


def test_by_initial_returns_every_matching_color() -> None:
    assert [c.id for c in CLASSIC_PALETTE.by_initial("B")] == ["black", "brown"]
    assert [c.id for c in CLASSIC_PALETTE.by_initial("M")] == ["magenta", "mint", "mustard"]
    assert [c.id for c in CLASSIC_PALETTE.by_initial("w")] == ["white"]


def test_by_initial_with_no_match_is_empty() -> None:
    assert CLASSIC_PALETTE.by_initial("Z") == ()


def test_colors_are_immutable() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        CLASSIC_PALETTE.by_id("black").hex = "#000000"  # type: ignore[misc]


def test_initial_is_the_first_letter_of_the_name() -> None:
    assert Color(id="red", name="Red", hex="#ff0000").initial == "R"


def test_palette_rejects_duplicate_ids() -> None:
    red = Color(id="red", name="Red", hex="#ff0000")
    with pytest.raises(ValueError):
        Palette((red, red))


@pytest.mark.parametrize("bad", ["", "Bl", " b", "1"])
def test_by_initial_needs_exactly_one_letter(bad: str) -> None:
    with pytest.raises(ValueError):
        CLASSIC_PALETTE.by_initial(bad)


@pytest.mark.parametrize(
    ("color_id", "name", "hex_value"),
    [
        ("", "Red", "#ff0000"),
        ("red", "", "#ff0000"),
        ("red", "Red", "red"),
        ("red", "Red", "#ff000"),
        ("red", "Red", "#gg0000"),
        ("red", "Red", "ff0000"),
    ],
)
def test_color_rejects_bad_fields(color_id: str, name: str, hex_value: str) -> None:
    with pytest.raises(ValueError):
        Color(id=color_id, name=name, hex=hex_value)


def test_adjusted_classic_hex_values() -> None:
    assert CLASSIC_PALETTE.by_id("mustard").hex == "#ccb800"
    assert CLASSIC_PALETTE.by_id("purple").hex == "#9440d8"


# --------------------------------------------------------------------------- attributes

CLASSIC_ATTRIBUTES = {
    "black": ("neutral", "dark", "grey"),
    "brown": ("warm", "dark", "brown"),
    "cobalt": ("cool", "dark", "blue"),
    "coral": ("warm", "light", "red"),
    "emerald": ("cool", "light", "green"),
    "magenta": ("warm", "light", "pink"),
    "mint": ("cool", "light", "green"),
    "mustard": ("warm", "light", "yellow"),
    "orange": ("warm", "light", "orange"),
    "purple": ("cool", "dark", "purple"),
    "teal": ("cool", "dark", "blue"),
    "white": ("neutral", "light", "grey"),
}


def test_classic_attributes_are_assigned() -> None:
    for color in CLASSIC_PALETTE:
        assert (color.temperature, color.tone, color.family) == CLASSIC_ATTRIBUTES[color.id]


def test_classic_attributes_agree_with_the_hex() -> None:
    for color in CLASSIC_PALETTE:
        assert attributes_from_hex(color.hex) == CLASSIC_ATTRIBUTES[color.id]
        assert Color(color.id, color.name, color.hex) == color


@pytest.mark.parametrize(
    ("hex_value", "expected"),
    [
        ("#ff0000", ("warm", "light", "red")),
        ("#ffc0cb", ("warm", "light", "pink")),
        ("#ffd700", ("warm", "light", "yellow")),
        ("#0000ff", ("cool", "dark", "blue")),
        ("#00ff00", ("cool", "light", "green")),
        ("#808080", ("neutral", "light", "grey")),
        ("#202020", ("neutral", "dark", "grey")),
        ("#7b3f00", ("warm", "dark", "brown")),
        ("#8000ff", ("cool", "dark", "purple")),
        ("#ff00ff", ("warm", "light", "pink")),
    ],
)
def test_attributes_are_derived_from_the_hex(
    hex_value: str, expected: tuple[str, str, str]
) -> None:
    color = Color("x", "X", hex_value)
    assert (color.temperature, color.tone, color.family) == expected


def test_attributes_can_be_overridden() -> None:
    color = Color("teal", "Teal", "#008080", temperature="neutral", tone="light", family="green")
    assert (color.temperature, color.tone, color.family) == ("neutral", "light", "green")


def test_one_attribute_can_be_overridden_alone() -> None:
    color = Color("teal", "Teal", "#008080", family="green")
    assert (color.temperature, color.tone, color.family) == ("cool", "dark", "green")


@pytest.mark.parametrize(
    "fields",
    [{"temperature": "hot"}, {"tone": "medium"}, {"family": "teal"}, {"family": "warm"}],
)
def test_unknown_attribute_values_are_rejected(fields: dict[str, str]) -> None:
    with pytest.raises(ValueError):
        Color("x", "X", "#123456", **fields)


def test_has_checks_every_attribute() -> None:
    mint = CLASSIC_PALETTE.by_id("mint")
    assert mint.has("cool") and mint.has("light") and mint.has("green")
    assert not mint.has("warm") and not mint.has("dark") and not mint.has("blue")


def test_attribute_vocabularies_do_not_overlap() -> None:
    assert not set(TEMPERATURES) & set(TONES)
    assert not (set(TEMPERATURES) | set(TONES)) & set(FAMILIES)
    assert set(QUALITIES) == set(TEMPERATURES) | set(TONES)


# --------------------------------------------------------------------------- palettes


def test_extended_palettes_extend_the_classic_one() -> None:
    assert EXTENDED_16.colors[:12] == CLASSIC_PALETTE.colors
    assert EXTENDED_20.colors[:16] == EXTENDED_16.colors
    assert len(EXTENDED_16) == 16 == len(BOARD_4X4)
    assert len(EXTENDED_20) == 20 == len(BOARD_4X5)


def test_new_colors_have_their_own_initials() -> None:
    classic = {color.initial for color in CLASSIC_PALETTE}
    new = [color.initial for color in EXTENDED_20.colors[12:]]
    distinct = [letter for letter in new if letter not in classic]
    assert len(set(distinct)) == len(distinct)
    assert new.count("C") <= 1
    assert len(distinct) >= 7
    assert not {"Q", "R", "X"} & set(new)


@pytest.mark.parametrize("palette", [EXTENDED_16, EXTENDED_20])
def test_palette_colors_are_easy_to_tell_apart(palette: Palette) -> None:
    closest = min(ciede2000(a.hex, b.hex) for a, b in combinations(palette, 2))
    assert closest >= 20


def test_extended_attributes_agree_with_the_hex() -> None:
    for color in EXTENDED_20:
        assert attributes_from_hex(color.hex) == (color.temperature, color.tone, color.family)


def test_palette_registry() -> None:
    assert PALETTES["classic"] is CLASSIC_PALETTE
    assert PALETTES["extended-16"] is EXTENDED_16
    assert PALETTES["extended-20"] is EXTENDED_20


def test_ciede2000_matches_reference_pairs() -> None:
    assert ciede2000("#ffffff", "#ffffff") == 0
    assert 20 < ciede2000("#0047ab", "#9440d8") < 22
