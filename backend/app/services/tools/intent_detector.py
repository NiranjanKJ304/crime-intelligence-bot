"""
Intent Detector.

Lightweight regex + keyword classifier that runs BEFORE the LLM call.
Used for logging/metrics and as a routing hint.
The actual routing decision is made by the LLM via tool calling.
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class DetectedIntent:
    """Result of intent detection on a user query."""
    intent: str  # case_lookup, officer_lookup, victim_lookup, accused_lookup,
                 # relationship_query, semantic_search, statistics, general
    identifiers: dict[str, str | int] = field(default_factory=dict)
    confidence: float = 0.0
    raw_query: str = ""


class IntentDetector:
    """Classifies user queries into intent categories using regex patterns."""

    # Patterns ordered by specificity (most specific first)
    PATTERNS = [
        # Case lookups
        (r'\bcase\s*(?:number|no|#|id)?\s*[:\s]?\s*(\d+)', "case_lookup", "case_id"),
        (r'\bcase\s+(\d+)', "case_lookup", "case_id"),
        (r'\bshow\s+case\s+(\d+)', "case_lookup", "case_id"),

        # Crime number / FIR lookups
        (r'\bcrime\s*(?:number|no|#)?\s*[:\s]?\s*([A-Za-z0-9/\-]+\d+)', "crime_number_lookup", "crime_number"),
        (r'\bfir\s*(?:number|no|#)?\s*[:\s]?\s*([A-Za-z0-9/\-]+)', "crime_number_lookup", "crime_number"),
        (r'\bcr[/ ]?\d{4}[/ ]\d+', "crime_number_lookup", "crime_number"),

        # Officer lookups
        (r'\bofficer\s*(?:id|number|no|#)?\s*[:\s]?\s*(\d+)', "officer_lookup", "officer_id"),
        (r'\bemployee\s*(?:id|number|no|#)?\s*[:\s]?\s*(\d+)', "officer_lookup", "officer_id"),
        (r'\binvestigating\s+officer\s+(\d+)', "officer_lookup", "officer_id"),

        # Victim lookups
        (r'\bvictim\s*(?:id|number|no|#)?\s*[:\s]?\s*(\d+)', "victim_lookup", "victim_id"),

        # Accused lookups
        (r'\baccused\s*(?:id|number|no|#)?\s*[:\s]?\s*(\d+)', "accused_lookup", "accused_id"),
        (r'\bsuspect\s*(?:id|number|no|#)?\s*[:\s]?\s*(\d+)', "accused_lookup", "accused_id"),

        # Complainant lookups
        (r'\bcomplainant\s*(?:id|number|no|#)?\s*[:\s]?\s*(\d+)', "complainant_lookup", "complainant_id"),
    ]

    # Relationship keywords
    RELATIONSHIP_KEYWORDS = [
        "related", "connected", "linked", "network", "co-accused", "coaccused",
        "gang", "together", "arrested by", "who arrested", "investigated by",
        "who investigated", "appear together", "repeat offender", "collaboration",
        "timeline", "chronolog",
    ]

    # Statistics keywords
    STATISTICS_KEYWORDS = [
        "how many", "total", "count", "statistics", "stat", "summary",
        "distribution", "breakdown", "percentage",
    ]

    @staticmethod
    def detect(query: str) -> DetectedIntent:
        """Classify a user query into an intent category."""
        q_lower = query.lower().strip()

        # 1. Check regex patterns for exact ID lookups
        for pattern, intent, id_key in IntentDetector.PATTERNS:
            match = re.search(pattern, q_lower)
            if match:
                identifier = match.group(1) if match.lastindex else match.group(0)
                # Try to convert to int if it looks numeric
                try:
                    identifier = int(identifier)
                except (ValueError, TypeError):
                    pass

                logger.info(f"Intent detected: {intent} | {id_key}={identifier}")
                return DetectedIntent(
                    intent=intent,
                    identifiers={id_key: identifier},
                    confidence=0.9,
                    raw_query=query,
                )

        # 2. Check for relationship keywords
        for kw in IntentDetector.RELATIONSHIP_KEYWORDS:
            if kw in q_lower:
                logger.info(f"Intent detected: relationship_query (keyword: {kw})")
                return DetectedIntent(
                    intent="relationship_query",
                    confidence=0.7,
                    raw_query=query,
                )

        # 3. Check for statistics keywords
        for kw in IntentDetector.STATISTICS_KEYWORDS:
            if kw in q_lower:
                logger.info(f"Intent detected: statistics_query (keyword: {kw})")
                return DetectedIntent(
                    intent="statistics_query",
                    confidence=0.7,
                    raw_query=query,
                )

        # 4. Default: semantic search (natural language query)
        logger.info("Intent detected: semantic_search (default)")
        return DetectedIntent(
            intent="semantic_search",
            confidence=0.5,
            raw_query=query,
        )
