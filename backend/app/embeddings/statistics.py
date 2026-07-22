"""
Statistics tracking for embedding generation.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class EmbeddingStatistics:
    """Tracks generation metrics and errors."""

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        """Reset all statistics for a new run."""
        self.documents_read = 0
        self.embeddings_generated = 0
        self.vectors_uploaded = 0
        self.errors: list[str] = []
        self.valid_count = 0
        self.skipped_count = 0
        self.error_count = 0

    def record_read(self, count: int) -> None:
        """Record documents read from store."""
        self.documents_read += count

    def record_encoded(self, count: int) -> None:
        """Record successfully generated embeddings."""
        self.embeddings_generated += count

    def record_uploaded(self, count: int) -> None:
        """Record vectors uploaded to Qdrant."""
        self.vectors_uploaded += count

    def record_validation(self, is_valid: bool, issues: list) -> None:
        """Record validation results."""
        if not is_valid:
            self.error_count += 1
        elif any(issue.severity == "warning" for issue in issues):
            self.skipped_count += 1
        else:
            self.valid_count += 1

    def record_error(self, doc_id: str, error: str) -> None:
        """Record an error during processing."""
        msg = f"Document {doc_id}: {error}"
        logger.error(msg)
        self.errors.append(msg)

    def summary(self) -> dict[str, Any]:
        """Return a summary of statistics."""
        return {
            "documents_processed": self.documents_read,
            "embeddings_generated": self.embeddings_generated,
            "vectors_uploaded": self.vectors_uploaded,
            "validation": {
                "valid": self.valid_count,
                "skipped": self.skipped_count,
                "errors": self.error_count,
            },
            "errors": self.errors,
        }
