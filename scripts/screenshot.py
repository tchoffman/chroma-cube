"""Retake the README screenshot: a game in progress on the demo card, at 100x32.

uv run python scripts/screenshot.py docs/screenshot.svg
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from chroma_cube.puzzles import classic_puzzles
from chroma_cube.ui import ChromaCubeApp
from chroma_cube.ui.screens import PlayScreen

SIZE = (100, 32)


async def take(out: Path) -> None:
    app = ChromaCubeApp(classic_puzzles()[:1])
    async with app.run_test(size=SIZE) as pilot:
        await pilot.press("enter")
        await pilot.press("w", "enter")
        await pilot.press("c", "right", "enter")
        await pilot.press("m", "down", "down", "enter")
        await pilot.press("t", "up", "right")
        await pilot.pause()
        assert isinstance(app.screen, PlayScreen)
        assert app.screen.state.held is not None, "the screenshot should show a held cube"
        svg = app.export_screenshot(title="Chroma Cube")
    out.write_text(svg, encoding="utf-8")


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("docs/screenshot.svg")
    asyncio.run(take(out))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
