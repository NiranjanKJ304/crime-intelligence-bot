"""
Embedding Manager. Orchestrates the pipeline.
"""

from __future__ import annotations

import logging
from typing import Generator
from qdrant_client.http.models import PointStruct

from app.document_generation.schemas import AIDocument
from app.embeddings.config import EmbeddingConfig
from app.embeddings.model_manager import ModelManager
from app.embeddings.batch_processor import BatchProcessor
from app.embeddings.vector_validator import VectorValidator
from app.embeddings.collection_manager import CollectionManager
from app.embeddings.qdrant_loader import QdrantLoader
from app.embeddings.statistics import EmbeddingStatistics
from app.embeddings.utils import build_payload, generate_point_id

logger = logging.getLogger(__name__)


class EmbeddingManager:
    """Orchestrates the embedding pipeline components."""

    def __init__(self, 
                 config: EmbeddingConfig,
                 model_mgr: ModelManager,
                 batch_processor: BatchProcessor,
                 validator: VectorValidator,
                 collection_mgr: CollectionManager,
                 loader: QdrantLoader,
                 stats: EmbeddingStatistics):
        self.config = config
        self.model_mgr = model_mgr
        self.batch_processor = batch_processor
        self.validator = validator
        self.collection_mgr = collection_mgr
        self.loader = loader
        self.stats = stats

    def process_document_stream(self, document_stream: Generator[list[AIDocument], None, None]) -> dict[str, str]:
        """
        Process batches of documents, returning a dictionary of successfully processed 
        document IDs and their updated_at timestamps (for manifest).
        """
        processed_updates = {}
        
        for batch in document_stream:
            if not batch:
                continue
                
            self.stats.record_read(len(batch))
            
            # Encode
            for pairs in self.batch_processor.process_documents(batch):
                if not pairs:
                    continue
                    
                self.stats.record_encoded(len(pairs))
                
                # Validate
                valid_pairs = self.validator.validate_batch(pairs)
                
                # Record validation stats
                for doc, vector in pairs:
                    val_result = self.validator.validate(doc, vector)
                    self.stats.record_validation(val_result.is_valid, val_result.issues)
                    
                if not valid_pairs:
                    continue
                    
                # Create Points
                points = []
                for doc, vector in valid_pairs:
                    try:
                        point_id = generate_point_id(doc.document_id)
                        payload = build_payload(doc)
                        
                        points.append(
                            PointStruct(
                                id=point_id,
                                vector=vector.tolist(),
                                payload=payload
                            )
                        )
                    except Exception as e:
                        self.stats.record_error(doc.document_id, f"Payload/Point generation failed: {e}")
                        
                # Upload
                if points:
                    try:
                        uploaded_count = self.loader.upsert_batch(points)
                        self.stats.record_uploaded(uploaded_count)
                        
                        # Record successes for manifest
                        for doc, _ in valid_pairs:
                            processed_updates[doc.document_id] = doc.metadata.updated_at
                            
                    except Exception as e:
                        # Batch upload completely failed
                        for doc, _ in valid_pairs:
                            self.stats.record_error(doc.document_id, f"Upload failed: {e}")
                            
        return processed_updates
