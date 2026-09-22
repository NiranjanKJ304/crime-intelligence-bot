"""
Typed schemas for the structured `data` payload returned by the backend.

Mirrors ChatResponse.response_type / data in backend/app/llm/schemas.py.
Keep both in sync when adding a response type.
"""

from __future__ import annotations

from typing import Any, Literal, TypedDict

ResponseType = Literal[
    "answer",
    "case_details",
    "officer_details",
    "person_details",
    "search_results",
    "statistics",
]

RESPONSE_TYPES: tuple[str, ...] = (
    "answer", "case_details", "officer_details", "person_details", "search_results", "statistics",
)


class CaseRecord(TypedDict, total=False):
    case_id: int
    case_number: int | str
    crime_number: int | str | None
    police_person_id: int | None
    station_id: int | None
    status: Any | None


class ChargesheetRecord(TypedDict, total=False):
    filed: bool
    date: str | None
    court_name: str | None


class OfficerRecord(TypedDict, total=False):
    employee_id: int
    first_name: str
    kgid: str | None
    designation: Any | None
    rank: Any | None


class PersonRecord(TypedDict, total=False):
    victim_id: int
    accused_id: int
    case_id: int | None
    name: str
    age: int | None
    gender: Any | None
    person_id: str | None


class CaseDetailsData(TypedDict, total=False):
    case: CaseRecord | None
    chargesheet: ChargesheetRecord | None


class OfficerDetailsData(TypedDict, total=False):
    officer: OfficerRecord
    case: CaseRecord | None


class PersonDetailsData(TypedDict, total=False):
    role: Literal["victim", "accused"]
    persons: list[PersonRecord]
    case: CaseRecord | None


class SearchResultsData(TypedDict, total=False):
    entity: str
    query: str
    total: int
    results: list[dict[str, Any]]
    note: str | None


class StatisticsData(TypedDict, total=False):
    title: str
    metrics: dict[str, Any]


ResponseData = CaseDetailsData | OfficerDetailsData | PersonDetailsData | SearchResultsData | StatisticsData
