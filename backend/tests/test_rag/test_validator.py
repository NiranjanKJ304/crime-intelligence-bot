"""
Tests for RAG Validator.
"""

import pytest
from app.rag.validator import QueryValidator
from app.llm.exceptions import LLMValidationError

def test_validator_valid():
    assert QueryValidator.validate("  test query  ") == "test query"

def test_validator_empty():
    with pytest.raises(LLMValidationError):
        QueryValidator.validate("")
    
    with pytest.raises(LLMValidationError):
        QueryValidator.validate(None)
        
    with pytest.raises(LLMValidationError):
        QueryValidator.validate("   ")

def test_validator_too_short():
    with pytest.raises(LLMValidationError):
        QueryValidator.validate("a")
