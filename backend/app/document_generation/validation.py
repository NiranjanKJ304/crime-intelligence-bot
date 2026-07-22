"""
Validation logic for AI Documents.
"""

from __future__ import annotations

import logging

from app.document_generation.config import DocumentConfig
from app.document_generation.schemas import AIDocument, ValidationIssue, ValidationResult

logger = logging.getLogger(__name__)


class DocumentValidator:
    """Validates generated AI Documents."""

    def __init__(self, config: DocumentConfig):
        self.config = config

    def validate(self, doc: AIDocument) -> ValidationResult:
        """Validate a single document."""
        issues: list[ValidationIssue] = []
        is_valid = True

        # Check for empty text
        if not doc.text or not doc.text.strip():
            issues.append(ValidationIssue(
                document_id=doc.document_id,
                severity="error",
                message="Document text is empty"
            ))
            is_valid = False

        # Check for minimum length
        elif len(doc.text) < 50:
            issues.append(ValidationIssue(
                document_id=doc.document_id,
                severity="warning",
                message=f"Document text below minimum length ({len(doc.text)} chars)"
            ))

        # Check for maximum length
        if len(doc.text) > self.config.max_document_length:
            issues.append(ValidationIssue(
                document_id=doc.document_id,
                severity="warning",
                message=f"Document text exceeds maximum length ({len(doc.text)} chars)"
            ))
            # The builder or store should handle truncation if needed

        # Check metadata
        if doc.metadata.entity_id is None:
            issues.append(ValidationIssue(
                document_id=doc.document_id,
                severity="error",
                message="Missing entity_id in metadata"
            ))
            is_valid = False

        if doc.metadata.document_type != doc.document_type:
            issues.append(ValidationIssue(
                document_id=doc.document_id,
                severity="error",
                message="Document type mismatch in metadata"
            ))
            is_valid = False

        # Check document ID format
        expected_prefix = f"{doc.document_type}_"
        if not doc.document_id.startswith(expected_prefix):
            issues.append(ValidationIssue(
                document_id=doc.document_id,
                severity="error",
                message=f"Invalid document_id format (expected prefix {expected_prefix})"
            ))
            is_valid = False

        return ValidationResult(is_valid=is_valid, issues=issues)

    def validate_batch(self, docs: list[AIDocument]) -> list[ValidationResult]:
        """Validate a batch of documents, checking for duplicates."""
        results = []
        seen_ids = set()

        for doc in docs:
            result = self.validate(doc)
            
            # Check for duplicates within the batch
            if doc.document_id in seen_ids:
                result.issues.append(ValidationIssue(
                    document_id=doc.document_id,
                    severity="warning",
                    message="Duplicate document_id in batch"
                ))
            seen_ids.add(doc.document_id)
            
            results.append(result)

        return results
