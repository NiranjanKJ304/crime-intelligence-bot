"""
Tests for Metadata Filter.
"""
import pytest

from app.retrieval.metadata_filter import MetadataFilter


def test_validate_and_build_empty():
    mf = MetadataFilter()
    assert mf.validate_and_build(None) is None
    assert mf.validate_and_build({}) is None


def test_validate_and_build_valid():
    mf = MetadataFilter()
    q_filter = mf.validate_and_build({
        "document_type": "case_summary",
        "crime_year": 2024
    })
    
    assert q_filter is not None
    assert len(q_filter.must) == 2


def test_validate_and_build_invalid():
    mf = MetadataFilter()
    with pytest.raises(ValueError, match="Invalid filter keys"):
        mf.validate_and_build({
            "document_type": "case_summary",
            "injection_key": "some_value"
        })
