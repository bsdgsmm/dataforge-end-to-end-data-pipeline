"""Command-line entry point. Every pipeline stage is a subcommand.

Airflow tasks and Makefile targets call these commands, so the same code path
runs locally, in CI, and under orchestration.
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.engine import Engine

from dataforge.config import (
    ConfigurationError,
    load_path_settings,
    load_quality_settings,
)
from dataforge.contracts import CONTRACTS
from dataforge.database.engine import build_engine
from dataforge.database.schema import ensure_schema
from dataforge.generation.synthetic import (
    GenerationParams,
    generate_dataset,
    source_files_present,
    write_dataset,
)
from dataforge.ingestion.loader import load_batch
from dataforge.logging_config import configure_logging
from dataforge.quality.post_load import run_post_load_checks
from dataforge.quality.report import build_report, write_report
from dataforge.quality.store import fetch_check_results, fetch_load_stats, save_check_results
from dataforge.runs import finish_run, stage_statuses, track_stage
from dataforge.transform import parse_test_results, run_dbt, target_dir
from dataforge.validation.results import Severity, ValidationResult
from dataforge.validation.validator import validate_source_dir

logger = logging.getLogger("dataforge")

EXIT_FAILURE = 1
EXIT_CONFIGURATION = 2
DBT_COMMANDS = ("parse", "compile", "seed", "run", "test", "build", "docs")


def _default_run_id() -> str:
    return f"manual__{datetime.now(UTC):%Y%m%dT%H%M%SZ}"


def _engine() -> Engine:
    engine = build_engine()
    ensure_schema(engine)
    return engine


def cmd_generate_data(args: argparse.Namespace) -> int:
    output_dir = args.output_dir or load_path_settings().source_dir
    if args.skip_if_present and source_files_present(output_dir):
        logger.info("Source files already present in %s; skipping generation", output_dir)
        return 0
    params = GenerationParams(
        seed=args.seed,
        customers=args.customers,
        products=args.products,
        inject_defects=args.inject_defects,
    )
    logger.info("Generating synthetic dataset with %s", params)
    write_dataset(generate_dataset(params), output_dir)
    return 0


def cmd_check_sources(args: argparse.Namespace) -> int:
    source_dir = load_path_settings().source_dir
    missing = []
    for contract in CONTRACTS:
        path = source_dir / contract.file_name
        if path.is_file() and path.stat().st_size > 0:
            logger.info("Found %s (%s bytes)", path, path.stat().st_size)
        else:
            missing.append(contract.file_name)
    if missing:
        logger.error(
            "Missing or empty source files in %s: %s. Run `make generate-data` or "
            "deliver the extracts before running the pipeline.",
            source_dir,
            ", ".join(missing),
        )
        return EXIT_FAILURE
    return 0


def cmd_init_db(args: argparse.Namespace) -> int:
    _engine()
    logger.info("Raw and audit schemas are in place")
    return 0


def _validate(engine: Engine, run_id: str) -> ValidationResult:
    paths = load_path_settings()
    result = validate_source_dir(paths.source_dir, load_quality_settings().max_rejected_ratio)
    save_check_results(engine, run_id, "source_validation", result.checks)
    rejected = {name: data.rejected_count for name, data in result.entities.items()}
    logger.info(
        "Validation finished: %s checks, %s failed, quarantined rows per entity: %s",
        len(result.checks),
        len(result.failed_checks()),
        rejected,
    )
    return result


def cmd_validate(args: argparse.Namespace) -> int:
    engine = _engine()
    with track_stage(engine, args.run_id, "validate_source"):
        result = _validate(engine, args.run_id)
        if not result.is_loadable:
            details = "; ".join(
                f"{c.entity}.{c.check_name}: {c.message}" for c in result.blocking_failures
            )
            raise RuntimeError(f"Blocking validation failures: {details}")
    return 0


def cmd_load(args: argparse.Namespace) -> int:
    engine = _engine()
    with track_stage(engine, args.run_id, "load_raw"):
        result = _validate(engine, args.run_id)
        load_batch(engine, args.run_id, result, load_path_settings().source_dir)
    return 0


def cmd_dbt(args: argparse.Namespace) -> int:
    project_dir = load_path_settings().dbt_project_dir
    dbt_args = [args.command, *args.dbt_args]
    if args.run_id is None:
        run_dbt(project_dir, dbt_args)
        return 0

    engine = _engine()
    with track_stage(engine, args.run_id, f"dbt_{args.command}"):
        try:
            run_dbt(project_dir, dbt_args)
        finally:
            if args.command in {"test", "build"}:
                results_path = target_dir(project_dir)
                if (results_path / "run_results.json").exists():
                    save_check_results(
                        engine, args.run_id, "dbt_test", parse_test_results(results_path)
                    )
    return 0


def _write_report(engine: Engine, run_id: str) -> dict:
    report = build_report(
        run_id, fetch_check_results(engine, run_id), fetch_load_stats(engine, run_id)
    )
    path = write_report(report, load_path_settings().report_dir)
    logger.info("Data quality report (%s) written to %s", report["status"], path)
    return report


def cmd_quality_check(args: argparse.Namespace) -> int:
    engine = _engine()
    with track_stage(engine, args.run_id, "quality_checks"):
        checks = run_post_load_checks(engine, args.run_id)
        save_check_results(engine, args.run_id, "post_load", checks)
        _write_report(engine, args.run_id)
        blocking = [c for c in checks if c.severity is Severity.BLOCKING and not c.passed]
        for check in checks:
            if not check.passed:
                logger.warning(
                    "[%s] %s on %s: %s",
                    check.severity,
                    check.check_name,
                    check.entity,
                    check.message,
                )
        if blocking:
            raise RuntimeError(
                f"{len(blocking)} blocking post-load checks failed: "
                + ", ".join(f"{c.entity}.{c.check_name}" for c in blocking)
            )
    return 0


def cmd_finalize(args: argparse.Namespace) -> int:
    engine = _engine()
    if args.status == "failed":
        finish_run(engine, args.run_id, "failed")
        _write_report(engine, args.run_id)
        logger.error(
            "Run %s marked as failed. Query audit.pipeline_stage_runs for details.", args.run_id
        )
        return 0

    statuses = stage_statuses(engine, args.run_id)
    unfinished = {stage: status for stage, status in statuses.items() if status != "succeeded"}
    if unfinished or not statuses:
        finish_run(
            engine,
            args.run_id,
            "failed",
            f"Stages not succeeded: {unfinished or 'no stages recorded'}",
        )
        logger.error("Run %s cannot be finalized; stage states: %s", args.run_id, statuses)
        return EXIT_FAILURE

    report = _write_report(engine, args.run_id)
    finish_run(engine, args.run_id, "succeeded")
    for stage, summary in report["summary"].items():
        logger.info(
            "%s: %s checks, %s passed, %s failed",
            stage,
            summary["checks"],
            summary["passed"],
            summary["failed"],
        )
    for stats in report["load_stats"]:
        logger.info(
            "%s: %s received, %s valid, %s quarantined",
            stats["entity"],
            stats["rows_received"],
            stats["rows_valid"],
            stats["rows_rejected"],
        )
    logger.info("Run %s succeeded with data quality status %s", args.run_id, report["status"])
    return 0


def cmd_run_pipeline(args: argparse.Namespace) -> int:
    """Run every stage in order without Airflow."""
    steps: list[tuple[Callable[[argparse.Namespace], int], argparse.Namespace]] = [
        (cmd_check_sources, args),
        (cmd_validate, args),
        (cmd_load, args),
        (cmd_dbt, argparse.Namespace(command="seed", dbt_args=[], run_id=args.run_id)),
        (cmd_dbt, argparse.Namespace(command="run", dbt_args=[], run_id=args.run_id)),
        (cmd_dbt, argparse.Namespace(command="test", dbt_args=[], run_id=args.run_id)),
        (cmd_quality_check, args),
    ]
    for step, step_args in steps:
        try:
            exit_code = step(step_args)
        except Exception:
            cmd_finalize(argparse.Namespace(run_id=args.run_id, status="failed"))
            raise
        if exit_code != 0:
            cmd_finalize(argparse.Namespace(run_id=args.run_id, status="failed"))
            return exit_code
    return cmd_finalize(argparse.Namespace(run_id=args.run_id, status="succeeded"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dataforge", description=__doc__)
    parser.add_argument("--log-level", default=None, help="Overrides DATAFORGE_LOG_LEVEL.")
    sub = parser.add_subparsers(dest="subcommand", required=True)

    generate = sub.add_parser("generate-data", help="Write deterministic synthetic CSV files.")
    generate.add_argument("--output-dir", type=Path, default=None)
    generate.add_argument("--seed", type=int, default=42)
    generate.add_argument("--customers", type=int, default=1500)
    generate.add_argument("--products", type=int, default=120)
    generate.add_argument(
        "--inject-defects",
        action="store_true",
        help="Append known-invalid records to exercise quality checks.",
    )
    generate.add_argument("--skip-if-present", action="store_true")
    generate.set_defaults(func=cmd_generate_data)

    sub.add_parser("check-sources", help="Verify that all source files exist.").set_defaults(
        func=cmd_check_sources
    )
    sub.add_parser("init-db", help="Create raw and audit tables.").set_defaults(func=cmd_init_db)

    def with_run_id(name: str, help_text: str, func: Callable, required: bool = True):
        command = sub.add_parser(name, help=help_text)
        if required:
            command.add_argument("--run-id", required=True)
        else:
            command.add_argument("--run-id", default=_default_run_id())
        command.set_defaults(func=func)
        return command

    with_run_id("validate", "Validate source files and record results.", cmd_validate)
    with_run_id("load", "Validate and load source files into raw tables.", cmd_load)
    with_run_id("quality-check", "Run post-load checks and write the report.", cmd_quality_check)
    finalize = with_run_id("finalize", "Record the final run status.", cmd_finalize)
    finalize.add_argument("--status", choices=["succeeded", "failed"], default="succeeded")
    with_run_id(
        "run-pipeline", "Run all stages locally without Airflow.", cmd_run_pipeline, required=False
    )

    dbt = sub.add_parser(
        "dbt",
        help="Run a dbt command against the project. Pass extra dbt arguments after `--`, "
        "e.g. `dataforge dbt run -- --select marts`.",
    )
    dbt.add_argument("command", choices=DBT_COMMANDS)
    dbt.add_argument("--run-id", default=None, help="Track the command as a pipeline stage.")
    dbt.set_defaults(func=cmd_dbt)
    return parser


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    passthrough: list[str] = []
    if "--" in argv:
        separator = argv.index("--")
        argv, passthrough = argv[:separator], argv[separator + 1 :]
    args = build_parser().parse_args(argv)
    args.dbt_args = passthrough
    configure_logging(args.log_level)
    try:
        return args.func(args)
    except ConfigurationError as exc:
        logger.error("Configuration error: %s", exc)
        return EXIT_CONFIGURATION
    except Exception:
        logger.exception("Command %s failed", args.subcommand)
        return EXIT_FAILURE
