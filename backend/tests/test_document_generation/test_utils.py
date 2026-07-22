"""
Tests for Document Generation utility functions.
"""

from app.document_generation.utils import build_sentence, format_date, pluralize, safe_str


def test_format_date():
    assert format_date(None) == ""
    assert format_date("2024-01-15T10:30:00Z") == "15 January 2024"
    assert format_date("invalid-date") == "invalid-date"

def test_safe_str():
    assert safe_str(None) == ""
    assert safe_str("") == ""
    assert safe_str(" ") == ""
    assert safe_str("None") == ""
    assert safe_str("N/A") == ""
    assert safe_str("Hello") == "Hello"
    assert safe_str(None, "default") == "default"

def test_pluralize():
    assert pluralize(1, "case", "cases") == "case"
    assert pluralize(0, "case", "cases") == "cases"
    assert pluralize(5, "case", "cases") == "cases"

def test_build_sentence():
    assert build_sentence(["This is a test"]) == "This is a test."
    assert build_sentence(["This", "is", "a", "test"]) == "This is a test."
    assert build_sentence(["This.", "is.", "a", "test"]) == "This. is. a test."
    assert build_sentence(["This is a test."]) == "This is a test."
    assert build_sentence(["", "   ", None]) == ""
