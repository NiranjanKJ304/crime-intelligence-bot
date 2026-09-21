"""
Integration tests for multi-step tool planning.

These tests run against the live services (PostgreSQL, Neo4j, Qdrant)
AND the Groq API to verify that the iterative tool-calling loop correctly
chains multiple tool calls to answer relational questions.

Requirements:
  - Backend database services running (PostgreSQL, Neo4j, Qdrant)
  - GROQ_API_KEY set in the environment
  - Database populated with synthetic data
"""

import pytest
import asyncio

from app.core.config import get_settings
from app.llm.schemas import ChatRequest
from app.services.tools.mapper import ColumnMapper
from app.services.tools.router import QueryRouter


@pytest.fixture(scope="module", autouse=True)
def setup_mapper():
    """Ensure the column mapper is initialized before tests run."""
    mapper = ColumnMapper.get_instance()
    try:
        mapper.initialize()
    except Exception as e:
        pytest.skip(f"Database not available or clean schema not populated: {e}")
    yield


@pytest.fixture(scope="module")
def settings():
    return get_settings()


@pytest.fixture(scope="module")
def router(settings):
    return QueryRouter(settings)


def _run(coro):
    """Helper to run async functions in sync tests."""
    return asyncio.get_event_loop().run_until_complete(coro)


# ── Single-step tests (baseline) ─────────────────────────────────────


class TestSingleStepLookups:
    """Verify that factual queries return deterministically with 0 LLM calls."""

    def test_case_lookup(self, router):
        request = ChatRequest(query="Tell me about Case Number 202300001")
        result = _run(router.route(request))
        assert result is not None
        assert result.answer
        assert result.retrieval.prompt_tokens == 0, "Factual lookup should use 0 LLM tokens"
        assert "202300001" in result.answer

class TestMultiStepPlanning:
    """Verify that multi-step facts are resolved via the Intent Detector and Planner deterministically."""

    def test_officer_from_case(self, router):
        request = ChatRequest(query="Who is the investigating officer for Case Number 202300001?")
        result = _run(router.route(request))
        assert result is not None
        assert result.answer
        assert result.retrieval.prompt_tokens == 0, "Factual query should bypass LLM"
        answer_lower = result.answer.lower()
        assert any(kw in answer_lower for kw in ["officer", "kgid", "designation", "kumar", "singh", "sharma"])

    def test_victim_from_case(self, router):
        request = ChatRequest(query="What is the age and gender of the victim in Case Number 202300001?")
        result = _run(router.route(request))
        assert result is not None
        assert result.answer
        assert result.retrieval.prompt_tokens == 0, "Factual query should bypass LLM"
        answer_lower = result.answer.lower()
        assert any(kw in answer_lower for kw in ["victim", "age", "years", "old", "gender"])


class TestReasoningQueries:
    """Verify that reasoning queries STILL invoke the LLM with the compact context."""
    
    def test_summarize_case(self, router):
        request = ChatRequest(query="Summarize Case Number 202300001")
        result = _run(router.route(request))
        assert result is not None
        assert result.answer
        assert result.retrieval.prompt_tokens > 0, "Reasoning queries MUST use the LLM"
        assert result.retrieval.prompt_tokens < 1500, "Context must be compact (should be ~100-300 tokens)"
        
    def test_case_network(self, router):
        request = ChatRequest(query="Show the criminal network for Case Number 202300001")
        result = _run(router.route(request))
        assert result is not None
        assert result.answer
        assert result.retrieval.prompt_tokens > 0, "Graph reasoning MUST use the LLM"
        assert "find_case_network" in result.sources, "Should have executed the network tool"
        
    def test_co_accused(self, router):
        request = ChatRequest(query="Find co-accused for Case Number 202300001")
        result = _run(router.route(request))
        assert result is not None
        assert result.answer
        assert result.retrieval.prompt_tokens > 0, "Graph reasoning MUST use the LLM"
        assert "find_co_accused" in result.sources, "Should have executed the co-accused tool"
        
    def test_timeline(self, router):
        request = ChatRequest(query="Explain the investigation timeline for Case Number 202300001")
        result = _run(router.route(request))
        assert result is not None
        assert result.answer
        assert result.retrieval.prompt_tokens > 0, "Graph reasoning MUST use the LLM"
        assert "get_case_timeline" in result.sources, "Should have executed the timeline tool"


class TestConversationMemory:
    """Verify that conversation history allows reference resolution for factual queries."""

    def test_follow_up_reference(self, router):
        history = [
            {"role": "user", "content": "Tell me about Case Number 202300001"},
            {"role": "assistant", "content": "Case Number 202300001 is a criminal case."},
        ]
        request = ChatRequest(
            query="Who is the investigating officer for that case?",
            history=history,
        )
        result = _run(router.route(request))
        assert result is not None
        assert result.answer
        assert result.retrieval.prompt_tokens == 0, "Factual history resolution should bypass LLM"


class TestErrorHandling:
    """Verify graceful handling of missing data."""

    def test_nonexistent_case(self, router):
        request = ChatRequest(query="Tell me about Case Number 999999999")
        result = _run(router.route(request))
        if result is not None:
            assert result.answer
            assert result.retrieval.prompt_tokens == 0

