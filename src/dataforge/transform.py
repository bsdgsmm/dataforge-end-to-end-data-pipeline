"""Thin wrapper around the dbt CLI so dbt stages are tracked like other stages."""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path

from dataforge.validation.results import CheckResult, Severity

logger = logging.getLogger(__name__)


class DbtCommandError(RuntimeError):
    pass


def dbt_executable() -> str:
    sibling = Path(sys.executable).with_name("dbt")
    if sibling.exists():
        return str(sibling)
    found = shutil.which("dbt")
    if found is None:
        raise DbtCommandError("dbt executable not found. Install with: pip install -e '.[dbt]'")
    return found


def target_dir(project_dir: Path) -> Path:
    configured = os.environ.get("DBT_TARGET_PATH")
    return Path(configured) if configured else project_dir / "target"


def run_dbt(project_dir: Path, args: list[str]) -> None:
    command = [
        dbt_executable(),
        *args,
        "--project-dir",
        str(project_dir),
        "--profiles-dir",
        str(project_dir),
    ]
    logger.info("Running: %s", " ".join(command))
    completed = subprocess.run(command, check=False)  # noqa: S603 - fixed argv, no shell
    if completed.returncode != 0:
        raise DbtCommandError(
            f"dbt {args[0]} exited with code {completed.returncode}. "
            "See the dbt output above for the failing model or test."
        )


def parse_test_results(target: Path) -> list[CheckResult]:
    """Convert dbt test results into CheckResult records.

    Severity comes from manifest.json because run_results.json omits it.
    """
    run_results = json.loads((target / "run_results.json").read_text(encoding="utf-8"))
    manifest_path = target / "manifest.json"
    nodes = (
        json.loads(manifest_path.read_text(encoding="utf-8")).get("nodes", {})
        if manifest_path.exists()
        else {}
    )
    checks = []
    for result in run_results.get("results", []):
        unique_id: str = result["unique_id"]
        if not unique_id.startswith("test."):
            continue
        status = result["status"]
        configured = nodes.get(unique_id, {}).get("config", {}).get("severity", "error")
        failures = result.get("failures") or 0
        if status == "error":
            failures = max(failures, 1)
        checks.append(
            CheckResult(
                check_name=unique_id.split(".")[2],
                entity="dbt",
                severity=Severity.WARNING if configured.lower() == "warn" else Severity.BLOCKING,
                checked_records=None,
                failed_records=0 if status == "pass" else int(failures),
                message=(result.get("message") or "") if status != "pass" else "",
            )
        )
    return checks
