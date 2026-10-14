from __future__ import annotations

import hashlib
from collections import Counter
from decimal import Decimal
from pathlib import Path

import pytest

from dataforge.contracts import CONTRACTS, ORDER_STATUSES
from dataforge.generation.synthetic import (
    GenerationParams,
    generate_dataset,
    source_files_present,
    write_dataset,
)
from dataforge.validation.validator import validate_source_dir

SMALL = GenerationParams(customers=150, products=24)


def _digest(directory: Path) -> dict[str, str]:
    return {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(directory.glob("*.csv"))
    }


@pytest.fixture(scope="module")
def dataset():
    return generate_dataset(SMALL)


def test_same_seed_produces_identical_files(tmp_path: Path) -> None:
    write_dataset(generate_dataset(SMALL), tmp_path / "a")
    write_dataset(generate_dataset(SMALL), tmp_path / "b")
    assert _digest(tmp_path / "a") == _digest(tmp_path / "b")


def test_different_seed_produces_different_data() -> None:
    first = generate_dataset(SMALL)
    second = generate_dataset(GenerationParams(seed=7, customers=150, products=24))
    assert first["orders"] != second["orders"]


def test_files_follow_contract_columns(tmp_path: Path, dataset) -> None:
    write_dataset(dataset, tmp_path)
    assert source_files_present(tmp_path)
    for contract in CONTRACTS:
        header = (tmp_path / contract.file_name).read_text(encoding="utf-8").splitlines()[0]
        assert header.split(",") == contract.column_names


def test_primary_keys_are_unique(dataset) -> None:
    for contract in CONTRACTS:
        keys = [row[contract.primary_key] for row in dataset[contract.entity]]
        assert len(keys) == len(set(keys)), contract.entity


def test_foreign_keys_resolve(dataset) -> None:
    customer_ids = {c["customer_id"] for c in dataset["customers"]}
    product_ids = {p["product_id"] for p in dataset["products"]}
    order_ids = {o["order_id"] for o in dataset["orders"]}
    assert {o["customer_id"] for o in dataset["orders"]} <= customer_ids
    assert {i["order_id"] for i in dataset["order_items"]} == order_ids
    assert {i["product_id"] for i in dataset["order_items"]} <= product_ids
    assert {p["order_id"] for p in dataset["payments"]} <= order_ids


def test_orders_are_placed_after_signup(dataset) -> None:
    signed_up = {c["customer_id"]: c["signed_up_at"] for c in dataset["customers"]}
    for order in dataset["orders"]:
        assert order["ordered_at"] >= signed_up[order["customer_id"]]
        assert order["updated_at"] >= order["ordered_at"]


def test_statuses_are_valid_and_varied(dataset) -> None:
    statuses = Counter(o["order_status"] for o in dataset["orders"])
    assert set(statuses) <= ORDER_STATUSES
    assert statuses["delivered"] > statuses["cancelled"] > 0


def test_succeeded_charges_equal_item_net_for_fulfilled_orders(dataset) -> None:
    totals: dict[str, Decimal] = Counter()
    for item in dataset["order_items"]:
        totals[item["order_id"]] += Decimal(item["unit_price"]) * int(item["quantity"]) - Decimal(
            item["discount_amount"]
        )
    charged: dict[str, Decimal] = Counter()
    for payment in dataset["payments"]:
        if payment["transaction_type"] == "charge" and payment["payment_status"] == "succeeded":
            charged[payment["order_id"]] += Decimal(payment["amount"])
    for order in dataset["orders"]:
        if order["order_status"] in {"processing", "shipped", "delivered"}:
            assert charged[order["order_id"]] == totals[order["order_id"]].quantize(Decimal("0.01"))


def test_clean_dataset_passes_validation(tmp_path: Path, dataset) -> None:
    write_dataset(dataset, tmp_path)
    result = validate_source_dir(tmp_path, max_rejected_ratio=0.0)
    assert result.failed_checks() == []


def test_defect_injection_is_detected(tmp_path: Path) -> None:
    write_dataset(generate_dataset(GenerationParams(inject_defects=True)), tmp_path)
    result = validate_source_dir(tmp_path, max_rejected_ratio=0.05)
    failed = {(c.entity, c.check_name) for c in result.failed_checks()}
    assert ("customers", "unique:customer_id") in failed
    assert ("products", "unique:product_id") in failed
    assert ("orders", "accepted_values:order_status") in failed
    assert ("orders", "relationship:customer_id->customers") in failed
    assert ("order_items", "range:quantity") in failed
    assert ("order_items", "valid_type:unit_price") in failed
    assert ("payments", "valid_type:created_at") in failed
    assert ("payments", "payments_reconcile_to_order_total") in failed
    assert result.is_loadable
