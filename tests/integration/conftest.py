"""Integration fixtures. Requires a reachable PostgreSQL and DATAFORGE_DB_* variables.

Tests run against a separate database (DATAFORGE_TEST_DB_NAME, default `dataforge_test`)
that is dropped and recreated per session, so development data is never touched.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError

from dataforge.config import ConfigurationError, load_database_settings
from dataforge.database.engine import build_engine
from tests.integration.support import reset_warehouse


@pytest.fixture(scope="session")
def test_database() -> Iterator[str]:
    try:
        settings = load_database_settings()
    except ConfigurationError as exc:
        pytest.skip(f"Integration tests need database settings: {exc}")

    test_name = os.environ.get("DATAFORGE_TEST_DB_NAME", "dataforge_test")
    admin = create_engine(settings.url(), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{test_name}" WITH (FORCE)'))
            conn.execute(text(f'CREATE DATABASE "{test_name}"'))
    except OperationalError as exc:
        pytest.skip(f"PostgreSQL is not reachable: {exc.orig}")

    original = os.environ.get("DATAFORGE_DB_NAME")
    os.environ["DATAFORGE_DB_NAME"] = test_name
    yield test_name
    if original is None:
        os.environ.pop("DATAFORGE_DB_NAME", None)
    else:
        os.environ["DATAFORGE_DB_NAME"] = original
    admin.dispose()


@pytest.fixture(scope="session")
def engine(test_database: str) -> Iterator[Engine]:
    engine = build_engine()
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def dbt_target(tmp_path_factory: pytest.TempPathFactory) -> Path:
    target = tmp_path_factory.mktemp("dbt_target")
    os.environ["DBT_TARGET_PATH"] = str(target)
    os.environ["DBT_LOG_PATH"] = str(tmp_path_factory.mktemp("dbt_logs"))
    return target


@pytest.fixture
def fresh_warehouse(engine: Engine) -> Engine:
    reset_warehouse(engine)
    return engine
