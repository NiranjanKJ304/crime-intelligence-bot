"""
Tests for Embedding Statistics.
"""

from app.embeddings.statistics import EmbeddingStatistics


def test_embedding_statistics():
    stats = EmbeddingStatistics()
    
    stats.record_read(10)
    stats.record_encoded(10)
    
    # 8 valid, 1 skipped, 1 error
    for _ in range(8):
        class Issue: pass
        stats.record_validation(True, [])
        
    class WarnIssue:
        severity = "warning"
    stats.record_validation(True, [WarnIssue()])
    stats.record_validation(False, [])
    
    stats.record_uploaded(8)
    stats.record_error("doc_1", "test error")
    
    summary = stats.summary()
    assert summary["documents_processed"] == 10
    assert summary["embeddings_generated"] == 10
    assert summary["vectors_uploaded"] == 8
    
    assert summary["validation"]["valid"] == 8
    assert summary["validation"]["skipped"] == 1
    assert summary["validation"]["errors"] == 1
    assert len(summary["errors"]) == 1
