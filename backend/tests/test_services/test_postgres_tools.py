"""
Unit tests for the PostgreSQL tool functions (mapper-driven, fake executor).
"""

import pytest

from app.services.tools import postgres_tools
from app.services.tools.dtos import AccusedDTO, CaseLookupDTO, OfficerDTO
from app.services.tools.exceptions import IdentifierValidationError


class TestCaseLookup:
    def test_lookup_by_case_number(self, fake_db):
        case = postgres_tools.get_case_lookup(case_number=202300001)
        assert isinstance(case, CaseLookupDTO)
        assert case.case_id == 1
        assert case.case_number == 202300001
        assert case.crime_number == 100170200202300001
        assert case.police_person_id == 5313

        sql, params, table = fake_db.queries[-1]
        assert table == "CaseMaster"
        assert '"CaseNo" = :val' in sql
        assert params == {"val": 202300001}
        assert isinstance(params["val"], int)
        assert "SELECT *" not in sql
        assert '"CaseMasterID"' in sql and '"PolicePersonID"' in sql
        assert "LIMIT 1" in sql

    def test_lookup_by_case_number_as_string_is_coerced(self, fake_db):
        case = postgres_tools.get_case_lookup(case_number="202300001")
        assert case.case_id == 1
        assert fake_db.queries[-1][1] == {"val": 202300001}

    def test_lookup_by_crime_number_uses_crime_column(self, fake_db):
        case = postgres_tools.get_case_lookup(crime_number=100170200202300001)
        assert case.case_id == 1
        assert '"CrimeNo" = :val' in fake_db.queries[-1][0]

    def test_case_number_and_crime_number_are_not_interchangeable(self, fake_db):
        assert postgres_tools.get_case_lookup(case_number=100170200202300001) is None
        assert postgres_tools.get_case_lookup(crime_number=202300001) is None

    def test_lookup_by_case_id(self, fake_db):
        case = postgres_tools.get_case_lookup(case_id=1)
        assert case.case_number == 202300001
        assert '"CaseMasterID" = :val' in fake_db.queries[-1][0]

    def test_unknown_case_returns_none(self, fake_db):
        assert postgres_tools.get_case_lookup(case_number=999999999) is None

    def test_invalid_identifier_never_reaches_sql(self, fake_db):
        with pytest.raises(IdentifierValidationError):
            postgres_tools.get_case_lookup(case_number="CR/2023/001")
        assert fake_db.queries == []

    def test_no_identifier_returns_none(self, fake_db):
        assert postgres_tools.get_case_lookup() is None
        assert fake_db.queries == []


class TestOfficerLookup:
    def test_officer_by_employee_id(self, fake_db):
        officer = postgres_tools.get_officer_compact(5313)
        assert isinstance(officer, OfficerDTO)
        assert officer.employee_id == 5313
        assert officer.kgid == "KG10313"
        assert officer.first_name == "Oliver"
        assert officer.designation == 7

        sql, params, table = fake_db.queries[-1]
        assert table == "Employee"
        assert '"EmployeeID" = :val' in sql
        assert params == {"val": 5313}
        assert '"KGID"' in sql and '"FirstName"' in sql and '"DesignationID"' in sql

    def test_unknown_officer_returns_none(self, fake_db):
        assert postgres_tools.get_officer_compact(424242) is None


class TestAccusedLookups:
    def test_find_accused_by_name_returns_all_records(self, fake_db):
        matches = postgres_tools.find_accused_by_name("Fiyaz Saran")
        assert len(matches) == 15
        assert all(isinstance(m, AccusedDTO) for m in matches)
        assert {m.accused_id for m in matches} == set(range(1, 16))
        assert matches[0].person_id == "A1" and matches[0].case_id == 1
        sql, params, _ = fake_db.queries[-1]
        assert params == {"name": "Fiyaz Saran"}
        assert "lower(" in sql

    def test_find_accused_by_name_is_case_insensitive(self, fake_db):
        assert len(postgres_tools.find_accused_by_name("fiyaz saran")) == 15

    def test_find_accused_by_name_empty(self, fake_db):
        assert postgres_tools.find_accused_by_name("") == []
        assert postgres_tools.find_accused_by_name("Nobody Here") == []

    def test_case_accused_list_uses_case_master_id(self, fake_db):
        accused = postgres_tools.get_case_accused_list(1)
        assert [a.accused_id for a in accused] == [1, 2]
        assert '"CaseMasterID" = :val' in fake_db.queries[-1][0]
