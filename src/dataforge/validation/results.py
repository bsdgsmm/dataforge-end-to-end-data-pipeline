from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

import pandas as pd

from dataforge.contracts import SourceContract


class Severity(StrEnum):
    BLOCKING = "blocking"
    """Stops the pipeline stage."""
    ERROR = "error"
    """Affected rows are quarantined; the pipeline continues."""
    WARNING = "warning"
    """Rows are kept and loaded; the issue is reported."""


@dataclass(frozen=True)
class CheckResult:
    check_name: str
    entity: str
    severity: Severity
    checked_records: int | None
    failed_records: int
    message: str = ""
    sample_keys: tuple[str, ...] = ()

    @property
    def passed(self) -> bool:
        return self.failed_records == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_name": self.check_name,
            "entity": self.entity,
            "severity": str(self.severity),
            "status": "passed" if self.passed else "failed",
            "checked_records": self.checked_records,
            "failed_records": self.failed_records,
            "message": self.message,
            "sample_keys": list(self.sample_keys),
        }


@dataclass
class EntityData:
    contract: SourceContract
    frame: pd.DataFrame
    rejections: dict[int, list[str]] = field(default_factory=lambda: defaultdict(list))

    def reject(self, positions: list[int] | pd.Index, reason: str) -> None:
        for position in positions:
            self.rejections[int(position)].append(reason)

    def is_rejected(self, position: int) -> bool:
        return bool(self.rejections.get(position))

    @property
    def valid_mask(self) -> pd.Series:
        rejected = set(position for position, reasons in self.rejections.items() if reasons)
        return pd.Series(
            [position not in rejected for position in range(len(self.frame))],
            index=self.frame.index,
            dtype=bool,
        )

    @property
    def valid_frame(self) -> pd.DataFrame:
        return self.frame[self.valid_mask]

    @property
    def rejected_count(self) -> int:
        return sum(1 for reasons in self.rejections.values() if reasons)


@dataclass
class ValidationResult:
    entities: dict[str, EntityData] = field(default_factory=dict)
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def blocking_failures(self) -> list[CheckResult]:
        return [c for c in self.checks if c.severity is Severity.BLOCKING and not c.passed]

    @property
    def is_loadable(self) -> bool:
        return not self.blocking_failures

    def failed_checks(self, severity: Severity | None = None) -> list[CheckResult]:
        return [
            c for c in self.checks if not c.passed and (severity is None or c.severity is severity)
        ]
