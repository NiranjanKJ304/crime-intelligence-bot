"""
Retrieval Engine configuration.
"""

from __future__ import annotations

from dataclasses import dataclass
from app.core.config import Settings, get_settings


@dataclass(frozen=True)
class RetrievalConfig:
    """Immutable retrieval platform configuration."""

    top_k: int
    default_score_threshold: float
    query_cache_size: int
    query_cache_ttl: int
    max_context_tokens: int
    default_document_limit: int
    qdrant_host: str
    qdrant_port: int
    qdrant_collection: str
    embedding_model: str


def build_retrieval_config(settings: Settings | None = None) -> RetrievalConfig:
    """Build a RetrievalConfig from application settings."""
    settings = settings or get_settings()
    return RetrievalConfig(
        top_k=settings.top_k,
        default_score_threshold=settings.default_score_threshold,
        query_cache_size=settings.query_cache_size,
        query_cache_ttl=settings.query_cache_ttl,
        max_context_tokens=settings.max_context_tokens,
        default_document_limit=settings.default_document_limit,
        qdrant_host=settings.qdrant_host,
        qdrant_port=settings.qdrant_port,
        qdrant_collection=settings.qdrant_collection,
        embedding_model=settings.embedding_model,
    )
