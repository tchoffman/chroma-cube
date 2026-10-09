"""Command-line entry point."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from chroma_cube.puzzles import classic_puzzles
from chroma_cube.ui import ChromaCubeApp


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="chroma-cube",
        description="Play Chroma Cube, the color-cube logic puzzle, in the terminal.",
    )
    parser.parse_args(argv)
    ChromaCubeApp(classic_puzzles()).run()


if __name__ == "__main__":
    main()
