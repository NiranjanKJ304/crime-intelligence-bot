"""
Query Processor for normalizations.
"""

from __future__ import annotations

import re
import unicodedata


class QueryProcessor:
    """Normalizes and cleans raw queries."""

    # Configurable abbreviation expansion
    ABBREVIATIONS = {
        "fir": "first information report",
        "ipc": "indian penal code",
        "crpc": "code of criminal procedure",
        "ps": "police station",
        "io": "investigating officer",
        "sho": "station house officer",
        "kgid": "karnataka government id",
    }

    def process(self, raw_query: str) -> str:
        """Normalize, expand, and clean a raw query."""
        if not raw_query:
            return ""
            
        text = raw_query.strip()
        text = self._normalize_unicode(text)
        text = self._normalize_whitespace(text)
        text = text.lower()
        text = self._expand_abbreviations(text)
        
        return text.strip()

    def _normalize_unicode(self, text: str) -> str:
        """Normalize unicode characters (e.g., NFKC)."""
        return unicodedata.normalize("NFKC", text)

    def _normalize_whitespace(self, text: str) -> str:
        """Replace multiple spaces/newlines with a single space."""
        return re.sub(r"\s+", " ", text)

    def _expand_abbreviations(self, text: str) -> str:
        """Expand known abbreviations using word boundaries."""
        for abbr, expansion in self.ABBREVIATIONS.items():
            # \b ensures we only match whole words, not substrings
            pattern = rf"\b{abbr}\b"
            text = re.sub(pattern, expansion, text)
        return text
