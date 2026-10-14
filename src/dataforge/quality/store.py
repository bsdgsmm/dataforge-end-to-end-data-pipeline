from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from sqlalchemy import delete, insert, select
from sqlalchemy.engine import Engine

from dataforge.database.schema import data_quality_results, raw_load_stats
from dataforge.validation.results import CheckResult


def save_check_results(
    engine: Engine, run_id: str, stage: str, checks: Iterable[CheckResult]
) -> None:
    """Replace the stored results of one stage for one run."""
    rows = [
        {
            "run_id": run_id,
            "stage": stage,
            "check_name": check.check_name,
            "entity": check.entity,
            "severity": str(check.severity),
            "status": "passed" if check.passed else "failed",
            "checked_records": check.checked_records,
            "failed_records": check.failed_records,
            "message": check.message or None,
            "sample_keys": list(check.sample_keys) or None,
        }
        for check in checks
    ]
    with engine.begin() as conn:
        conn.execute(
            delete(data_quality_results).where(
                data_quality_results.c.run_id == run_id,
                data_quality_results.c.stage == stage,
            )
        )
        if rows:
            conn.execute(insert(data_quality_results), rows)


def fetch_check_results(engine: Engine, run_id: str) -> list[dict[str, Any]]:
    table = data_quality_results
    with engine.connect() as conn:
        result = conn.execute(
            select(
                table.c.stage,
                table.c.check_name,
                table.c.entity,
                table.c.severity,
                table.c.status,
                table.c.checked_records,
                table.c.failed_records,
                table.c.message,
                table.c.sample_keys,
            )
            .where(table.c.run_id == run_id)
            .order_by(table.c.result_id)
        )
        return [dict(row._mapping) for row in result]


def fetch_load_stats(engine: Engine, run_id: str) -> list[dict[str, Any]]:
    table = raw_load_stats
    with engine.connect() as conn:
        result = conn.execute(
            select(table.c.entity, table.c.rows_received, table.c.rows_valid, table.c.rows_rejected)
            .where(table.c.run_id == run_id)
            .order_by(table.c.entity)
        )
        return [dict(row._mapping) for row in result]
