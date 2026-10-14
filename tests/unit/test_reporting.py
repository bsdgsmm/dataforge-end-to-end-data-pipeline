from __future__ import annotations

import csv
import json
from pathlib import Path

from dataforge.contracts import ORDER_STATUSES, REVENUE_ELIGIBLE_ORDER_STATUSES
from dataforge.quality.report import build_report, overall_status, safe_run_dir_name, write_report
from dataforge.transform import parse_test_results
from dataforge.validation.results import Severity
from tests.support import DBT_PROJECT_DIR

SEED = DBT_PROJECT_DIR / "seeds" / "order_statuses.csv"


def _result(stage: str, status: str, severity: str = "error") -> dict:
    return {
        "stage": stage,
        "check_name": "c",
        "entity": "e",
        "severity": severity,
        "status": status,
        "checked_records": 1,
        "failed_records": int(status == "failed"),
        "message": "a | b",
        "sample_keys": None,
    }


def test_overall_status() -> None:
    assert overall_status([_result("post_load", "passed")]) == "passed"
    assert overall_status([_result("post_load", "failed", "warning")]) == "passed_with_issues"
    assert overall_status([_result("post_load", "failed", "blocking")]) == "failed"


def test_report_is_written_as_json_and_markdown(tmp_path: Path) -> None:
    report = build_report(
        "scheduled__2026-01-01T03:00:00+00:00",
        [_result("post_load", "passed"), _result("source_validation", "failed")],
        [{"entity": "orders", "rows_received": 5, "rows_valid": 4, "rows_rejected": 1}],
    )
    assert list(report["summary"]) == ["source_validation", "post_load"]
    markdown_path = write_report(report, tmp_path)

    assert markdown_path.parent.name == "scheduled__2026-01-01T03_00_00_00_00"
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "| orders | 5 | 4 | 1 |" in markdown
    assert "a \\| b" in markdown
    saved = json.loads((markdown_path.parent / "data_quality_report.json").read_text())
    assert saved["status"] == "passed_with_issues"


def test_safe_run_dir_name_strips_path_characters() -> None:
    assert "/" not in safe_run_dir_name("../../etc/passwd")


def test_dbt_results_are_mapped_to_checks(tmp_path: Path) -> None:
    (tmp_path / "run_results.json").write_text(
        json.dumps(
            {
                "results": [
                    {
                        "unique_id": "test.marketplace_analytics.unique_fct_orders_order_id.abc",
                        "status": "pass",
                        "failures": 0,
                        "message": None,
                    },
                    {
                        "unique_id": "test.marketplace_analytics.assert_revenue_orders_fully_paid",
                        "status": "warn",
                        "failures": 3,
                        "message": "Got 3 results",
                    },
                    {"unique_id": "model.marketplace_analytics.fct_orders", "status": "success"},
                ]
            }
        )
    )
    (tmp_path / "manifest.json").write_text(
        json.dumps(
            {
                "nodes": {
                    "test.marketplace_analytics.assert_revenue_orders_fully_paid": {
                        "config": {"severity": "WARN"}
                    },
                }
            }
        )
    )
    checks = parse_test_results(tmp_path)
    assert [c.check_name for c in checks] == [
        "unique_fct_orders_order_id",
        "assert_revenue_orders_fully_paid",
    ]
    assert checks[0].passed and checks[0].severity is Severity.BLOCKING
    assert checks[1].failed_records == 3 and checks[1].severity is Severity.WARNING


def test_order_status_seed_matches_python_contract() -> None:
    with SEED.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert {row["order_status"] for row in rows} == ORDER_STATUSES
    assert {
        row["order_status"] for row in rows if row["is_revenue_eligible"] == "true"
    } == REVENUE_ELIGIBLE_ORDER_STATUSES
