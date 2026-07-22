"""
Tests for Vector Validation.
"""

import numpy as np

from app.document_generation.schemas import AIDocument, DocumentMetadata
from app.embeddings.config import EmbeddingConfig
from app.embeddings.vector_validator import VectorValidator


def test_validator_valid():
    config = EmbeddingConfig("", 10, "cpu", "", 0, "", 10, "")
    validator = VectorValidator(config, 384)
    
    doc = AIDocument(
        document_id="case_summary_1",
        document_type="case_summary",
        text="Sample text",
        metadata=DocumentMetadata(
            document_id="case_summary_1",
            document_type="case_summary",
            entity_id=1,
            created_at="now",
            updated_at="now"
        )
    )
    vector = np.random.rand(384)
    
    res = validator.validate(doc, vector)
    assert res.is_valid
    assert len(res.issues) == 0


def test_validator_invalid_dim():
    config = EmbeddingConfig("", 10, "cpu", "", 0, "", 10, "")
    validator = VectorValidator(config, 384)
    
    doc = AIDocument(
        document_id="case_summary_1",
        document_type="case_summary",
        text="Sample text",
        metadata=DocumentMetadata(
            document_id="case_summary_1",
            document_type="case_summary",
            entity_id=1,
            created_at="now",
            updated_at="now"
        )
    )
    vector = np.random.rand(300) # Wrong dimension
    
    res = validator.validate(doc, vector)
    assert not res.is_valid
    assert any("Dimension mismatch" in i.message for i in res.issues)


def test_validator_nan():
    config = EmbeddingConfig("", 10, "cpu", "", 0, "", 10, "")
    validator = VectorValidator(config, 384)
    
    doc = AIDocument(
        document_id="case_summary_1",
        document_type="case_summary",
        text="Sample text",
        metadata=DocumentMetadata(
            document_id="case_summary_1",
            document_type="case_summary",
            entity_id=1,
            created_at="now",
            updated_at="now"
        )
    )
    vector = np.random.rand(384)
    vector[0] = np.nan
    
    res = validator.validate(doc, vector)
    assert not res.is_valid
    assert any("NaN" in i.message for i in res.issues)
