"""
Tests for Response Builder.
"""

from app.rag.response_builder import ResponseBuilder
from app.llm.schemas import Citation, RetrievalMetrics

def test_response_builder():
    citations = [
        Citation(document_id="d1", document_type="case", score=0.8),
        Citation(document_id="d2", document_type="case", score=0.9)
    ]
    
    metrics = RetrievalMetrics(
        documents_used=2,
        retrieval_time_ms=10.0,
        prompt_build_time_ms=1.0,
        llm_time_ms=50.0,
        model="test-model"
    )
    
    resp = ResponseBuilder.build(
        query="test query",
        answer="test answer",
        citations=citations,
        sources=["d1", "d2"],
        retrieval_metrics=metrics
    )
    
    assert resp.query == "test query"
    assert resp.answer == "test answer"
    assert len(resp.citations) == 2
    assert resp.confidence == 0.85 # (0.8 + 0.9) / 2
    assert resp.retrieval.model == "test-model"
