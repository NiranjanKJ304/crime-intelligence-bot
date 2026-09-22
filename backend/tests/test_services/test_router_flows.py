"""
End-to-end tests of Router -> IntentDetector -> Planner -> PostgreSQL tools
-> TemplateEngine for the deterministic factual path.

Groq is mocked and asserted to be *not called* for every factual lookup.
"""

from unittest.mock import AsyncMock

import pytest

from app.core.config import Settings
from app.llm.schemas import ChatRequest
from app.services.tools.exceptions import DatabaseQueryError, MappingError, ToolError
from app.services.tools.router import QueryRouter


@pytest.fixture
def router(fake_db):
    settings = Settings(groq_api_key="test-key-not-used")
    r = QueryRouter(settings)
    r.provider.client.chat.completions.create = AsyncMock(side_effect=AssertionError("Groq must not be called"))
    return r


async def _ask(router: QueryRouter, query: str, history=None):
    return await router.route(ChatRequest(query=query, history=history))


class TestCaseLookupFlow:
    @pytest.mark.parametrize("query", [
        "Find CaseNo 202300001",
        "Show case 202300001",
        "Tell me about Case Number 202300001",
        "case no: 202300001",
    ])
    async def test_find_case_by_caseno(self, router, fake_db, query):
        result = await _ask(router, query)
        assert "202300001" in result.answer
        assert "CaseMasterID):** 1" in result.answer
        assert "100170200202300001" in result.answer  # CrimeNo shown, distinct from CaseNo
        assert result.retrieval.prompt_tokens == 0
        assert result.sources == ["get_case_lookup"]
        assert fake_db.tables_queried == ["CaseMaster"]
        router.provider.client.chat.completions.create.assert_not_called()

    async def test_crime_number_lookup_uses_crimeno(self, router, fake_db):
        result = await _ask(router, "crime no 100170200202300001")
        assert "CaseMasterID):** 1" in result.answer
        assert '"CrimeNo" = :val' in fake_db.queries[0][0]

    async def test_unknown_caseno_is_clean_not_found(self, router, fake_db):
        result = await _ask(router, "Find CaseNo 999999999")
        assert result.answer == "No case was found for CaseNo 999999999."
        assert result.retrieval.prompt_tokens == 0
        assert result.citations == []
        router.provider.client.chat.completions.create.assert_not_called()

    async def test_non_numeric_caseno_is_validation_message(self, router, fake_db):
        result = await _ask(router, "Find case number 12/2023")
        assert "not a valid numeric CaseNo" in result.answer
        assert fake_db.queries == []


class TestOfficerLookupFlow:
    @pytest.mark.parametrize("query", [
        "Find officer EmployeeID 5313",
        "Officer 5313",
        "employee id 5313",
        "who is officer 5313?",
    ])
    async def test_find_officer_by_employee_id(self, router, fake_db, query):
        result = await _ask(router, query)
        assert "Oliver" in result.answer
        assert "KG10313" in result.answer
        assert "5313" in result.answer
        assert result.retrieval.prompt_tokens == 0
        assert fake_db.tables_queried == ["Employee"]
        assert fake_db.queries[0][1] == {"val": 5313}
        router.provider.client.chat.completions.create.assert_not_called()

    async def test_unknown_employee_id(self, router, fake_db):
        result = await _ask(router, "Find officer EmployeeID 424242")
        assert result.answer == "No officer was found with EmployeeID 424242."
        assert result.retrieval.prompt_tokens == 0
        router.provider.client.chat.completions.create.assert_not_called()


class TestCaseToOfficerChain:
    async def test_investigating_officer_for_caseno(self, router, fake_db):
        result = await _ask(router, "Who is the investigating officer for CaseNo 202300001?")
        assert "Oliver" in result.answer
        assert "CaseNo 202300001" in result.answer
        assert "5313" in result.answer
        assert result.retrieval.prompt_tokens == 0
        # Chain: CaseNo -> CaseMasterID/PolicePersonID -> Employee
        assert fake_db.tables_queried == ["CaseMaster", "Employee"]
        assert fake_db.queries[0][1] == {"val": 202300001}
        assert fake_db.queries[1][1] == {"val": 5313}
        assert result.sources == ["get_case_lookup", "get_officer_compact"]
        router.provider.client.chat.completions.create.assert_not_called()

    async def test_officer_for_unknown_case(self, router, fake_db):
        result = await _ask(router, "Who is the investigating officer for CaseNo 999999999?")
        assert result.answer == "No case was found for CaseNo 999999999."
        assert fake_db.tables_queried == ["CaseMaster"]

    async def test_follow_up_resolves_case_from_history(self, router, fake_db):
        history = [
            {"role": "user", "content": "Find CaseNo 202300001"},
            {"role": "assistant", "content": "### Case Details\n- **Case Number (CaseNo):** 202300001"},
        ]
        result = await _ask(router, "Who is the investigating officer for that case?", history=history)
        assert "Oliver" in result.answer
        assert result.retrieval.prompt_tokens == 0


class TestAccusedByName:
    @pytest.mark.parametrize("query", ["Fiyaz Saran", "accused Fiyaz Saran", "find accused named Fiyaz Saran"])
    async def test_multiple_records_are_all_returned(self, router, fake_db, query):
        result = await _ask(router, query)
        assert "Found **15** accused record(s)" in result.answer
        assert "not a unique identity" in result.answer
        assert "AccusedMasterID 1 | CaseMasterID 1 | PersonID A1" in result.answer
        assert "AccusedMasterID 15 | CaseMasterID 14 | PersonID A15" in result.answer
        assert result.retrieval.prompt_tokens == 0
        router.provider.client.chat.completions.create.assert_not_called()

    async def test_unknown_name(self, router, fake_db):
        result = await _ask(router, "accused named Nobody Here")
        assert result.answer == "No accused records were found for the name 'Nobody Here'."


class TestStructuredPayload:
    """response_type/data mirror the Markdown answer so rich clients can render cards."""

    async def test_case_details(self, router, fake_db):
        result = await _ask(router, "Find CaseNo 202300001")
        assert result.response_type == "case_details"
        assert result.data["case"]["case_id"] == 1
        assert result.data["case"]["case_number"] == 202300001
        assert result.data["case"]["police_person_id"] == 5313

    async def test_officer_details_with_case_context(self, router, fake_db):
        result = await _ask(router, "Who is the investigating officer for CaseNo 202300001?")
        assert result.response_type == "officer_details"
        assert result.data["officer"] == {"employee_id": 5313, "first_name": "Oliver", "kgid": "KG10313",
                                          "designation": 7, "rank": 4}
        assert result.data["case"]["case_number"] == 202300001

    async def test_officer_details_direct(self, router, fake_db):
        result = await _ask(router, "Find officer EmployeeID 5313")
        assert result.response_type == "officer_details"
        assert result.data["case"] is None

    async def test_person_details(self, router, fake_db):
        result = await _ask(router, "Who are the accused in CaseNo 202300001?")
        assert result.response_type == "person_details"
        assert result.data["role"] == "accused"
        assert [p["accused_id"] for p in result.data["persons"]] == [1, 2]
        assert result.data["persons"][0]["person_id"] == "A1"

    async def test_search_results(self, router, fake_db):
        result = await _ask(router, "Fiyaz Saran")
        assert result.response_type == "search_results"
        assert result.data["entity"] == "accused"
        assert result.data["total"] == 15
        assert len(result.data["results"]) == 15
        assert "not a unique identity" in result.data["note"]

    async def test_not_found_is_plain_answer(self, router, fake_db):
        result = await _ask(router, "Find CaseNo 999999999")
        assert result.response_type == "answer"
        assert result.data is None


class TestToolFailuresPropagateAsToolError:
    async def test_mapping_error_is_raised_not_swallowed(self, router, fake_db, monkeypatch):
        from app.services.tools import postgres_tools

        def boom(*_, **__):
            raise MappingError("Mapping not found for CaseMaster.case_number.", {"logical_table": "CaseMaster"})

        monkeypatch.setattr(postgres_tools, "get_case_lookup", boom)
        with pytest.raises(ToolError) as exc:
            await _ask(router, "Find CaseNo 202300001")
        assert exc.value.user_message == "Database schema configuration error."

    async def test_database_error_is_raised(self, router, fake_db, monkeypatch):
        from app.services.tools import postgres_tools

        def boom(*_, **__):
            raise DatabaseQueryError("connection refused")

        monkeypatch.setattr(postgres_tools, "_execute_query", boom)
        with pytest.raises(DatabaseQueryError) as exc:
            await _ask(router, "Find CaseNo 202300001")
        assert exc.value.user_message == "Database query failed."
