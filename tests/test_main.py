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
    monkeypatch.setattr(entry, "serve", lambda host, port, public_url: calls.append("serve"))
    main([])
    assert calls == ["terminal"]


def test_serve_defaults_to_localhost_port_8000(monkeypatch: pytest.MonkeyPatch) -> None:
    served: list[tuple[str, int, str | None]] = []
    monkeypatch.setattr(entry, "run_terminal", lambda: pytest.fail("terminal app started"))
    monkeypatch.setattr(
        entry, "serve", lambda host, port, public_url: served.append((host, port, public_url))
    )
    main(["--serve"])
    assert served == [("127.0.0.1", 8000, None)]


def test_serve_takes_host_and_port(monkeypatch: pytest.MonkeyPatch) -> None:
    served: list[tuple[str, int, str | None]] = []
    monkeypatch.setattr(
        entry, "serve", lambda host, port, public_url: served.append((host, port, public_url))
    )
    main(
        [
            "--serve",
            "--host",
            "0.0.0.0",
            "--port",
            "9001",
            "--public-url",
            "http://192.168.1.20:9001",
        ]
    )
    assert served == [("0.0.0.0", 9001, "http://192.168.1.20:9001")]


@pytest.mark.parametrize("port", ["0", "70000", "-1", "abc"])
def test_serve_rejects_a_port_outside_1_to_65535(
    port: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(entry, "serve", lambda host, port, public_url: pytest.fail("served"))
    with pytest.raises(SystemExit) as exit_info:
        main(["--serve", "--port", port])
    assert exit_info.value.code == 2
    assert "1-65535" in capsys.readouterr().err


@pytest.mark.parametrize("port", ["1", "65535"])
def test_serve_accepts_the_ends_of_the_port_range(
    port: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    served: list[int] = []
    monkeypatch.setattr(entry, "serve", lambda host, port, public_url: served.append(port))
    main(["--serve", "--port", port])
    assert served == [int(port)]


def test_public_url_without_serve_is_an_error(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["--public-url", "http://192.168.1.20:8000"])
    assert exit_info.value.code == 2
    assert "--serve" in capsys.readouterr().err


def test_host_or_port_without_serve_is_an_error(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["--port", "9001"])
    assert exit_info.value.code == 2
    assert "--serve" in capsys.readouterr().err


def test_serve_starts_textual_serve_on_this_game(monkeypatch: pytest.MonkeyPatch) -> None:
    created: dict[str, Any] = {}

    class FakeServer:
        def __init__(
            self, command: str, host: str, port: int, public_url: str | None, **kwargs: Any
        ) -> None:
            created.update(command=command, host=host, port=port, public_url=public_url)

        def serve(self) -> None:
            created["served"] = True

    fake_module = type(sys)("textual_serve.server")
    fake_module.Server = FakeServer  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "textual_serve.server", fake_module)
    entry.serve("127.0.0.1", 8123, "http://example.test:8123")
    assert created["host"] == "127.0.0.1"
    assert created["port"] == 8123
    assert created["public_url"] == "http://example.test:8123"
    assert created["served"] is True
    assert "-m chroma_cube" in created["command"]


def test_serve_without_textual_serve_explains_how_to_install(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setitem(sys.modules, "textual_serve.server", None)
    with pytest.raises(SystemExit) as exit_info:
        entry.serve("127.0.0.1", 8000, None)
    assert exit_info.value.code == 1
    err = capsys.readouterr().err
    assert "chroma-cube[web]" in err
    assert len(err.strip().splitlines()) == 1


def test_the_served_command_is_quoted_for_a_posix_shell(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(entry.sys, "platform", "darwin")
    monkeypatch.setattr(entry.sys, "executable", "/Users/a b/python")
    assert entry.game_command() == "'/Users/a b/python' -m chroma_cube"


def test_the_served_command_is_quoted_for_cmd_on_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(entry.sys, "platform", "win32")
    monkeypatch.setattr(entry.sys, "executable", r"C:\Program Files\Python\python.exe")
    assert entry.game_command() == r'"C:\Program Files\Python\python.exe" -m chroma_cube'
