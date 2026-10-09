from chroma_cube.core import CLASSIC_PALETTE, Truth
from chroma_cube.ui.swatch import STATUS_MARKERS, is_dark, luminance, text_color


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
