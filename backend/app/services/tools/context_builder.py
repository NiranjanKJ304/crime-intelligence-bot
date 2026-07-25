"""
Compact Context Builder.

Builds a minimal text representation of case data to feed to the LLM
for reasoning queries, saving thousands of tokens per request.
"""

from __future__ import annotations

import logging
from typing import Any

from app.services.tools import postgres_tools

logger = logging.getLogger(__name__)


class ContextBuilder:
    """Builds highly compact text contexts for the LLM."""

    @staticmethod
    def build_case_summary_context(case_id: int) -> str:
        """
        Fetch basic case data and format it into a tight, ~100 token string.
        This replaces the old `get_case_by_id` which returned ~3000 tokens of JSON.
        """
        parts = []
        
        # 1. Base Case Lookup
        case = postgres_tools.get_case_lookup(case_id=case_id)
        if not case:
            return f"Error: Case ID {case_id} not found."
            
        parts.append(f"Case: {case.case_number} | Crime (FIR): {case.crime_number} | Status: {case.status or 'Unknown'}")
        
        # 2. Officer
        if case.officer_id:
            officer = postgres_tools.get_officer_compact(case.officer_id)
            if officer:
                parts.append(f"Officer: {officer.name} ({officer.designation or officer.rank or 'Unknown Rank'}, KGID: {officer.kgid})")
                
        # 3. Victims
        # Instead of fetching full rows, fetch the list of IDs then compact them, or just use the list func and compact
        victims_raw = postgres_tools.get_case_victims_list(case_id)
        if victims_raw:
            parts.append(f"Victims ({len(victims_raw)}):")
            for v in victims_raw:
                name = v.get("VictimName") or v.get("name", "Unknown")
                age = v.get("Age") or v.get("age", "?")
                gender = v.get("Sex") or v.get("gender", "?")
                parts.append(f"  - {name} ({age}, {gender})")
        else:
            parts.append("Victims: None recorded")
            
        # 4. Accused
        accused_raw = postgres_tools.get_case_accused_list(case_id)
        if accused_raw:
            parts.append(f"Accused ({len(accused_raw)}):")
            for a in accused_raw:
                name = a.get("AccusedName") or a.get("name", "Unknown")
                age = a.get("Age") or a.get("age", "?")
                gender = a.get("Sex") or a.get("gender", "?")
                parts.append(f"  - {name} ({age}, {gender})")
        else:
            parts.append("Accused: None recorded")
            
        # 5. Chargesheet
        cs = postgres_tools.get_chargesheet_status(case_id)
        if cs and cs.filed:
            parts.append(f"Chargesheet: Filed on {cs.date or 'Unknown'} at {cs.court_name or 'Unknown'}")
        else:
            parts.append("Chargesheet: Not Filed")
            
        return "\n".join(parts)
