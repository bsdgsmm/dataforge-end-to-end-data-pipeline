"""Run and stage bookkeeping in audit.pipeline_runs / audit.pipeline_stage_runs."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine

from dataforge.database.schema import pipeline_runs, pipeline_stage_runs

logger = logging.getLogger(__name__)

MAX_ERROR_LENGTH = 2000


def ensure_run(engine: Engine, run_id: str) -> None:
    with engine.begin() as conn:
        conn.execute(
            insert(pipeline_runs)
            .values(run_id=run_id, status="running")
            .on_conflict_do_update(
                index_elements=[pipeline_runs.c.run_id],
                set_={"status": "running", "finished_at": None, "error_message": None},
            )
        )


@contextmanager
def track_stage(engine: Engine, run_id: str, stage: str) -> Iterator[None]:
    """Record start, success, or failure of a pipeline stage. Retries increment `attempt`."""
    ensure_run(engine, run_id)
    with engine.begin() as conn:
        conn.execute(
            insert(pipeline_stage_runs)
            .values(run_id=run_id, stage=stage, status="running", attempt=1, started_at=func.now())
            .on_conflict_do_update(
                index_elements=[pipeline_stage_runs.c.run_id, pipeline_stage_runs.c.stage],
                set_={
                    "status": "running",
                    "attempt": pipeline_stage_runs.c.attempt + 1,
                    "started_at": func.now(),
                    "finished_at": None,
                    "error_message": None,
                },
            )
        )
        conn.execute(
            update(pipeline_runs)
            .where(pipeline_runs.c.run_id == run_id)
            .values(current_stage=stage)
        )
    logger.info("Stage %s started for run %s", stage, run_id)
    try:
        yield
    except BaseException as exc:
        message = f"{type(exc).__name__}: {exc}"[:MAX_ERROR_LENGTH]
        _finish_stage(engine, run_id, stage, "failed", message)
        logger.error("Stage %s failed for run %s: %s", stage, run_id, message)
        raise
    _finish_stage(engine, run_id, stage, "succeeded", None)
    logger.info("Stage %s succeeded for run %s", stage, run_id)


def _finish_stage(
    engine: Engine, run_id: str, stage: str, status: str, error_message: str | None
) -> None:
    with engine.begin() as conn:
        conn.execute(
            update(pipeline_stage_runs)
            .where(pipeline_stage_runs.c.run_id == run_id, pipeline_stage_runs.c.stage == stage)
            .values(status=status, finished_at=func.now(), error_message=error_message)
        )
        if status == "failed":
            conn.execute(
                update(pipeline_runs)
                .where(pipeline_runs.c.run_id == run_id)
                .values(status="failed", error_message=f"{stage}: {error_message}")
            )


def finish_run(engine: Engine, run_id: str, status: str, error_message: str | None = None) -> None:
    with engine.begin() as conn:
        if status == "failed" and error_message is None:
            failed = conn.execute(
                select(pipeline_stage_runs.c.stage, pipeline_stage_runs.c.error_message).where(
                    pipeline_stage_runs.c.run_id == run_id,
                    pipeline_stage_runs.c.status == "failed",
                )
            ).first()
            error_message = (
                f"{failed.stage}: {failed.error_message}"
                if failed is not None
                else "Failed outside a tracked stage; see the orchestrator task logs."
            )
        conn.execute(
            insert(pipeline_runs)
            .values(
                run_id=run_id, status=status, finished_at=func.now(), error_message=error_message
            )
            .on_conflict_do_update(
                index_elements=[pipeline_runs.c.run_id],
                set_={"status": status, "finished_at": func.now(), "error_message": error_message},
            )
        )
    logger.info("Run %s finished with status %s", run_id, status)


def stage_statuses(engine: Engine, run_id: str) -> dict[str, str]:
    with engine.connect() as conn:
        rows = conn.execute(
            select(pipeline_stage_runs.c.stage, pipeline_stage_runs.c.status).where(
                pipeline_stage_runs.c.run_id == run_id
            )
        )
        return {row.stage: row.status for row in rows}
