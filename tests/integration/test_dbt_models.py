"""Builds the dbt project on the hand-built fixture and checks metrics calculated by hand.

See tests/fixtures/README.md for the expected values.
"""

from __future__ import annotations

import shutil
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine

from dataforge.quality.post_load import run_post_load_checks
from dataforge.transform import parse_test_results, run_dbt
from tests.integration.support import build_models, load_source, reset_warehouse
from tests.support import DBT_PROJECT_DIR, SMALL_SOURCE_DIR

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def built(engine: Engine, dbt_target: Path, tmp_path_factory: pytest.TempPathFactory) -> Engine:
    source = tmp_path_factory.mktemp("source")
    shutil.copytree(SMALL_SOURCE_DIR, source, dirs_exist_ok=True)
    reset_warehouse(engine)
    load_source(engine, source, "fixture-batch")
    build_models()
    return engine


def _rows(engine: Engine, sql: str) -> list:
    with engine.connect() as conn:
        return conn.execute(text(sql)).all()


def test_staging_normalizes_source_values(built: Engine) -> None:
    customer = _rows(
        built,
        "SELECT email, country_code, city "
        "FROM staging.stg_marketplace__customers "
        "WHERE customer_id = 'CUS-000001'",
    )[0]
    assert customer.email == "ava.smith1@example.com"
    assert customer.country_code == "US"
    sku = _rows(
        built,
        "SELECT sku, is_active FROM staging.stg_marketplace__products "
        "WHERE product_id = 'PRD-00001'",
    )[0]
    assert sku.sku == "BOO-NOV-00001" and sku.is_active is True


def test_order_level_revenue_and_refunds(built: Engine) -> None:
    orders = {
        r.order_id: r for r in _rows(built, "SELECT * FROM marts.fct_orders ORDER BY order_id")
    }
    first = orders["ORD-0000001"]
    assert (first.gross_sales_amount, first.discount_amount, first.net_sales_amount) == (
        Decimal("120.00"),
        Decimal("10.00"),
        Decimal("110.00"),
    )
    assert first.refunded_amount == Decimal("20.00")
    assert first.net_revenue_amount == Decimal("90.00")
    assert first.refund_status == "partial"

    assert orders["ORD-0000003"].is_revenue_eligible is False
    assert orders["ORD-0000003"].net_revenue_amount == Decimal("0.00")
    assert orders["ORD-0000004"].captured_amount == Decimal("0.00")
    assert orders["ORD-0000005"].refund_status == "full"
    assert orders["ORD-0000005"].failed_charge_count == 1
    assert orders["ORD-0000005"].net_revenue_amount == Decimal("0.00")
    assert [orders[o].customer_order_number for o in sorted(orders)] == [1, 2, None, None, 1]


def test_daily_revenue_totals(built: Engine) -> None:
    rows = _rows(built, "SELECT * FROM marts.mart_daily_revenue ORDER BY revenue_date")
    assert [str(r.revenue_date) for r in rows] == ["2025-03-01", "2025-03-02", "2025-03-03"]
    assert [r.net_revenue_amount for r in rows] == [
        Decimal("90.00"),
        Decimal("100.00"),
        Decimal("0.00"),
    ]
    assert sum(r.gross_sales_amount for r in rows) == Decimal("230.00")
    assert sum(r.discount_amount for r in rows) == Decimal("10.00")
    assert sum(r.refunded_amount for r in rows) == Decimal("30.00")
    assert [r.orders_placed for r in rows] == [1, 2, 2]
    assert rows[1].cancelled_orders == 1
    assert rows[0].average_order_value == Decimal("110.00")


def test_product_performance_allocates_refunds(built: Engine) -> None:
    products = {
        r.product_id: r for r in _rows(built, "SELECT * FROM marts.mart_product_performance")
    }
    book, watch = products["PRD-00001"], products["PRD-00002"]
    assert (book.units_sold, book.net_sales_amount) == (3, Decimal("30.00"))
    assert book.allocated_refund_amount == Decimal("13.64")
    assert watch.net_sales_amount == Decimal("190.00")
    assert watch.allocated_refund_amount == Decimal("16.36")
    assert watch.net_revenue_rank == 1


def test_customer_summary_identifies_repeat_customers(built: Engine) -> None:
    summary = {
        r.customer_id: r for r in _rows(built, "SELECT * FROM marts.mart_customer_order_summary")
    }
    assert summary["CUS-000001"].customer_segment == "repeat"
    assert summary["CUS-000001"].lifetime_net_revenue_amount == Decimal("190.00")
    assert summary["CUS-000002"].customer_segment == "one_time"
    assert summary["CUS-000002"].total_orders == 3
    assert summary["CUS-000003"].customer_segment == "no_orders"


def test_status_and_refund_rates(built: Engine) -> None:
    march = _rows(built, "SELECT * FROM marts.mart_order_status_refunds")[0]
    assert march.total_orders == 5
    assert march.cancellation_rate == Decimal("0.2000")
    assert march.cancelled_after_capture_orders == 1
    assert (march.refunded_orders, march.fully_refunded_orders) == (2, 1)
    assert march.refund_order_rate == Decimal("0.6667")
    assert march.refund_amount_rate == Decimal("0.1364")


def test_mart_constraints_are_enforced(built: Engine) -> None:
    constraints = {
        (r.table_name, r.constraint_type)
        for r in _rows(
            built,
            """
            SELECT tc.table_name, tc.constraint_type
            FROM information_schema.table_constraints AS tc
            WHERE tc.table_schema = 'marts'
              AND tc.constraint_type IN ('PRIMARY KEY', 'FOREIGN KEY')
        """,
        )
    }
    assert ("fct_orders", "FOREIGN KEY") in constraints
    assert ("fct_order_items", "FOREIGN KEY") in constraints
    assert {
        ("dim_customers", "PRIMARY KEY"),
        ("dim_products", "PRIMARY KEY"),
        ("fct_orders", "PRIMARY KEY"),
        ("fct_order_items", "PRIMARY KEY"),
    } <= constraints


def test_dbt_tests_pass(built: Engine, dbt_target: Path) -> None:
    run_dbt(DBT_PROJECT_DIR, ["test"])
    results = parse_test_results(dbt_target)
    assert len(results) > 50
    assert [r.check_name for r in results if not r.passed] == []


def test_post_load_checks_pass(built: Engine) -> None:
    checks = run_post_load_checks(built, "fixture-batch")
    assert [(c.entity, c.check_name) for c in checks if not c.passed] == []


def test_staging_keeps_latest_valid_version_across_batches(
    built: Engine, dbt_target: Path, source_dir: Path, edit_source
) -> None:
    edit_source(
        "products.csv",
        lambda df: df.assign(
            list_price=df["list_price"].where(df["product_id"] != "PRD-00002", "120.00"),
            product_name=df["product_name"].where(df["product_id"] != "PRD-00001", ""),
        ),
    )
    load_source(built, source_dir, "fixture-batch-2")
    run_dbt(DBT_PROJECT_DIR, ["run", "--select", "staging"])

    rows = {
        r.product_id: r
        for r in _rows(
            built,
            "SELECT product_id, product_name, list_price, source_batch_id "
            "FROM staging.stg_marketplace__products",
        )
    }
    assert rows["PRD-00002"].list_price == Decimal("120.00")
    assert rows["PRD-00002"].source_batch_id == "fixture-batch-2"
    # The newer PRD-00001 row is quarantined (missing name), so the last valid version wins.
    assert rows["PRD-00001"].product_name == "Nova Travel Guide"
    assert rows["PRD-00001"].source_batch_id == "fixture-batch"
