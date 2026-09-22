"""
Structured trace logging for the deterministic query pipeline.

Emits one multi-line record per stage so a single request can be followed
from user query → intent → planner → SQL → response in the logs.
Never pass secrets (connection strings, API keys) as fields.
"""

from __future__ import annotations

import logging
from typing import Any


def trace(logger: logging.Logger, stage: str, **fields: Any) -> None:
    if not logger.isEnabledFor(logging.DEBUG):
        return
    lines = [f"[TRACE] {stage}"]
    for key, value in fields.items():
        label = key.replace("_", " ").upper()
        if isinstance(value, (list, tuple)) and not value:
            value = "(none)"
        lines.append(f"  {label}: {value}")
    logger.debug("\n".join(lines))
