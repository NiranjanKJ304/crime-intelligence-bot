"""
Document Store for persisting AI Documents.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.document_generation.schemas import AIDocument
from app.etl.utils import safe_json_serialize

logger = logging.getLogger(__name__)


class DocumentStore:
    """File-based JSON store for AI Documents."""

    def __init__(self, base_path: str):
        self.base_path = Path(base_path)
        self.index_path = self.base_path / "_index.json"
        
        # Ensure base path exists
        self.base_path.mkdir(parents=True, exist_ok=True)
        
        # Ensure type directories exist
        for doc_type in [
            "case_summary", "accused_profile", "victim_profile", 
            "officer_profile", "district_summary", "court_summary"
        ]:
            (self.base_path / doc_type).mkdir(parents=True, exist_ok=True)

    def save(self, doc: AIDocument) -> None:
        """Save a single document."""
        filepath = self._get_filepath(doc.document_type, doc.document_id)
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(doc.model_dump(), f, indent=2, default=safe_json_serialize)

    def save_batch(self, docs: list[AIDocument]) -> int:
        """Save a batch of documents."""
        for doc in docs:
            self.save(doc)
        return len(docs)

    def get(self, document_id: str) -> AIDocument | None:
        """Retrieve a document by ID."""
        doc_type = self._extract_type_from_id(document_id)
        if not doc_type:
            return None
            
        filepath = self._get_filepath(doc_type, document_id)
        if not filepath.exists():
            return None
            
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                return AIDocument(**data)
        except Exception as e:
            logger.error(f"Failed to read document {document_id}: {e}")
            return None

    def list_by_type(self, doc_type: str) -> list[str]:
        """List all document IDs for a given type."""
        dir_path = self.base_path / doc_type
        if not dir_path.exists():
            return []
            
        return [f.stem for f in dir_path.glob("*.json")]

    def delete_all(self) -> int:
        """Delete all documents and indices."""
        count = 0
        for p in self.base_path.rglob("*.json"):
            if p.is_file():
                p.unlink()
                count += 1
        return count

    def rebuild_index(self) -> dict[str, Any]:
        """Rebuild the master index based on stored files."""
        total = 0
        by_type: dict[str, int] = {}
        documents = {}
        
        for doc_type in [
            "case_summary", "accused_profile", "victim_profile", 
            "officer_profile", "district_summary", "court_summary"
        ]:
            dir_path = self.base_path / doc_type
            if dir_path.exists():
                files = list(dir_path.glob("*.json"))
                count = len(files)
                total += count
                by_type[doc_type] = count
                
                for f in files:
                    documents[f.stem] = f"{doc_type}/{f.name}"
                    
        index_data = {
            "total_documents": total,
            "by_type": by_type,
            "documents": documents,
            "built_at": datetime.now(timezone.utc).isoformat()
        }
        
        with open(self.index_path, "w", encoding="utf-8") as f:
            json.dump(index_data, f, indent=2, default=safe_json_serialize)
            
        return index_data

    def get_statistics(self) -> dict[str, Any]:
        """Get statistics from the index."""
        if not self.index_path.exists():
            return self.rebuild_index()
            
        with open(self.index_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _get_filepath(self, doc_type: str, document_id: str) -> Path:
        """Get the file path for a document."""
        return self.base_path / doc_type / f"{document_id}.json"

    def _extract_type_from_id(self, document_id: str) -> str | None:
        """Extract the document type from the ID (e.g., case_summary_123 -> case_summary)."""
        types = [
            "case_summary", "accused_profile", "victim_profile", 
            "officer_profile", "district_summary", "court_summary"
        ]
        for t in types:
            if document_id.startswith(f"{t}_"):
                return t
        return None
