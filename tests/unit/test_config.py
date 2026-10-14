from __future__ import annotations

import pytest

from dataforge.config import (
    ConfigurationError,
    load_database_settings,
    load_quality_settings,
)


def test_missing_credentials_raise_actionable_error() -> None:
    with pytest.raises(ConfigurationError, match="DATAFORGE_DB_USER, DATAFORGE_DB_PASSWORD"):
        load_database_settings({})


def test_database_settings_defaults_and_overrides() -> None:
    settings = load_database_settings(
        {
            "DATAFORGE_DB_USER": "pipeline",
            "DATAFORGE_DB_PASSWORD": "secret-value",
            "DATAFORGE_DB_PORT": "6543",
        }
    )
    assert settings.host == "localhost"
    assert settings.port == 6543
    assert settings.name == "marketplace"
    assert settings.url().database == "marketplace"


def test_password_is_not_exposed_in_repr() -> None:
    settings = load_database_settings(
        {"DATAFORGE_DB_USER": "pipeline", "DATAFORGE_DB_PASSWORD": "secret-value"}
    )
    assert "secret-value" not in repr(settings)
    assert "secret-value" not in str(settings.url())


def test_invalid_port_is_rejected() -> None:
    with pytest.raises(ConfigurationError, match="DATAFORGE_DB_PORT"):
        load_database_settings(
            {"DATAFORGE_DB_USER": "u", "DATAFORGE_DB_PASSWORD": "p", "DATAFORGE_DB_PORT": "abc"}
        )


@pytest.mark.parametrize("value", ["-0.1", "1.5", "lots"])
def test_rejected_ratio_must_be_a_fraction(value: str) -> None:
    with pytest.raises(ConfigurationError, match="DATAFORGE_MAX_REJECTED_RATIO"):
        load_quality_settings({"DATAFORGE_MAX_REJECTED_RATIO": value})
