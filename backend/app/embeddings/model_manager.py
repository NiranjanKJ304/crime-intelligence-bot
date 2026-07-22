"""
Model Manager for SentenceTransformers.
"""

from __future__ import annotations

import logging
import numpy as np
from typing import Any

from app.embeddings.config import EmbeddingConfig

logger = logging.getLogger(__name__)


class ModelManager:
    """Singleton model manager for embedding generation."""

    _instance: ModelManager | None = None

    def __init__(self, config: EmbeddingConfig):
        self.config = config
        self._model = None
        self._dimensions = 0

    @classmethod
    def get_instance(cls, config: EmbeddingConfig) -> ModelManager:
        """Return the singleton instance, creating it if needed."""
        if cls._instance is None:
            cls._instance = cls(config)
        # Update config in case it changed (though it shouldn't during a run)
        cls._instance.config = config
        return cls._instance

    def load_model(self) -> None:
        """Load the SentenceTransformer model (downloads once, then cached)."""
        if self._model is not None:
            return

        logger.info(f"Loading embedding model: {self.config.embedding_model} on {self.config.embedding_device}")
        
        # Import lazily to avoid slowing down startup if embeddings aren't used
        from sentence_transformers import SentenceTransformer
        
        try:
            self._model = SentenceTransformer(
                model_name_or_path=self.config.embedding_model,
                device=self.config.embedding_device
            )
            # Determine dimensions by encoding a test string
            test_emb = self._model.encode("test")
            self._dimensions = len(test_emb)
            logger.info(f"Model loaded successfully. Dimensions: {self._dimensions}")
        except Exception as e:
            logger.error(f"Failed to load model {self.config.embedding_model}: {e}")
            raise RuntimeError(f"Model loading failed: {e}")

    def encode(self, texts: list[str]) -> np.ndarray:
        """Encode a list of texts into embedding vectors."""
        if self._model is None:
            self.load_model()
            
        if not texts:
            return np.array([])
            
        # sentence-transformers natively handles batching if needed, but we pass our configured size
        return self._model.encode(
            texts,
            batch_size=self.config.embedding_batch_size,
            show_progress_bar=False,
            convert_to_numpy=True
        )

    @property
    def dimensions(self) -> int:
        """Return the embedding dimensionality."""
        if self._model is None:
            self.load_model()
        return self._dimensions

    @property
    def model_name(self) -> str:
        """Return the currently loaded model name."""
        return self.config.embedding_model

    def validate_model(self) -> dict[str, Any]:
        """Validate model health: dimensions, test encoding."""
        if self._model is None:
            self.load_model()
            
        try:
            test_vec = self.encode(["health check"])[0]
            return {
                "status": "healthy",
                "model": self.model_name,
                "dimensions": self.dimensions,
                "test_vector_shape": test_vec.shape,
                "device": self._model.device.type if hasattr(self._model, "device") else self.config.embedding_device
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }

    def get_info(self) -> dict[str, Any]:
        """Return model metadata."""
        is_loaded = self._model is not None
        device = "unknown"
        if is_loaded and hasattr(self._model, "device"):
            device = self._model.device.type
            
        return {
            "current_model": self.config.embedding_model,
            "dimensions": self._dimensions if is_loaded else "unknown (not loaded)",
            "device": device if is_loaded else self.config.embedding_device,
            "is_loaded": is_loaded
        }
