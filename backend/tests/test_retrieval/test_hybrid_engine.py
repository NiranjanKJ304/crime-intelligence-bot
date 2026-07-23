import pytest
from unittest.mock import MagicMock, patch

from app.core.config import Settings
from app.retrieval.schemas import RetrievalRequest, RankedResult, GraphResult
from app.retrieval.retrieval_engine import RetrievalEngine


@pytest.fixture
def mock_engine():
    settings = Settings()
    
    with patch("app.retrieval.retrieval_engine.QdrantClient") as mock_qdrant, \
         patch("app.retrieval.retrieval_engine.ModelManager") as mock_model_mgr, \
         patch("app.retrieval.retrieval_engine.GraphSearch") as mock_graph_search, \
         patch("app.retrieval.retrieval_engine.CacheManager") as mock_cache:
         
         # Need to reset singletons for testing
         RetrievalEngine._cache_manager = None
         RetrievalEngine._analytics = None
         
         engine = RetrievalEngine(settings)
         
         # Mock the dependencies that hit external services
         engine.searcher = MagicMock()
         engine.embedding = MagicMock()
         engine.graph_searcher = MagicMock()
         engine.cache = MagicMock()
         
         # Setup mock returns
         engine.cache.get.return_value = None
         engine.embedding.embed.return_value = [0.1] * 384
         
         from app.retrieval.schemas import RawSearchHit
         engine.searcher.search.return_value = [
             RawSearchHit(score=0.9, document_id="c1", document_type="case_summary", text_preview="", metadata={"district": "Mysuru"}, vector_id="v1")
         ]
         
         engine.graph_searcher.search_by_entities.return_value = [
             GraphResult(node="Case: c1", relationship="HAS", connected_to="Info")
         ]
         
         yield engine


def test_hybrid_search(mock_engine):
    request = RetrievalRequest(query="Show theft in Mysuru", include_explanation=True)
    
    response = mock_engine.hybrid(request)
    
    assert response.query == "Show theft in Mysuru"
    assert response.metadata.district == "Mysuru"
    assert response.metadata.crime_type == "theft"
    assert len(response.retrieved_documents) == 1
    assert len(response.graph_results) == 1
    assert "Graph Relationships" in response.context
    assert response.statistics.documents == 1
    assert response.retrieved_documents[0].explanation is not None
    assert "Corroborated by graph" in response.retrieved_documents[0].explanation.ranking_reason


def test_search_with_explanation(mock_engine):
    request = RetrievalRequest(query="Show theft in Mysuru", include_explanation=True)
    
    response = mock_engine.search(request)
    
    assert len(response.results) == 1
    assert response.results[0].explanation is not None
    assert response.results[0].explanation.similarity_contribution > 0


def test_search_without_explanation(mock_engine):
    request = RetrievalRequest(query="Show theft in Mysuru", include_explanation=False)
    
    response = mock_engine.search(request)
    
    assert len(response.results) == 1
    assert response.results[0].explanation is None


def test_similar_case(mock_engine):
    request = type("SimilarCaseRequest", (), {"case_id": "c1", "top_k": 5})()
    
    response = mock_engine.similar_case(request)
    assert "case c1" in response.query


def test_context_endpoint(mock_engine):
    request = RetrievalRequest(query="Show theft in Mysuru")
    
    response = mock_engine.context(request)
    
    assert response.query == "Show theft in Mysuru"
    assert "Graph Relationships" in response.context


def test_health_check(mock_engine):
    with patch("app.core.neo4j_db.get_neo4j_driver") as mock_driver:
        response = mock_engine.health()
        assert response.status == "healthy"
        assert response.qdrant == "healthy"
        assert response.neo4j == "healthy"


def test_get_config(mock_engine):
    config = mock_engine.get_config()
    assert "top_k" in config
    assert "ranking_weights" in config
