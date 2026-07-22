"""
Tests for Statistics Tracker.
"""

from app.document_generation.schemas import ValidationIssue
from app.document_generation.statistics import StatisticsTracker


def test_statistics_tracker():
    tracker = StatisticsTracker()
    
    tracker.record_generated("case_summary", 10)
    tracker.record_generated("accused_profile", 5)
    
    tracker.record_validation(True, [])
    tracker.record_validation(True, [ValidationIssue(document_id="1", severity="warning", message="warn")])
    tracker.record_validation(False, [ValidationIssue(document_id="2", severity="error", message="err")])
    
    tracker.record_error("case_summary", 1, "test error")
    
    summary = tracker.summary()
    assert summary["total_documents"] == 15
    assert summary["documents_generated"]["case_summary"] == 10
    assert summary["documents_generated"]["accused_profile"] == 5
    assert summary["validation"]["valid"] == 1
    assert summary["validation"]["warnings"] == 1
    assert summary["validation"]["errors"] == 1
    assert len(summary["errors"]) == 1
