"""
Data Transfer Objects (DTOs) for the tools layer.

These compact objects replace raw database row dictionaries,
significantly reducing token usage and separating database models
from the presentation/LLM layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

@dataclass
class CaseLookupDTO:
    case_id: int
    case_number: str
    crime_number: str
    officer_id: int | None
    station_id: int | None
    status: str | None

    def to_template_context(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "case_no": self.case_number,
            "crime_no": self.crime_number,
            "status": self.status or "Unknown",
        }

@dataclass
class OfficerDTO:
    officer_id: int
    name: str
    kgid: str | None
    designation: str | None
    rank: str | None

    def to_template_context(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kgid": self.kgid or "Unknown",
            "designation": self.designation or self.rank or "Unknown Rank",
        }

@dataclass
class VictimDTO:
    victim_id: int
    name: str
    age: int | None
    gender: str | None

    def to_template_context(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "age": self.age if self.age is not None else "Unknown",
            "gender": self.gender or "Unknown",
        }

@dataclass
class AccusedDTO:
    accused_id: int
    name: str
    age: int | None
    gender: str | None

    def to_template_context(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "age": self.age if self.age is not None else "Unknown",
            "gender": self.gender or "Unknown",
        }

@dataclass
class ChargesheetDTO:
    filed: bool
    date: str | None
    court_name: str | None

    def to_template_context(self) -> dict[str, Any]:
        return {
            "filed": self.filed,
            "date": self.date or "Unknown",
            "court_name": self.court_name or "Unknown",
        }
