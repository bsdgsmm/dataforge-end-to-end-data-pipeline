from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine

from dataforge.ingestion import loader
from dataforge.runs import finish_run, track_stage
from tests.integration.support import load_source

pytestmark = pytest.mark.integration


def _count(engine: Engine, sql: str, **params) -> int:
    with engine.connect() as conn:
        return int(conn.execute(text(sql), params).scalar_one())


def test_reloading_the_same_batch_is_idempotent(fresh_warehouse: Engine, source_dir: Path) -> None:
    load_source(fresh_warehouse, source_dir, "batch-1")
    first = _count(fresh_warehouse, "SELECT count(*) FROM raw.order_items")
    load_source(fresh_warehouse, source_dir, "batch-1")
    load_source(fresh_warehouse, source_dir, "batch-1")

    assert first == 6
    assert _count(fresh_warehouse, "SELECT count(*) FROM raw.order_items") == first
    assert _count(fresh_warehouse, "SELECT count(*) FROM audit.raw_load_stats") == 5


def test_rerun_picks_up_corrected_source_data(
    fresh_warehouse: Engine, source_dir: Path, edit_source
) -> None:
    load_source(fresh_warehouse, source_dir, "batch-1")
    edit_source("products.csv", lambda df: df.assign(list_price="12.50"))
    load_source(fresh_warehouse, source_dir, "batch-1")

    prices = _count(
        fresh_warehouse,
        "SELECT count(*) FROM raw.products WHERE _batch_id = 'batch-1' AND list_price = '12.50'",
    )
    assert prices == 2
    assert _count(fresh_warehouse, "SELECT count(*) FROM raw.products") == 2


def test_new_batches_are_kept_side_by_side(fresh_warehouse: Engine, source_dir: Path) -> None:
    load_source(fresh_warehouse, source_dir, "batch-1")
    load_source(fresh_warehouse, source_dir, "batch-2")
    assert _count(fresh_warehouse, "SELECT count(DISTINCT _batch_id) FROM raw.orders") == 2
    assert _count(fresh_warehouse, "SELECT count(*) FROM raw.orders") == 10


def test_quarantined_rows_are_stored_with_reasons(
    fresh_warehouse: Engine, source_dir: Path, edit_source
) -> None:
    edit_source(
        "order_items.csv",
        lambda df: df.assign(
            quantity=df["quantity"].where(df["order_item_id"] != "ORD-0000002-01", "-1")
        ),
    )
    load_source(fresh_warehouse, source_dir, "batch-1")

    with fresh_warehouse.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT 'orders' AS entity, order_id AS key, _rejection_reasons FROM raw.orders "
                "WHERE _is_rejected UNION ALL "
                "SELECT 'order_items', order_item_id, _rejection_reasons FROM raw.order_items "
                "WHERE _is_rejected UNION ALL "
                "SELECT 'payments', payment_id, _rejection_reasons FROM raw.payments "
                "WHERE _is_rejected ORDER BY 1, 2"
            )
        ).all()
        stats = dict(
            conn.execute(text("SELECT entity, rows_rejected FROM audit.raw_load_stats")).all()
        )

    assert [(r.entity, r.key) for r in rows] == [
        ("order_items", "ORD-0000002-01"),
        ("orders", "ORD-0000002"),
        ("payments", "PAY-0000003"),
    ]
    assert rows[0]._rejection_reasons == ["out_of_range:quantity"]
    assert rows[1]._rejection_reasons == ["order_without_valid_items"]
    assert stats == {"customers": 0, "products": 0, "orders": 1, "order_items": 1, "payments": 1}


def test_failed_stage_is_recorded(fresh_warehouse: Engine) -> None:
    with pytest.raises(ValueError, match="boom"), track_stage(fresh_warehouse, "run-x", "load_raw"):
        raise ValueError("boom")
    with track_stage(fresh_warehouse, "run-x", "validate_source"):
        pass
    finish_run(fresh_warehouse, "run-x", "failed")

    with fresh_warehouse.connect() as conn:
        run = conn.execute(
            text("SELECT status, error_message FROM audit.pipeline_runs WHERE run_id = 'run-x'")
        ).one()
        stages = dict(
            conn.execute(
                text("SELECT stage, status FROM audit.pipeline_stage_runs WHERE run_id = 'run-x'")
            ).all()
        )
    assert run.status == "failed"
    assert run.error_message == "load_raw: ValueError: boom"
    assert stages == {"load_raw": "failed", "validate_source": "succeeded"}


def test_retried_stage_increments_attempt(fresh_warehouse: Engine) -> None:
    for _ in range(3):
        with track_stage(fresh_warehouse, "run-y", "dbt_run"):
            pass
    assert (
        _count(
            fresh_warehouse,
            "SELECT attempt FROM audit.pipeline_stage_runs WHERE run_id = 'run-y'",
        )
        == 3
    )


def test_load_is_atomic_across_entities(
    fresh_warehouse: Engine, source_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    load_source(fresh_warehouse, source_dir, "batch-1")
    original = loader.build_raw_rows

    def fail_on_payments(data, run_id, source_file):
        if data.contract.entity == "payments":
            raise RuntimeError("simulated failure mid-load")
        return original(data, run_id, source_file)

    monkeypatch.setattr(loader, "build_raw_rows", fail_on_payments)
    frame = pd.read_csv(source_dir / "orders.csv", dtype=str)
    frame.iloc[:2].to_csv(source_dir / "orders.csv", index=False)
    with pytest.raises(RuntimeError, match="simulated"):
        load_source(fresh_warehouse, source_dir, "batch-1")

    assert _count(fresh_warehouse, "SELECT count(*) FROM raw.orders") == 5
