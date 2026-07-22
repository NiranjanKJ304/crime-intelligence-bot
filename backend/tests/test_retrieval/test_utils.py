"""
Tests for Retrieval Utilities.
"""

from app.retrieval.utils import estimate_tokens, generate_cache_key


def test_estimate_tokens():
    assert estimate_tokens("") == 0
    assert estimate_tokens("a") == 0
    assert estimate_tokens("abcd") == 1
    assert estimate_tokens("a" * 40) == 10
    

def test_generate_cache_key():
    k1 = generate_cache_key("test", {"a": 1, "b": 2}, 10, 0.5)
    k2 = generate_cache_key("test", {"b": 2, "a": 1}, 10, 0.5) # Diff dict order
    k3 = generate_cache_key("test", {"a": 1}, 10, 0.5)
    k4 = generate_cache_key("test2", {"a": 1, "b": 2}, 10, 0.5)
    
    assert k1 == k2 # Deterministic despite dict order
    assert k1 != k3
    assert k1 != k4
