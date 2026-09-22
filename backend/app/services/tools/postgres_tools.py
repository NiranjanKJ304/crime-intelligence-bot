"""
PostgreSQL Tool Functions.

Every database operation is a parameterised, pre-defined Python function.
The LLM NEVER generates SQL — it can only call these functions by name.

All table and column references go through ColumnMapper, which resolves
logical names ("CaseMaster", "case_number") to whatever physical schema,
table and column actually exist in the configured database. Identifier
values are validated against the physical column type before any SQL runs.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import text

from app.core.database import get_engine
from app.services.tools.dtos import (
    AccusedDTO,
    CaseLookupDTO,
    ChargesheetDTO,
    OfficerDTO,
    VictimDTO,
)
from app.services.tools.exceptions import DatabaseQueryError
from app.services.tools.mapper import ColumnMapper
from app.services.tools.tracing import trace

logger = logging.getLogger(__name__)


# ── Internal helpers ──────────────────────────────────────────────────

def _mapper() -> ColumnMapper:
    return ColumnMapper.get_instance()


def _q(column: str) -> str:
    """Quote a physical identifier."""
    return '"' + column.replace('"', '""') + '"'


def _execute_query(
    query_str: str,
    params: dict[str, Any],
    *,
    logical_table: str,
    purpose: str,
) -> list[dict[str, Any]]:
    """Execute a parameterised SQL query and return rows as dicts."""
    engine = get_engine()
    try:
        with engine.connect() as conn:
            result = conn.execute(text(query_str), params)
            keys = list(result.keys())
            rows = [dict(zip(keys, row)) for row in result.fetchall()]
    except Exception as exc:
        logger.exception("PostgreSQL query failed (%s on %s)", purpose, logical_table)
        raise DatabaseQueryError(f"Query '{purpose}' failed on {logical_table}: {exc}") from exc

    trace(
        logger,
        f"SQL {purpose}",
        logical_table=logical_table,
        physical_table=_mapper().get_table(logical_table),
        sql=" ".join(query_str.split()),
        parameters=params,
        row_count=len(rows),
    )
    return rows


def _select_columns(logical_table: str, logical_columns: list[str]) -> tuple[str, dict[str, str]]:
    """
    Build an explicit SELECT column list for the logical columns that exist.

    Returns (sql_fragment, {logical: physical}) — optional columns that are
    not present in the physical table are silently skipped.
    """
    mapper = _mapper()
    mapping: dict[str, str] = {}
    for logical in logical_columns:
        if mapper.has_column(logical_table, logical):
            mapping[logical] = mapper.get_column(logical_table, logical)
    fragment = ", ".join(_q(physical) for physical in mapping.values())
    return fragment, mapping


def _identifier_filter(logical_table: str, logical_column: str, value: Any) -> tuple[str, dict[str, Any], str]:
    """Return (where_clause, params, physical_column) with the value coerced to the column type."""
    mapper = _mapper()
    physical = mapper.get_column(logical_table, logical_column)
    coerced = mapper.coerce_value(logical_table, logical_column, value)
    trace(
        logger,
        "Identifier resolution",
        logical_table=logical_table,
        physical_table=mapper.get_table(logical_table),
        logical_column=logical_column,
        physical_column=physical,
        value=coerced,
        value_type=type(coerced).__name__,
    )
    return f"{_q(physical)} = :val", {"val": coerced}, physical


def _pick(row: dict[str, Any], mapping: dict[str, str], logical: str, default: Any = None) -> Any:
    physical = mapping.get(logical)
    if physical is None:
        return default
    value = row.get(physical)
    return default if value is None else value


def _fetch_rows(
    logical_table: str,
    logical_columns: list[str],
    filter_column: str,
    value: Any,
    *,
    purpose: str,
    order_by: str | None = None,
    limit: int | None = None,
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    mapper = _mapper()
    select_sql, mapping = _select_columns(logical_table, logical_columns)
    where_sql, params, _ = _identifier_filter(logical_table, filter_column, value)
    sql = f"SELECT {select_sql} FROM {mapper.get_table(logical_table)} WHERE {where_sql}"
    if order_by and order_by in mapping:
        sql += f" ORDER BY {_q(mapping[order_by])}"
    if limit:
        sql += f" LIMIT {int(limit)}"
    rows = _execute_query(sql, params, logical_table=logical_table, purpose=purpose)
    return rows, mapping


# ── Case lookups (compact) ────────────────────────────────────────────

_CASE_COLUMNS = ["case_id", "case_number", "crime_number", "police_person_id", "station_id", "status"]


def _row_to_case(row: dict[str, Any], mapping: dict[str, str]) -> CaseLookupDTO:
    return CaseLookupDTO(
        case_id=_pick(row, mapping, "case_id"),
        case_number=_pick(row, mapping, "case_number", ""),
        crime_number=_pick(row, mapping, "crime_number"),
        police_person_id=_pick(row, mapping, "police_person_id"),
        station_id=_pick(row, mapping, "station_id"),
        status=_pick(row, mapping, "status"),
    )


def get_case_lookup(
    case_id: int | None = None,
    case_number: int | str | None = None,
    crime_number: int | str | None = None,
) -> CaseLookupDTO | None:
    """
    Lightweight case lookup returning only IDs and key metadata.

    Exactly one identifier is used, in priority order case_id → case_number
    → crime_number. CaseNo, CrimeNo and CaseMasterID are distinct columns and
    are never interchanged.
    """
    if case_id is not None:
        filter_col, value = "case_id", case_id
    elif case_number is not None:
        filter_col, value = "case_number", case_number
    elif crime_number is not None:
        filter_col, value = "crime_number", crime_number
    else:
        return None

    rows, mapping = _fetch_rows("CaseMaster", _CASE_COLUMNS, filter_col, value, purpose="get_case_lookup", limit=1)
    if not rows:
        return None
    return _row_to_case(rows[0], mapping)


# ── Officer lookups ───────────────────────────────────────────────────

_OFFICER_COLUMNS = ["employee_id", "first_name", "kgid", "designation", "rank"]


def get_officer_compact(employee_id: int) -> OfficerDTO | None:
    """Fetch minimal officer details by EmployeeID."""
    rows, mapping = _fetch_rows("Employee", _OFFICER_COLUMNS, "employee_id", employee_id, purpose="get_officer_compact", limit=1)
    if not rows:
        return None
    row = rows[0]
    return OfficerDTO(
        employee_id=_pick(row, mapping, "employee_id"),
        first_name=_pick(row, mapping, "first_name", "Unknown"),
        kgid=_pick(row, mapping, "kgid"),
        designation=_pick(row, mapping, "designation"),
        rank=_pick(row, mapping, "rank"),
    )


# ── Victim / Accused lookups ──────────────────────────────────────────

_VICTIM_COLUMNS = ["victim_id", "case_master_id", "victim_name", "age", "gender"]
_ACCUSED_COLUMNS = ["accused_id", "case_master_id", "accused_name", "age", "gender", "person_id"]


def _row_to_victim(row: dict[str, Any], mapping: dict[str, str]) -> VictimDTO:
    return VictimDTO(
        victim_id=_pick(row, mapping, "victim_id"),
        case_id=_pick(row, mapping, "case_master_id"),
        name=_pick(row, mapping, "victim_name", "Unknown"),
        age=_pick(row, mapping, "age"),
        gender=_pick(row, mapping, "gender"),
    )


def _row_to_accused(row: dict[str, Any], mapping: dict[str, str]) -> AccusedDTO:
    return AccusedDTO(
        accused_id=_pick(row, mapping, "accused_id"),
        case_id=_pick(row, mapping, "case_master_id"),
        name=_pick(row, mapping, "accused_name", "Unknown"),
        age=_pick(row, mapping, "age"),
        gender=_pick(row, mapping, "gender"),
        person_id=_pick(row, mapping, "person_id"),
    )


def get_victim_compact(victim_id: int) -> VictimDTO | None:
    rows, mapping = _fetch_rows("Victim", _VICTIM_COLUMNS, "victim_id", victim_id, purpose="get_victim_compact", limit=1)
    return _row_to_victim(rows[0], mapping) if rows else None


def get_accused_compact(accused_id: int) -> AccusedDTO | None:
    rows, mapping = _fetch_rows("Accused", _ACCUSED_COLUMNS, "accused_id", accused_id, purpose="get_accused_compact", limit=1)
    return _row_to_accused(rows[0], mapping) if rows else None


def get_case_victims_list(case_id: int) -> list[VictimDTO]:
    """All victims recorded against a CaseMasterID."""
    rows, mapping = _fetch_rows("Victim", _VICTIM_COLUMNS, "case_master_id", case_id, purpose="get_case_victims_list", order_by="victim_id")
    return [_row_to_victim(r, mapping) for r in rows]


def get_case_accused_list(case_id: int) -> list[AccusedDTO]:
    """All accused recorded against a CaseMasterID."""
    rows, mapping = _fetch_rows("Accused", _ACCUSED_COLUMNS, "case_master_id", case_id, purpose="get_case_accused_list", order_by="accused_id")
    return [_row_to_accused(r, mapping) for r in rows]


def find_accused_by_name(name: str, limit: int = 50) -> list[AccusedDTO]:
    """
    All accused records matching a name (case-insensitive exact match).

    A name is NOT a unique identity — the same person name can appear on many
    cases — so every match is returned with its AccusedMasterID, CaseMasterID
    and PersonID rather than picking one arbitrarily.
    """
    cleaned = (name or "").strip()
    if not cleaned:
        return []
    mapper = _mapper()
    select_sql, mapping = _select_columns("Accused", _ACCUSED_COLUMNS)
    name_col = _q(mapper.get_column("Accused", "accused_name"))
    order_col = _q(mapper.get_column("Accused", "accused_id"))
    sql = (
        f"SELECT {select_sql} FROM {mapper.get_table('Accused')} "
        f"WHERE lower({name_col}) = lower(:name) ORDER BY {order_col} LIMIT {int(limit)}"
    )
    rows = _execute_query(sql, {"name": cleaned}, logical_table="Accused", purpose="find_accused_by_name")
    return [_row_to_accused(r, mapping) for r in rows]


# ── Chargesheet / arrests / sections ──────────────────────────────────

def get_chargesheet_status(case_id: int) -> ChargesheetDTO:
    rows, mapping = _fetch_rows(
        "ChargesheetDetails", ["chargesheet_id", "case_master_id", "date", "court_name"],
        "case_master_id", case_id, purpose="get_chargesheet_status", limit=1,
    )
    if not rows:
        return ChargesheetDTO(filed=False, date=None, court_name=None)
    row = rows[0]
    date_val = _pick(row, mapping, "date")
    return ChargesheetDTO(
        filed=True,
        date=str(date_val) if date_val is not None else None,
        court_name=_pick(row, mapping, "court_name"),
    )


def _fetch_full_rows(logical_table: str, filter_column: str, value: Any, *, purpose: str, limit: int | None = None) -> list[dict[str, Any]]:
    """Full-record fetch with an explicit column list derived from the catalog."""
    mapper = _mapper()
    columns = ", ".join(_q(c) for c in mapper.get_all_columns(logical_table))
    where_sql, params, _ = _identifier_filter(logical_table, filter_column, value)
    sql = f"SELECT {columns} FROM {mapper.get_table(logical_table)} WHERE {where_sql}"
    if limit:
        sql += f" LIMIT {int(limit)}"
    return _execute_query(sql, params, logical_table=logical_table, purpose=purpose)


def get_arrest_details(case_id: int) -> list[dict[str, Any]]:
    return _fetch_full_rows("ArrestSurrender", "case_master_id", case_id, purpose="get_arrest_details")


def get_chargesheet(case_id: int) -> list[dict[str, Any]]:
    return _fetch_full_rows("ChargesheetDetails", "case_master_id", case_id, purpose="get_chargesheet")


def get_act_sections(case_id: int) -> list[dict[str, Any]]:
    return _fetch_full_rows("ActSectionAssociation", "case_master_id", case_id, purpose="get_act_sections")


# ── Full-record lookups (verbose; not used on the chat hot path) ──────

def _enrich_case(case: dict[str, Any]) -> dict[str, Any]:
    case_id = case.get(_mapper().get_column("CaseMaster", "case_id"))
    if case_id is not None:
        case["accused"] = [a.to_dict() for a in get_case_accused_list(case_id)]
        case["victims"] = [v.to_dict() for v in get_case_victims_list(case_id)]
        case["arrests"] = get_arrest_details(case_id)
        case["chargesheets"] = get_chargesheet(case_id)
    return case


def get_case_by_id(case_id: int) -> dict[str, Any] | None:
    rows = _fetch_full_rows("CaseMaster", "case_id", case_id, purpose="get_case_by_id", limit=1)
    return _enrich_case(rows[0]) if rows else None


def get_case_by_number(case_number: int | str) -> dict[str, Any] | None:
    rows = _fetch_full_rows("CaseMaster", "case_number", case_number, purpose="get_case_by_number", limit=1)
    return _enrich_case(rows[0]) if rows else None


def get_case_by_crime_number(crime_number: int | str) -> dict[str, Any] | None:
    rows = _fetch_full_rows("CaseMaster", "crime_number", crime_number, purpose="get_case_by_crime_number", limit=1)
    return _enrich_case(rows[0]) if rows else None


def get_officer(employee_id: int) -> dict[str, Any] | None:
    rows = _fetch_full_rows("Employee", "employee_id", employee_id, purpose="get_officer", limit=1)
    return rows[0] if rows else None


def get_victim(victim_id: int) -> dict[str, Any] | None:
    rows = _fetch_full_rows("Victim", "victim_id", victim_id, purpose="get_victim", limit=1)
    return rows[0] if rows else None


def get_accused(accused_id: int) -> dict[str, Any] | None:
    rows = _fetch_full_rows("Accused", "accused_id", accused_id, purpose="get_accused", limit=1)
    return rows[0] if rows else None


def get_complainant(complainant_id: int) -> dict[str, Any] | None:
    rows = _fetch_full_rows("ComplainantDetails", "complainant_id", complainant_id, purpose="get_complainant", limit=1)
    return rows[0] if rows else None
