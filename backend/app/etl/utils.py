"""
Shared utility functions for the ETL pipeline.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


def safe_json_serialize(obj: Any) -> Any:
    """Convert non-serializable objects for JSON output."""
    if isinstance(obj, (datetime,)):
        return obj.isoformat()
    if isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    if isinstance(obj, (set, frozenset)):
        return list(obj)
    if hasattr(obj, "__dict__"):
        return str(obj)
    return str(obj)


def save_json_report(data: dict[str, Any], filepath: Path) -> None:
    """Save a dictionary as a JSON file."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=safe_json_serialize)


def now_utc() -> datetime:
    """Return the current UTC datetime."""
    return datetime.now(timezone.utc)


def sanitize_table_name(name: str) -> str:
    """Sanitize a table name for use as a clean table identifier."""
    import re
    return re.sub(r"[^a-zA-Z0-9_]", "_", name.lower())


def dataframe_summary(df: pd.DataFrame) -> dict[str, Any]:
    """Generate a concise summary of a DataFrame."""
    return {
        "rows": len(df),
        "columns": len(df.columns),
        "column_names": list(df.columns),
        "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
        "memory_mb": round(df.memory_usage(deep=True).sum() / 1024 / 1024, 2),
        "null_counts": {
            col: int(count)
            for col, count in df.isnull().sum().items()
            if count > 0
        },
    }
