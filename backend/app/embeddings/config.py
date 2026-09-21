"""
Embedding Platform configuration.
"""

from __future__ import annotations

from dataclasses import dataclass
from app.core.config import Settings, get_settings


@dataclass(frozen=True)
class EmbeddingConfig:
    """Immutable embedding platform configuration."""

    embedding_model: str
    embedding_batch_size: int
    embedding_device: str
    qdrant_host: str
    qdrant_port: int
    qdrant_collection: str
    top_k: int
    document_store_path: str
    qdrant_path: str = "./qdrant_storage"


def build_embedding_config(settings: Settings | None = None) -> EmbeddingConfig:
    """Build an EmbeddingConfig from application settings."""
    settings = settings or get_settings()
    return EmbeddingConfig(
        embedding_model=settings.embedding_model,
        embedding_batch_size=settings.embedding_batch_size,
        embedding_device=settings.embedding_device,
        qdrant_host=settings.qdrant_host,
        qdrant_port=settings.qdrant_port,
        qdrant_collection=settings.qdrant_collection,
        top_k=settings.top_k,
        document_store_path=settings.document_store_path,
        qdrant_path=settings.qdrant_path,
    )
