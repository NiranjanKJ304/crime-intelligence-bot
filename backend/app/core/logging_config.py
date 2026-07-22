"""
Structured logging configuration for the ETL pipeline.

Each pipeline stage gets its own logger. All logs are written as
structured JSON to rotating log files AND streamed to stdout.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from app.core.config import get_settings


class JSONFormatter(logging.Formatter):
    """Emit log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        # Attach extra fields (rows, duration_ms, errors, etc.)
        for key in ("stage", "table", "rows", "duration_ms", "errors", "warnings"):
            value = getattr(record, key, None)
            if value is not None:
                log_entry[key] = value

        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, default=str)


def setup_logging() -> None:
    """Configure root and per-stage loggers."""
    settings = get_settings()
    log_path = settings.log_path

    root_logger = logging.getLogger("crime_bot")
    root_logger.setLevel(logging.DEBUG if settings.debug else logging.INFO)

    # Prevent duplicate handlers on repeated calls
    if root_logger.handlers:
        return

    formatter = JSONFormatter()

    # ── Rotating file handler ──────────────────────────────────────
    file_handler = RotatingFileHandler(
        filename=log_path / "etl.log",
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    # ── Console handler ────────────────────────────────────────────
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)


def get_stage_logger(stage: str) -> logging.Logger:
    """
    Return a logger namespaced under the pipeline stage.

    Example:
        logger = get_stage_logger("extract")
        logger.info("Extracted table", extra={"table": "CaseMaster", "rows": 5000})
    """
    return logging.getLogger(f"crime_bot.etl.{stage}")


class StageTimer:
    """
    Context manager that logs stage start/end with duration.

    Usage:
        with StageTimer("extract", table="CaseMaster"):
            ...  # extraction logic
    """

    def __init__(self, stage: str, **extra: Any) -> None:
        self.stage = stage
        self.extra = extra
        self.logger = get_stage_logger(stage)
        self._start: datetime | None = None

    def __enter__(self) -> "StageTimer":
        self._start = datetime.now(timezone.utc)
        self.logger.info(
            f"Stage '{self.stage}' started",
            extra={"stage": self.stage, **self.extra},
        )
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        assert self._start is not None
        duration_ms = (datetime.now(timezone.utc) - self._start).total_seconds() * 1000
        if exc_type:
            self.logger.error(
                f"Stage '{self.stage}' failed after {duration_ms:.0f}ms",
                extra={"stage": self.stage, "duration_ms": duration_ms, **self.extra},
                exc_info=(exc_type, exc_val, exc_tb),
            )
        else:
            self.logger.info(
                f"Stage '{self.stage}' completed in {duration_ms:.0f}ms",
                extra={"stage": self.stage, "duration_ms": duration_ms, **self.extra},
            )
