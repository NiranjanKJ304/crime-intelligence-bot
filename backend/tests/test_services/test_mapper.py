"""
Tests for ColumnMapper: logical -> physical resolution against the real
public schema layout, fallback rules, type coercion and diagnostics.
"""

import pytest

from app.services.tools.exceptions import IdentifierValidationError, MappingError
from tests.test_services.conftest import PUBLIC_SCHEMA, build_catalog, make_mapper


class TestTableResolution:
    def test_resolves_public_tables_when_clean_schema_missing(self, fake_mapper):
        assert fake_mapper.get_physical_table("CaseMaster") == ("public", "CaseMaster")
        assert fake_mapper.get_physical_table("Employee") == ("public", "Employee")
        assert fake_mapper.get_physical_table("Accused") == ("public", "Accused")
        assert fake_mapper.get_table("CaseMaster") == '"public"."CaseMaster"'

    def test_prefers_clean_tables_when_present(self, monkeypatch, public_catalog):
        catalog = dict(public_catalog)
        catalog.update(build_catalog("clean", {"CaseMaster": PUBLIC_SCHEMA["CaseMaster"]}, prefix="clean_"))
        mapper = make_mapper(monkeypatch, catalog)
        mapper.initialize()
        assert mapper.get_physical_table("CaseMaster") == ("clean", "clean_CaseMaster")
        assert mapper.get_physical_table("Employee") == ("public", "Employee")

    def test_require_clean_schema_reports_etl_error(self, monkeypatch, public_catalog):
        mapper = make_mapper(monkeypatch, public_catalog, require_clean=True)
        with pytest.raises(MappingError) as exc:
            mapper.initialize()
        assert "REQUIRE_CLEAN_SCHEMA" in str(exc.value)
        assert "clean.clean_CaseMaster" in exc.value.diagnostics["expected_physical_tables"]
        assert "public.CaseMaster" in exc.value.diagnostics["available_physical_tables"]

    def test_missing_table_diagnostics(self, monkeypatch, public_catalog):
        catalog = {k: v for k, v in public_catalog.items() if k[1] != "Employee"}
        mapper = make_mapper(monkeypatch, catalog)
        with pytest.raises(MappingError) as exc:
            mapper.initialize()
        diag = exc.value.diagnostics
        assert diag["logical_table"] == "Employee"
        assert diag["configured_schemas"]["source_schema"] == "public"
        assert "public.CaseMaster" in diag["available_physical_tables"]


class TestColumnResolution:
    @pytest.mark.parametrize("table,logical,physical", [
        ("CaseMaster", "case_id", "CaseMasterID"),
        ("CaseMaster", "case_number", "CaseNo"),
        ("CaseMaster", "crime_number", "CrimeNo"),
        ("CaseMaster", "police_person_id", "PolicePersonID"),
        ("CaseMaster", "status", "CaseStatusID"),
        ("Employee", "employee_id", "EmployeeID"),
        ("Employee", "first_name", "FirstName"),
        ("Employee", "kgid", "KGID"),
        ("Accused", "accused_id", "AccusedMasterID"),
        ("Accused", "accused_name", "AccusedName"),
        ("Accused", "person_id", "PersonID"),
        ("Accused", "case_master_id", "CaseMasterID"),
        ("Victim", "victim_name", "VictimName"),
    ])
    def test_logical_columns(self, fake_mapper, table, logical, physical):
        assert fake_mapper.get_column(table, logical) == physical

    def test_unknown_column_has_diagnostics(self, fake_mapper):
        with pytest.raises(MappingError) as exc:
            fake_mapper.get_column("CaseMaster", "nonexistent")
        diag = exc.value.diagnostics
        assert diag["requested_logical_column"] == "nonexistent"
        assert diag["resolved_physical_table"] == "public.CaseMaster"
        assert "CaseNo" in diag["available_columns"]
        assert diag["mapped_columns"]["case_number"] == "CaseNo"

    def test_optional_column_absent(self, monkeypatch, public_catalog):
        catalog = dict(public_catalog)
        catalog[("public", "Accused")] = {k: v for k, v in catalog[("public", "Accused")].items() if k != "personid"}
        mapper = make_mapper(monkeypatch, catalog)
        mapper.initialize()  # must not raise — person_id is optional
        assert not mapper.has_column("Accused", "person_id")

    def test_required_column_missing_fails_with_candidates(self, monkeypatch, public_catalog):
        catalog = dict(public_catalog)
        catalog[("public", "CaseMaster")] = {k: v for k, v in catalog[("public", "CaseMaster")].items() if k != "caseno"}
        mapper = make_mapper(monkeypatch, catalog)
        with pytest.raises(MappingError) as exc:
            mapper.initialize()
        assert "case_number" in str(exc.value)
        assert "caseno" in exc.value.diagnostics["expected_candidates"]


class TestTypeCoercion:
    def test_bigint_columns_get_ints(self, fake_mapper):
        assert fake_mapper.coerce_value("CaseMaster", "case_number", "202300001") == 202300001
        assert fake_mapper.coerce_value("CaseMaster", "case_number", 202300001) == 202300001
        assert fake_mapper.coerce_value("Employee", "employee_id", "5313") == 5313

    def test_text_columns_get_strings(self, fake_mapper):
        assert fake_mapper.coerce_value("Accused", "person_id", "A1") == "A1"
        assert fake_mapper.coerce_value("Employee", "kgid", " KG10313 ") == "KG10313"

    def test_non_numeric_for_bigint_rejected(self, fake_mapper):
        with pytest.raises(IdentifierValidationError):
            fake_mapper.coerce_value("CaseMaster", "case_number", "CR/2023/001")
        with pytest.raises(IdentifierValidationError):
            fake_mapper.coerce_value("CaseMaster", "case_id", "1; DROP TABLE x")

    def test_describe_is_secret_free(self, fake_mapper):
        desc = fake_mapper.describe()
        assert desc["tables"]["CaseMaster"]["physical"] == "public.CaseMaster"
        assert "password" not in str(desc).lower()
