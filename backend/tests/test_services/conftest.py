"""
Fixtures for the tools layer: an in-memory replica of the real public schema
(column names + PostgreSQL types) and a fake query executor, so the mapper,
planner and router can be exercised without a live database.
"""

from __future__ import annotations

import re
from typing import Any

import pytest

from app.services.tools import postgres_tools
from app.services.tools.mapper import TABLE_SPECS, ColumnMapper, PhysicalColumn

# Mirrors the actual public schema of crime_db.
PUBLIC_SCHEMA: dict[str, list[tuple[str, str]]] = {
    "CaseMaster": [
        ("CaseMasterID", "bigint"), ("CrimeNo", "bigint"), ("CaseNo", "bigint"),
        ("CrimeRegistered Date", "text"), ("PolicePersonID", "bigint"), ("PoliceStationID", "bigint"),
        ("CaseCategoryID", "bigint"), ("GravityOffenceID", "bigint"), ("CrimeMajorHeadID", "bigint"),
        ("CrimeMinorHeadID", "bigint"), ("CaseStatusID", "bigint"), ("CourtID", "bigint"),
        ("IncidentFromDate", "text"), ("IncidentToDate", "text"), ("InfoReceivedPSDate", "text"),
        ("latitude", "double precision"), ("longitude", "double precision"), ("BriefFacts", "text"),
    ],
    "Employee": [
        ("EmployeeID", "bigint"), ("DistrictID", "bigint"), ("UnitID", "bigint"), ("RankID", "bigint"),
        ("DesignationID", "bigint"), ("KGID", "text"), ("FirstName", "text"), ("EmployeeDOB", "text"),
        ("GenderID", "bigint"), ("BloodGroupID", "bigint"), ("PhysicallyChallenged", "bigint"),
        ("AppointmentDate", "text"),
    ],
    "Accused": [
        ("AccusedMasterID", "bigint"), ("CaseMasterID", "bigint"), ("AccusedName", "text"),
        ("AgeYear", "bigint"), ("GenderID", "bigint"), ("PersonID", "text"),
    ],
    "Victim": [
        ("VictimMasterID", "bigint"), ("CaseMasterID", "bigint"), ("VictimName", "text"),
        ("AgeYear", "bigint"), ("GenderID", "bigint"), ("Victim Police", "bigint"),
    ],
    "ChargesheetDetails": [
        ("CSID", "bigint"), ("CaseMasterID", "bigint"), ("csdate", "text"), ("cstype", "text"),
        ("PolicePersonID", "bigint"),
    ],
    "ComplainantDetails": [
        ("ComplainantID", "bigint"), ("CaseMasterID", "bigint"), ("ComplainantName", "text"),
        ("AgeYear", "bigint"), ("OccupationID", "bigint"), ("ReligionID", "bigint"),
        ("CasteID", "bigint"), ("GenderID", "bigint"),
    ],
    "ArrestSurrender": [
        ("ArrestSurrenderID", "bigint"), ("CaseMasterID", "bigint"), ("ArrestSurrenderTypeID", "bigint"),
        ("ArrestSurrenderDate", "text"), ("IOID", "bigint"), ("CourtID", "bigint"),
        ("AccusedMasterID", "bigint"),
    ],
    "ActSectionAssociation": [
        ("CaseMasterID", "bigint"), ("ActID", "bigint"), ("SectionID", "bigint"),
    ],
}


def build_catalog(schema: str, tables: dict[str, list[tuple[str, str]]], prefix: str = "") -> dict:
    return {
        (schema, f"{prefix}{table}"): {name.lower(): PhysicalColumn(name, dtype) for name, dtype in cols}
        for table, cols in tables.items()
    }


def make_mapper(monkeypatch, catalog: dict, *, source_schema="public", clean_schema="clean", require_clean=False) -> ColumnMapper:
    """Create a ColumnMapper whose discovery step is replaced by the given catalog."""
    ColumnMapper.reset_instance()
    mapper = ColumnMapper.__new__(ColumnMapper)
    mapper.source_schema = source_schema
    mapper.clean_schema = clean_schema
    mapper.require_clean_schema = require_clean
    mapper.engine = None
    mapper.specs = TABLE_SPECS
    mapper._tables = {}
    mapper._catalog = {}
    mapper._initialized = False
    monkeypatch.setattr(mapper, "_load_catalog", lambda: setattr(mapper, "_catalog", catalog))
    ColumnMapper._instance = mapper
    return mapper


@pytest.fixture
def public_catalog() -> dict:
    return build_catalog("public", PUBLIC_SCHEMA)


@pytest.fixture
def fake_mapper(monkeypatch, public_catalog) -> ColumnMapper:
    mapper = make_mapper(monkeypatch, public_catalog)
    mapper.initialize()
    yield mapper
    ColumnMapper.reset_instance()


# ── Fake data (matches verified rows in crime_db) ─────────────────────

CASE_ROWS = [
    {"CaseMasterID": 1, "CaseNo": 202300001, "CrimeNo": 100170200202300001,
     "PolicePersonID": 5313, "PoliceStationID": 200, "CaseStatusID": 3},
    {"CaseMasterID": 2, "CaseNo": 202300002, "CrimeNo": 100170200202300002,
     "PolicePersonID": 5001, "PoliceStationID": 201, "CaseStatusID": 1},
]
EMPLOYEE_ROWS = [
    {"EmployeeID": 5313, "KGID": "KG10313", "FirstName": "Oliver", "DesignationID": 7, "RankID": 4},
    {"EmployeeID": 5001, "KGID": "KG10001", "FirstName": "Asha", "DesignationID": 5, "RankID": 3},
]
ACCUSED_ROWS = [
    {"AccusedMasterID": i, "CaseMasterID": case_id, "AccusedName": "Fiyaz Saran", "AgeYear": 55, "GenderID": 1, "PersonID": f"A{i}"}
    for i, case_id in enumerate([1, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14], start=1)
] + [
    {"AccusedMasterID": 99, "CaseMasterID": 2, "AccusedName": "Ravi Kumar", "AgeYear": 31, "GenderID": 1, "PersonID": "A99"},
]
VICTIM_ROWS = [
    {"VictimMasterID": 1, "CaseMasterID": 1, "VictimName": "Meera", "AgeYear": 29, "GenderID": 2},
]


class FakeDB:
    """Replaces postgres_tools._execute_query; answers from in-memory rows."""

    TABLES = {
        "CaseMaster": CASE_ROWS,
        "Employee": EMPLOYEE_ROWS,
        "Accused": ACCUSED_ROWS,
        "Victim": VICTIM_ROWS,
        "ChargesheetDetails": [],
        "ArrestSurrender": [],
        "ActSectionAssociation": [],
        "ComplainantDetails": [],
    }

    def __init__(self):
        self.queries: list[tuple[str, dict[str, Any], str]] = []

    def __call__(self, sql: str, params: dict[str, Any], *, logical_table: str, purpose: str) -> list[dict]:
        self.queries.append((sql, params, logical_table))
        assert "SELECT *" not in sql.upper(), "tools must not use SELECT *"
        assert f'"public"."{logical_table}"' in sql

        rows = self.TABLES[logical_table]
        where = re.search(r'WHERE\s+(?:lower\()?"([^"]+)"\)?\s*=\s*(?:lower\()?:(\w+)', sql)
        if where:
            column, param = where.group(1), where.group(2)
            value = params[param]
            if "lower(" in sql:
                rows = [r for r in rows if str(r.get(column, "")).lower() == str(value).lower()]
            else:
                rows = [r for r in rows if r.get(column) == value]

        limit = re.search(r"LIMIT\s+(\d+)", sql)
        if limit:
            rows = rows[: int(limit.group(1))]

        selected = re.findall(r'"([^"]+)"', sql.split(" FROM ")[0])
        return [{c: r.get(c) for c in selected} for r in rows]

    @property
    def tables_queried(self) -> list[str]:
        return [q[2] for q in self.queries]


@pytest.fixture
def fake_db(monkeypatch, fake_mapper) -> FakeDB:
    db = FakeDB()
    monkeypatch.setattr(postgres_tools, "_execute_query", db)
    return db
