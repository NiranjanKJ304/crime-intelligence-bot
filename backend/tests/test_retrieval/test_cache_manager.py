"""
Tests for Cache Manager.
"""
import time
from app.retrieval.config import RetrievalConfig
from app.retrieval.schemas import RetrievalResponse
from app.retrieval.cache_manager import CacheManager


def get_mock_config(size, ttl):
    return RetrievalConfig(
        top_k=10, default_score_threshold=0.5, query_cache_size=size, query_cache_ttl=ttl,
        max_context_tokens=1000, default_document_limit=10, qdrant_host="", qdrant_port=0,
        qdrant_collection="", embedding_model=""
    )


def mock_response():
    return RetrievalResponse(
        query="test", processed_query="test", results=[], context="",
        total_results=0, search_time_ms=0, model="m"
    )


def test_cache_put_get():
    cache = CacheManager(get_mock_config(10, 10))
    cache.put("k1", mock_response())
    
    res = cache.get("k1")
    assert res is not None
    assert res.query == "test"
    

def test_cache_ttl():
    # TTL 0.1 seconds
    cache = CacheManager(get_mock_config(10, 0.1))
    cache.put("k1", mock_response())
    
    time.sleep(0.2)
    assert cache.get("k1") is None


def test_cache_lru():
    cache = CacheManager(get_mock_config(2, 10))
    cache.put("k1", mock_response())
    cache.put("k2", mock_response())
    cache.put("k3", mock_response()) # Should evict k1
    
    assert cache.get("k1") is None
    assert cache.get("k2") is not None
    assert cache.get("k3") is not None
    
    # Touch k2
    cache.get("k2")
    cache.put("k4", mock_response()) # Should evict k3
    
    assert cache.get("k3") is None
    assert cache.get("k2") is not None
    assert cache.get("k4") is not None


def test_cache_clear():
    cache = CacheManager(get_mock_config(10, 10))
    cache.put("k1", mock_response())
    assert cache.stats()["size"] == 1
    
    cache.clear()
    assert cache.stats()["size"] == 0
