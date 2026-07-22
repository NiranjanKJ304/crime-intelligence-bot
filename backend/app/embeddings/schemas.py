"""
Pydantic schemas for the Embedding Platform.
"""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    """Request schema for semantic search."""
    query: str
    top_k: int | None = None
    filters: dict[str, Any] | None = None


class SearchResult(BaseModel):
    """A single matched document from semantic search."""
    rank: int
    score: float
    document_id: str
    document_type: str
    text_preview: str
    metadata: dict[str, Any]
    vector_id: str


class SearchResponse(BaseModel):
    """Response schema for semantic search."""
    query: str
    results: list[SearchResult]
    total_results: int
    search_time_ms: float
    model: str


class ValidationIssue(BaseModel):
    """Issue found during vector validation."""
    document_id: str
    severity: str
    message: str


class VectorValidationResult(BaseModel):
    """Result of validating a single document-vector pair."""
    is_valid: bool
    issues: list[ValidationIssue] = Field(default_factory=list)


class EmbeddingBuildResult(BaseModel):
    """Result of a full embedding build."""
    status: str
    started_at: str
    completed_at: str
    duration_seconds: float
    documents_processed: int
    embeddings_generated: int
    vectors_uploaded: int
    validation: dict[str, int]
    model: str
    collection: str
    dimensions: int
    errors: list[str]


class SyncPlan(BaseModel):
    """Plan for incremental synchronization."""
    new_documents: list[str]
    modified_documents: list[str]
    deleted_documents: list[str]
    unchanged_count: int


class SyncResult(BaseModel):
    """Result of an incremental synchronization."""
    status: str
    new_documents: int
    modified_documents: int
    deleted_documents: int
    unchanged_documents: int
    duration_seconds: float
    errors: list[str]
