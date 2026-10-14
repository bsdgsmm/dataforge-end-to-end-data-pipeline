"""Every analytical and diagnostic SQL file must run against the implemented schema."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine

from dataforge.generation.synthetic import GenerationParams, generate_dataset, write_dataset
from tests.integration.support import build_models, load_source, reset_warehouse
from tests.support import PROJECT_ROOT

pytestmark = pytest.mark.integration

SQL_FILES = sorted((PROJECT_ROOT / "sql").rglob("*.sql"))


@pytest.fixture(scope="module")
def generated_warehouse(
    engine: Engine, dbt_target: Path, tmp_path_factory: pytest.TempPathFactory
) -> Engine:
    source = tmp_path_factory.mktemp("generated")
    write_dataset(generate_dataset(GenerationParams(customers=300, products=40)), source)
    reset_warehouse(engine)
    load_source(engine, source, "generated-batch", max_ratio=0.0)
    build_models()
    return engine


def test_sql_directory_is_not_empty() -> None:
    assert len(SQL_FILES) >= 10


@pytest.mark.parametrize("path", SQL_FILES, ids=lambda p: str(p.relative_to(PROJECT_ROOT)))
def test_sql_file_executes(generated_warehouse: Engine, path: Path) -> None:
    with generated_warehouse.connect() as conn:
        result = conn.execute(text(path.read_text(encoding="utf-8")))
        rows = result.all()
    if path.parent.name == "analysis":
        assert rows, f"{path.name} returned no rows on a generated dataset"
