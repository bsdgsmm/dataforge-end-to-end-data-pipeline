from __future__ import annotations

from pathlib import Path

import pandas as pd

from dataforge.validation.results import Severity
from dataforge.validation.validator import validate_source_dir

LENIENT = 1.0


def _failed(result, entity: str, check_name: str):
    return next(
        (c for c in result.failed_checks() if c.entity == entity and c.check_name == check_name),
        None,
    )


def _reasons(result, entity: str, key: str) -> list[str]:
    data = result.entities[entity]
    keys = data.frame[data.contract.primary_key].str.strip()
    position = int(keys[keys == key].index[0])
    return data.rejections.get(position, [])


def test_fixture_dataset_is_clean(source_dir: Path) -> None:
    result = validate_source_dir(source_dir, max_rejected_ratio=0.0)
    assert result.failed_checks() == []
    assert all(data.rejected_count == 0 for data in result.entities.values())


def test_missing_file_is_blocking(source_dir: Path) -> None:
    (source_dir / "payments.csv").unlink()
    result = validate_source_dir(source_dir, LENIENT)
    check = _failed(result, "payments", "file_present")
    assert check is not None and check.severity is Severity.BLOCKING
    assert not result.is_loadable


def test_missing_required_column_is_blocking(source_dir: Path, edit_source) -> None:
    edit_source("orders.csv", lambda df: df.drop(columns=["order_status"]))
    result = validate_source_dir(source_dir, LENIENT)
    check = _failed(result, "orders", "required_columns_present")
    assert check is not None
    assert check.sample_keys == ("order_status",)
    assert not result.is_loadable


def test_unexpected_column_is_only_a_warning(source_dir: Path, edit_source) -> None:
    edit_source("products.csv", lambda df: df.assign(color="red"))
    result = validate_source_dir(source_dir, LENIENT)
    check = _failed(result, "products", "no_unexpected_columns")
    assert check is not None and check.severity is Severity.WARNING
    assert result.is_loadable


def test_header_only_file_is_blocking(source_dir: Path, edit_source) -> None:
    edit_source("customers.csv", lambda df: df.iloc[0:0])
    result = validate_source_dir(source_dir, LENIENT)
    assert _failed(result, "customers", "file_not_empty") is not None


def test_missing_required_value_quarantines_row(source_dir: Path, edit_source) -> None:
    def blank_email(df: pd.DataFrame) -> pd.DataFrame:
        df.loc[df["customer_id"] == "CUS-000003", "email"] = "  "
        return df

    edit_source("customers.csv", blank_email)
    result = validate_source_dir(source_dir, LENIENT)
    assert _failed(result, "customers", "not_null:email").failed_records == 1
    assert "missing_required_value:email" in _reasons(result, "customers", "CUS-000003")


def test_optional_column_may_be_empty(source_dir: Path) -> None:
    result = validate_source_dir(source_dir, LENIENT)
    assert _reasons(result, "customers", "CUS-000003") == []


def test_invalid_types_are_quarantined(source_dir: Path, edit_source) -> None:
    def corrupt(df: pd.DataFrame) -> pd.DataFrame:
        df.loc[0, "quantity"] = "two"
        df.loc[1, "unit_price"] = "10.999"
        return df

    edit_source("order_items.csv", corrupt)
    result = validate_source_dir(source_dir, LENIENT)
    assert _failed(result, "order_items", "valid_type:quantity").failed_records == 1
    assert _failed(result, "order_items", "valid_type:unit_price").failed_records == 1


def test_invalid_timestamp_and_future_timestamp(source_dir: Path, edit_source) -> None:
    def corrupt(df: pd.DataFrame) -> pd.DataFrame:
        df.loc[0, "created_at"] = "2025-02-30T10:00:00Z"
        df.loc[1, "created_at"] = "2999-01-01T00:00:00Z"
        return df

    edit_source("payments.csv", corrupt)
    result = validate_source_dir(source_dir, LENIENT)
    assert _failed(result, "payments", "valid_type:created_at").sample_keys == ("PAY-0000001",)
    assert _failed(result, "payments", "not_in_future:created_at").sample_keys == ("PAY-0000002",)


def test_invalid_statuses_are_quarantined(source_dir: Path, edit_source) -> None:
    edit_source("orders.csv", lambda df: df.replace({"order_status": {"shipped": "teleported"}}))
    edit_source("payments.csv", lambda df: df.replace({"payment_status": {"pending": "maybe"}}))
    result = validate_source_dir(source_dir, LENIENT)
    assert _failed(result, "orders", "accepted_values:order_status").sample_keys == ("ORD-0000002",)
    assert _failed(result, "payments", "accepted_values:payment_status").sample_keys == (
        "PAY-0000006",
    )


def test_negative_and_zero_values_are_rejected(source_dir: Path, edit_source) -> None:
    def corrupt(df: pd.DataFrame) -> pd.DataFrame:
        df.loc[0, "quantity"] = "0"
        df.loc[1, "discount_amount"] = "-1.00"
        return df

    edit_source("order_items.csv", corrupt)
    edit_source(
        "payments.csv",
        lambda df: df.assign(
            amount=df["amount"].where(df["payment_id"] != "PAY-0000003", "-100.00")
        ),
    )
    result = validate_source_dir(source_dir, LENIENT)
    assert _failed(result, "order_items", "range:quantity").failed_records == 1
    assert _failed(result, "order_items", "range:discount_amount").failed_records == 1
    assert _failed(result, "payments", "range:amount").sample_keys == ("PAY-0000003",)


def test_discount_larger_than_line_total_is_rejected(source_dir: Path, edit_source) -> None:
    edit_source(
        "order_items.csv",
        lambda df: df.assign(
            discount_amount=df["discount_amount"].where(
                df["order_item_id"] != "ORD-0000002-01", "150.00"
            )
        ),
    )
    result = validate_source_dir(source_dir, LENIENT)
    assert _failed(result, "order_items", "discount_not_above_line_total").sample_keys == (
        "ORD-0000002-01",
    )


def test_exact_duplicates_keep_first_copy(source_dir: Path, edit_source) -> None:
    edit_source("products.csv", lambda df: pd.concat([df, df.iloc[[0]]], ignore_index=True))
    result = validate_source_dir(source_dir, LENIENT)
    products = result.entities["products"]
    assert products.rejections[2] == ["duplicate_record"]
    assert not products.is_rejected(0)
    assert _failed(result, "products", "unique:product_id").failed_records == 1


def test_conflicting_duplicates_quarantine_every_copy(source_dir: Path, edit_source) -> None:
    def conflicting_copy(df: pd.DataFrame) -> pd.DataFrame:
        copy = df.iloc[[1]].assign(list_price="120.00")
        return pd.concat([df, copy], ignore_index=True)

    edit_source("products.csv", conflicting_copy)
    result = validate_source_dir(source_dir, LENIENT)
    products = result.entities["products"]
    assert products.is_rejected(1) and products.is_rejected(2)
    assert products.rejections[1] == ["conflicting_duplicate_key:product_id"]


def test_orphaned_foreign_keys_cascade(source_dir: Path, edit_source) -> None:
    edit_source("orders.csv", lambda df: df.replace({"customer_id": {"CUS-000001": "CUS-404"}}))
    result = validate_source_dir(source_dir, LENIENT)
    assert _failed(result, "orders", "relationship:customer_id->customers").failed_records == 2
    assert _failed(result, "order_items", "relationship:order_id->orders").failed_records == 3
    assert _failed(result, "payments", "relationship:order_id->orders").failed_records == 3
    assert "orphaned_foreign_key:customer_id" in _reasons(result, "orders", "ORD-0000001")


def test_quarantined_parent_orphans_children(source_dir: Path, edit_source) -> None:
    edit_source(
        "products.csv",
        lambda df: df.assign(
            list_price=df["list_price"].where(df["product_id"] != "PRD-00002", "free")
        ),
    )
    result = validate_source_dir(source_dir, LENIENT)
    assert _failed(result, "order_items", "relationship:product_id->products").sample_keys == (
        "ORD-0000001-02",
        "ORD-0000002-01",
    )
    assert "order_without_valid_items" in _reasons(result, "orders", "ORD-0000002")


def test_order_without_items_is_quarantined(source_dir: Path, edit_source) -> None:
    edit_source("order_items.csv", lambda df: df[df["order_id"] != "ORD-0000004"])
    result = validate_source_dir(source_dir, LENIENT)
    assert _failed(result, "orders", "order_has_valid_items").sample_keys == ("ORD-0000004",)
    assert "orphaned_foreign_key:order_id" in _reasons(result, "payments", "PAY-0000006")


def test_payment_mismatch_is_a_warning_and_rows_are_kept(source_dir: Path, edit_source) -> None:
    edit_source(
        "payments.csv",
        lambda df: df.assign(amount=df["amount"].where(df["payment_id"] != "PAY-0000003", "95.00")),
    )
    result = validate_source_dir(source_dir, LENIENT)
    check = _failed(result, "payments", "payments_reconcile_to_order_total")
    assert check.severity is Severity.WARNING
    assert check.sample_keys == ("ORD-0000002",)
    assert result.entities["payments"].rejected_count == 0


def test_over_refund_and_uncaptured_cancellation_warnings(source_dir: Path, edit_source) -> None:
    def change(df: pd.DataFrame) -> pd.DataFrame:
        df.loc[df["payment_id"] == "PAY-0000002", "amount"] = "500.00"
        return df[df["payment_id"] != "PAY-0000005"]

    edit_source("payments.csv", change)
    result = validate_source_dir(source_dir, LENIENT)
    assert _failed(result, "payments", "refunds_not_above_charges").sample_keys == ("ORD-0000001",)
    assert _failed(result, "payments", "cancelled_orders_fully_refunded").sample_keys == (
        "ORD-0000003",
    )


def test_rejected_ratio_above_threshold_blocks_load(source_dir: Path, edit_source) -> None:
    edit_source(
        "order_items.csv",
        lambda df: df.assign(
            quantity=df["quantity"].where(df["order_item_id"] != "ORD-0000003-01", "-1")
        ),
    )
    assert validate_source_dir(source_dir, max_rejected_ratio=0.5).is_loadable
    strict = validate_source_dir(source_dir, max_rejected_ratio=0.1)
    check = _failed(strict, "order_items", "rejected_ratio_within_threshold")
    assert check.severity is Severity.BLOCKING
    assert not strict.is_loadable
