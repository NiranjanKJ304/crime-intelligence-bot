"""
Intent Detector.

Lightweight regex + keyword classifier that runs BEFORE any LLM call.
Classifies queries into 5 main categories to determine the execution path:
identifier_lookup, factual_query, semantic_search, graph_query, reasoning.

Identifier kinds are kept distinct — CaseNo, CrimeNo (FIR) and CaseMasterID
are different columns and are never interchanged.
"""

from __future__ import annotations

import logging
import re
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


_ID_KEYWORD = r"(?:number|num|no\.?|id|#)?"
_LEAD_IN = (
    r"(?:(?:show|find|get|lookup|search|display|fetch)\s+(?:me\s+)?(?:the\s+|all\s+)?"
    r"|who\s+is\s+(?:the\s+)?|tell\s+me\s+about\s+(?:the\s+)?|details\s+(?:of|for)\s+(?:the\s+)?"
    r"|info(?:rmation)?\s+(?:on|about)\s+(?:the\s+)?)?"
)


class IntentDetector:
    """Classifies user queries into intent categories using regex patterns."""

    # Case reference anywhere in the query. `kind` decides which physical
    # identifier is meant; `kw` distinguishes "case id" (CaseMasterID)
    # from "case number" (CaseNo).
    CASE_REF = re.compile(
        r"\b(?P<kind>case\s*master\s*id|case|fir|cr|crime)\s*(?P<kw>" + _ID_KEYWORD + r")\s*[:#]?\s*"
        r"(?P<value>\d+(?:/[A-Za-z0-9]+)*|[A-Za-z]{1,4}/[A-Za-z0-9/\-]*\d+)\b",
        re.IGNORECASE,
    )

    # Whole-query entity lookups by numeric ID.
    OFFICER_REF = re.compile(
        r"^" + _LEAD_IN + r"(?:investigating\s+officer|officer|employee|police\s*person|io)\s*"
        r"(?:employee\s*|police\s*person\s*)?" + _ID_KEYWORD + r"\s*[:#]?\s*(?P<value>\d+)\s*\??$",
        re.IGNORECASE,
    )
    VICTIM_REF = re.compile(
        r"^" + _LEAD_IN + r"victim\s*(?:master\s*)?" + _ID_KEYWORD + r"\s*[:#]?\s*(?P<value>\d+)\s*\??$",
        re.IGNORECASE,
    )
    ACCUSED_REF = re.compile(
        r"^" + _LEAD_IN + r"(?:accused|suspect)\s*(?:master\s*)?" + _ID_KEYWORD + r"\s*[:#]?\s*(?P<value>\d+)\s*\??$",
        re.IGNORECASE,
    )

    # "find accused named Fiyaz Saran", "accused Fiyaz Saran"
    ACCUSED_NAME_REF = re.compile(
        r"^" + _LEAD_IN + r"(?:accused|suspect)s?\s+"
        r"(?:named?\s+|called\s+|records?\s+(?:for|of)\s+|with\s+(?:the\s+)?name\s+)?"
        r"(?P<name>[A-Za-z][A-Za-z.'\-]*(?:\s+[A-Za-z][A-Za-z.'\-]*){0,3})\s*\??$",
        re.IGNORECASE,
    )
    # Bare proper name: "Fiyaz Saran"
    BARE_NAME_REF = re.compile(r"^(?P<name>[A-Z][a-z.'\-]+(?:\s+[A-Z][a-z.'\-]+){1,3})\s*\??$")

    NAME_STOPWORDS = {
        "in", "of", "for", "with", "from", "at", "by", "and", "or", "to", "on", "the", "a", "an",
        "case", "cases", "who", "was", "were", "is", "are", "list", "all", "persons", "person",
        "people", "records", "record", "details", "involved", "arrested", "network", "related",
    }

    REASONING_KEYWORDS = [
        "summarize", "summary", "explain", "compare", "report", "briefing",
        "generate", "analysis", "synthesize", "difference", "similarities",
    ]

    GRAPH_KEYWORDS = [
        "related", "connected", "linked", "network", "co-accused", "coaccused",
        "gang", "together", "arrested by", "who arrested", "investigated by",
        "who investigated", "appear together", "repeat offender", "collaboration",
        "timeline", "chronolog",
    ]

    # ── Helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _typed(value: str) -> int | str:
        return int(value) if value.isdigit() else value

    @classmethod
    def extract_case_reference(cls, query: str) -> tuple[str, int | str] | None:
        """Return (identifier_key, value) for the first case reference in the query."""
        match = cls.CASE_REF.search(query)
        if not match:
            return None
        kind = re.sub(r"\s+", "", match.group("kind").lower())
        kw = (match.group("kw") or "").lower().rstrip(".")
        value = cls._typed(match.group("value"))

        if kind == "casemasterid" or (kind == "case" and kw == "id"):
            return "case_id", value
        if kind == "case":
            return "case_number", value
        return "crime_number", value

    @classmethod
    def _looks_like_name(cls, name: str) -> bool:
        words = name.lower().split()
        return bool(words) and not any(w in cls.NAME_STOPWORDS for w in words)

    # ── Detection ─────────────────────────────────────────────────────

    @classmethod
    def detect(cls, query: str) -> DetectedIntent:
        """Classify a user query into an intent category."""
        raw = query.strip()
        q_lower = raw.lower()

        is_reasoning = any(kw in q_lower for kw in cls.REASONING_KEYWORDS)
        has_graph_kw = any(kw in q_lower for kw in cls.GRAPH_KEYWORDS)

        case_ref = cls.extract_case_reference(raw)
        has_case_ref = case_ref is not None or any(x in q_lower for x in ("that case", "this case", "the case"))

        # 1. Case-scoped sub-intents (factual or reasoning about one case)
        sub_intent = None
        if has_case_ref:
            if any(kw in q_lower for kw in ["network", "connections", "criminal network"]):
                sub_intent = "case_network"
            elif any(kw in q_lower for kw in ["co-accused", "co accused", "associates", "accomplices"]):
                sub_intent = "co_accused"
            elif any(kw in q_lower for kw in ["timeline", "chronology", "sequence"]):
                sub_intent = "case_timeline"
            elif any(kw in q_lower for kw in ["summarize", "summary", "brief"]):
                sub_intent = "summarize_case"
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
            identifiers: dict[str, str | int] = {}
            if case_ref:
                identifiers[case_ref[0]] = case_ref[1]
            if sub_intent in ("case_network", "co_accused", "case_timeline", "summarize_case"):
                intent = "reasoning"
            else:
                intent = "reasoning" if is_reasoning else "factual_query"
            logger.info("Intent detected: %s | sub=%s | identifiers=%s", intent, sub_intent, identifiers)
            return DetectedIntent(intent=intent, sub_intent=sub_intent, identifiers=identifiers,
                                  confidence=0.95, raw_query=raw)

        # 2. Whole-query entity lookups by ID
        for pattern, loop_sub_intent, id_key in (
            (cls.OFFICER_REF, "officer", "officer_id"),
            (cls.VICTIM_REF, "victim", "victim_id"),
            (cls.ACCUSED_REF, "accused", "accused_id"),
        ):
            match = pattern.match(raw)
            if match:
                identifiers = {id_key: int(match.group("value"))}
                intent = "reasoning" if is_reasoning else "identifier_lookup"
                logger.info("Intent detected: %s | sub=%s | identifiers=%s", intent, loop_sub_intent, identifiers)
                return DetectedIntent(intent=intent, sub_intent=loop_sub_intent, identifiers=identifiers,
                                      confidence=0.9, raw_query=raw)

        # 3. Plain case reference ("Show case 202300001", "FIR number 12345")
        if case_ref:
            key, value = case_ref
            loop_sub_intent = {"case_id": "case_by_id", "case_number": "case_by_number", "crime_number": "case_by_crime"}[key]
            intent = "reasoning" if is_reasoning else "identifier_lookup"
            logger.info("Intent detected: %s | sub=%s | identifiers=%s", intent, loop_sub_intent, {key: value})
            return DetectedIntent(intent=intent, sub_intent=loop_sub_intent, identifiers={key: value},
                                  confidence=0.9, raw_query=raw)

        # 4. Relationship keywords → graph
        if has_graph_kw:
            logger.info("Intent detected: graph_query")
            return DetectedIntent(intent="reasoning" if is_reasoning else "graph_query",
                                  sub_intent="relationship", confidence=0.7, raw_query=raw)

        # 5. Accused lookup by name (all matching records are returned — a
        #    name is never treated as a unique identity)
        name_match = cls.ACCUSED_NAME_REF.match(raw) or cls.BARE_NAME_REF.match(raw)
        if name_match and cls._looks_like_name(name_match.group("name")):
            name = " ".join(name_match.group("name").split())
            confidence = 0.85 if name_match.re is cls.ACCUSED_NAME_REF else 0.6
            logger.info("Intent detected: identifier_lookup | sub=accused_by_name | name=%s", name)
            return DetectedIntent(intent="reasoning" if is_reasoning else "identifier_lookup",
                                  sub_intent="accused_by_name", identifiers={"accused_name": name},
                                  confidence=confidence, raw_query=raw)

        # 6. Default: semantic search
        logger.info("Intent detected: semantic_search (default)")
        return DetectedIntent(intent="reasoning" if is_reasoning else "semantic_search",
                              sub_intent="similar_cases", confidence=0.5, raw_query=raw)
