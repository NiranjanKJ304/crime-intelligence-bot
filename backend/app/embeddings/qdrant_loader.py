"""
Qdrant Loader for batch uploading vectors.
"""

from __future__ import annotations

import logging
import time

from qdrant_client import QdrantClient
from qdrant_client.http.models import PointStruct

from app.embeddings.config import EmbeddingConfig

logger = logging.getLogger(__name__)


class QdrantLoader:
    """Handles batch uploading of vectors and payloads to Qdrant."""

    def __init__(self, client: QdrantClient, config: EmbeddingConfig):
        self.client = client
        self.config = config
        self.collection_name = config.qdrant_collection

    def upsert_batch(self, points: list[PointStruct]) -> int:
        """Upsert a batch of points with retry logic."""
        if not points:
            return 0

        max_retries = 3
        backoff = 1

        for attempt in range(max_retries):
            try:
                self.client.upsert(
                    collection_name=self.collection_name,
                    points=points,
                    wait=True  # Ensure indexing is aware
                )
                return len(points)
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"Failed to upsert batch after {max_retries} attempts: {e}")
                    raise
                
                logger.warning(f"Upsert failed (attempt {attempt+1}/{max_retries}): {e}. Retrying in {backoff}s...")
                time.sleep(backoff)
                backoff *= 2
                
        return 0

    def delete_points(self, point_ids: list[str]) -> int:
        """Delete specific points from the collection."""
        if not point_ids:
            return 0
            
        try:
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=point_ids,
                wait=True
            )
            return len(point_ids)
        except Exception as e:
            logger.error(f"Failed to delete {len(point_ids)} points: {e}")
            raise
