import dataclasses

import pytest

from chroma_cube.core import CLASSIC_PALETTE, Color, Palette

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
