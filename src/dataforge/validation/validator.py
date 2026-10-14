"""Source-file validation.

Validation never drops data. Each row is either valid or carries a list of
rejection reasons; the loader persists both so rejected rows remain queryable.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pandas as pd

from dataforge.contracts import (
    CONTRACTS,
    REVENUE_ELIGIBLE_ORDER_STATUSES,
    Column,
    ColumnType,
    SourceContract,
)
from dataforge.validation.parsers import PARSERS, is_valid_email, parse_decimal
from dataforge.validation.results import CheckResult, EntityData, Severity, ValidationResult

logger = logging.getLogger(__name__)

SAMPLE_SIZE = 5
RECONCILIATION_TOLERANCE = Decimal("0.01")


def _sample(keys: pd.Series | list[str]) -> tuple[str, ...]:
    return tuple(str(key) for key in list(keys)[:SAMPLE_SIZE])


def read_source_file(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, dtype=str, keep_default_na=False, na_filter=False)
    frame.columns = [str(column).strip() for column in frame.columns]
    return frame.reset_index(drop=True)


def _check_file(
    contract: SourceContract, source_dir: Path
) -> tuple[pd.DataFrame | None, list[CheckResult]]:
    path = source_dir / contract.file_name
    if not path.is_file():
        return None, [
            CheckResult(
                "file_present",
                contract.entity,
                Severity.BLOCKING,
                1,
                1,
                f"Expected source file {path} does not exist.",
            )
        ]
    try:
        frame = read_source_file(path)
    except (pd.errors.ParserError, pd.errors.EmptyDataError, UnicodeDecodeError) as exc:
        return None, [
            CheckResult(
                "file_readable",
                contract.entity,
                Severity.BLOCKING,
                1,
                1,
                f"Could not parse {path.name} as UTF-8 CSV: {exc}",
            )
        ]

    checks = []
    missing = [name for name in contract.column_names if name not in frame.columns]
    checks.append(
        CheckResult(
            "required_columns_present",
            contract.entity,
            Severity.BLOCKING,
            len(contract.column_names),
            len(missing),
            f"Missing columns in {path.name}: {', '.join(missing)}" if missing else "",
            tuple(missing),
        )
    )
    unexpected = [name for name in frame.columns if name not in contract.column_names]
    checks.append(
        CheckResult(
            "no_unexpected_columns",
            contract.entity,
            Severity.WARNING,
            len(frame.columns),
            len(unexpected),
            f"Unexpected columns are ignored: {', '.join(unexpected)}" if unexpected else "",
            tuple(unexpected),
        )
    )
    if len(frame) == 0:
        checks.append(
            CheckResult(
                "file_not_empty",
                contract.entity,
                Severity.BLOCKING,
                0,
                1,
                f"{path.name} contains a header but no data rows.",
            )
        )
    return frame, checks


def _below_minimum(value: float, column: Column) -> bool:
    if column.exclusive_min:
        return value <= column.min_value
    return value < column.min_value


def _check_columns(data: EntityData, now: datetime) -> list[CheckResult]:
    contract, frame = data.contract, data.frame
    keys = frame[contract.primary_key]
    total = len(frame)
    checks: list[CheckResult] = []

    for column in contract.columns:
        values = frame[column.name].str.strip()
        empty = values == ""

        if column.required:
            failed = frame.index[empty]
            data.reject(failed, f"missing_required_value:{column.name}")
            checks.append(
                CheckResult(
                    f"not_null:{column.name}",
                    contract.entity,
                    Severity.ERROR,
                    total,
                    len(failed),
                    f"{len(failed)} rows have no value for required column {column.name}."
                    if len(failed)
                    else "",
                    _sample(keys[failed]),
                )
            )

        parser = PARSERS[column.type]
        parsed = values.where(~empty).map(lambda v, p=parser: p(v) if isinstance(v, str) else None)
        if column.type is not ColumnType.TEXT:
            failed = frame.index[~empty & parsed.isna()]
            data.reject(failed, f"invalid_type:{column.name}")
            checks.append(
                CheckResult(
                    f"valid_type:{column.name}",
                    contract.entity,
                    Severity.ERROR,
                    total,
                    len(failed),
                    f"{len(failed)} values in {column.name} are not valid {column.type}."
                    if len(failed)
                    else "",
                    _sample(keys[failed]),
                )
            )

        if column.accepted_values is not None:
            failed = frame.index[~empty & ~values.isin(column.accepted_values)]
            data.reject(failed, f"invalid_value:{column.name}")
            checks.append(
                CheckResult(
                    f"accepted_values:{column.name}",
                    contract.entity,
                    Severity.ERROR,
                    total,
                    len(failed),
                    f"{len(failed)} rows have {column.name} outside "
                    f"{sorted(column.accepted_values)}."
                    if len(failed)
                    else "",
                    _sample(keys[failed]),
                )
            )

        if column.min_value is not None:
            failed = frame.index[
                parsed.map(
                    lambda v, col=column: v is not None and _below_minimum(float(v), col)
                ).astype(bool)
            ]
            minimum = column.min_value
            data.reject(failed, f"out_of_range:{column.name}")
            operator = ">" if column.exclusive_min else ">="
            checks.append(
                CheckResult(
                    f"range:{column.name}",
                    contract.entity,
                    Severity.ERROR,
                    total,
                    len(failed),
                    f"{len(failed)} rows violate {column.name} {operator} {minimum}."
                    if len(failed)
                    else "",
                    _sample(keys[failed]),
                )
            )

        if column.type is ColumnType.TIMESTAMP:
            in_future = parsed.map(lambda v: v is not None and v > now).astype(bool)
            failed = frame.index[in_future]
            data.reject(failed, f"future_timestamp:{column.name}")
            checks.append(
                CheckResult(
                    f"not_in_future:{column.name}",
                    contract.entity,
                    Severity.ERROR,
                    total,
                    len(failed),
                    f"{len(failed)} rows have {column.name} after {now.isoformat()}."
                    if len(failed)
                    else "",
                    _sample(keys[failed]),
                )
            )
    return checks


def _check_entity_rules(data: EntityData) -> list[CheckResult]:
    contract, frame = data.contract, data.frame
    keys = frame[contract.primary_key]
    checks: list[CheckResult] = []

    if contract.entity == "customers":
        emails = frame["email"].str.strip()
        failed = frame.index[(emails != "") & ~emails.map(is_valid_email)]
        checks.append(
            CheckResult(
                "email_format",
                contract.entity,
                Severity.WARNING,
                len(frame),
                len(failed),
                f"{len(failed)} customers have a malformed email address; rows are kept."
                if len(failed)
                else "",
                _sample(keys[failed]),
            )
        )

    if contract.entity == "order_items":

        def exceeds(row: pd.Series) -> bool:
            price = parse_decimal(row["unit_price"].strip())
            discount = parse_decimal(row["discount_amount"].strip())
            quantity = row["quantity"].strip()
            if price is None or discount is None or not quantity.isdigit():
                return False
            # Non-positive quantities are already rejected by the range check.
            return int(quantity) > 0 and discount > price * int(quantity)

        failed = frame.index[frame.apply(exceeds, axis=1).astype(bool)]
        data.reject(failed, "discount_exceeds_line_total")
        checks.append(
            CheckResult(
                "discount_not_above_line_total",
                contract.entity,
                Severity.ERROR,
                len(frame),
                len(failed),
                f"{len(failed)} order items have a discount larger than quantity * unit_price."
                if len(failed)
                else "",
                _sample(keys[failed]),
            )
        )
    return checks


def _check_duplicates(data: EntityData) -> CheckResult:
    contract, frame = data.contract, data.frame
    key = contract.primary_key
    columns = contract.column_names
    stripped_keys = frame[key].str.strip()
    duplicated_key = stripped_keys.duplicated(keep=False) & (stripped_keys != "")

    exact_copies = frame.index[duplicated_key & frame[columns].duplicated(keep="first")]
    data.reject(exact_copies, "duplicate_record")

    remaining = frame.loc[duplicated_key].drop(index=exact_copies)
    conflicting_keys = remaining[key].str.strip()
    conflicting = remaining.index[conflicting_keys.duplicated(keep=False)]
    data.reject(conflicting, f"conflicting_duplicate_key:{key}")

    failed = sorted(set(exact_copies) | set(conflicting))
    return CheckResult(
        f"unique:{key}",
        contract.entity,
        Severity.ERROR,
        len(frame),
        len(failed),
        f"{len(exact_copies)} exact duplicate rows quarantined; "
        f"{len(conflicting)} rows share a key with conflicting values and were all quarantined."
        if failed
        else "",
        _sample(frame.loc[failed, key].unique()),
    )


def _valid_keys(data: EntityData, column: str) -> set[str]:
    return set(data.valid_frame[column].str.strip())


def _check_foreign_key(
    child: EntityData, column: str, parent: EntityData, parent_column: str
) -> CheckResult:
    parent_keys = _valid_keys(parent, parent_column)
    frame = child.frame
    values = frame[column].str.strip()
    orphaned = frame.index[child.valid_mask & (values != "") & ~values.isin(parent_keys)]
    child.reject(orphaned, f"orphaned_foreign_key:{column}")
    return CheckResult(
        f"relationship:{column}->{parent.contract.entity}",
        child.contract.entity,
        Severity.ERROR,
        len(frame),
        len(orphaned),
        f"{len(orphaned)} rows reference {parent.contract.entity} keys that are missing "
        "or quarantined."
        if len(orphaned)
        else "",
        _sample(frame.loc[orphaned, child.contract.primary_key]),
    )


def _check_orders_have_items(orders: EntityData, items: EntityData) -> CheckResult:
    order_ids = orders.frame["order_id"].str.strip()
    with_items = _valid_keys(items, "order_id")
    failed = orders.frame.index[orders.valid_mask & ~order_ids.isin(with_items)]
    orders.reject(failed, "order_without_valid_items")
    return CheckResult(
        "order_has_valid_items",
        "orders",
        Severity.ERROR,
        len(orders.frame),
        len(failed),
        f"{len(failed)} orders have no valid order items." if len(failed) else "",
        _sample(order_ids[failed]),
    )


def _check_payment_reconciliation(
    orders: EntityData, items: EntityData, payments: EntityData
) -> list[CheckResult]:
    order_frame = orders.valid_frame
    status_by_order = dict(
        zip(
            order_frame["order_id"].str.strip(),
            order_frame["order_status"].str.strip(),
            strict=True,
        )
    )

    order_totals: dict[str, Decimal] = defaultdict(Decimal)
    for row in items.valid_frame.itertuples(index=False):
        net = Decimal(row.unit_price.strip()) * int(row.quantity.strip()) - Decimal(
            row.discount_amount.strip()
        )
        order_totals[row.order_id.strip()] += net

    charged: dict[str, Decimal] = defaultdict(Decimal)
    refunded: dict[str, Decimal] = defaultdict(Decimal)
    for row in payments.valid_frame.itertuples(index=False):
        if row.payment_status.strip() != "succeeded":
            continue
        target = charged if row.transaction_type.strip() == "charge" else refunded
        target[row.order_id.strip()] += Decimal(row.amount.strip())

    eligible = [o for o, s in status_by_order.items() if s in REVENUE_ELIGIBLE_ORDER_STATUSES]
    mismatched = [
        o for o in eligible if abs(charged[o] - order_totals[o]) > RECONCILIATION_TOLERANCE
    ]
    over_refunded = [o for o in status_by_order if refunded[o] - charged[o] > Decimal(0)]
    cancelled_captured = [
        o
        for o, s in status_by_order.items()
        if s == "cancelled" and charged[o] - refunded[o] > RECONCILIATION_TOLERANCE
    ]
    return [
        CheckResult(
            "payments_reconcile_to_order_total",
            "payments",
            Severity.WARNING,
            len(eligible),
            len(mismatched),
            f"{len(mismatched)} processing/shipped/delivered orders have succeeded charges "
            "that differ from the sum of their item net amounts."
            if mismatched
            else "",
            _sample(mismatched),
        ),
        CheckResult(
            "refunds_not_above_charges",
            "payments",
            Severity.WARNING,
            len(status_by_order),
            len(over_refunded),
            f"{len(over_refunded)} orders were refunded more than was charged."
            if over_refunded
            else "",
            _sample(over_refunded),
        ),
        CheckResult(
            "cancelled_orders_fully_refunded",
            "payments",
            Severity.WARNING,
            sum(1 for s in status_by_order.values() if s == "cancelled"),
            len(cancelled_captured),
            f"{len(cancelled_captured)} cancelled orders still hold captured funds."
            if cancelled_captured
            else "",
            _sample(cancelled_captured),
        ),
    ]


def _check_rejected_ratio(data: EntityData, max_ratio: float) -> CheckResult:
    total = len(data.frame)
    rejected = data.rejected_count
    ratio = rejected / total if total else 0.0
    exceeded = ratio > max_ratio
    return CheckResult(
        "rejected_ratio_within_threshold",
        data.contract.entity,
        Severity.BLOCKING,
        total,
        rejected if exceeded else 0,
        f"{rejected}/{total} rows ({ratio:.2%}) were quarantined, above the allowed "
        f"{max_ratio:.2%}. Inspect the source extract before loading."
        if exceeded
        else f"{rejected}/{total} rows quarantined ({ratio:.2%}).",
    )


def validate_source_dir(
    source_dir: Path,
    max_rejected_ratio: float,
    now: datetime | None = None,
) -> ValidationResult:
    now = now or datetime.now(UTC)
    result = ValidationResult()

    for contract in CONTRACTS:
        frame, checks = _check_file(contract, source_dir)
        result.checks.extend(checks)
        if frame is not None:
            result.entities[contract.entity] = EntityData(contract, frame)

    if result.blocking_failures:
        return result

    for data in result.entities.values():
        result.checks.extend(_check_columns(data, now))
        result.checks.extend(_check_entity_rules(data))
        result.checks.append(_check_duplicates(data))

    entities = result.entities
    customers, products = entities["customers"], entities["products"]
    orders, items, payments = entities["orders"], entities["order_items"], entities["payments"]
    result.checks.append(_check_foreign_key(orders, "customer_id", customers, "customer_id"))
    result.checks.append(_check_foreign_key(items, "order_id", orders, "order_id"))
    result.checks.append(_check_foreign_key(items, "product_id", products, "product_id"))
    result.checks.append(_check_orders_have_items(orders, items))
    result.checks.append(_check_foreign_key(payments, "order_id", orders, "order_id"))
    result.checks.extend(_check_payment_reconciliation(orders, items, payments))

    for data in entities.values():
        result.checks.append(_check_rejected_ratio(data, max_rejected_ratio))

    for check in result.failed_checks():
        log = logger.error if check.severity is Severity.BLOCKING else logger.warning
        log("[%s] %s on %s: %s", check.severity, check.check_name, check.entity, check.message)
    return result
