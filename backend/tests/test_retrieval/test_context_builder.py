"""
Tests for Context Builder.
"""

from app.retrieval.config import RetrievalConfig
from app.retrieval.schemas import RankedResult
from app.retrieval.context_builder import ContextBuilder


def get_mock_config():
    return RetrievalConfig(
        top_k=10,
        default_score_threshold=0.5,
        query_cache_size=10,
        query_cache_ttl=10,
        max_context_tokens=1000,
        default_document_limit=10,
        qdrant_host="",
        qdrant_port=0,
        qdrant_collection="",
        embedding_model=""
    )


def test_build_context_empty():
    builder = ContextBuilder(get_mock_config())
    assert builder.build_context([]) == ""


def test_build_context_grouping():
    builder = ContextBuilder(get_mock_config())
    
    results = [
        RankedResult(rank=1, similarity_score=0.9, final_score=0.9, document_id="c1", document_type="case_summary", text_preview="Case 1 text", metadata={}, vector_id="v1"),
        RankedResult(rank=2, similarity_score=0.8, final_score=0.8, document_id="a1", document_type="accused_profile", text_preview="Accused 1 text", metadata={}, vector_id="v2"),
        RankedResult(rank=3, similarity_score=0.7, final_score=0.7, document_id="c2", document_type="case_summary", text_preview="Case 2 text", metadata={}, vector_id="v3"),
    ]
    
    ctx = builder.build_context(results)
    
    assert "=== RETRIEVED CONTEXT ===" in ctx
    assert "--- Case Summaries (2 documents) ---" in ctx
    assert "--- Accused Profiles (1 document) ---" in ctx
    assert "Case 1 text" in ctx
    assert "Accused 1 text" in ctx
    assert "=== END CONTEXT ===" in ctx


def test_build_context_deduplication():
    builder = ContextBuilder(get_mock_config())
    
    results = [
        RankedResult(rank=1, similarity_score=0.9, final_score=0.9, document_id="c1", document_type="case_summary", text_preview="Case 1 text", metadata={}, vector_id="v1"),
        # Duplicate document_id
        RankedResult(rank=2, similarity_score=0.8, final_score=0.8, document_id="c1", document_type="case_summary", text_preview="Case 1 text dup", metadata={}, vector_id="v2"),
    ]
    
    ctx = builder.build_context(results)
    assert "Case Summaries (1 document)" in ctx
    assert "Case 1 text" in ctx
    assert "Case 1 text dup" not in ctx


def test_build_context_truncation():
    config = get_mock_config()
    # Very small token limit
    config = RetrievalConfig(
        top_k=10, default_score_threshold=0.5, query_cache_size=10, query_cache_ttl=10,
        max_context_tokens=45, # enough to pass the >20 remaining check
        default_document_limit=10, qdrant_host="", qdrant_port=0, qdrant_collection="", embedding_model=""
    )
    builder = ContextBuilder(config)
    
    results = [
        RankedResult(rank=1, similarity_score=0.9, final_score=0.9, document_id="c1", document_type="case_summary", text_preview="Very long text that will definitely exceed the small token limit we just set above because it keeps going and going and going.", metadata={}, vector_id="v1"),
    ]
    
    ctx = builder.build_context(results)
    assert "[TRUNCATED]" in ctx
