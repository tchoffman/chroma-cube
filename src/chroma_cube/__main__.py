"""Command-line entry point."""

from chroma_cube.puzzles import classic_puzzles
from chroma_cube.ui import ChromaCubeApp


def main() -> None:
    ChromaCubeApp(classic_puzzles()).run()


if __name__ == "__main__":
    main()
