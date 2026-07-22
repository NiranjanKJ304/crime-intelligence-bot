"""
Tests for Ranking Engine.
"""
import datetime
from app.retrieval.config import RetrievalConfig
from app.retrieval.schemas import RawSearchHit
from app.retrieval.ranking_engine import RankingEngine


def get_mock_config():
    return RetrievalConfig(
        top_k=10, default_score_threshold=0.5, query_cache_size=10, query_cache_ttl=10,
        max_context_tokens=1000, default_document_limit=10, qdrant_host="", qdrant_port=0,
        qdrant_collection="", embedding_model=""
    )


def test_ranking_empty():
    engine = RankingEngine(get_mock_config())
    assert engine.rank([]) == []


def test_ranking_ordering():
    engine = RankingEngine(get_mock_config())
    
    hits = [
        # Score 0.9, type case_summary (priority 1.0)
        RawSearchHit(score=0.9, document_id="d1", document_type="case_summary", text_preview="", metadata={}, vector_id=""),
        # Score 0.95, type court_summary (priority 0.5)
        RawSearchHit(score=0.95, document_id="d2", document_type="court_summary", text_preview="", metadata={}, vector_id="")
    ]
    
    # Sim weights: 0.7*sim + 0.1*type
    # d1: 0.7*0.9 + 0.1*1.0 = 0.63 + 0.10 = 0.73
    # d2: 0.7*0.95 + 0.1*0.5 = 0.665 + 0.05 = 0.715
    # So d1 should rank higher than d2 despite having lower similarity!
    
    ranked = engine.rank(hits)
    assert len(ranked) == 2
    assert ranked[0].document_id == "d1"
    assert ranked[1].document_id == "d2"


def test_ranking_freshness():
    engine = RankingEngine(get_mock_config())
    
    now = datetime.datetime.now(datetime.timezone.utc)
    old_date = (now - datetime.timedelta(days=365)).isoformat()
    new_date = now.isoformat()
    
    hits = [
        RawSearchHit(score=0.8, document_id="old", document_type="case_summary", text_preview="", metadata={"updated_at": old_date}, vector_id=""),
        RawSearchHit(score=0.8, document_id="new", document_type="case_summary", text_preview="", metadata={"updated_at": new_date}, vector_id="")
    ]
    
    ranked = engine.rank(hits)
    assert ranked[0].document_id == "new"
    assert ranked[1].document_id == "old"
    
def test_ranking_explanation():
    engine = RankingEngine(get_mock_config())
    hits = [
        RawSearchHit(score=0.9, document_id="d1", document_type="case_summary", text_preview="", metadata={}, vector_id="")
    ]
    
    ranked = engine.rank(hits, include_explanation=True)
    assert ranked[0].explanation is not None
    assert ranked[0].explanation.similarity_contribution > 0
    assert "priority" in ranked[0].explanation.ranking_reason
