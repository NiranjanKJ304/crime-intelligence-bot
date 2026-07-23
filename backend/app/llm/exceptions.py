"""
Custom exceptions for the LLM / RAG layer.
"""

class LLMError(Exception):
    """Base exception for all LLM errors."""
    pass

class LLMConnectionError(LLMError):
    """Raised when the connection to the LLM provider fails."""
    pass

class LLMRateLimitError(LLMError):
    """Raised when the LLM provider rate limits the request."""
    pass

class LLMValidationError(LLMError):
    """Raised when the user input or retrieved context is invalid."""
    pass

class EmptyRetrievalError(LLMError):
    """Raised when retrieval yields no results and we should short-circuit the LLM."""
    pass
