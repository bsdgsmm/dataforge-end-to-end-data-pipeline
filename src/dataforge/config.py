"""Runtime configuration loaded from environment variables."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.engine import URL


class ConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True)
class DatabaseSettings:
    host: str
    port: int
    name: str
    user: str
    password: str

    def url(self, database: str | None = None) -> URL:
        return URL.create(
            drivername="postgresql+psycopg2",
            username=self.user,
            password=self.password,
            host=self.host,
            port=self.port,
            database=database or self.name,
        )

    def __repr__(self) -> str:
        return (
            f"DatabaseSettings(host={self.host!r}, port={self.port}, "
            f"name={self.name!r}, user={self.user!r}, password='***')"
        )


@dataclass(frozen=True)
class PathSettings:
    source_dir: Path
    report_dir: Path
    dbt_project_dir: Path


@dataclass(frozen=True)
class QualitySettings:
    max_rejected_ratio: float


def _get(env: Mapping[str, str], name: str, default: str | None = None) -> str | None:
    value = env.get(name, default)
    if value is None:
        return None
    value = value.strip()
    return value or default


def load_database_settings(env: Mapping[str, str] | None = None) -> DatabaseSettings:
    env = os.environ if env is None else env
    required = ("DATAFORGE_DB_USER", "DATAFORGE_DB_PASSWORD")
    missing = [name for name in required if not _get(env, name)]
    if missing:
        raise ConfigurationError(
            "Missing required database settings: "
            + ", ".join(missing)
            + ". Copy .env.example to .env and export it, or set the variables directly."
        )

    port_value = _get(env, "DATAFORGE_DB_PORT", "5432")
    try:
        port = int(port_value)
    except ValueError as exc:
        raise ConfigurationError(
            f"DATAFORGE_DB_PORT must be an integer, got {port_value!r}"
        ) from exc

    return DatabaseSettings(
        host=_get(env, "DATAFORGE_DB_HOST", "localhost"),
        port=port,
        name=_get(env, "DATAFORGE_DB_NAME", "marketplace"),
        user=_get(env, "DATAFORGE_DB_USER"),
        password=_get(env, "DATAFORGE_DB_PASSWORD"),
    )


def load_path_settings(env: Mapping[str, str] | None = None) -> PathSettings:
    env = os.environ if env is None else env
    return PathSettings(
        source_dir=Path(_get(env, "DATAFORGE_SOURCE_DIR", "data/source")).resolve(),
        report_dir=Path(_get(env, "DATAFORGE_REPORT_DIR", "data/reports")).resolve(),
        dbt_project_dir=Path(
            _get(env, "DATAFORGE_DBT_PROJECT_DIR", "dbt/marketplace_analytics")
        ).resolve(),
    )


def load_quality_settings(env: Mapping[str, str] | None = None) -> QualitySettings:
    env = os.environ if env is None else env
    raw_value = _get(env, "DATAFORGE_MAX_REJECTED_RATIO", "0.02")
    try:
        ratio = float(raw_value)
    except ValueError as exc:
        raise ConfigurationError(
            f"DATAFORGE_MAX_REJECTED_RATIO must be a number, got {raw_value!r}"
        ) from exc
    if not 0 <= ratio <= 1:
        raise ConfigurationError(
            f"DATAFORGE_MAX_REJECTED_RATIO must be between 0 and 1, got {ratio}"
        )
    return QualitySettings(max_rejected_ratio=ratio)
