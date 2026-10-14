from __future__ import annotations

import shutil
from collections.abc import Callable
from pathlib import Path

import pandas as pd
import pytest

from tests.support import SMALL_SOURCE_DIR


@pytest.fixture
def source_dir(tmp_path: Path) -> Path:
    """A writable copy of the hand-built fixture dataset."""
    target = tmp_path / "source"
    shutil.copytree(SMALL_SOURCE_DIR, target)
    return target


@pytest.fixture
def edit_source(source_dir: Path) -> Callable[[str, Callable[[pd.DataFrame], pd.DataFrame]], None]:
    """Apply a DataFrame transformation to one fixture CSV in place."""

    def _edit(file_name: str, change: Callable[[pd.DataFrame], pd.DataFrame]) -> None:
        path = source_dir / file_name
        frame = pd.read_csv(path, dtype=str, keep_default_na=False)
        change(frame).to_csv(path, index=False)

    return _edit
