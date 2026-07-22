"""
Tests for Sync Manager.
"""

import json
from pathlib import Path
from unittest.mock import Mock

from app.embeddings.config import EmbeddingConfig
from app.embeddings.sync_manager import SyncManager


def test_detect_changes(tmp_path: Path):
    config = EmbeddingConfig(
        embedding_model="test-model",
        embedding_batch_size=10,
        embedding_device="cpu",
        qdrant_host="localhost",
        qdrant_port=6333,
        qdrant_collection="test",
        top_k=10,
        document_store_path=str(tmp_path)
    )
    
    # Create initial manifest
    manifest = {
        "model": "test-model",
        "collection": "test",
        "documents": {
            "doc1": "2024-01-01T00:00:00Z", # unchanged
            "doc2": "2024-01-01T00:00:00Z", # modified
            "doc3": "2024-01-01T00:00:00Z"  # deleted
        }
    }
    with open(tmp_path / "_sync_manifest.json", "w") as f:
        json.dump(manifest, f)
        
    # Mock document store
    mock_store = Mock()
    mock_store.get_statistics.return_value = {
        "documents": {
            "doc1": "path/doc1",
            "doc2": "path/doc2",
            "doc4": "path/doc4" # new
        }
    }
    
    def mock_get(doc_id):
        m = Mock()
        if doc_id == "doc1":
            m.metadata.updated_at = "2024-01-01T00:00:00Z"
        elif doc_id == "doc2":
            m.metadata.updated_at = "2024-01-02T00:00:00Z" # changed!
        elif doc_id == "doc4":
            m.metadata.updated_at = "2024-01-02T00:00:00Z"
        return m
        
    mock_store.get.side_effect = mock_get
    
    sync_mgr = SyncManager(config)
    plan = sync_mgr.detect_changes(mock_store)
    
    assert plan.unchanged_count == 1
    assert "doc4" in plan.new_documents
    assert "doc2" in plan.modified_documents
    assert "doc3" in plan.deleted_documents
