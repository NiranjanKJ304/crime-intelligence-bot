"""
Small utility helpers shared across pages.
"""

from datetime import datetime


def fmt_ms(ms: float | None) -> str:
    """Format milliseconds into a human‑friendly string."""
    if ms is None:
        return "—"
    if ms < 1:
        return f"{ms * 1000:.0f} µs"
    if ms < 1000:
        return f"{ms:.1f} ms"
    return f"{ms / 1000:.2f} s"


def fmt_score(score: float | None) -> str:
    """Format a 0‑1 score as a percentage string."""
    if score is None:
        return "—"
    return f"{score * 100:.1f}%"


def fmt_tokens(n: int | None) -> str:
    if n is None or n == 0:
        return "—"
    return f"{n:,}"


def now_str() -> str:
    return datetime.now().strftime("%Y‑%m‑%d  %H:%M:%S")


def truncate(text: str, length: int = 200) -> str:
    if len(text) <= length:
        return text
    return text[:length].rstrip() + " …"
