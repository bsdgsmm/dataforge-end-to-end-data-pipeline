"""Database helpers shared by integration tests."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import Engine

from dataforge.database.schema import ensure_schema
from dataforge.ingestion.loader import load_batch
from dataforge.runs import ensure_run
from dataforge.transform import run_dbt
from dataforge.validation.validator import validate_source_dir
from tests.support import DBT_PROJECT_DIR

MANAGED_SCHEMAS = ("raw", "audit", "staging", "intermediate", "marts", "reference")


def reset_warehouse(engine: Engine) -> None:
    with engine.begin() as conn:
        for schema in MANAGED_SCHEMAS:
            conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
    ensure_schema(engine)


def load_source(engine: Engine, source_dir: Path, run_id: str, max_ratio: float = 1.0):
    ensure_run(engine, run_id)
    result = validate_source_dir(source_dir, max_rejected_ratio=max_ratio)
    return result, load_batch(engine, run_id, result, source_dir)


def build_models() -> None:
    run_dbt(DBT_PROJECT_DIR, ["seed"])
    run_dbt(DBT_PROJECT_DIR, ["run"])
