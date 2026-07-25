"""
Backend Template Engine.

Generates human-readable, formatted responses for factual queries
without requiring a round-trip to the LLM.
"""

from __future__ import annotations

import logging
from typing import Any

from app.services.tools.dtos import (
    CaseLookupDTO,
    OfficerDTO,
    VictimDTO,
    AccusedDTO,
    ChargesheetDTO
)

logger = logging.getLogger(__name__)


class TemplateEngine:
    """Generates natural language responses directly from DTOs."""

    @staticmethod
    def render_factual_response(sub_intent: str, data: Any, case_no: str) -> str:
        """Render a deterministic response for a case-specific factual query."""
        
        if not data:
            return f"I could not find the requested information for Case {case_no}."

        if sub_intent == "officer_for_case":
            if not isinstance(data, OfficerDTO):
                return f"Officer data for Case {case_no} is unavailable."
            return (
                f"The investigating officer for Case {case_no} is **{data.name}** "
                f"(KGID: {data.kgid or 'N/A'}). Designation: {data.designation or data.rank or 'N/A'}."
            )
            
        elif sub_intent == "victim_for_case":
            if isinstance(data, list):
                if not data:
                    return f"There are no victims listed for Case {case_no}."
                
                parts = [f"Found {len(data)} victim(s) for Case {case_no}:"]
                for i, v in enumerate(data):
                    if isinstance(v, dict):
                        age = v.get("Age") or v.get("age")
                        name = v.get("VictimName") or v.get("name")
                        gender = v.get("Sex") or v.get("gender")
                    else:
                        age = v.age
                        name = v.name
                        gender = v.gender
                    age_str = f"{age} years old" if age else "Age unknown"
                    parts.append(f"{i+1}. **{name or 'Unknown'}** ({age_str}, {gender or 'Gender unknown'})")
                return "\n".join(parts)
            else:
                return f"The victim in Case {case_no} is **{data.name}**, {data.age or 'unknown'} years old, {data.gender or 'unknown'}."
                
        elif sub_intent == "accused_for_case":
            if isinstance(data, list):
                if not data:
                    return f"There are no accused listed for Case {case_no}."
                
                parts = [f"Found {len(data)} accused for Case {case_no}:"]
                for i, a in enumerate(data):
                    if isinstance(a, dict):
                        age = a.get("Age") or a.get("age")
                        name = a.get("AccusedName") or a.get("name")
                        gender = a.get("Sex") or a.get("gender")
                    else:
                        age = a.age
                        name = a.name
                        gender = a.gender
                    age_str = f"{age} years old" if age else "Age unknown"
                    parts.append(f"{i+1}. **{name or 'Unknown'}** ({age_str}, {gender or 'Gender unknown'})")
                return "\n".join(parts)
            else:
                return f"The accused in Case {case_no} is **{data.name}**, {data.age or 'unknown'} years old, {data.gender or 'unknown'}."
                
        elif sub_intent == "chargesheet_for_case":
            if not isinstance(data, ChargesheetDTO):
                return f"Chargesheet data for Case {case_no} is unavailable."
                
            if data.filed:
                return f"Yes, the chargesheet for Case {case_no} was filed on **{data.date or 'an unknown date'}** at {data.court_name or 'the assigned court'}."
            else:
                return f"No chargesheet has been filed yet for Case {case_no}."
                
        elif sub_intent == "status_for_case":
            if not isinstance(data, CaseLookupDTO):
                return f"Status data for Case {case_no} is unavailable."
            return (
                f"**Case Number:** {data.case_number}\n"
                f"**Crime Number:** {data.crime_number}\n"
                f"**Status:** {data.status or 'Unknown'}"
            )
            
        return f"Data retrieved for Case {case_no}, but I could not format it properly."


    @staticmethod
    def render_identifier_response(sub_intent: str, data: Any) -> str:
        """Render a deterministic response for an exact entity lookup."""
        
        if not data:
            return "No records were found for that identifier."

        if sub_intent in ("case_by_number", "case_by_crime"):
            if not isinstance(data, CaseLookupDTO):
                return "Case data unavailable."
            return (
                f"### Case Details\n"
                f"- **Case Number:** {data.case_number}\n"
                f"- **Crime Number (FIR):** {data.crime_number}\n"
                f"- **Current Status:** {data.status or 'Unknown'}\n"
                f"- **Database ID:** {data.case_id}"
            )
            
        elif sub_intent == "officer":
            if not isinstance(data, OfficerDTO):
                return "Officer data unavailable."
            return (
                f"### Officer Details\n"
                f"- **Name:** {data.name}\n"
                f"- **KGID:** {data.kgid or 'N/A'}\n"
                f"- **Designation/Rank:** {data.designation or data.rank or 'N/A'}\n"
                f"- **Database ID:** {data.officer_id}"
            )
            
        elif sub_intent == "victim":
            if not isinstance(data, VictimDTO):
                return "Victim data unavailable."
            return (
                f"### Victim Details\n"
                f"- **Name:** {data.name}\n"
                f"- **Age:** {data.age or 'Unknown'}\n"
                f"- **Gender:** {data.gender or 'Unknown'}\n"
                f"- **Database ID:** {data.victim_id}"
            )
            
        elif sub_intent == "accused":
            if not isinstance(data, AccusedDTO):
                return "Accused data unavailable."
            return (
                f"### Accused Details\n"
                f"- **Name:** {data.name}\n"
                f"- **Age:** {data.age or 'Unknown'}\n"
                f"- **Gender:** {data.gender or 'Unknown'}\n"
                f"- **Database ID:** {data.accused_id}"
            )
            
        return "Record retrieved successfully."
