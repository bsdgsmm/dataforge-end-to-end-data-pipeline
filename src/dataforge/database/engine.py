from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from dataforge.config import DatabaseSettings, load_database_settings


def build_engine(settings: DatabaseSettings | None = None) -> Engine:
    settings = settings or load_database_settings()
    return create_engine(
        settings.url(),
        pool_pre_ping=True,
        connect_args={"application_name": "dataforge", "connect_timeout": 10},
    )
