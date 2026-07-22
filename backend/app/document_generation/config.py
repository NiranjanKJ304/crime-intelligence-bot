"""
Document Generation configuration.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import Settings, get_settings


@dataclass(frozen=True)
class DocumentConfig:
    """Immutable document generation configuration."""

    clean_schema: str
    document_store_path: str
    batch_size: int
    max_document_length: int


def build_document_config(settings: Settings | None = None) -> DocumentConfig:
    """Build a DocumentConfig from application settings."""
    settings = settings or get_settings()
    return DocumentConfig(
        clean_schema=settings.clean_schema,
        document_store_path=settings.document_store_path,
        batch_size=settings.document_batch_size,
        max_document_length=settings.max_document_length,
    )
