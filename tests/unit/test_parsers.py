from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from dataforge.validation.parsers import (
    is_valid_email,
    parse_boolean,
    parse_date,
    parse_decimal,
    parse_integer,
    parse_timestamp,
)


@pytest.mark.parametrize(("value", "expected"), [("3", 3), ("-2", -2), ("0", 0)])
def test_parse_integer_accepts_whole_numbers(value: str, expected: int) -> None:
    assert parse_integer(value) == expected


@pytest.mark.parametrize("value", ["3.0", "three", "", "1e3", " 4"])
def test_parse_integer_rejects_other_values(value: str) -> None:
    assert parse_integer(value) is None


@pytest.mark.parametrize(
    ("value", "expected"), [("10", "10"), ("10.5", "10.5"), ("-0.01", "-0.01")]
)
def test_parse_decimal_accepts_up_to_two_places(value: str, expected: str) -> None:
    assert parse_decimal(value) == Decimal(expected)


@pytest.mark.parametrize("value", ["10.123", "twelve", "1,000.00", "", "NaN"])
def test_parse_decimal_rejects_invalid_amounts(value: str) -> None:
    assert parse_decimal(value) is None


def test_parse_boolean_is_case_insensitive_and_strict() -> None:
    assert parse_boolean("TRUE") is True
    assert parse_boolean("false") is False
    assert parse_boolean("yes") is None


def test_parse_timestamp_requires_offset() -> None:
    assert parse_timestamp("2025-03-01T10:00:00Z") == datetime(2025, 3, 1, 10, tzinfo=UTC)
    assert parse_timestamp("2025-03-01T10:00:00+02:00") is not None
    assert parse_timestamp("2025-03-01T10:00:00") is None
    assert parse_timestamp("2025-13-45T00:00:00Z") is None
    assert parse_timestamp("20250301T100000Z") is None


def test_parse_date() -> None:
    assert parse_date("2025-02-28") is not None
    assert parse_date("2025-02-30") is None


@pytest.mark.parametrize(
    ("value", "valid"),
    [("a@example.com", True), (" A.B@Example.org ", True), ("not-an-email", False), ("a@b", False)],
)
def test_email_format(value: str, valid: bool) -> None:
    assert is_valid_email(value) is valid
