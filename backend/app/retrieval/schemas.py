"""
Pydantic schemas for the Retrieval Engine.
"""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class ExtractedEntities(BaseModel):
    """Entities extracted from a natural language query."""
    district: str | None = None
    crime_type: str | None = None
    year: int | None = None
    case_numbers: list[str] = Field(default_factory=list)
    ipc_sections: list[str] = Field(default_factory=list)
    names: list[str] = Field(default_factory=list)
    document_type: str | None = None
    raw_entities: list[str] = Field(default_factory=list)


class GraphResult(BaseModel):
    """A result matched from the Neo4j Graph."""
    node: str
    relationship: str
    connected_to: str
    score: float = 1.0


class ProcessedQuery(BaseModel):
    """Output from the Query Processor."""
    original_query: str
    normalized_query: str
    entities: ExtractedEntities


class SimilarCaseRequest(BaseModel):
    """Request schema for finding similar cases."""
    case_id: str
    top_k: int | None = None


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
    graph_confidence_contribution: float = 0.0
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


class HybridMetadata(BaseModel):
    """Metadata included in the hybrid search response."""
    district: str | None = None
    crime_type: str | None = None
    year: int | None = None
    filters: dict[str, Any] = Field(default_factory=dict)
    entities_detected: list[str] = Field(default_factory=list)


class HybridStatistics(BaseModel):
    """Performance statistics for hybrid search."""
    documents: int
    graph_nodes: int
    graph_relationships: int
    retrieval_time_ms: float
    qdrant_search_ms: float
    graph_search_ms: float
    ranking_ms: float
    context_build_ms: float


class HybridResponse(BaseModel):
    """Output format for the full Hybrid Enterprise Retrieval Engine."""
    query: str
    metadata: HybridMetadata
    retrieved_documents: list[RankedResult]
    graph_results: list[GraphResult]
    context: str
    statistics: HybridStatistics


class ContextResponse(BaseModel):
    """Response containing only the formatted context string."""
    query: str
    context: str
    cache_hit: bool = False


class HealthResponse(BaseModel):
    """Health check response for the retrieval subsystem."""
    status: str
    embedding_model: str
    qdrant: str
    neo4j: str
    cache: str
    details: dict[str, Any] = Field(default_factory=dict)
