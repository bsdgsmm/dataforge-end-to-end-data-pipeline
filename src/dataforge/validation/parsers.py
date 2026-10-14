"""Strict parsers that define which text values the staging layer can safely cast."""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import date, datetime
from decimal import Decimal

from dataforge.contracts import ColumnType

_INTEGER = re.compile(r"^-?\d+$")
_DECIMAL = re.compile(r"^-?\d+(\.\d{1,2})?$")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(\.\d{1,6})?(Z|[+-]\d{2}:\d{2})$")
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")
_BOOLEANS = {"true": True, "false": False}


def parse_integer(value: str) -> int | None:
    return int(value) if _INTEGER.match(value) else None


def parse_decimal(value: str) -> Decimal | None:
    return Decimal(value) if _DECIMAL.match(value) else None


def parse_boolean(value: str) -> bool | None:
    return _BOOLEANS.get(value.lower())


def parse_date(value: str) -> date | None:
    if not _DATE.match(value):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def parse_timestamp(value: str) -> datetime | None:
    """Accept ISO 8601 timestamps with an explicit UTC offset only."""
    if not _TIMESTAMP.match(value):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def is_valid_email(value: str) -> bool:
    return bool(_EMAIL.match(value.strip()))


PARSERS: dict[ColumnType, Callable[[str], object]] = {
    ColumnType.TEXT: lambda value: value,
    ColumnType.INTEGER: parse_integer,
    ColumnType.DECIMAL: parse_decimal,
    ColumnType.BOOLEAN: parse_boolean,
    ColumnType.DATE: parse_date,
    ColumnType.TIMESTAMP: parse_timestamp,
}
