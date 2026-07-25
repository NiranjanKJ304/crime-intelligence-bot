"""
Intent Detector.

Lightweight regex + keyword classifier that runs BEFORE the LLM call.
Classifies queries into 5 main categories to determine the execution path:
identifier_lookup, factual_query, semantic_search, graph_query, reasoning.
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class DetectedIntent:
    """Result of intent detection on a user query."""
    intent: str  # identifier_lookup, factual_query, semantic_search, graph_query, reasoning
    sub_intent: str | None = None
    identifiers: dict[str, str | int] = field(default_factory=dict)
    confidence: float = 0.0
    raw_query: str = ""


class IntentDetector:
    """Classifies user queries into intent categories using regex patterns."""

    # Patterns ordered by specificity (most specific first)
    
    # 1. Identifier Lookups (Just looking up the entity directly without asking for related entities)
    IDENTIFIER_PATTERNS = [
        (r'^(?:show |find )?\bcase\s*(?:number|no|#|id)?\s*[:\s]?\s*(\d+)$', "case_by_number", "case_number"),
        (r'^(?:show |find )?\b(?:crime|fir)\s*(?:number|no|#)?\s*[:\s]?\s*([A-Za-z0-9/\-]+\d+)$', "case_by_crime", "crime_number"),
        (r'^(?:show |find )?\bofficer\s*(?:id|number|no|#)?\s*[:\s]?\s*(\d+)$', "officer", "officer_id"),
        (r'^(?:show |find )?\bemployee\s*(?:id|number|no|#)?\s*[:\s]?\s*(\d+)$', "officer", "officer_id"),
        (r'^(?:show |find )?\bvictim\s*(?:id|number|no|#)?\s*[:\s]?\s*(\d+)$', "victim", "victim_id"),
        (r'^(?:show |find )?\baccused\s*(?:id|number|no|#)?\s*[:\s]?\s*(\d+)$', "accused", "accused_id"),
    ]

    # 2. Reasoning Keywords
    REASONING_KEYWORDS = [
        "summarize", "summary", "explain", "compare", "report", "briefing",
        "generate", "analysis", "synthesize", "difference", "similarities"
    ]

    # 3. Graph Keywords
    GRAPH_KEYWORDS = [
        "related", "connected", "linked", "network", "co-accused", "coaccused",
        "gang", "together", "arrested by", "who arrested", "investigated by",
        "who investigated", "appear together", "repeat offender", "collaboration",
        "timeline", "chronolog",
    ]

    @staticmethod
    def detect(query: str) -> DetectedIntent:
        """Classify a user query into an intent category."""
        q_lower = query.lower().strip()
        
        is_reasoning = any(kw in q_lower for kw in IntentDetector.REASONING_KEYWORDS)
        
        # Extract case number anywhere in the query
        case_number = None
        match = re.search(r'\b(?:case(?: number| no|id)?|fir|cr|crime(?: number| no)?)\s*(?:#|:)?\s*([A-Za-z0-9/\-]*\d+)', q_lower)
        if match:
            case_number = match.group(1)
            
        has_case_ref = bool(case_number) or any(x in q_lower for x in ["that case", "this case", "the case"])

        # 1. Identify sub-intent
        sub_intent = None
        if has_case_ref:
            # Check highly specific or multi-word intents first
            if any(kw in q_lower for kw in ["network", "connections", "criminal network"]):
                sub_intent = "case_network"
            elif any(kw in q_lower for kw in ["co-accused", "co accused", "associates", "accomplices"]):
                sub_intent = "co_accused"
            elif any(kw in q_lower for kw in ["timeline", "chronology", "sequence"]):
                sub_intent = "case_timeline"
            elif any(kw in q_lower for kw in ["summarize", "summary", "brief"]):
                sub_intent = "summarize_case"
            # Then check simpler factual keywords
            elif "officer" in q_lower or "investigat" in q_lower:
                sub_intent = "officer_for_case"
            elif "victim" in q_lower:
                sub_intent = "victim_for_case"
            elif "accused" in q_lower or "suspect" in q_lower:
                sub_intent = "accused_for_case"
            elif "chargesheet" in q_lower or "charge sheet" in q_lower:
                sub_intent = "chargesheet_for_case"
            elif "status" in q_lower:
                sub_intent = "status_for_case"

        if sub_intent:
            identifiers = {}
            if case_number:
                try:
                    identifiers["case_number"] = int(case_number)
                except ValueError:
                    identifiers["crime_number"] = case_number
                
            # These specific sub-intents require reasoning/LLM
            if sub_intent in ("case_network", "co_accused", "case_timeline", "summarize_case"):
                intent = "reasoning"
            else:
                intent = "reasoning" if is_reasoning else "factual_query"
                
            logger.info(f"Intent detected: {intent} | sub={sub_intent} | identifiers={identifiers}")
            return DetectedIntent(
                intent=intent,
                sub_intent=sub_intent,
                identifiers=identifiers,
                confidence=0.95,
                raw_query=query,
            )

        # 2. Check Identifier Lookups (Strict match for single entity lookups)
        for pattern, loop_sub_intent, id_key in IntentDetector.IDENTIFIER_PATTERNS:
            match = re.search(pattern, q_lower)
            if match:
                identifier = match.group(1)
                identifiers = {}
                if identifier:
                    try:
                        identifier = int(identifier)
                    except (ValueError, TypeError):
                        pass
                    identifiers[id_key] = identifier

                intent = "reasoning" if is_reasoning else "identifier_lookup"
                logger.info(f"Intent detected: {intent} | sub={loop_sub_intent} | identifiers={identifiers}")
                return DetectedIntent(
                    intent=intent,
                    sub_intent=loop_sub_intent,
                    identifiers=identifiers,
                    confidence=0.9,
                    raw_query=query,
                )

        # Catch basic "Tell me about Case X" (where it has a case number but no specific question)
        if case_number and not sub_intent:
            identifiers = {}
            try:
                identifiers["case_number"] = int(case_number)
            except ValueError:
                identifiers["crime_number"] = case_number
                
            intent = "reasoning" if is_reasoning else "identifier_lookup"
            logger.info(f"Intent detected: {intent} | sub=case_by_number | identifiers={identifiers}")
            return DetectedIntent(
                intent=intent,
                sub_intent="case_by_number",
                identifiers=identifiers,
                confidence=0.8,
                raw_query=query,
            )

        # 3. Check for relationship keywords
        for kw in IntentDetector.GRAPH_KEYWORDS:
            if kw in q_lower:
                logger.info(f"Intent detected: graph_query (keyword: {kw})")
                return DetectedIntent(
                    intent="reasoning" if is_reasoning else "graph_query",
                    sub_intent="relationship",
                    confidence=0.7,
                    raw_query=query,
                )

        # 4. Default: semantic search (natural language query)
        logger.info("Intent detected: semantic_search (default)")
        return DetectedIntent(
            intent="reasoning" if is_reasoning else "semantic_search",
            sub_intent="similar_cases",
            confidence=0.5,
            raw_query=query,
        )
