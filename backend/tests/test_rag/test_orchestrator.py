"""
Tests for RAG Orchestrator.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from app.rag.orchestrator import RAGOrchestrator
from app.llm.schemas import ChatRequest, ProviderResponse
from app.retrieval.schemas import RetrievalResponse, RankedResult

@pytest.fixture
def mock_engine():
    engine = MagicMock()
    # Setup mock return for engine.query
    engine.query.return_value = RetrievalResponse(
        query="test query",
        processed_query="test query",
        results=[
            RankedResult(
                rank=1,
                similarity_score=0.9,
                final_score=0.9,
                document_id="doc_1",
                document_type="case",
                text_preview="text",
                metadata={},
                vector_id="v1"
            )
        ],
        context="Mock Context",
        total_results=1,
        search_time_ms=10.0,
        model="test-model",
        cache_hit=False
    )
    return engine

@pytest.fixture
def mock_llm_client():
    client = MagicMock()
    client.generate = AsyncMock(return_value=ProviderResponse(
        content="This is the answer from [doc_1].",
        prompt_tokens=10,
        completion_tokens=10,
        total_tokens=20
    ))
    return client

@pytest.fixture
def settings():
    s = MagicMock()
    s.max_context_documents = 5
    s.model_name = "test-model"
    return s

@pytest.mark.asyncio
async def test_chat_success(mock_engine, mock_llm_client, settings):
    orchestrator = RAGOrchestrator(mock_engine, mock_llm_client, settings)
    
    request = ChatRequest(query="test query")
    response = await orchestrator.chat(request)
    
    assert response.query == "test query"
    assert response.answer == "This is the answer from [doc_1]."
    assert len(response.citations) == 1
    assert response.citations[0].document_id == "doc_1"
    assert response.retrieval.documents_used == 1

@pytest.mark.asyncio
async def test_chat_empty_retrieval(mock_engine, mock_llm_client, settings):
    # Setup mock to return no documents
    engine_mock = mock_engine
    engine_mock.query.return_value.results = []
    
    orchestrator = RAGOrchestrator(engine_mock, mock_llm_client, settings)
    request = ChatRequest(query="test query")
    response = await orchestrator.chat(request)
    
    assert response.answer == "No supporting evidence was found."
    assert len(response.citations) == 0
    # LLM should not be called
    mock_llm_client.generate.assert_not_called()
