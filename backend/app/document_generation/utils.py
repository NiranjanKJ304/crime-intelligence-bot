"""
Shared utility functions for text generation.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any


def format_date(val: Any) -> str:
    """Format a date/datetime object into a human-readable string."""
    if val is None:
        return ""
    try:
        if isinstance(val, str):
            # Attempt to parse
            try:
                dt = datetime.fromisoformat(val.replace('Z', '+00:00'))
                return dt.strftime("%d %B %Y")
            except ValueError:
                return val # return string as-is if unparseable
        if isinstance(val, (datetime, date)):
            return val.strftime("%d %B %Y")
    except Exception:
        pass
    return str(val)


def safe_str(val: Any, default: str = "") -> str:
    """Safely convert a value to string, replacing None or empty with default."""
    if val is None or str(val).strip() == "" or str(val).lower() == "none" or str(val).lower() == "n/a":
        return default
    return str(val).strip()


def pluralize(count: int, singular: str, plural: str) -> str:
    """Simple pluralization helper."""
    return singular if count == 1 else plural


def build_sentence(parts: list[str]) -> str:
    """Build a sentence from parts, ensuring proper spacing and trailing period."""
    clean_parts = [p.strip() for p in parts if p and p.strip()]
    if not clean_parts:
        return ""
    
    sentence = " ".join(clean_parts)
    if not sentence.endswith("."):
        sentence += "."
    return sentence
