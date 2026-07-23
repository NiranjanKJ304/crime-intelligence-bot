"""
Query Processor for normalizations.
"""

from __future__ import annotations

import re
import unicodedata

from app.retrieval.schemas import ProcessedQuery
from app.retrieval.entity_extractor import EntityExtractor


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

    def __init__(self):
        self.extractor = EntityExtractor()

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

    def process_with_entities(self, raw_query: str) -> ProcessedQuery:
        """Normalize query and extract entities."""
        normalized = self.process(raw_query)
        entities = self.extractor.extract(normalized)
        
        return ProcessedQuery(
            original_query=raw_query or "",
            normalized_query=normalized,
            entities=entities
        )

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
