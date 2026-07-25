"""
PostgreSQL Tool Functions.

Every database operation is a parameterised, pre-defined Python function.
The LLM NEVER generates SQL — it can only call these functions by name.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import text

from app.core.database import get_engine
from app.services.tools.mapper import ColumnMapper
from app.services.tools.dtos import (
    CaseLookupDTO,
    OfficerDTO,
    VictimDTO,
    AccusedDTO,
    ChargesheetDTO
)

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
    """Fetch a case by its internal ID."""
    mapper = ColumnMapper.get_instance()
    col = mapper.get_column("clean_CaseMaster", "case_id")
    
    rows = _execute_query(
        f'SELECT * FROM "{CLEAN_SCHEMA}"."clean_CaseMaster" WHERE "{col}" = :case_id LIMIT 1',
        {"case_id": case_id},
    )
    if not rows:
        return None
    case = rows[0]

    case["accused"] = get_case_accused_list(case_id)
    case["victims"] = get_case_victims_list(case_id)
    case["arrests"] = get_arrest_details(case_id)
    case["chargesheets"] = get_chargesheet(case_id)
    return case


def get_case_by_crime_number(crime_number: str) -> dict[str, Any] | None:
    """Fetch a case by its CrimeNumber / FIR number."""
    mapper = ColumnMapper.get_instance()
    col = mapper.get_column("clean_CaseMaster", "crime_number")
    id_col = mapper.get_column("clean_CaseMaster", "case_id")
    
    rows = _execute_query(
        f'SELECT * FROM "{CLEAN_SCHEMA}"."clean_CaseMaster" WHERE "{col}" = :cn LIMIT 1',
        {"cn": crime_number},
    )
    if not rows:
        return None
    case = rows[0]
    case_id = case.get(id_col)
    if case_id:
        case["accused"] = get_case_accused_list(case_id)
        case["victims"] = get_case_victims_list(case_id)
        case["arrests"] = get_arrest_details(case_id)
        case["chargesheets"] = get_chargesheet(case_id)
    return case


def get_case_by_number(case_number: str) -> dict[str, Any] | None:
    """Fetch a case by its Case Number."""
    mapper = ColumnMapper.get_instance()
    col = mapper.get_column("clean_CaseMaster", "case_number")
    id_col = mapper.get_column("clean_CaseMaster", "case_id")
    
    rows = _execute_query(
        f'SELECT * FROM "{CLEAN_SCHEMA}"."clean_CaseMaster" WHERE "{col}" = :cn LIMIT 1',
        {"cn": case_number},
    )
    if not rows:
        return None
    case = rows[0]
    case_id = case.get(id_col)
    if case_id:
        case["accused"] = get_case_accused_list(case_id)
        case["victims"] = get_case_victims_list(case_id)
        case["arrests"] = get_arrest_details(case_id)
        case["chargesheets"] = get_chargesheet(case_id)
    return case


# ── Compact Projection Lookups ────────────────────────────────────────

def get_case_lookup(case_id: int | None = None, case_number: str | None = None, crime_number: str | None = None) -> CaseLookupDTO | None:
    """Lightweight case lookup returning only IDs and key metadata."""
    mapper = ColumnMapper.get_instance()
    
    id_col = mapper.get_column("clean_CaseMaster", "case_id")
    cno_col = mapper.get_column("clean_CaseMaster", "case_number")
    crno_col = mapper.get_column("clean_CaseMaster", "crime_number")
    # Explicitly use column mappings
    
    where_clause = ""
    params = {}
    if case_id:
        where_clause = f'"{id_col}" = :val'
        params = {"val": case_id}
    elif case_number:
        where_clause = f'"{cno_col}" = :val'
        params = {"val": case_number}
    elif crime_number:
        where_clause = f'"{crno_col}" = :val'
        params = {"val": crime_number}
    else:
        return None
        

    if not rows:
        return None
        
    row = rows[0]
    try:
        officer_col = mapper.get_column("clean_CaseMaster", "officer_id")
    except:
        officer_col = "PolicePersonID"
        
    try:
        station_col = mapper.get_column("clean_CaseMaster", "station_id")
    except:
        station_col = "PoliceStationID"
        
    try:
        status_col = mapper.get_column("clean_CaseMaster", "status")
    except:
        status_col = "Status"
        
    cols = f'"{id_col}", "{cno_col}", "{crno_col}", "{officer_col}", "{station_col}", "{status_col}"'
        
    rows = _execute_query(f'SELECT {cols} FROM "{CLEAN_SCHEMA}"."clean_CaseMaster" WHERE {where_clause} LIMIT 1', params)
    if not rows:
        return None
        
    row = rows[0]
    
    return CaseLookupDTO(
        case_id=row.get(id_col, 0),
        case_number=row.get(cno_col, ""),
        crime_number=row.get(crno_col, ""),
        officer_id=row.get(officer_col) if row.get(officer_col) else None,
        station_id=row.get(station_col) if row.get(station_col) else None,
        status=row.get(status_col)
    )



# ── Entity Lookups ────────────────────────────────────────────────────

def get_officer(officer_id: int) -> dict[str, Any] | None:
    """Fetch an officer/employee by their ID."""
    mapper = ColumnMapper.get_instance()
    col = mapper.get_column("clean_Employee", "officer_id")
    
    rows = _execute_query(
        f'SELECT * FROM "{CLEAN_SCHEMA}"."clean_Employee" WHERE "{col}" = :oid LIMIT 1',
        {"oid": officer_id},
    )
    return rows[0] if rows else None


def get_victim(victim_id: int) -> dict[str, Any] | None:
    """Fetch a victim by their ID."""
    mapper = ColumnMapper.get_instance()
    col = mapper.get_column("clean_Victim", "victim_id")
    
    rows = _execute_query(
        f'SELECT * FROM "{CLEAN_SCHEMA}"."clean_Victim" WHERE "{col}" = :vid LIMIT 1',
        {"vid": victim_id},
    )
    return rows[0] if rows else None


def get_accused(accused_id: int) -> dict[str, Any] | None:
    """Fetch an accused by their ID."""
    mapper = ColumnMapper.get_instance()
    col = mapper.get_column("clean_Accused", "accused_id")
    
    rows = _execute_query(
        f'SELECT * FROM "{CLEAN_SCHEMA}"."clean_Accused" WHERE "{col}" = :aid LIMIT 1',
        {"aid": accused_id},
    )
    return rows[0] if rows else None


def get_complainant(complainant_id: int) -> dict[str, Any] | None:
    """Fetch a complainant by their ID."""
    mapper = ColumnMapper.get_instance()
    col = mapper.get_column("clean_ComplainantDetails", "complainant_id")
    
    rows = _execute_query(
        f'SELECT * FROM "{CLEAN_SCHEMA}"."clean_ComplainantDetails" WHERE "{col}" = :cid LIMIT 1',
        {"cid": complainant_id},
    )
    return rows[0] if rows else None


# ── Compact Entity Lookups ──────────────────────────────────────────

def get_officer_compact(officer_id: int) -> OfficerDTO | None:
    """Fetch minimal officer details."""
    mapper = ColumnMapper.get_instance()
    col = mapper.get_column("clean_Employee", "officer_id")
    
    name_col = mapper.get_column("clean_Employee", "name")
    kgid_col = mapper.get_column("clean_Employee", "kgid")
    desig_col = mapper.get_column("clean_Employee", "designation")
    rank_col = mapper.get_column("clean_Employee", "rank")
    
    cols = f'"{col}", "{name_col}", "{kgid_col}", "{desig_col}", "{rank_col}"'
    rows = _execute_query(f'SELECT {cols} FROM "{CLEAN_SCHEMA}"."clean_Employee" WHERE "{col}" = :oid LIMIT 1', {"oid": officer_id})
    if not rows:
        return None
    row = rows[0]
    return OfficerDTO(
        officer_id=officer_id,
        name=row.get(name_col, "Unknown"),
        kgid=row.get(kgid_col),
        designation=row.get(desig_col),
        rank=row.get(rank_col)
    )


def get_victim_compact(victim_id: int) -> VictimDTO | None:
    """Fetch minimal victim details."""
    mapper = ColumnMapper.get_instance()
    col = mapper.get_column("clean_Victim", "victim_id")
    
    name_col = mapper.get_column("clean_Victim", "name")
    age_col = mapper.get_column("clean_Victim", "age")
    gender_col = mapper.get_column("clean_Victim", "gender")
    
    cols = f'"{col}", "{name_col}", "{age_col}", "{gender_col}"'
    rows = _execute_query(f'SELECT {cols} FROM "{CLEAN_SCHEMA}"."clean_Victim" WHERE "{col}" = :vid LIMIT 1', {"vid": victim_id})
    if not rows:
        return None
    row = rows[0]
    return VictimDTO(
        victim_id=victim_id,
        name=row.get(name_col, "Unknown"),
        age=row.get(age_col),
        gender=row.get(gender_col)
    )


def get_accused_compact(accused_id: int) -> AccusedDTO | None:
    """Fetch minimal accused details."""
    mapper = ColumnMapper.get_instance()
    col = mapper.get_column("clean_Accused", "accused_id")
    
    name_col = mapper.get_column("clean_Accused", "name")
    age_col = mapper.get_column("clean_Accused", "age")
    gender_col = mapper.get_column("clean_Accused", "gender")
    
    cols = f'"{col}", "{name_col}", "{age_col}", "{gender_col}"'
    rows = _execute_query(f'SELECT {cols} FROM "{CLEAN_SCHEMA}"."clean_Accused" WHERE "{col}" = :aid LIMIT 1', {"aid": accused_id})
    if not rows:
        return None
    row = rows[0]
    return AccusedDTO(
        accused_id=accused_id,
        name=row.get(name_col, "Unknown"),
        age=row.get(age_col),
        gender=row.get(gender_col)
    )



# ── Relationship Lookups ──────────────────────────────────────────────

def get_case_accused_list(case_id: int) -> list[dict[str, Any]]:
    """Fetch all accused associated with a case."""
    mapper = ColumnMapper.get_instance()
    col = mapper.get_column("clean_Accused", "case_id")
    
    return _execute_query(
        f'SELECT * FROM "{CLEAN_SCHEMA}"."clean_Accused" WHERE "{col}" = :cid',
        {"cid": case_id},
    )


def get_case_victims_list(case_id: int) -> list[dict[str, Any]]:
    """Fetch all victims associated with a case."""
    mapper = ColumnMapper.get_instance()
    col = mapper.get_column("clean_Victim", "case_id")
    
    return _execute_query(
        f'SELECT * FROM "{CLEAN_SCHEMA}"."clean_Victim" WHERE "{col}" = :cid',
        {"cid": case_id},
    )


def get_arrest_details(case_id: int) -> list[dict[str, Any]]:
    """Fetch arrest records for a case."""
    mapper = ColumnMapper.get_instance()
    col = mapper.get_column("clean_ArrestSurrender", "case_id")
    
    return _execute_query(
        f'SELECT * FROM "{CLEAN_SCHEMA}"."clean_ArrestSurrender" WHERE "{col}" = :cid',
        {"cid": case_id},
    )


def get_chargesheet(case_id: int) -> list[dict[str, Any]]:
    """Fetch chargesheet details for a case."""
    mapper = ColumnMapper.get_instance()
    col = mapper.get_column("clean_ChargesheetDetails", "case_id")
    
    return _execute_query(
        f'SELECT * FROM "{CLEAN_SCHEMA}"."clean_ChargesheetDetails" WHERE "{col}" = :cid',
        {"cid": case_id},
    )

def get_chargesheet_status(case_id: int) -> ChargesheetDTO | None:
    """Fetch minimal chargesheet status."""
    mapper = ColumnMapper.get_instance()
    col = mapper.get_column("clean_ChargesheetDetails", "case_id")
    date_col = mapper.get_column("clean_ChargesheetDetails", "date")
    court_col = mapper.get_column("clean_ChargesheetDetails", "court_name")
    
    cols = f'"{col}", "{date_col}", "{court_col}"'
    rows = _execute_query(
        f'SELECT {cols} FROM "{CLEAN_SCHEMA}"."clean_ChargesheetDetails" WHERE "{col}" = :cid LIMIT 1',
        {"cid": case_id},
    )
    
    if not rows:
        return ChargesheetDTO(filed=False, date=None, court_name=None)
        
    row = rows[0]
    return ChargesheetDTO(
        filed=True,
        date=row.get(date_col),
        court_name=row.get(court_col)
    )



def get_cases_by_station(station_id: int) -> list[dict[str, Any]]:
    """Fetch cases registered at a police station."""
    mapper = ColumnMapper.get_instance()
    col = mapper.get_column("clean_CaseMaster", "station_id")
    id_col = mapper.get_column("clean_CaseMaster", "case_id")
    
    return _execute_query(
        f'SELECT * FROM "{CLEAN_SCHEMA}"."clean_CaseMaster" WHERE "{col}" = :sid ORDER BY "{id_col}" LIMIT 50',
        {"sid": station_id},
    )


def get_cases_by_district(district_id: int) -> list[dict[str, Any]]:
    """Fetch cases in a district."""
    mapper = ColumnMapper.get_instance()
    col = mapper.get_column("clean_CaseMaster", "station_id")
    id_col = mapper.get_column("clean_CaseMaster", "case_id")
    
    return _execute_query(
        f"""
        SELECT cm.* FROM "{CLEAN_SCHEMA}"."clean_CaseMaster" cm
        JOIN "{CLEAN_SCHEMA}"."clean_Unit" u ON cm."{col}" = u."UnitID"
        WHERE u."DistrictID" = :did
        ORDER BY cm."{id_col}" LIMIT 50
        """,
        {"did": district_id},
    )


def get_act_sections(case_id: int) -> list[dict[str, Any]]:
    """Fetch act/section associations for a case."""
    mapper = ColumnMapper.get_instance()
    col = mapper.get_column("clean_ActSectionAssociation", "case_id")
    
    return _execute_query(
        f'SELECT * FROM "{CLEAN_SCHEMA}"."clean_ActSectionAssociation" WHERE "{col}" = :cid',
        {"cid": case_id},
    )

