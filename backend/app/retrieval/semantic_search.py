"""
Semantic Search execution.
"""

from __future__ import annotations

import logging
from qdrant_client import QdrantClient
from qdrant_client.http import models as rest
import numpy as np

from app.retrieval.config import RetrievalConfig
from app.retrieval.schemas import RawSearchHit

logger = logging.getLogger(__name__)


class SemanticSearch:
    """Executes semantic search against Qdrant."""

    def __init__(self, client: QdrantClient, config: RetrievalConfig):
        self.client = client
        self.config = config
        self.collection_name = config.qdrant_collection

    def search(
        self, 
        vector: np.ndarray, 
        query_filter: rest.Filter | None, 
        top_k: int, 
        threshold: float
    ) -> list[RawSearchHit]:
        """Search Qdrant and return raw hits exceeding threshold."""
        try:
            results = self.client.search(
                collection_name=self.collection_name,
                query_vector=vector.tolist(),
                query_filter=query_filter,
                limit=top_k,
                score_threshold=threshold,
                with_payload=True
            )
            
            raw_hits = []
            for point in results:
                payload = point.payload or {}
                raw_hits.append(RawSearchHit(
                    score=point.score,
                    document_id=payload.get("document_id", ""),
                    document_type=payload.get("document_type", ""),
                    text_preview=payload.get("text_preview", ""),
                    metadata={
                        k: v for k, v in payload.items() 
                        if k not in ["document_id", "document_type", "text_preview"]
                    },
                    vector_id=str(point.id)
                ))
            return raw_hits
            
        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            raise RuntimeError(f"Semantic search failed: {e}")
