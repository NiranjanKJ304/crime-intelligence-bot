"""
Validation logic for RAG inputs.
"""

from app.llm.exceptions import LLMValidationError

class QueryValidator:
    """Validates user queries before processing."""
    
    @staticmethod
    def validate(query: str | None) -> str:
        """Validate and return the cleaned query."""
        if not query:
            raise LLMValidationError("Query cannot be empty.")
            
        cleaned = str(query).strip()
        if not cleaned:
            raise LLMValidationError("Query cannot be entirely whitespace.")
            
        if len(cleaned) < 3:
            raise LLMValidationError("Query is too short. Please provide more detail.")
            
        return cleaned
