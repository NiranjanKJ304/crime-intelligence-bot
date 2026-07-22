"""
Pydantic schemas for the Retrieval Engine.
"""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class RetrievalRequest(BaseModel):
    """Request schema for full retrieval pipeline."""
    query: str
    top_k: int | None = None
    score_threshold: float | None = None
    filters: dict[str, Any] | None = None
    max_results: int | None = None
    include_context: bool = True
    include_explanation: bool = True


class ResultExplanation(BaseModel):
    """Explanation of why a result was ranked a certain way."""
    similarity_contribution: float
    freshness_contribution: float
    type_priority_contribution: float
    metadata_richness_contribution: float
    ranking_reason: str


class RankedResult(BaseModel):
    """A ranked search result with optional explanation."""
    rank: int
    similarity_score: float
    final_score: float
    document_id: str
    document_type: str
    text_preview: str
    metadata: dict[str, Any]
    vector_id: str
    explanation: ResultExplanation | None = None


class RetrievalResponse(BaseModel):
    """Response schema for full retrieval pipeline."""
    query: str
    processed_query: str
    results: list[RankedResult]
    context: str = ""
    total_results: int
    search_time_ms: float
    model: str
    cache_hit: bool = False


class RawSearchHit(BaseModel):
    """Internal model for a raw Qdrant hit before ranking."""
    score: float
    document_id: str
    document_type: str
    text_preview: str
    metadata: dict[str, Any]
    vector_id: str


class SearchOnlyResponse(BaseModel):
    """Response schema for semantic search without context."""
    query: str
    processed_query: str
    results: list[RankedResult]
    total_results: int
    search_time_ms: float
    model: str
    cache_hit: bool = False
