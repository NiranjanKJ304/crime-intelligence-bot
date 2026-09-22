"""
API-boundary tests: tool/database failures must become structured errors,
never tracebacks, and never terminate the SSE stream early.
"""

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1 import chat_routes
from app.llm.schemas import ChatResponse, RetrievalMetrics
from app.services.tools.exceptions import DatabaseQueryError, MappingError


class _Router:
    def __init__(self, behaviour):
        self._behaviour = behaviour

    async def route(self, request):
        if isinstance(self._behaviour, Exception):
            raise self._behaviour
        return self._behaviour


def _ok_response() -> ChatResponse:
    return ChatResponse(
        query="Find CaseNo 202300001",
        answer="### Case Details\n- **Case Number (CaseNo):** 202300001",
        citations=[], sources=["get_case_lookup"], confidence=1.0,
        retrieval=RetrievalMetrics(documents_used=1, retrieval_time_ms=3.0, prompt_build_time_ms=0,
                                   llm_time_ms=0, model="none"),
    )


def _client(behaviour) -> TestClient:
    app = FastAPI()
    app.include_router(chat_routes.router)
    app.dependency_overrides[chat_routes.get_query_router] = lambda: _Router(behaviour)
    return TestClient(app)


def _sse_events(body: str) -> list:
    events = []
    for line in body.splitlines():
        if line.startswith("data: "):
            payload = line[6:]
            events.append(payload if payload == "[DONE]" else json.loads(payload))
    return events


class TestSyncEndpoint:
    def test_success(self):
        resp = _client(_ok_response()).post("/api/v1/chat", json={"query": "Find CaseNo 202300001"})
        assert resp.status_code == 200
        assert "202300001" in resp.json()["answer"]

    def test_mapping_error_is_safe_500(self):
        err = MappingError("Mapping not found for CaseMaster.case_id.", {"logical_table": "CaseMaster"})
        resp = _client(err).post("/api/v1/chat", json={"query": "Find CaseNo 202300001"})
        assert resp.status_code == 500
        assert resp.json() == {"detail": "Database schema configuration error."}
        assert "Traceback" not in resp.text and "Mapping not found" not in resp.text

    def test_database_error_is_safe_500(self):
        resp = _client(DatabaseQueryError("boom")).post("/api/v1/chat", json={"query": "x"})
        assert resp.status_code == 500
        assert resp.json() == {"detail": "Database query failed."}

    def test_unexpected_error_is_generic(self):
        resp = _client(RuntimeError("secret internal detail")).post("/api/v1/chat", json={"query": "x"})
        assert resp.status_code == 500
        assert "secret internal detail" not in resp.text


class TestStreamEndpoint:
    def test_success_stream(self):
        resp = _client(_ok_response()).post("/api/v1/chat/stream", json={"query": "Find CaseNo 202300001"})
        assert resp.status_code == 200
        events = _sse_events(resp.text)
        assert events[0]["event"] == "token"
        assert "202300001" in events[0]["data"]
        assert events[1]["event"] == "complete"
        assert events[-1] == "[DONE]"

    @pytest.mark.parametrize("error,message", [
        (MappingError("Mapping not found for CaseMaster.case_id.", {}), "Database schema configuration error."),
        (DatabaseQueryError("connection refused"), "Database query failed."),
        (RuntimeError("internal"), chat_routes.GENERIC_ERROR),
    ])
    def test_errors_become_structured_events_and_stream_completes(self, error, message):
        resp = _client(error).post("/api/v1/chat/stream", json={"query": "Find CaseNo 202300001"})
        assert resp.status_code == 200
        events = _sse_events(resp.text)
        assert events == [{"event": "error", "data": message}, "[DONE]"]
        assert "Traceback" not in resp.text
