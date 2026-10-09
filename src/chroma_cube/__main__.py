"""Command-line entry point."""

from __future__ import annotations

import argparse
import shlex
import sys
from collections.abc import Sequence

INSTALL_WEB = (
    "Browser play needs textual-serve: "
    "uv tool install 'chroma-cube[web] @ git+https://github.com/tchoffman/chroma-cube' "
    "(or `uv sync --extra web` in a checkout)"
)


def run_terminal() -> None:
    """Play in this terminal."""
    from chroma_cube.puzzles import classic_puzzles
    from chroma_cube.ui import ChromaCubeApp

    ChromaCubeApp(classic_puzzles()).run()


def serve(host: str, port: int) -> None:
    """Serve the game to a browser; each page load runs its own copy of the app."""
    try:
        from textual_serve.server import Server
    except ImportError:
        print(INSTALL_WEB, file=sys.stderr)
        raise SystemExit(1) from None
    command = f"{shlex.quote(sys.executable)} -m chroma_cube"
    Server(command, host=host, port=port, title="Chroma Cube").serve()


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="chroma-cube",
        description="Play Chroma Cube, the color-cube logic puzzle, in the terminal or a browser.",
    )
    parser.add_argument(
        "--serve", action="store_true", help="serve the game in a web browser instead"
    )
    parser.add_argument("--host", help="address to serve on with --serve (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, help="port to serve on with --serve (default: 8000)")
    args = parser.parse_args(argv)
    if not args.serve:
        if args.host is not None or args.port is not None:
            parser.error("--host and --port only apply with --serve")
        run_terminal()
        return
    serve(args.host or "127.0.0.1", 8000 if args.port is None else args.port)


if __name__ == "__main__":
    main()
