"""Data-quality report rendered from audit tables for a single run."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

STAGE_ORDER = ("source_validation", "dbt_test", "post_load")


def overall_status(results: list[dict[str, Any]]) -> str:
    failed = [r for r in results if r["status"] == "failed"]
    if any(r["severity"] == "blocking" for r in failed):
        return "failed"
    if failed:
        return "passed_with_issues"
    return "passed"


def build_report(
    run_id: str, results: list[dict[str, Any]], load_stats: list[dict[str, Any]]
) -> dict[str, Any]:
    by_stage: dict[str, list[dict[str, Any]]] = {}
    for result in results:
        by_stage.setdefault(result["stage"], []).append(result)
    summary = {
        stage: {
            "checks": len(rows),
            "passed": sum(1 for r in rows if r["status"] == "passed"),
            "failed": sum(1 for r in rows if r["status"] == "failed"),
        }
        for stage, rows in sorted(
            by_stage.items(),
            key=lambda item: STAGE_ORDER.index(item[0]) if item[0] in STAGE_ORDER else 99,
        )
    }
    return {
        "run_id": run_id,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "status": overall_status(results),
        "summary": summary,
        "load_stats": load_stats,
        "checks": results,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# Data Quality Report — `{report['run_id']}`",
        "",
        f"- Generated at: {report['generated_at']}",
        f"- Overall status: **{report['status']}**",
        "",
        "## Records loaded",
        "",
        "| Entity | Received | Valid | Quarantined |",
        "| --- | ---: | ---: | ---: |",
    ]
    lines += [
        f"| {s['entity']} | {s['rows_received']} | {s['rows_valid']} | {s['rows_rejected']} |"
        for s in report["load_stats"]
    ]
    lines += [
        "",
        "## Summary by stage",
        "",
        "| Stage | Checks | Passed | Failed |",
        "| --- | ---: | ---: | ---: |",
    ]
    lines += [
        f"| {stage} | {s['checks']} | {s['passed']} | {s['failed']} |"
        for stage, s in report["summary"].items()
    ]
    failed = [c for c in report["checks"] if c["status"] == "failed"]
    lines += ["", "## Failed checks", ""]
    if failed:
        lines += [
            "| Stage | Entity | Check | Severity | Failed records | Details |",
            "| --- | --- | --- | --- | ---: | --- |",
        ]
        for c in failed:
            message = (c.get("message") or "").replace("|", "\\|")
            lines.append(
                f"| {c['stage']} | {c['entity']} | `{c['check_name']}` | {c['severity']} "
                f"| {c['failed_records']} | {message} |"
            )
    else:
        lines.append("All checks passed.")
    return "\n".join(lines) + "\n"


def safe_run_dir_name(run_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", run_id)


def write_report(report: dict[str, Any], report_dir: Path) -> Path:
    target = report_dir / safe_run_dir_name(report["run_id"])
    target.mkdir(parents=True, exist_ok=True)
    (target / "data_quality_report.json").write_text(
        json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8"
    )
    markdown_path = target / "data_quality_report.md"
    markdown_path.write_text(render_markdown(report), encoding="utf-8")
    return markdown_path
