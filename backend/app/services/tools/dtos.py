"""
Data Transfer Objects (DTOs) for the tools layer.

These compact objects replace raw database row dictionaries,
significantly reducing token usage and separating database models
from the presentation/LLM layer.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


@dataclass
class CaseLookupDTO:
    case_id: int
    case_number: int | str
    crime_number: int | str | None
    police_person_id: int | None
    station_id: int | None
    status: Any | None

    def to_template_context(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "case_no": self.case_number,
            "crime_no": self.crime_number,
            "status": self.status if self.status is not None else "Unknown",
        }

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class OfficerDTO:
    employee_id: int
    first_name: str
    kgid: str | None
    designation: Any | None
    rank: Any | None

    def to_template_context(self) -> dict[str, Any]:
        return {
            "name": self.first_name,
            "kgid": self.kgid or "Unknown",
            "designation": self.designation or self.rank or "Unknown Rank",
        }

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class VictimDTO:
    victim_id: int
    case_id: int | None
    name: str
    age: int | None
    gender: Any | None

    def to_template_context(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "age": self.age if self.age is not None else "Unknown",
            "gender": self.gender if self.gender is not None else "Unknown",
        }

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AccusedDTO:
    accused_id: int
    case_id: int | None
    name: str
    age: int | None
    gender: Any | None
    person_id: str | None = None

    def to_template_context(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "age": self.age if self.age is not None else "Unknown",
            "gender": self.gender if self.gender is not None else "Unknown",
            "person_id": self.person_id or "Unknown",
        }

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


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

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
