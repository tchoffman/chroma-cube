import pytest

from chroma_cube.__main__ import main


def test_help_prints_usage_without_starting_the_game(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["--help"])
    assert exit_info.value.code == 0
    assert "usage: chroma-cube" in capsys.readouterr().out
