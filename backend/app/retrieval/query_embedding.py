"""
Query Embedding wrapper.
"""

from __future__ import annotations

import logging
import numpy as np

from app.embeddings.model_manager import ModelManager

logger = logging.getLogger(__name__)


class QueryEmbedding:
    """Wraps ModelManager to embed single queries."""

    def __init__(self, model_mgr: ModelManager):
        self.model_mgr = model_mgr

    def embed(self, query: str) -> np.ndarray:
        """Generate a single embedding for a query."""
        if not query or not query.strip():
            raise ValueError("Query cannot be empty for embedding.")
            
        try:
            # model_mgr.encode expects a list and returns an ndarray
            vectors = self.model_mgr.encode([query])
            if vectors is None or len(vectors) == 0:
                raise RuntimeError("Model returned empty vectors.")
                
            return vectors[0]
        except Exception as e:
            logger.error(f"Failed to embed query: {e}")
            raise
