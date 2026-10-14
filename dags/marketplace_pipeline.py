"""
### Marketplace pipeline

Daily batch pipeline for the synthetic marketplace dataset:
source check → (optional sample generation) → validation → raw load →
dbt seed/run/test → post-load quality checks → final run status.

* **Schedule:** 03:00 UTC every day. All timestamps and date boundaries are UTC.
* **Batch identity:** the Airflow `run_id` is used as the batch id in `raw.*` and `audit.*`.
  Re-running a task or the whole DAG run replaces that batch instead of duplicating it.
* **Processing logic** lives in the `dataforge` package and runs through its CLI in an
  isolated virtualenv, so parsing this file stays lightweight.
"""

from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path

import pendulum
from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import DAG, Param, TriggerRule, task
from airflow.sdk.exceptions import AirflowFailException

DATAFORGE_CLI = os.environ.get("DATAFORGE_CLI", "dataforge")
SOURCE_DIR = os.environ.get("DATAFORGE_SOURCE_DIR", "data/source")
SOURCE_FILES = ("customers.csv", "products.csv", "orders.csv", "order_items.csv", "payments.csv")

TASK_ENV = {"DATAFORGE_RUN_ID": "{{ run_id }}", "DATAFORGE_CLI": DATAFORGE_CLI}

default_args = {
    "owner": "data-platform",
    "retries": 2,
    "retry_delay": timedelta(minutes=2),
    "retry_exponential_backoff": True,
    "max_retry_delay": timedelta(minutes=10),
    "execution_timeout": timedelta(minutes=30),
}


def cli_task(task_id: str, arguments: str, **kwargs) -> BashOperator:
    return BashOperator(
        task_id=task_id,
        bash_command=f'"$DATAFORGE_CLI" {arguments}',
        env=TASK_ENV,
        append_env=True,
        **kwargs,
    )


with DAG(
    dag_id="marketplace_pipeline",
    description="Ingest, validate, transform, and quality-check marketplace data.",
    schedule="0 3 * * *",
    start_date=pendulum.datetime(2026, 1, 1, tz="UTC"),
    catchup=False,
    max_active_runs=1,
    default_args=default_args,
    params={
        "generate_if_missing": Param(
            True,
            type="boolean",
            description="Generate the synthetic sample dataset when source files are missing.",
        ),
    },
    tags=["dataforge", "marketplace", "dbt"],
    doc_md=__doc__,
) as dag:

    @task.branch(retries=0)
    def check_source_availability(**context) -> str:
        source_dir = Path(SOURCE_DIR)
        missing = [name for name in SOURCE_FILES if not (source_dir / name).is_file()]
        if not missing:
            return "validate_source_files"
        if context["params"]["generate_if_missing"]:
            return "generate_sample_data"
        raise AirflowFailException(
            f"Missing source files in {source_dir}: {', '.join(missing)}. Deliver the extracts "
            "or trigger the DAG with generate_if_missing=true."
        )

    generate_sample_data = cli_task("generate_sample_data", "generate-data --skip-if-present")

    validate_source_files = cli_task(
        "validate_source_files",
        'validate --run-id "$DATAFORGE_RUN_ID"',
        retries=0,
        trigger_rule=TriggerRule.NONE_FAILED_MIN_ONE_SUCCESS,
    )
    load_raw_tables = cli_task("load_raw_tables", 'load --run-id "$DATAFORGE_RUN_ID"')
    dbt_seed = cli_task("dbt_seed", 'dbt seed --run-id "$DATAFORGE_RUN_ID"')
    dbt_run = cli_task("dbt_run", 'dbt run --run-id "$DATAFORGE_RUN_ID"')
    dbt_test = cli_task("dbt_test", 'dbt test --run-id "$DATAFORGE_RUN_ID"', retries=0)
    run_quality_checks = cli_task(
        "run_quality_checks", 'quality-check --run-id "$DATAFORGE_RUN_ID"', retries=0
    )
    publish_pipeline_status = cli_task(
        "publish_pipeline_status", 'finalize --run-id "$DATAFORGE_RUN_ID" --status succeeded'
    )
    record_pipeline_failure = cli_task(
        "record_pipeline_failure",
        'finalize --run-id "$DATAFORGE_RUN_ID" --status failed',
        trigger_rule=TriggerRule.ONE_FAILED,
    )

    source_check = check_source_availability()
    source_check >> [generate_sample_data, validate_source_files]
    generate_sample_data >> validate_source_files
    (
        validate_source_files
        >> load_raw_tables
        >> dbt_seed
        >> dbt_run
        >> dbt_test
        >> run_quality_checks
        >> publish_pipeline_status
    )
    # The branch task is deliberately not upstream: branching skips every direct downstream
    # task it does not select. A failed source check still reaches this task as
    # upstream_failed through validate_source_files.
    [
        generate_sample_data,
        validate_source_files,
        load_raw_tables,
        dbt_seed,
        dbt_run,
        dbt_test,
        run_quality_checks,
        publish_pipeline_status,
    ] >> record_pipeline_failure
