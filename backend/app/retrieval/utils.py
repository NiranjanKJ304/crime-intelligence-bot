"""
Utilities for the Retrieval Engine.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from app.etl.utils import safe_json_serialize


def estimate_tokens(text: str) -> int:
    """
    Estimate tokens using a simple heuristic (characters / 4).
    This is faster than loading a full tokenizer for simple boundaries.
    """
    if not text:
        return 0
    return len(text) // 4


def generate_cache_key(query: str, filters: dict[str, Any] | None, top_k: int | None, threshold: float | None) -> str:
    """
    Generate a deterministic SHA-256 hash for a search request.
    """
    # Sort keys for deterministic JSON output
    filters_json = json.dumps(filters or {}, sort_keys=True, default=safe_json_serialize)
    
    components = [
        f"q:{query}",
        f"f:{filters_json}",
        f"k:{top_k if top_k is not None else 'default'}",
        f"t:{threshold if threshold is not None else 'default'}"
    ]
    
    raw_key = "|".join(components)
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
