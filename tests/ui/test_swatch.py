from chroma_cube.core import CLASSIC_PALETTE, EXTENDED_20, Truth
from chroma_cube.ui.swatch import (
    STATUS_MARKERS,
    cube_tints,
    darken,
    is_dark,
    lighten,
    luminance,
    text_color,
)


def test_light_cubes_get_dark_text_and_dark_cubes_light_text() -> None:
    assert text_color("#f5f5f5") == "#000000"
    assert text_color("#98ffb3") == "#000000"
    assert text_color("#1c1c1c") == "#ffffff"
    assert text_color("#0047ab") == "#ffffff"


def test_black_and_other_dark_cubes_count_as_dark() -> None:
    dark = {color.id for color in CLASSIC_PALETTE if is_dark(color.hex)}
    assert {"black", "cobalt", "brown"} <= dark
    assert not {"white", "mint", "mustard", "orange"} & dark


def test_every_classic_name_keeps_a_readable_contrast() -> None:
    for color in CLASSIC_PALETTE:
        assert _contrast(color.hex, text_color(color.hex)) >= 4.5, color.name


def test_each_truth_has_its_marker() -> None:
    assert STATUS_MARKERS == {Truth.UNKNOWN: "·", Truth.SATISFIED: "✓", Truth.VIOLATED: "✗"}


def _contrast(a: str, b: str) -> float:
    high, low = sorted((luminance(a), luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def test_the_ui_dark_line_is_the_core_tone_line() -> None:
    from chroma_cube.core import EXTENDED_20, LIGHT_LUMINANCE
    from chroma_cube.core import luminance as core_luminance

    assert luminance is core_luminance
    assert is_dark("#757575") and not is_dark("#767676")
    assert core_luminance("#767676") >= LIGHT_LUMINANCE > core_luminance("#757575")
    for color in EXTENDED_20:
        assert is_dark(color.hex) == (color.tone == "dark"), color.name


def test_lighten_mixes_toward_white() -> None:
    assert lighten("#000000", 0.5) == "#808080"
    assert lighten("#ff8c00", 0.5) == "#ffc680"
    assert lighten("#0047AB", 0) == "#0047ab"
    assert lighten("#0047ab", 1) == "#ffffff"


def test_darken_mixes_toward_black() -> None:
    assert darken("#ffffff", 0.5) == "#808080"
    assert darken("#ff8c00", 0.5) == "#804600"
    assert darken("#0047ab", 0) == "#0047ab"
    assert darken("#0047ab", 1) == "#000000"


def test_a_loose_cube_is_lit_on_top_and_shaded_on_its_side_and_bottom() -> None:
    for color in (*CLASSIC_PALETTE, *EXTENDED_20):
        tints = cube_tints(color.hex)
        face = luminance(color.hex)
        assert luminance(tints.top) > face, color.name
        assert luminance(tints.side) < face, color.name
        assert luminance(tints.bottom) <= luminance(tints.side), color.name
        assert _contrast(tints.top, tints.side) >= 2.5, color.name
        strongest = max(_contrast(color.hex, tints.top), _contrast(color.hex, tints.side))
        assert strongest >= 2, color.name


def test_a_given_cube_is_pressed_in_with_a_shadowed_top_and_flat_sides() -> None:
    tints = cube_tints("#ff8c00", given=True)
    assert luminance(tints.top) < luminance("#ff8c00")
    assert tints.side == tints.bottom == "#ff8c00"
