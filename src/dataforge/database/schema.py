"""Warehouse tables owned by the Python pipeline (raw landing and audit).

Staging, intermediate, and mart schemas are owned by dbt.
"""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    PrimaryKeyConstraint,
    Table,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.engine import Engine
from sqlalchemy.schema import CreateSchema

from dataforge.contracts import CONTRACTS, SourceContract

RAW_SCHEMA = "raw"
AUDIT_SCHEMA = "audit"

metadata = MetaData()

pipeline_runs = Table(
    "pipeline_runs",
    metadata,
    Column("run_id", Text, primary_key=True),
    Column("status", Text, nullable=False),
    Column("current_stage", Text),
    Column("started_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("finished_at", DateTime(timezone=True)),
    Column("error_message", Text),
    schema=AUDIT_SCHEMA,
)

pipeline_stage_runs = Table(
    "pipeline_stage_runs",
    metadata,
    Column("run_id", Text, ForeignKey(pipeline_runs.c.run_id), nullable=False),
    Column("stage", Text, nullable=False),
    Column("status", Text, nullable=False),
    Column("attempt", Integer, nullable=False),
    Column("started_at", DateTime(timezone=True), nullable=False),
    Column("finished_at", DateTime(timezone=True)),
    Column("error_message", Text),
    PrimaryKeyConstraint("run_id", "stage"),
    schema=AUDIT_SCHEMA,
)

raw_load_stats = Table(
    "raw_load_stats",
    metadata,
    Column("run_id", Text, ForeignKey(pipeline_runs.c.run_id), nullable=False),
    Column("entity", Text, nullable=False),
    Column("source_file", Text, nullable=False),
    Column("rows_received", Integer, nullable=False),
    Column("rows_valid", Integer, nullable=False),
    Column("rows_rejected", Integer, nullable=False),
    Column("loaded_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    PrimaryKeyConstraint("run_id", "entity"),
    schema=AUDIT_SCHEMA,
)

data_quality_results = Table(
    "data_quality_results",
    metadata,
    Column("result_id", BigInteger, primary_key=True, autoincrement=True),
    Column("run_id", Text, ForeignKey(pipeline_runs.c.run_id), nullable=False),
    Column("stage", Text, nullable=False),
    Column("check_name", Text, nullable=False),
    Column("entity", Text, nullable=False),
    Column("severity", Text, nullable=False),
    Column("status", Text, nullable=False),
    Column("checked_records", Integer),
    Column("failed_records", Integer, nullable=False),
    Column("message", Text),
    Column("sample_keys", ARRAY(Text)),
    Column("checked_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Index("ix_data_quality_results_run_stage", "run_id", "stage"),
    schema=AUDIT_SCHEMA,
)


def _raw_table(contract: SourceContract) -> Table:
    return Table(
        contract.entity,
        metadata,
        Column("_batch_id", Text, ForeignKey(pipeline_runs.c.run_id), nullable=False),
        Column("_source_line", Integer, nullable=False),
        *(Column(name, Text) for name in contract.column_names),
        Column("_source_file", Text, nullable=False),
        Column("_record_hash", Text, nullable=False),
        Column("_is_rejected", Boolean, nullable=False),
        Column("_rejection_reasons", ARRAY(Text)),
        Column("_loaded_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
        PrimaryKeyConstraint("_batch_id", "_source_line"),
        Index(f"ix_raw_{contract.entity}_{contract.primary_key}", contract.primary_key),
        schema=RAW_SCHEMA,
    )


RAW_TABLES: dict[str, Table] = {contract.entity: _raw_table(contract) for contract in CONTRACTS}


def ensure_schema(engine: Engine) -> None:
    """Create schemas and tables if they do not exist. Safe to call repeatedly."""
    with engine.begin() as conn:
        for schema in (RAW_SCHEMA, AUDIT_SCHEMA):
            conn.execute(CreateSchema(schema, if_not_exists=True))
        metadata.create_all(conn, checkfirst=True)
