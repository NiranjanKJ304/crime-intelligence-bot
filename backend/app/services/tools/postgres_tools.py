"""
PostgreSQL Tool Functions.

Every database operation is a parameterised, pre-defined Python function.
The LLM NEVER generates SQL — it can only call these functions by name.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from sqlalchemy import text

from app.core.database import get_engine

logger = logging.getLogger(__name__)

CLEAN_SCHEMA = "clean"


def _execute_query(query_str: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Execute a parameterised SQL query and return rows as dicts."""
    engine = get_engine()
    try:
        with engine.connect() as conn:
            result = conn.execute(text(query_str), params or {})
            keys = list(result.keys())
            rows = [dict(zip(keys, row)) for row in result.fetchall()]
            return rows
    except Exception as e:
        logger.error(f"PostgreSQL query error: {e}")
        return []


# ── Case Lookups ──────────────────────────────────────────────────────

def get_case_by_id(case_id: int) -> dict[str, Any] | None:
    """Fetch a case by its CaseMasterID."""
    rows = _execute_query(
        f'SELECT * FROM "{CLEAN_SCHEMA}"."clean_CaseMaster" WHERE "CaseMasterID" = :case_id LIMIT 1',
        {"case_id": case_id},
    )
    if not rows:
        return None
    case = rows[0]

    # Enrich with related entities
    case["accused"] = get_case_accused_list(case_id)
    case["victims"] = get_case_victims_list(case_id)
    case["arrests"] = get_arrest_details(case_id)
    case["chargesheets"] = get_chargesheet(case_id)
    return case


def get_case_by_crime_number(crime_number: str) -> dict[str, Any] | None:
    """Fetch a case by its CrimeNumber / FIR number."""
    rows = _execute_query(
        f'SELECT * FROM "{CLEAN_SCHEMA}"."clean_CaseMaster" WHERE "CrimeNumber" = :cn LIMIT 1',
        {"cn": crime_number},
    )
    if not rows:
        return None
    case = rows[0]
    case_id = case.get("CaseMasterID")
    if case_id:
        case["accused"] = get_case_accused_list(case_id)
        case["victims"] = get_case_victims_list(case_id)
        case["arrests"] = get_arrest_details(case_id)
        case["chargesheets"] = get_chargesheet(case_id)
    return case


# ── Entity Lookups ────────────────────────────────────────────────────

def get_officer(officer_id: int) -> dict[str, Any] | None:
    """Fetch an officer/employee by EmployeeID."""
    rows = _execute_query(
        f'SELECT * FROM "{CLEAN_SCHEMA}"."clean_Employee" WHERE "EmployeeID" = :oid LIMIT 1',
        {"oid": officer_id},
    )
    return rows[0] if rows else None


def get_victim(victim_id: int) -> dict[str, Any] | None:
    """Fetch a victim by VictimMasterID."""
    rows = _execute_query(
        f'SELECT * FROM "{CLEAN_SCHEMA}"."clean_Victim" WHERE "VictimMasterID" = :vid LIMIT 1',
        {"vid": victim_id},
    )
    return rows[0] if rows else None


def get_accused(accused_id: int) -> dict[str, Any] | None:
    """Fetch an accused by AccusedMasterID."""
    rows = _execute_query(
        f'SELECT * FROM "{CLEAN_SCHEMA}"."clean_Accused" WHERE "AccusedMasterID" = :aid LIMIT 1',
        {"aid": accused_id},
    )
    return rows[0] if rows else None


def get_complainant(complainant_id: int) -> dict[str, Any] | None:
    """Fetch a complainant by ComplainantID."""
    rows = _execute_query(
        f'SELECT * FROM "{CLEAN_SCHEMA}"."clean_ComplainantDetails" WHERE "ComplainantID" = :cid LIMIT 1',
        {"cid": complainant_id},
    )
    return rows[0] if rows else None


# ── Relationship Lookups ──────────────────────────────────────────────

def get_case_accused_list(case_id: int) -> list[dict[str, Any]]:
    """Fetch all accused associated with a case."""
    return _execute_query(
        f'SELECT * FROM "{CLEAN_SCHEMA}"."clean_Accused" WHERE "CaseMasterID" = :cid',
        {"cid": case_id},
    )


def get_case_victims_list(case_id: int) -> list[dict[str, Any]]:
    """Fetch all victims associated with a case."""
    return _execute_query(
        f'SELECT * FROM "{CLEAN_SCHEMA}"."clean_Victim" WHERE "CaseMasterID" = :cid',
        {"cid": case_id},
    )


def get_arrest_details(case_id: int) -> list[dict[str, Any]]:
    """Fetch arrest records for a case."""
    return _execute_query(
        f'SELECT * FROM "{CLEAN_SCHEMA}"."clean_ArrestSurrender" WHERE "CaseMasterID" = :cid',
        {"cid": case_id},
    )


def get_chargesheet(case_id: int) -> list[dict[str, Any]]:
    """Fetch chargesheet details for a case."""
    return _execute_query(
        f'SELECT * FROM "{CLEAN_SCHEMA}"."clean_ChargesheetDetails" WHERE "CaseMasterID" = :cid',
        {"cid": case_id},
    )


def get_cases_by_station(station_id: int) -> list[dict[str, Any]]:
    """Fetch cases registered at a police station."""
    return _execute_query(
        f'SELECT * FROM "{CLEAN_SCHEMA}"."clean_CaseMaster" WHERE "PoliceStationID" = :sid ORDER BY "CaseMasterID" LIMIT 50',
        {"sid": station_id},
    )


def get_cases_by_district(district_id: int) -> list[dict[str, Any]]:
    """Fetch cases in a district."""
    return _execute_query(
        f"""
        SELECT cm.* FROM "{CLEAN_SCHEMA}"."clean_CaseMaster" cm
        JOIN "{CLEAN_SCHEMA}"."clean_Unit" u ON cm."PoliceStationID" = u."UnitID"
        WHERE u."DistrictID" = :did
        ORDER BY cm."CaseMasterID" LIMIT 50
        """,
        {"did": district_id},
    )


def get_act_sections(case_id: int) -> list[dict[str, Any]]:
    """Fetch act/section associations for a case."""
    return _execute_query(
        f'SELECT * FROM "{CLEAN_SCHEMA}"."clean_ActSectionAssociation" WHERE "CaseMasterID" = :cid',
        {"cid": case_id},
    )
