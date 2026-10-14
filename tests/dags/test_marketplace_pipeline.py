"""DAG structure tests. Run with Airflow installed: `make test-dag`."""

from __future__ import annotations

import importlib.util
from datetime import timedelta
from itertools import pairwise
from pathlib import Path

import pytest

from tests.support import PROJECT_ROOT

pytestmark = pytest.mark.airflow
airflow = pytest.importorskip("airflow")

from airflow.sdk import TriggerRule  # noqa: E402
from airflow.sdk.exceptions import AirflowFailException  # noqa: E402

DAG_FILE = PROJECT_ROOT / "dags" / "marketplace_pipeline.py"
MAIN_PATH = [
    "validate_source_files",
    "load_raw_tables",
    "dbt_seed",
    "dbt_run",
    "dbt_test",
    "run_quality_checks",
    "publish_pipeline_status",
]


@pytest.fixture(scope="module")
def dag_module():
    spec = importlib.util.spec_from_file_location("marketplace_pipeline", DAG_FILE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def dag(dag_module):
    return dag_module.dag


def test_dag_configuration(dag) -> None:
    assert dag.dag_id == "marketplace_pipeline"
    assert dag.catchup is False
    assert dag.max_active_runs == 1
    assert str(dag.timezone) in {"UTC", "Timezone('UTC')"}
    assert dag.params["generate_if_missing"] is True


def test_main_path_runs_in_order(dag) -> None:
    for upstream, downstream in pairwise(MAIN_PATH):
        assert upstream in dag.get_task(downstream).upstream_task_ids


def test_source_check_branches_to_generation_or_validation(dag) -> None:
    check = dag.get_task("check_source_availability")
    assert check.downstream_task_ids == {"generate_sample_data", "validate_source_files"}
    assert dag.get_task("validate_source_files").trigger_rule == (
        TriggerRule.NONE_FAILED_MIN_ONE_SUCCESS
    )


def test_failure_recorder_watches_every_stage(dag) -> None:
    recorder = dag.get_task("record_pipeline_failure")
    assert recorder.trigger_rule == TriggerRule.ONE_FAILED
    assert set(MAIN_PATH) | {"generate_sample_data"} == recorder.upstream_task_ids


def test_retry_policy(dag) -> None:
    assert dag.get_task("load_raw_tables").retries == 2
    assert dag.get_task("load_raw_tables").retry_delay == timedelta(minutes=2)
    for deterministic in ("validate_source_files", "dbt_test", "run_quality_checks"):
        assert dag.get_task(deterministic).retries == 0, deterministic


def test_cli_tasks_pass_run_id_through_environment(dag) -> None:
    load = dag.get_task("load_raw_tables")
    assert load.env["DATAFORGE_RUN_ID"] == "{{ run_id }}"
    assert load.append_env is True
    assert '--run-id "$DATAFORGE_RUN_ID"' in load.bash_command


def _branch(dag_module, tmp_path: Path, generate_if_missing: bool) -> str:
    callable_ = dag_module.dag.get_task("check_source_availability").python_callable
    dag_module.SOURCE_DIR = str(tmp_path)
    return callable_(params={"generate_if_missing": generate_if_missing})


def test_branch_validates_when_files_exist(dag_module, tmp_path: Path) -> None:
    for name in dag_module.SOURCE_FILES:
        (tmp_path / name).write_text("header\n")
    assert _branch(dag_module, tmp_path, False) == "validate_source_files"


def test_branch_generates_when_files_missing(dag_module, tmp_path: Path) -> None:
    assert _branch(dag_module, tmp_path, True) == "generate_sample_data"


def test_branch_fails_fast_without_generation(dag_module, tmp_path: Path) -> None:
    with pytest.raises(AirflowFailException, match="Missing source files"):
        _branch(dag_module, tmp_path, False)


def test_source_files_match_contracts(dag_module) -> None:
    contracts = pytest.importorskip("dataforge.contracts")
    assert set(dag_module.SOURCE_FILES) == {c.file_name for c in contracts.CONTRACTS}
