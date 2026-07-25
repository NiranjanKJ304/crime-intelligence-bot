"""
Pydantic schemas for the LLM / RAG layer.
"""

from __future__ import annotations
from typing import Any, AsyncGenerator
from pydantic import BaseModel, Field

class ChatRequest(BaseModel):
    """Incoming request for a chat query."""
    query: str
    filters: dict[str, Any] | None = None
    top_k: int | None = None
    stream: bool = False
    history: list[dict[str, str]] | None = None  # Previous conversation turns

class Citation(BaseModel):
    """A citation referencing a retrieved document."""
    document_id: str
    document_type: str
    score: float
    text_snippet: str | None = None

class RetrievalMetrics(BaseModel):
    """Performance metrics for the RAG pipeline."""
    documents_used: int
    retrieval_time_ms: float
    prompt_build_time_ms: float
    llm_time_ms: float
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

class ChatResponse(BaseModel):
    """Structured response for a chat query."""
    query: str
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    confidence: float
    retrieval: RetrievalMetrics

class ProviderResponse(BaseModel):
    """Response from the LLM provider."""
    content: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

class StreamEvent(BaseModel):
    """SSE Stream Event."""
    event: str
    data: Any
