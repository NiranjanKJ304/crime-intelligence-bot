"""
Embedding Pipeline facade.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Generator

from qdrant_client import QdrantClient

from app.document_generation.document_store import DocumentStore
from app.document_generation.schemas import AIDocument
from app.embeddings.config import EmbeddingConfig
from app.embeddings.schemas import EmbeddingBuildResult, SyncResult
from app.embeddings.model_manager import ModelManager
from app.embeddings.batch_processor import BatchProcessor
from app.embeddings.vector_validator import VectorValidator
from app.embeddings.collection_manager import CollectionManager
from app.embeddings.qdrant_loader import QdrantLoader
from app.embeddings.qdrant_search import QdrantSearch
from app.embeddings.sync_manager import SyncManager
from app.embeddings.statistics import EmbeddingStatistics
from app.embeddings.embedding_manager import EmbeddingManager
from app.embeddings.utils import generate_point_id

logger = logging.getLogger(__name__)


class EmbeddingPipeline:
    """High-level API for the embedding platform."""

    def __init__(self, config: EmbeddingConfig):
        self.config = config
        
        # Initialize Qdrant Client
        self.qdrant_client = QdrantClient(
            host=config.qdrant_host,
            port=config.qdrant_port
        )
        
        # Initialize Document Store
        self.doc_store = DocumentStore(config.document_store_path)
        
        # Initialize Components
        self.model_mgr = ModelManager.get_instance(config)
        self.batch_processor = BatchProcessor(config, self.model_mgr)
        self.collection_mgr = CollectionManager(self.qdrant_client, config, self.model_mgr.dimensions)
        self.validator = VectorValidator(config, self.model_mgr.dimensions)
        self.loader = QdrantLoader(self.qdrant_client, config)
        self.search_service = QdrantSearch(self.qdrant_client, config, self.model_mgr)
        self.sync_mgr = SyncManager(config)
        self.stats = EmbeddingStatistics()
        
        self.manager = EmbeddingManager(
            config=config,
            model_mgr=self.model_mgr,
            batch_processor=self.batch_processor,
            validator=self.validator,
            collection_mgr=self.collection_mgr,
            loader=self.loader,
            stats=self.stats
        )

    def _document_generator(self, doc_ids: list[str], batch_size: int = 500) -> Generator[list[AIDocument], None, None]:
        """Generator that yields batches of AIDocuments from the store."""
        batch = []
        for doc_id in doc_ids:
            doc = self.doc_store.get(doc_id)
            if doc:
                batch.append(doc)
                
            if len(batch) >= batch_size:
                yield batch
                batch = []
                
        if batch:
            yield batch

    def build(self) -> EmbeddingBuildResult:
        """Full build of all documents."""
        start_time = time.time()
        start_dt = datetime.now(timezone.utc).isoformat()
        
        self.stats.reset()
        
        # 1. Load model and get dims
        self.model_mgr.load_model()
        self.collection_mgr.dimensions = self.model_mgr.dimensions
        self.validator.expected_dim = self.model_mgr.dimensions
        
        # 2. Rebuild collection
        self.collection_mgr.rebuild_collection()
        
        # 3. Get all documents
        store_stats = self.doc_store.get_statistics()
        doc_map = store_stats.get("documents", {})
        all_doc_ids = list(doc_map.keys())
        
        if not all_doc_ids:
            return EmbeddingBuildResult(
                status="success",
                started_at=start_dt,
                completed_at=datetime.now(timezone.utc).isoformat(),
                duration_seconds=0.0,
                documents_processed=0,
                embeddings_generated=0,
                vectors_uploaded=0,
                validation={"valid": 0, "skipped": 0, "errors": 0},
                model=self.config.embedding_model,
                collection=self.config.qdrant_collection,
                dimensions=self.model_mgr.dimensions,
                errors=[]
            )

        # 4. Process
        doc_stream = self._document_generator(all_doc_ids)
        processed_updates = self.manager.process_document_stream(doc_stream)
        
        # 5. Update Manifest
        self.sync_mgr.save_manifest(processed_updates)
        
        end_time = time.time()
        
        summary = self.stats.summary()
        return EmbeddingBuildResult(
            status="success" if not summary["errors"] else "partial_success",
            started_at=start_dt,
            completed_at=datetime.now(timezone.utc).isoformat(),
            duration_seconds=round(end_time - start_time, 2),
            documents_processed=summary["documents_processed"],
            embeddings_generated=summary["embeddings_generated"],
            vectors_uploaded=summary["vectors_uploaded"],
            validation=summary["validation"],
            model=self.config.embedding_model,
            collection=self.config.qdrant_collection,
            dimensions=self.model_mgr.dimensions,
            errors=summary["errors"]
        )

    def update(self) -> SyncResult:
        """Incremental synchronization."""
        start_time = time.time()
        
        # Ensure model is loaded and collection exists
        self.model_mgr.load_model()
        self.collection_mgr.dimensions = self.model_mgr.dimensions
        self.validator.expected_dim = self.model_mgr.dimensions
        self.collection_mgr.create_collection()
        
        # 1. Detect changes
        plan = self.sync_mgr.detect_changes(self.doc_store)
        
        if not (plan.new_documents or plan.modified_documents or plan.deleted_documents):
            return SyncResult(
                status="success",
                new_documents=0,
                modified_documents=0,
                deleted_documents=0,
                unchanged_documents=plan.unchanged_count,
                duration_seconds=0.0,
                errors=[]
            )
            
        self.stats.reset()
        errors = []
        
        # 2. Process Deletions
        if plan.deleted_documents:
            point_ids = [generate_point_id(doc_id) for doc_id in plan.deleted_documents]
            try:
                self.loader.delete_points(point_ids)
                self.sync_mgr.remove_from_manifest(plan.deleted_documents)
            except Exception as e:
                errors.append(f"Failed to delete vectors: {e}")
                
        # 3. Process Additions/Modifications
        docs_to_process = plan.new_documents + plan.modified_documents
        if docs_to_process:
            doc_stream = self._document_generator(docs_to_process)
            processed_updates = self.manager.process_document_stream(doc_stream)
            self.sync_mgr.save_manifest(processed_updates)
            
        end_time = time.time()
        
        return SyncResult(
            status="success" if not self.stats.errors and not errors else "partial_success",
            new_documents=len(plan.new_documents),
            modified_documents=len(plan.modified_documents),
            deleted_documents=len(plan.deleted_documents),
            unchanged_documents=plan.unchanged_count,
            duration_seconds=round(end_time - start_time, 2),
            errors=errors + self.stats.errors
        )

    def rebuild(self) -> EmbeddingBuildResult:
        """Alias for build(). Deletes collection and regenerates."""
        return self.build()
