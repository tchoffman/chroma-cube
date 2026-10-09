"""Fixtures shared by every test."""

from collections.abc import Iterator
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    """Point the progress store at a throwaway directory so no test touches real saves."""
    data_dir = tmp_path_factory.mktemp("data")
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("CHROMA_CUBE_DATA_DIR", str(data_dir))
        yield data_dir
