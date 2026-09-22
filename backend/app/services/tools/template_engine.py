"""
Backend Template Engine.

Generates human-readable, formatted responses for factual queries
without requiring a round-trip to the LLM.
"""

from __future__ import annotations

import logging
from typing import Any

from app.services.tools.dtos import (
    AccusedDTO,
    CaseLookupDTO,
    ChargesheetDTO,
    OfficerDTO,
    VictimDTO,
)

logger = logging.getLogger(__name__)


def _fmt(value: Any, default: str = "Unknown") -> str:
    return default if value is None or value == "" else str(value)


def _person_line(index: int, person: VictimDTO | AccusedDTO) -> str:
    age = f"{person.age} years old" if person.age is not None else "Age unknown"
    gender = f"Gender ID {person.gender}" if person.gender is not None else "Gender unknown"
    return f"{index}. **{person.name or 'Unknown'}** ({age}, {gender})"


class TemplateEngine:
    """Generates natural language responses directly from DTOs."""

    @staticmethod
    def render_case_details(case: CaseLookupDTO) -> str:
        return (
            f"### Case Details\n"
            f"- **Case Number (CaseNo):** {_fmt(case.case_number)}\n"
            f"- **Crime Number (CrimeNo / FIR):** {_fmt(case.crime_number)}\n"
            f"- **Case Status ID:** {_fmt(case.status)}\n"
            f"- **Investigating Officer (PolicePersonID):** {_fmt(case.police_person_id, 'Not recorded')}\n"
            f"- **Police Station ID:** {_fmt(case.station_id, 'Not recorded')}\n"
            f"- **Database ID (CaseMasterID):** {case.case_id}"
        )

    @staticmethod
    def render_officer_details(officer: OfficerDTO, heading: str = "### Officer Details") -> str:
        return (
            f"{heading}\n"
            f"- **Name:** {officer.first_name}\n"
            f"- **KGID:** {_fmt(officer.kgid, 'N/A')}\n"
            f"- **Designation ID:** {_fmt(officer.designation, 'N/A')}\n"
            f"- **Rank ID:** {_fmt(officer.rank, 'N/A')}\n"
            f"- **Employee ID:** {officer.employee_id}"
        )

    @staticmethod
    def render_factual_response(sub_intent: str, data: Any, case_label: str) -> str:
        """Render a deterministic response for a case-specific factual query."""

        if sub_intent == "officer_for_case":
            if not isinstance(data, OfficerDTO):
                return f"No investigating officer could be resolved for {case_label}."
            designation = _fmt(data.designation, _fmt(data.rank, "N/A"))
            return (
                f"The investigating officer for {case_label} is **{data.first_name}** "
                f"(EmployeeID {data.employee_id}, KGID: {_fmt(data.kgid, 'N/A')}). "
                f"Designation ID: {designation}."
            )

        if sub_intent == "victim_for_case":
            victims = data if isinstance(data, list) else ([data] if data else [])
            if not victims:
                return f"There are no victims listed for {case_label}."
            parts = [f"Found {len(victims)} victim(s) for {case_label}:"]
            parts += [_person_line(i + 1, v) for i, v in enumerate(victims)]
            return "\n".join(parts)

        if sub_intent == "accused_for_case":
            accused = data if isinstance(data, list) else ([data] if data else [])
            if not accused:
                return f"There are no accused listed for {case_label}."
            parts = [f"Found {len(accused)} accused for {case_label}:"]
            for i, a in enumerate(accused):
                line = _person_line(i + 1, a)
                if isinstance(a, AccusedDTO) and a.person_id:
                    line += f" — PersonID {a.person_id}, AccusedMasterID {a.accused_id}"
                parts.append(line)
            return "\n".join(parts)

        if sub_intent == "chargesheet_for_case":
            if not isinstance(data, ChargesheetDTO):
                return f"Chargesheet data for {case_label} is unavailable."
            if data.filed:
                return (
                    f"Yes, the chargesheet for {case_label} was filed on **{data.date or 'an unknown date'}**"
                    f"{f' at {data.court_name}' if data.court_name else ''}."
                )
            return f"No chargesheet has been filed yet for {case_label}."

        if sub_intent == "status_for_case":
            if not isinstance(data, CaseLookupDTO):
                return f"Status data for {case_label} is unavailable."
            return (
                f"**Case Number:** {_fmt(data.case_number)}\n"
                f"**Crime Number:** {_fmt(data.crime_number)}\n"
                f"**Status ID:** {_fmt(data.status)}"
            )

        if not data:
            return f"I could not find the requested information for {case_label}."
        return f"Data retrieved for {case_label}, but I could not format it properly."

    @staticmethod
    def render_identifier_response(sub_intent: str, data: Any) -> str:
        """Render a deterministic response for an exact entity lookup."""

        if sub_intent == "accused_by_name":
            matches = data if isinstance(data, list) else []
            if not matches:
                return "No accused records were found for that name."
            name = matches[0].name
            parts = [
                f"Found **{len(matches)}** accused record(s) for **{name}**. "
                f"A name is not a unique identity — each record below is a distinct entry:"
            ]
            for a in matches:
                parts.append(
                    f"- AccusedMasterID {a.accused_id} | CaseMasterID {_fmt(a.case_id)} | "
                    f"PersonID {_fmt(a.person_id)} | Age {_fmt(a.age)} | Gender ID {_fmt(a.gender)}"
                )
            if len(matches) > 1:
                parts.append("Specify a CaseMasterID, AccusedMasterID or PersonID to narrow this down.")
            return "\n".join(parts)

        if not data:
            return "No records were found for that identifier."

        if sub_intent in ("case_by_number", "case_by_crime", "case_by_id"):
            if not isinstance(data, CaseLookupDTO):
                return "Case data unavailable."
            return TemplateEngine.render_case_details(data)

        if sub_intent == "officer":
            if not isinstance(data, OfficerDTO):
                return "Officer data unavailable."
            return TemplateEngine.render_officer_details(data)

        if sub_intent == "victim":
            if not isinstance(data, VictimDTO):
                return "Victim data unavailable."
            return (
                f"### Victim Details\n"
                f"- **Name:** {data.name}\n"
                f"- **Age:** {_fmt(data.age)}\n"
                f"- **Gender ID:** {_fmt(data.gender)}\n"
                f"- **CaseMasterID:** {_fmt(data.case_id)}\n"
                f"- **Database ID (VictimMasterID):** {data.victim_id}"
            )

        if sub_intent == "accused":
            if not isinstance(data, AccusedDTO):
                return "Accused data unavailable."
            return (
                f"### Accused Details\n"
                f"- **Name:** {data.name}\n"
                f"- **Age:** {_fmt(data.age)}\n"
                f"- **Gender ID:** {_fmt(data.gender)}\n"
                f"- **PersonID:** {_fmt(data.person_id)}\n"
                f"- **CaseMasterID:** {_fmt(data.case_id)}\n"
                f"- **Database ID (AccusedMasterID):** {data.accused_id}"
            )

        return "Record retrieved successfully."
