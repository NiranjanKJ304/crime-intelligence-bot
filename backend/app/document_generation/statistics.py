"""
Statistics tracking for document generation.
"""

from __future__ import annotations

import logging
from typing import Any

from app.document_generation.schemas import DocumentStatistics

logger = logging.getLogger(__name__)


class StatisticsTracker:
    """Tracks generation metrics and errors."""

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        """Reset all statistics for a new run."""
        self.total_generated = 0
        self.by_type_generated: dict[str, int] = {}
        self.errors: list[str] = []
        self.valid_count = 0
        self.warning_count = 0
        self.error_count = 0

    def record_generated(self, doc_type: str, count: int) -> None:
        """Record successfully generated documents."""
        self.total_generated += count
        self.by_type_generated[doc_type] = self.by_type_generated.get(doc_type, 0) + count

    def record_validation(self, is_valid: bool, issues: list) -> None:
        """Record validation results."""
        if not is_valid:
            self.error_count += 1
        elif any(issue.severity == "warning" for issue in issues):
            self.warning_count += 1
        else:
            self.valid_count += 1

    def record_error(self, doc_type: str, entity_id: Any, error: str) -> None:
        """Record an error during generation."""
        msg = f"[{doc_type}] Entity {entity_id}: {error}"
        logger.error(msg)
        self.errors.append(msg)

    def summary(self) -> dict[str, Any]:
        """Return a summary of statistics."""
        return {
            "documents_generated": self.by_type_generated,
            "total_documents": self.total_generated,
            "validation": {
                "valid": self.valid_count,
                "warnings": self.warning_count,
                "errors": self.error_count,
            },
            "errors": self.errors,
        }
