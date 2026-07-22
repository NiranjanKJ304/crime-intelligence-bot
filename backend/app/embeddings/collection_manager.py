"""
Collection Manager for Qdrant.
"""

from __future__ import annotations

import logging
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams

from app.embeddings.config import EmbeddingConfig

logger = logging.getLogger(__name__)


class CollectionManager:
    """Manages the lifecycle and validation of Qdrant collections."""

    def __init__(self, client: QdrantClient, config: EmbeddingConfig, dimensions: int):
        self.client = client
        self.config = config
        self.dimensions = dimensions
        self.collection_name = config.qdrant_collection

    def collection_exists(self) -> bool:
        """Check if the collection exists in Qdrant."""
        return self.client.collection_exists(collection_name=self.collection_name)

    def create_collection(self) -> None:
        """Create the collection if it doesn't exist."""
        if self.collection_exists():
            logger.info(f"Collection '{self.collection_name}' already exists.")
            return

        logger.info(f"Creating collection '{self.collection_name}' with {self.dimensions} dimensions.")
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(
                size=self.dimensions,
                distance=Distance.COSINE
            ),
            # Enable on_disk_payload to save RAM for large collections
            on_disk_payload=True
        )

    def delete_collection(self) -> None:
        """Delete the collection if it exists."""
        if self.collection_exists():
            logger.info(f"Deleting collection '{self.collection_name}'.")
            self.client.delete_collection(collection_name=self.collection_name)

    def rebuild_collection(self) -> None:
        """Delete and recreate the collection."""
        self.delete_collection()
        self.create_collection()

    def validate_collection(self) -> dict[str, Any]:
        """Validate collection configuration against current model."""
        if not self.collection_exists():
            return {"status": "missing"}

        info = self.client.get_collection(collection_name=self.collection_name)
        
        # Access the config depending on Qdrant client version
        config = info.config.params.vectors if hasattr(info.config, 'params') else info.config.vectors
        
        actual_dim = getattr(config, 'size', None)
        actual_dist = getattr(config, 'distance', None)

        if actual_dim != self.dimensions:
            return {
                "status": "invalid_dimension",
                "expected": self.dimensions,
                "actual": actual_dim
            }
            
        return {
            "status": "valid",
            "dimensions": actual_dim,
            "distance": actual_dist,
            "points_count": info.points_count
        }

    def get_statistics(self) -> dict[str, Any]:
        """Get collection statistics."""
        if not self.collection_exists():
            return {"status": "missing", "points_count": 0}
            
        info = self.client.get_collection(collection_name=self.collection_name)
        return {
            "status": str(info.status),
            "points_count": info.points_count,
            "indexed_vectors_count": info.indexed_vectors_count
        }
