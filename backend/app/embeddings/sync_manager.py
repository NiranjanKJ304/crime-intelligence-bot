"""
Incremental synchronization manager.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from app.embeddings.config import EmbeddingConfig
from app.embeddings.schemas import SyncPlan
from app.document_generation.document_store import DocumentStore
from app.etl.utils import safe_json_serialize

logger = logging.getLogger(__name__)


class SyncManager:
    """Manages incremental synchronization using a manifest file."""

    def __init__(self, config: EmbeddingConfig):
        self.config = config
        self.manifest_path = Path(config.document_store_path) / "_sync_manifest.json"

    def load_manifest(self) -> dict:
        """Load the sync manifest."""
        if not self.manifest_path.exists():
            return {
                "model": self.config.embedding_model,
                "collection": self.config.qdrant_collection,
                "documents": {}
            }
            
        try:
            with open(self.manifest_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load sync manifest: {e}")
            return {
                "model": self.config.embedding_model,
                "collection": self.config.qdrant_collection,
                "documents": {}
            }

    def save_manifest(self, document_updates: dict[str, str]) -> None:
        """Save updates to the sync manifest."""
        manifest = self.load_manifest()
        
        # Update model info in case it changed (which would trigger full rebuild later)
        manifest["model"] = self.config.embedding_model
        manifest["collection"] = self.config.qdrant_collection
        
        # Apply updates
        manifest["documents"].update(document_updates)
        
        with open(self.manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, default=safe_json_serialize)

    def remove_from_manifest(self, document_ids: list[str]) -> None:
        """Remove deleted documents from the manifest."""
        manifest = self.load_manifest()
        for doc_id in document_ids:
            manifest["documents"].pop(doc_id, None)
            
        with open(self.manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, default=safe_json_serialize)

    def detect_changes(self, store: DocumentStore) -> SyncPlan:
        """Compare current store state against the manifest."""
        manifest = self.load_manifest()
        
        # If model changed, everything is "modified" (needs re-embed)
        model_changed = manifest.get("model") != self.config.embedding_model
        if model_changed:
            logger.warning(f"Model changed from {manifest.get('model')} to {self.config.embedding_model}. Full rebuild required.")
            
        store_index = store.get_statistics()
        store_docs = store_index.get("documents", {})
        
        manifest_docs = manifest.get("documents", {})
        
        new_docs = []
        modified_docs = []
        deleted_docs = []
        unchanged_count = 0
        
        # Check for new and modified
        for doc_id, filepath in store_docs.items():
            doc = store.get(doc_id)
            if not doc:
                continue
                
            updated_at = doc.metadata.updated_at
            
            if doc_id not in manifest_docs:
                new_docs.append(doc_id)
            elif model_changed or manifest_docs[doc_id] != updated_at:
                modified_docs.append(doc_id)
            else:
                unchanged_count += 1
                
        # Check for deleted
        for doc_id in manifest_docs:
            if doc_id not in store_docs:
                deleted_docs.append(doc_id)
                
        return SyncPlan(
            new_documents=new_docs,
            modified_documents=modified_docs,
            deleted_documents=deleted_docs,
            unchanged_count=unchanged_count
        )
