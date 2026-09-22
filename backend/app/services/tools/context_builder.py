"""
Compact Context Builder.

Builds a minimal text representation of case data to feed to the LLM
for reasoning queries, saving thousands of tokens per request.
"""

from __future__ import annotations

import logging

from app.services.tools import postgres_tools

logger = logging.getLogger(__name__)


class ContextBuilder:
    """Builds highly compact text contexts for the LLM."""

    @staticmethod
    def build_case_summary_context(case_id: int) -> str:
        """Fetch basic case data and format it into a tight, ~100 token string."""
        parts = []

        case = postgres_tools.get_case_lookup(case_id=case_id)
        if not case:
            return f"Error: Case ID {case_id} not found."

        parts.append(
            f"Case: {case.case_number} | Crime (FIR): {case.crime_number} | "
            f"Status: {case.status if case.status is not None else 'Unknown'}"
        )

        if case.police_person_id:
            officer = postgres_tools.get_officer_compact(case.police_person_id)
            if officer:
                parts.append(
                    f"Officer: {officer.first_name} "
                    f"({officer.designation or officer.rank or 'Unknown Rank'}, KGID: {officer.kgid})"
                )

        victims = postgres_tools.get_case_victims_list(case_id)
        if victims:
            parts.append(f"Victims ({len(victims)}):")
            for v in victims:
                parts.append(f"  - {v.name} ({v.age if v.age is not None else '?'}, {v.gender if v.gender is not None else '?'})")
        else:
            parts.append("Victims: None recorded")

        accused = postgres_tools.get_case_accused_list(case_id)
        if accused:
            parts.append(f"Accused ({len(accused)}):")
            for a in accused:
                parts.append(
                    f"  - {a.name} ({a.age if a.age is not None else '?'}, "
                    f"{a.gender if a.gender is not None else '?'}, PersonID: {a.person_id or '?'})"
                )
        else:
            parts.append("Accused: None recorded")

        cs = postgres_tools.get_chargesheet_status(case_id)
        if cs and cs.filed:
            parts.append(f"Chargesheet: Filed on {cs.date or 'Unknown'} at {cs.court_name or 'Unknown'}")
        else:
            parts.append("Chargesheet: Not Filed")

        return "\n".join(parts)
