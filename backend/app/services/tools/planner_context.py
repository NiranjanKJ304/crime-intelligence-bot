"""
Planner Context for deterministic tool chaining.

This object holds the state of the current request, allowing tools to be executed
sequentially without relying on the LLM to pass state between them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.services.tools.dtos import (
    AccusedDTO,
    CaseLookupDTO,
    ChargesheetDTO,
    OfficerDTO,
    VictimDTO,
)


@dataclass
class PlannerContext:
    """Request-scoped state object that every tool reads from and writes to."""

    # Identifiers (populated by entity extraction or early tool calls).
    # Values keep the type the user supplied; the tools layer coerces them
    # to the physical column type before querying.
    case_id: int | None = None
    case_number: int | str | None = None
    crime_number: int | str | None = None
    officer_id: int | None = None
    victim_ids: list[int] = field(default_factory=list)
    accused_ids: list[int] = field(default_factory=list)
    accused_name: str | None = None
    station_id: int | None = None
    court_id: int | None = None

    # Collected results (populated by tool execution)
    case_lookup: CaseLookupDTO | None = None
    officer: OfficerDTO | None = None
    victims: list[VictimDTO] = field(default_factory=list)
    accused: list[AccusedDTO] = field(default_factory=list)
    accused_matches: list[AccusedDTO] = field(default_factory=list)
    chargesheet: ChargesheetDTO | None = None
    network: list[dict] | None = None
    co_accused: list[dict] | None = None
    timeline: list[dict] | None = None
    semantic_results: list[dict] | None = None
    case_summary_text: str | None = None
    raw_tool_results: list[Any] = field(default_factory=list)

    # Metadata
    tools_executed: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    not_found: bool = False

    def has_error(self) -> bool:
        return len(self.errors) > 0
