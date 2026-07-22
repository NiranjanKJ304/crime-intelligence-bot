"""
Batch Processor for embedding generation.
"""

from __future__ import annotations

import logging
from typing import Generator
import numpy as np

from app.document_generation.schemas import AIDocument
from app.embeddings.config import EmbeddingConfig
from app.embeddings.model_manager import ModelManager

logger = logging.getLogger(__name__)


class BatchProcessor:
    """Streams and encodes batches of documents."""

    def __init__(self, config: EmbeddingConfig, model_mgr: ModelManager):
        self.config = config
        self.model_mgr = model_mgr

    def process_documents(self, documents: list[AIDocument]) -> Generator[list[tuple[AIDocument, np.ndarray]], None, None]:
        """
        Takes a list of documents, chunks them by batch size,
        encodes them, and yields batches of (document, vector) pairs.
        """
        batch_size = self.config.embedding_batch_size
        
        for i in range(0, len(documents), batch_size):
            batch = documents[i:i + batch_size]
            texts = [doc.text for doc in batch]
            
            try:
                # model_mgr.encode handles its own internal batching logic if needed,
                # but we pass our subset to ensure we don't blow up memory
                vectors = self.model_mgr.encode(texts)
                
                # Pair them up
                pairs = list(zip(batch, vectors))
                yield pairs
            except Exception as e:
                logger.error(f"Failed to encode batch starting at index {i}: {e}")
                # We yield empty to keep the pipeline moving, the caller should handle it
                yield []
