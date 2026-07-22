"""
Tests for Validation logic.
"""

from app.document_generation.config import DocumentConfig
from app.document_generation.schemas import AIDocument, DocumentMetadata
from app.document_generation.validation import DocumentValidator


def test_validator_empty_text():
    config = DocumentConfig(
        clean_schema="clean",
        document_store_path="/tmp",
        batch_size=10,
        max_document_length=1000
    )
    validator = DocumentValidator(config)
    
    doc = AIDocument(
        document_id="case_summary_1",
        document_type="case_summary",
        text="",
        metadata=DocumentMetadata(
            document_id="case_summary_1",
            document_type="case_summary",
            entity_id=1,
            created_at="2026-07-21T00:00:00Z",
            updated_at="2026-07-21T00:00:00Z"
        )
    )
    
    res = validator.validate(doc)
    assert not res.is_valid
    assert any(i.message == "Document text is empty" for i in res.issues)

def test_validator_min_length():
    config = DocumentConfig(
        clean_schema="clean",
        document_store_path="/tmp",
        batch_size=10,
        max_document_length=1000
    )
    validator = DocumentValidator(config)
    
    doc = AIDocument(
        document_id="case_summary_1",
        document_type="case_summary",
        text="Too short",
        metadata=DocumentMetadata(
            document_id="case_summary_1",
            document_type="case_summary",
            entity_id=1,
            created_at="2026-07-21T00:00:00Z",
            updated_at="2026-07-21T00:00:00Z"
        )
    )
    
    res = validator.validate(doc)
    assert res.is_valid
    assert any(i.severity == "warning" for i in res.issues)

def test_validator_invalid_id():
    config = DocumentConfig(
        clean_schema="clean",
        document_store_path="/tmp",
        batch_size=10,
        max_document_length=1000
    )
    validator = DocumentValidator(config)
    
    doc = AIDocument(
        document_id="invalid_1",
        document_type="case_summary",
        text="A sufficiently long text for passing validation rule of minimum length",
        metadata=DocumentMetadata(
            document_id="invalid_1",
            document_type="case_summary",
            entity_id=1,
            created_at="2026-07-21T00:00:00Z",
            updated_at="2026-07-21T00:00:00Z"
        )
    )
    
    res = validator.validate(doc)
    assert not res.is_valid
    assert any("Invalid document_id format" in i.message for i in res.issues)
