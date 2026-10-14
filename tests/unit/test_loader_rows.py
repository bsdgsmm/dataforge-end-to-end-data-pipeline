from __future__ import annotations

from pathlib import Path

import pytest

from dataforge.ingestion.loader import LoadBlockedError, build_raw_rows, load_batch, record_hash
from dataforge.validation.validator import validate_source_dir


def test_raw_rows_preserve_source_values_and_flags(source_dir: Path, edit_source) -> None:
    edit_source("orders.csv", lambda df: df.replace({"order_status": {"pending": "on_hold"}}))
    result = validate_source_dir(source_dir, max_rejected_ratio=1.0)
    rows = build_raw_rows(result.entities["orders"], "run-1", "orders.csv")

    assert [row["_source_line"] for row in rows] == [2, 3, 4, 5, 6]
    rejected = next(row for row in rows if row["order_id"] == "ORD-0000004")
    assert rejected["_is_rejected"] is True
    assert rejected["order_status"] == "on_hold"
    assert "invalid_value:order_status" in rejected["_rejection_reasons"]
    assert "orphaned_foreign_key:order_id" not in rejected["_rejection_reasons"]
    valid = next(row for row in rows if row["order_id"] == "ORD-0000001")
    assert valid["_is_rejected"] is False and valid["_rejection_reasons"] is None
    assert all(row["_batch_id"] == "run-1" for row in rows)


def test_raw_rows_keep_untrimmed_text_and_null_empty_values(source_dir: Path) -> None:
    result = validate_source_dir(source_dir, max_rejected_ratio=1.0)
    rows = build_raw_rows(result.entities["customers"], "run-1", "customers.csv")
    assert rows[0]["email"] == " Ava.Smith1@Example.com "
    assert rows[2]["city"] is None


def test_record_hash_is_stable_and_order_sensitive() -> None:
    assert record_hash(["a", "b"]) == record_hash(["a", "b"])
    assert record_hash(["a", "b"]) != record_hash(["b", "a"])
    assert record_hash(["ab", ""]) != record_hash(["a", "b"])


def test_load_refuses_batches_with_blocking_failures(source_dir: Path) -> None:
    (source_dir / "orders.csv").unlink()
    result = validate_source_dir(source_dir, max_rejected_ratio=1.0)
    with pytest.raises(LoadBlockedError, match=r"orders\.file_present"):
        load_batch(engine=None, run_id="run-1", validation=result, source_dir=source_dir)
