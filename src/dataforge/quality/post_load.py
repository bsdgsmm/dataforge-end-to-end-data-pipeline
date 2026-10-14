"""Warehouse-level checks that run after dbt has built the models.

They verify that nothing was lost or double counted between layers:
raw (valid rows) -> staging -> marts, and that revenue aggregates reconcile.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from dataforge.contracts import CONTRACTS
from dataforge.validation.results import CheckResult, Severity

STAGING_SCHEMA = "staging"
MARTS_SCHEMA = "marts"
TOLERANCE = Decimal("0.01")


def _scalar(conn: Connection, sql: str, **params: object) -> object:
    return conn.execute(text(sql), params).scalar_one()


# Table and column names interpolated below come from the in-code source contracts and
# fixed model names, never from user input; data values are always bound parameters.


def _batch_landed(conn: Connection, run_id: str) -> list[CheckResult]:
    checks = []
    for contract in CONTRACTS:
        rows = _scalar(
            conn,
            f"SELECT count(*) FROM raw.{contract.entity} WHERE _batch_id = :run_id",  # noqa: S608
            run_id=run_id,
        )
        checks.append(
            CheckResult(
                "batch_present_in_raw",
                contract.entity,
                Severity.BLOCKING,
                1,
                0 if rows else 1,
                "" if rows else f"No raw.{contract.entity} rows exist for batch {run_id}.",
            )
        )
    return checks


def _staging_matches_raw(conn: Connection) -> list[CheckResult]:
    checks = []
    for contract in CONTRACTS:
        key = contract.primary_key
        expected = _scalar(
            conn,
            f"SELECT count(DISTINCT trim({key})) FROM raw.{contract.entity} "  # noqa: S608
            "WHERE NOT _is_rejected",
        )
        actual = _scalar(
            conn,
            f"SELECT count(*) FROM {STAGING_SCHEMA}.stg_marketplace__{contract.entity}",  # noqa: S608
        )
        difference = abs(int(expected) - int(actual))
        checks.append(
            CheckResult(
                "staging_row_count_matches_raw",
                contract.entity,
                Severity.BLOCKING,
                int(expected),
                difference,
                f"Expected {expected} distinct valid keys in staging, found {actual}."
                if difference
                else "",
            )
        )
    return checks


def _marts_match_staging(conn: Connection) -> list[CheckResult]:
    pairs = [
        ("orders", "stg_marketplace__orders", "fct_orders"),
        ("order_items", "stg_marketplace__order_items", "fct_order_items"),
        ("customers", "stg_marketplace__customers", "dim_customers"),
        ("products", "stg_marketplace__products", "dim_products"),
    ]
    checks = []
    for entity, staging_model, mart_model in pairs:
        staged = int(_scalar(conn, f"SELECT count(*) FROM {STAGING_SCHEMA}.{staging_model}"))  # noqa: S608
        modeled = int(_scalar(conn, f"SELECT count(*) FROM {MARTS_SCHEMA}.{mart_model}"))  # noqa: S608
        difference = abs(staged - modeled)
        checks.append(
            CheckResult(
                f"{mart_model}_row_count_matches_staging",
                entity,
                Severity.BLOCKING,
                staged,
                difference,
                f"{staging_model} has {staged} rows but {mart_model} has {modeled}."
                if difference
                else "",
            )
        )
    return checks


REVENUE_TOTALS_SQL = """
    SELECT
        (SELECT coalesce(sum(net_revenue_amount), 0)
         FROM marts.fct_orders WHERE is_revenue_eligible) AS orders_net_revenue,
        (SELECT coalesce(sum(net_revenue_amount), 0)
         FROM marts.mart_daily_revenue) AS daily_net_revenue,
        (SELECT coalesce(sum(net_sales_amount), 0)
         FROM marts.fct_order_items WHERE is_revenue_eligible) AS items_net_sales,
        (SELECT coalesce(sum(net_sales_amount), 0)
         FROM marts.mart_product_performance) AS products_net_sales,
        (SELECT count(*) FROM marts.fct_orders) AS order_count
"""

UNBALANCED_ORDERS_SQL = """
    SELECT
        count(*) FILTER (WHERE is_revenue_eligible) AS eligible_orders,
        count(*) FILTER (
            WHERE is_revenue_eligible AND abs(payment_balance_amount) > :tolerance
        ) AS unbalanced_orders,
        (array_agg(order_id ORDER BY order_id) FILTER (
            WHERE is_revenue_eligible AND abs(payment_balance_amount) > :tolerance
        ))[1:5] AS sample_order_ids
    FROM marts.fct_orders
"""


def _revenue_reconciles(conn: Connection) -> list[CheckResult]:
    totals = conn.execute(text(REVENUE_TOTALS_SQL)).one()
    order_count = int(totals.order_count)
    checks = []
    for name, left, right in (
        (
            "daily_revenue_reconciles_to_fct_orders",
            totals.orders_net_revenue,
            totals.daily_net_revenue,
        ),
        (
            "product_performance_reconciles_to_fct_order_items",
            totals.items_net_sales,
            totals.products_net_sales,
        ),
    ):
        difference = abs(Decimal(left) - Decimal(right))
        failed = difference > TOLERANCE
        checks.append(
            CheckResult(
                name,
                "marts",
                Severity.BLOCKING,
                order_count,
                1 if failed else 0,
                f"Totals differ by {difference}: {left} vs {right}."
                if failed
                else f"Totals agree at {left}.",
            )
        )
    return checks


def _payment_balance(conn: Connection) -> CheckResult:
    row = conn.execute(text(UNBALANCED_ORDERS_SQL), {"tolerance": TOLERANCE}).one()
    return CheckResult(
        "eligible_orders_fully_paid",
        "fct_orders",
        Severity.WARNING,
        int(row.eligible_orders),
        int(row.unbalanced_orders),
        f"{row.unbalanced_orders} revenue-eligible orders have captured payments that differ "
        "from net sales."
        if row.unbalanced_orders
        else "",
        tuple(row.sample_order_ids or ()),
    )


def run_post_load_checks(engine: Engine, run_id: str) -> list[CheckResult]:
    with engine.connect() as conn:
        return [
            *_batch_landed(conn, run_id),
            *_staging_matches_raw(conn),
            *_marts_match_staging(conn),
            *_revenue_reconciles(conn),
            _payment_balance(conn),
        ]
