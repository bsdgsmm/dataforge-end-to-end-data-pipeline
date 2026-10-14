"""Idempotent raw-layer loading.

Each run is a batch identified by its run_id. Loading a batch deletes any rows
previously written for the same batch and inserts the new rows in a single
transaction, so retries and reruns replace data instead of duplicating it.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import delete, func, insert, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Connection, Engine

from dataforge.contracts import CONTRACTS
from dataforge.database.schema import RAW_TABLES, raw_load_stats
from dataforge.validation.results import EntityData, ValidationResult

logger = logging.getLogger(__name__)

# Serializes concurrent loads (e.g. a manual run overlapping a scheduled one).
LOAD_LOCK_KEY = 74_201_001
FIRST_DATA_LINE = 2


class LoadBlockedError(RuntimeError):
    pass


@dataclass(frozen=True)
class LoadStats:
    entity: str
    rows_received: int
    rows_valid: int
    rows_rejected: int


def record_hash(values: list[str]) -> str:
    return hashlib.sha256("\x1f".join(values).encode("utf-8")).hexdigest()


def build_raw_rows(data: EntityData, run_id: str, source_file: str) -> list[dict[str, object]]:
    columns = data.contract.column_names
    rows = []
    for position, values in enumerate(data.frame[columns].itertuples(index=False, name=None)):
        reasons = data.rejections.get(position) or []
        row: dict[str, object] = {
            name: (value if value != "" else None)
            for name, value in zip(columns, values, strict=True)
        }
        row.update(
            {
                "_batch_id": run_id,
                "_source_line": position + FIRST_DATA_LINE,
                "_source_file": source_file,
                "_record_hash": record_hash(list(values)),
                "_is_rejected": bool(reasons),
                "_rejection_reasons": sorted(set(reasons)) or None,
            }
        )
        rows.append(row)
    return rows


def _replace_batch(conn: Connection, data: EntityData, run_id: str, source_dir: Path) -> LoadStats:
    contract = data.contract
    table = RAW_TABLES[contract.entity]
    deleted = conn.execute(delete(table).where(table.c._batch_id == run_id)).rowcount
    if deleted:
        logger.info("Replacing %s existing %s rows for batch %s", deleted, contract.entity, run_id)

    rows = build_raw_rows(data, run_id, contract.file_name)
    if rows:
        conn.execute(insert(table), rows)

    stats = LoadStats(
        contract.entity, len(rows), len(rows) - data.rejected_count, data.rejected_count
    )
    conn.execute(
        pg_insert(raw_load_stats)
        .values(
            run_id=run_id,
            entity=contract.entity,
            source_file=str(source_dir / contract.file_name),
            rows_received=stats.rows_received,
            rows_valid=stats.rows_valid,
            rows_rejected=stats.rows_rejected,
        )
        .on_conflict_do_update(
            index_elements=[raw_load_stats.c.run_id, raw_load_stats.c.entity],
            set_={
                "source_file": str(source_dir / contract.file_name),
                "rows_received": stats.rows_received,
                "rows_valid": stats.rows_valid,
                "rows_rejected": stats.rows_rejected,
                "loaded_at": func.now(),
            },
        )
    )
    logger.info(
        "Loaded %s: %s rows received, %s valid, %s quarantined",
        contract.entity,
        stats.rows_received,
        stats.rows_valid,
        stats.rows_rejected,
    )
    return stats


def load_batch(
    engine: Engine, run_id: str, validation: ValidationResult, source_dir: Path
) -> list[LoadStats]:
    if not validation.is_loadable:
        failures = "; ".join(
            f"{c.entity}.{c.check_name}: {c.message}" for c in validation.blocking_failures
        )
        raise LoadBlockedError(f"Batch {run_id} has blocking validation failures: {failures}")

    with engine.begin() as conn:
        conn.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": LOAD_LOCK_KEY})
        return [
            _replace_batch(conn, validation.entities[contract.entity], run_id, source_dir)
            for contract in CONTRACTS
        ]
