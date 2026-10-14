from __future__ import annotations

import logging
import os
import sys

LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"


def configure_logging(level: str | None = None) -> None:
    resolved = (level or os.environ.get("DATAFORGE_LOG_LEVEL", "INFO")).upper()
    logging.basicConfig(
        level=getattr(logging, resolved, logging.INFO),
        format=LOG_FORMAT,
        stream=sys.stdout,
        force=True,
    )
