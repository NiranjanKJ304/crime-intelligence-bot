"""
Vector Validation logic.
"""

from __future__ import annotations

import logging
import numpy as np

from app.document_generation.schemas import AIDocument
from app.embeddings.config import EmbeddingConfig
from app.embeddings.schemas import VectorValidationResult, ValidationIssue

logger = logging.getLogger(__name__)


class VectorValidator:
    """Validates document-vector pairs before upload."""

    def __init__(self, config: EmbeddingConfig, expected_dim: int):
        self.config = config
        self.expected_dim = expected_dim

    def validate(self, doc: AIDocument, vector: np.ndarray) -> VectorValidationResult:
        """Validate a single document-vector pair."""
        issues: list[ValidationIssue] = []
        is_valid = True

        # Check for empty text in source document
        if not doc.text or not doc.text.strip():
            issues.append(ValidationIssue(
                document_id=doc.document_id,
                severity="error",
                message="Source document text is empty"
            ))
            is_valid = False

        # Check if vector is null/None
        if vector is None:
            issues.append(ValidationIssue(
                document_id=doc.document_id,
                severity="error",
                message="Generated vector is null"
            ))
            return VectorValidationResult(is_valid=False, issues=issues)

        # Check dimension mismatch
        if vector.shape[0] != self.expected_dim:
            issues.append(ValidationIssue(
                document_id=doc.document_id,
                severity="error",
                message=f"Dimension mismatch: expected {self.expected_dim}, got {vector.shape[0]}"
            ))
            is_valid = False

        # Check for NaN or Inf values
        if np.isnan(vector).any():
            issues.append(ValidationIssue(
                document_id=doc.document_id,
                severity="error",
                message="Vector contains NaN values"
            ))
            is_valid = False
            
        if np.isinf(vector).any():
            issues.append(ValidationIssue(
                document_id=doc.document_id,
                severity="error",
                message="Vector contains Infinity values"
            ))
            is_valid = False

        return VectorValidationResult(is_valid=is_valid, issues=issues)

    def validate_batch(self, pairs: list[tuple[AIDocument, np.ndarray]]) -> list[tuple[AIDocument, np.ndarray]]:
        """Validate a batch of pairs and return only the valid ones."""
        valid_pairs = []
        
        for doc, vector in pairs:
            result = self.validate(doc, vector)
            if result.is_valid:
                valid_pairs.append((doc, vector))
            else:
                for issue in result.issues:
                    logger.warning(f"Validation {issue.severity}: {issue.message}")
                    
        return valid_pairs
