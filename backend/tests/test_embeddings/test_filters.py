"""
Tests for Filter Builder.
"""

from qdrant_client.http import models as rest
from app.embeddings.filters import FilterBuilder


def test_build_filter_empty():
    assert FilterBuilder.build_filter(None) is None
    assert FilterBuilder.build_filter({}) is None


def test_build_filter_exact():
    f = FilterBuilder.build_filter({"crime_year": 2024})
    assert isinstance(f, rest.Filter)
    assert len(f.must) == 1
    
    cond = f.must[0]
    assert isinstance(cond, rest.FieldCondition)
    assert cond.key == "crime_year"
    assert isinstance(cond.match, rest.MatchValue)
    assert cond.match.value == 2024


def test_build_filter_in():
    f = FilterBuilder.build_filter({"document_type": ["case_summary", "victim_profile"]})
    cond = f.must[0]
    assert isinstance(cond, rest.FieldCondition)
    assert cond.key == "document_type"
    assert isinstance(cond.match, rest.MatchAny)
    assert cond.match.any == ["case_summary", "victim_profile"]


def test_build_filter_isnull():
    f = FilterBuilder.build_filter({"case_number": None})
    cond = f.must[0]
    assert isinstance(cond, rest.IsEmptyCondition)
    assert cond.is_empty.key == "case_number"
