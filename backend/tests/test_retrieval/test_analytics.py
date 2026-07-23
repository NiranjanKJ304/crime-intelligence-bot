"""
Tests for Retrieval Analytics.
"""

from app.retrieval.analytics import RetrievalAnalytics


def test_analytics_recording():
    analytics = RetrievalAnalytics()
    
    analytics.record_query(100.0, 0.9, ["case_summary", "victim_profile"], {"district": "bangalore"})
    analytics.record_query(50.0, 0.8, ["case_summary"], {"district": "bangalore", "crime_year": 2024}, graph_time_ms=20.0, is_hybrid=True)
    
    analytics.record_cache_hit()
    analytics.record_cache_miss()
    analytics.record_cache_miss()
    
    summary = analytics.summary()
    
    # 2 real queries + 1 cache hit = 3 total
    assert summary["total_queries"] == 3
    assert summary["hybrid_queries"] == 1
    assert summary["avg_search_time_ms"] == 75.0 # (100+50) / 2
    assert summary["avg_graph_time_ms"] == 20.0
    assert summary["avg_similarity"] == 0.85 # (0.9+0.8) / 2
    
    assert summary["top_document_types"]["case_summary"] == 2
    assert summary["top_document_types"]["victim_profile"] == 1
    
    assert summary["most_used_filters"]["district"] == 2
    assert summary["most_used_filters"]["crime_year"] == 1
    
    assert summary["cache_stats"]["hits"] == 1
    assert summary["cache_stats"]["misses"] == 2
    assert summary["cache_stats"]["hit_ratio"] == round(1/3, 3)
