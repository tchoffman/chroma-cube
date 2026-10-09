"""Command-line entry point."""

from __future__ import annotations

import argparse
import shlex
import subprocess
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


def game_command() -> str:
    """The shell command that starts one copy of the game, quoted for this platform's shell."""
    if sys.platform == "win32":
        return subprocess.list2cmdline([sys.executable, "-m", "chroma_cube"])
    return f"{shlex.quote(sys.executable)} -m chroma_cube"


def port_number(text: str) -> int:
    """An argparse type for a TCP port a browser can be pointed at."""
    try:
        port = int(text)
    except ValueError:
        port = 0
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError(f"must be a number from 1-65535, not {text!r}")
    return port


def serve(host: str, port: int, public_url: str | None) -> None:
    """Serve the game to a browser; each page load runs its own copy of the app."""
    try:
        from textual_serve.server import Server
    except ImportError:
        print(INSTALL_WEB, file=sys.stderr)
        raise SystemExit(1) from None
    Server(game_command(), host=host, port=port, title="Chroma Cube", public_url=public_url).serve()


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="chroma-cube",
        description="Play Chroma Cube, the color-cube logic puzzle, in the terminal or a browser.",
    )
    parser.add_argument(
        "--serve", action="store_true", help="serve the game in a web browser instead"
    )
    parser.add_argument("--host", help="address to serve on with --serve (default: 127.0.0.1)")
    parser.add_argument(
        "--port", type=port_number, help="port to serve on with --serve, 1-65535 (default: 8000)"
    )
    parser.add_argument(
        "--public-url",
        help="address browsers use to reach the server, e.g. http://192.168.1.20:8000 "
        "(default: built from --host and --port)",
    )
    args = parser.parse_args(argv)
    if not args.serve:
        if args.host is not None or args.port is not None or args.public_url is not None:
            parser.error("--host, --port and --public-url only apply with --serve")
        run_terminal()
        return
    serve(args.host or "127.0.0.1", 8000 if args.port is None else args.port, args.public_url)


if __name__ == "__main__":
    main()
