import sys
from typing import Any

import pytest

from chroma_cube import __main__ as entry
from chroma_cube.__main__ import main


def test_help_prints_usage_without_starting_the_game(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["--help"])
    assert exit_info.value.code == 0
    out = capsys.readouterr().out
    assert "usage: chroma-cube" in out
    assert "--serve" in out


def test_a_plain_run_starts_the_terminal_app(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(entry, "run_terminal", lambda: calls.append("terminal"))
    monkeypatch.setattr(entry, "serve", lambda host, port: calls.append("serve"))
    main([])
    assert calls == ["terminal"]


def test_serve_defaults_to_localhost_port_8000(monkeypatch: pytest.MonkeyPatch) -> None:
    served: list[tuple[str, int]] = []
    monkeypatch.setattr(entry, "run_terminal", lambda: pytest.fail("terminal app started"))
    monkeypatch.setattr(entry, "serve", lambda host, port: served.append((host, port)))
    main(["--serve"])
    assert served == [("127.0.0.1", 8000)]


def test_serve_takes_host_and_port(monkeypatch: pytest.MonkeyPatch) -> None:
    served: list[tuple[str, int]] = []
    monkeypatch.setattr(entry, "serve", lambda host, port: served.append((host, port)))
    main(["--serve", "--host", "0.0.0.0", "--port", "9001"])
    assert served == [("0.0.0.0", 9001)]


def test_host_or_port_without_serve_is_an_error(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["--port", "9001"])
    assert exit_info.value.code == 2
    assert "--serve" in capsys.readouterr().err


def test_serve_starts_textual_serve_on_this_game(monkeypatch: pytest.MonkeyPatch) -> None:
    created: dict[str, Any] = {}

    class FakeServer:
        def __init__(self, command: str, host: str, port: int, **kwargs: Any) -> None:
            created.update(command=command, host=host, port=port)

        def serve(self) -> None:
            created["served"] = True

    fake_module = type(sys)("textual_serve.server")
    fake_module.Server = FakeServer  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "textual_serve.server", fake_module)
    entry.serve("127.0.0.1", 8123)
    assert created["host"] == "127.0.0.1"
    assert created["port"] == 8123
    assert created["served"] is True
    assert "-m chroma_cube" in created["command"]


def test_serve_without_textual_serve_explains_how_to_install(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setitem(sys.modules, "textual_serve.server", None)
    with pytest.raises(SystemExit) as exit_info:
        entry.serve("127.0.0.1", 8000)
    assert exit_info.value.code == 1
    err = capsys.readouterr().err
    assert "chroma-cube[web]" in err
    assert len(err.strip().splitlines()) == 1
