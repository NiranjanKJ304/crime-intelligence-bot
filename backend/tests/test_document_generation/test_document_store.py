"""
Tests for Document Store.
"""

import json
import pytest
from pathlib import Path
from app.document_generation.document_store import DocumentStore
from app.document_generation.schemas import AIDocument, DocumentMetadata

@pytest.fixture
def temp_store(tmp_path: Path):
    return DocumentStore(str(tmp_path / "store"))

@pytest.fixture
def sample_doc():
    return AIDocument(
        document_id="case_summary_1",
        document_type="case_summary",
        text="Sample text",
        metadata=DocumentMetadata(
            document_id="case_summary_1",
            document_type="case_summary",
            entity_id=1,
            created_at="2026-07-21T00:00:00Z",
            updated_at="2026-07-21T00:00:00Z"
        )
    )

def test_save_and_get(temp_store, sample_doc):
    temp_store.save(sample_doc)
    
    retrieved = temp_store.get("case_summary_1")
    assert retrieved is not None
    assert retrieved.document_id == "case_summary_1"
    assert retrieved.text == "Sample text"
    
def test_get_not_found(temp_store):
    assert temp_store.get("case_summary_999") is None
    
def test_list_by_type(temp_store, sample_doc):
    temp_store.save(sample_doc)
    ids = temp_store.list_by_type("case_summary")
    assert len(ids) == 1
    assert ids[0] == "case_summary_1"
    
def test_delete_all(temp_store, sample_doc):
    temp_store.save(sample_doc)
    assert len(temp_store.list_by_type("case_summary")) == 1
    
    deleted = temp_store.delete_all()
    assert deleted == 1
    assert len(temp_store.list_by_type("case_summary")) == 0

def test_rebuild_index(temp_store, sample_doc):
    temp_store.save(sample_doc)
    
    index = temp_store.rebuild_index()
    assert index["total_documents"] == 1
    assert index["by_type"]["case_summary"] == 1
    assert "case_summary_1" in index["documents"]
