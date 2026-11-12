"""Read what the clue card's edges show on screen, not what their attributes hold."""

from textual.app import App

from chroma_cube.ui.card import ClueCard

_EDGE = "╭╮╰╯─ "


def card_edges(app: App[None]) -> tuple[str, str]:
    """The text drawn in the card's top and bottom edges, border characters stripped."""
    card = app.screen.query_one(ClueCard)
    lines = app.screen._compositor.render_strips()
    region = card.region
    top = lines[region.y].text[region.x : region.right]
    bottom = lines[region.bottom - 1].text[region.x : region.right]
    return top.strip(_EDGE), bottom.strip(_EDGE)
