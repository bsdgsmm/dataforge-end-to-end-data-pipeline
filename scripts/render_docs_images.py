"""Render documentation images into docs/images.

The architecture diagram is drawn from the project's layer definitions. The charts are
queried from the warehouse, so run the pipeline (and `make demo-defects` for the
quarantine chart) before running this script.
"""

from __future__ import annotations

import logging
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
from sqlalchemy import text

from dataforge.database.engine import build_engine
from dataforge.logging_config import configure_logging

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).parents[1] / "docs" / "images"
DEFECTS_RUN_ID = "manual__defects_demo"

SURFACE = "#fcfcfb"
TEXT_PRIMARY = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
GRID = "#e4e3df"
SERIES_BLUE = "#2a78d6"
CONTEXT_GRAY = "#b9b8b2"
LAYER_FILL = "#eef4fc"
LAYER_EDGE = "#2a78d6"
SUPPORT_FILL = "#f3f2ee"
SUPPORT_EDGE = "#8a8984"


def _style_axes(ax: plt.Axes) -> None:
    ax.set_facecolor(SURFACE)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=TEXT_SECONDARY, labelsize=9, length=0)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def _box(
    ax: plt.Axes,
    x: float,
    y: float,
    w: float,
    h: float,
    title: str,
    body: str,
    fill: str = LAYER_FILL,
    edge: str = LAYER_EDGE,
) -> None:
    ax.add_patch(
        FancyBboxPatch(
            (x, y),
            w,
            h,
            boxstyle="round,pad=0.02,rounding_size=0.08",
            facecolor=fill,
            edgecolor=edge,
            linewidth=1.2,
        )
    )
    ax.text(
        x + w / 2,
        y + h - 0.22,
        title,
        ha="center",
        va="top",
        fontsize=10.5,
        fontweight="bold",
        color=TEXT_PRIMARY,
    )
    ax.text(
        x + w / 2,
        y + h - 0.62,
        body,
        ha="center",
        va="top",
        fontsize=7.8,
        color=TEXT_SECONDARY,
        linespacing=1.45,
    )


def _arrow(
    ax: plt.Axes,
    start: tuple[float, float],
    end: tuple[float, float],
    style: str = "-|>",
    dashed: bool = False,
) -> None:
    ax.add_patch(
        FancyArrowPatch(
            start,
            end,
            arrowstyle=style,
            mutation_scale=12,
            color=SUPPORT_EDGE,
            linewidth=1.2,
            linestyle="--" if dashed else "-",
        )
    )


def render_architecture() -> Path:
    fig, ax = plt.subplots(figsize=(14, 6.6), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 6.6)
    ax.axis("off")

    ax.text(
        0.2,
        6.35,
        "DataForge — pipeline architecture",
        fontsize=14,
        fontweight="bold",
        color=TEXT_PRIMARY,
        va="top",
    )

    _box(
        ax,
        0.2,
        0.35,
        13.6,
        1.0,
        "Orchestration — Apache Airflow (marketplace_pipeline DAG)",
        "check sources → generate (if missing) → validate → load raw → dbt seed / run / test"
        " → quality checks → publish status  ·  retries, run_id = batch id",
        fill=SUPPORT_FILL,
        edge=SUPPORT_EDGE,
    )

    layers = [
        (
            "1  Source",
            "CSV extracts\ncustomers, products,\norders, order_items,\npayments\n"
            "(synthetic, seed 42)",
        ),
        (
            "2  Ingestion",
            "dataforge CLI\ncontract validation\nquarantine flags\natomic batch\nreplacement",
        ),
        ("3  Raw", "PostgreSQL: raw.*\ntext, as received\n_batch_id,\n_source_line,\n_is_rejected"),
        ("4  Staging", "dbt views\nlatest valid version\nper business key\ntypes, trims, casing"),
        ("5  Intermediate", "dbt views\npriced lines\npayments per order\nenriched orders"),
        (
            "6  Marts",
            "dbt tables + contracts\ndim_customers\ndim_products\nfct_orders\n"
            "fct_order_items\n+ 4 analytical marts",
        ),
        ("7  Delivery", "sql/analysis\nKPI queries\nBI / notebooks\nsql/diagnostics"),
    ]
    width, gap, top = 1.78, 0.17, 4.1
    for index, (title, body) in enumerate(layers):
        x = 0.2 + index * (width + gap)
        _box(ax, x, top - 2.0, width, 2.25, title, body)
        if index:
            _arrow(ax, (x - gap + 0.01, top - 0.85), (x - 0.01, top - 0.85))

    _box(
        ax,
        0.2,
        4.75,
        11.55,
        1.0,
        "Quality layer — audit schema",
        "pipeline_runs · pipeline_stage_runs · raw_load_stats · data_quality_results\n"
        "source validation + dbt tests + post-load reconciliation → report (JSON / Markdown)",
        fill=SUPPORT_FILL,
        edge=SUPPORT_EDGE,
    )
    for x in (2.95, 6.85, 10.75):
        _arrow(ax, (x, top + 0.18), (x, 4.75), dashed=True)
    for x in (2.95, 6.85, 10.75):
        _arrow(ax, (x, 1.37), (x, top - 2.02), style="-", dashed=True)

    ax.text(
        13.8,
        5.25,
        "Docker Compose:\nPostgreSQL 16\nAirflow 3\n(LocalExecutor)",
        ha="right",
        va="center",
        fontsize=8.5,
        color=TEXT_SECONDARY,
    )
    path = OUTPUT_DIR / "data-pipeline-architecture.png"
    fig.savefig(path, bbox_inches="tight", facecolor=SURFACE)
    plt.close(fig)
    return path


def render_daily_revenue(engine) -> Path:
    with engine.connect() as conn:
        rows = conn.execute(
            text("""
            SELECT
                revenue_date,
                net_revenue_amount,
                avg(net_revenue_amount) OVER (
                    ORDER BY revenue_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
                ) AS rolling_avg
            FROM marts.mart_daily_revenue
            ORDER BY revenue_date
        """)
        ).all()
    if not rows:
        raise RuntimeError("marts.mart_daily_revenue is empty; run the pipeline first.")
    dates = [r.revenue_date for r in rows]
    daily = [float(r.net_revenue_amount) for r in rows]
    rolling = [float(r.rolling_avg) for r in rows]

    fig, ax = plt.subplots(figsize=(12, 4.6), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    _style_axes(ax)
    ax.plot(dates, daily, color=CONTEXT_GRAY, linewidth=1, label="Daily net revenue")
    ax.plot(dates, rolling, color=SERIES_BLUE, linewidth=2, label="7-day rolling average")
    ax.yaxis.set_major_formatter(matplotlib.ticker.StrMethodFormatter("${x:,.0f}"))
    ax.set_title(
        "Daily net revenue, revenue-eligible orders (synthetic data, UTC)",
        loc="left",
        fontsize=12,
        color=TEXT_PRIMARY,
        pad=12,
    )
    ax.text(dates[-1], rolling[-1], "  7-day avg", color=TEXT_PRIMARY, fontsize=9, va="center")
    ax.legend(frameon=False, loc="upper left", fontsize=9, labelcolor=TEXT_SECONDARY)
    ax.margins(x=0.01)
    fig.text(
        0.01,
        0.01,
        "Source: marts.mart_daily_revenue · net revenue = gross sales - discounts - refunds",
        fontsize=8,
        color=TEXT_SECONDARY,
    )
    path = OUTPUT_DIR / "daily-net-revenue.png"
    fig.savefig(path, bbox_inches="tight", facecolor=SURFACE)
    plt.close(fig)
    return path


def render_quarantine(engine) -> Path:
    union = " UNION ALL ".join(
        f"SELECT '{entity}' AS entity, split_part(reason, ':', 1) AS reason "  # noqa: S608
        f"FROM raw.{entity}, unnest(_rejection_reasons) AS reason "
        "WHERE _batch_id = :run_id AND _is_rejected"
        for entity in ("customers", "products", "orders", "order_items", "payments")
    )
    with engine.connect() as conn:
        totals = dict(
            conn.execute(
                text(
                    "SELECT entity, rows_rejected FROM audit.raw_load_stats WHERE run_id = :run_id"
                ),
                {"run_id": DEFECTS_RUN_ID},
            ).all()
        )
        reasons = conn.execute(
            text(
                f"SELECT reason, count(*) AS n FROM ({union}) r GROUP BY reason "  # noqa: S608
                "ORDER BY n DESC"
            ),
            {"run_id": DEFECTS_RUN_ID},
        ).all()
    if not totals:
        raise RuntimeError(f"No load stats for {DEFECTS_RUN_ID}; run `make demo-defects` first.")

    fig, (left, right) = plt.subplots(
        1, 2, figsize=(12, 4.2), dpi=150, gridspec_kw={"width_ratios": [1, 1.25]}
    )
    fig.patch.set_facecolor(SURFACE)
    for ax, labels, values, title in (
        (left, list(totals), list(totals.values()), "Quarantined rows by entity"),
        (
            right,
            [r.reason for r in reasons],
            [r.n for r in reasons],
            "Rejection reasons (a row can have several)",
        ),
    ):
        _style_axes(ax)
        ax.grid(axis="y", visible=False)
        ax.grid(axis="x", color=GRID, linewidth=0.8)
        order = sorted(range(len(values)), key=lambda i: values[i])
        ax.barh(
            [labels[i] for i in order], [values[i] for i in order], color=SERIES_BLUE, height=0.6
        )
        for position, i in enumerate(order):
            ax.text(
                values[i], position, f"  {values[i]}", va="center", fontsize=9, color=TEXT_PRIMARY
            )
        ax.set_title(title, loc="left", fontsize=11, color=TEXT_PRIMARY, pad=10)
        ax.spines["bottom"].set_visible(False)
        ax.set_xticks([])
    fig.suptitle(
        f"Source validation on the defect-injected dataset (run {DEFECTS_RUN_ID})",
        x=0.01,
        ha="left",
        fontsize=12,
        color=TEXT_PRIMARY,
    )
    fig.text(
        0.01,
        -0.02,
        "Rows are kept in raw.* with _is_rejected = true and excluded "
        "from staging. Orphans cascade from quarantined parents.",
        fontsize=8,
        color=TEXT_SECONDARY,
    )
    fig.tight_layout()
    path = OUTPUT_DIR / "data-quality-quarantine.png"
    fig.savefig(path, bbox_inches="tight", facecolor=SURFACE)
    plt.close(fig)
    return path


def main() -> None:
    configure_logging()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    engine = build_engine()
    for path in (render_architecture(), render_daily_revenue(engine), render_quarantine(engine)):
        logger.info("Wrote %s", path)


if __name__ == "__main__":
    main()
