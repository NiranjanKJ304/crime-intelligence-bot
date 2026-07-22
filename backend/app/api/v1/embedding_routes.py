"""
REST API Routes for Embedding Platform.
"""

from __future__ import annotations

import logging
import os
from fastapi import APIRouter, Depends, HTTPException

from app.core.config import Settings, get_settings
from app.embeddings.config import EmbeddingConfig, build_embedding_config
from app.embeddings.embedding_pipeline import EmbeddingPipeline
from app.embeddings.schemas import (
    EmbeddingBuildResult,
    SyncResult,
    SearchRequest,
    SearchResponse
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/embedding", tags=["Embedding Platform"])


def get_pipeline(settings: Settings = Depends(get_settings)) -> EmbeddingPipeline:
    """Dependency provider for EmbeddingPipeline."""
    config = build_embedding_config(settings)
    return EmbeddingPipeline(config)


@router.get("/health")
def get_health(pipeline: EmbeddingPipeline = Depends(get_pipeline)) -> dict:
    """Return embedding health status."""
    try:
        qdrant_stats = pipeline.collection_mgr.get_statistics()
        is_qdrant_connected = qdrant_stats.get("status") == "green" or qdrant_stats.get("status") == "ok" or qdrant_stats.get("points_count") is not None
        
        return {
            "status": "healthy" if pipeline.model_mgr.dimensions > 0 else "degraded",
            "model_loaded": pipeline.model_mgr.dimensions > 0,
            "model_name": pipeline.model_mgr.model_name,
            "dimension": pipeline.model_mgr.dimensions,
            "cache_directory": os.environ.get("HF_HOME", "/app/.cache/huggingface"),
            "qdrant_connected": is_qdrant_connected
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        return {
            "status": "unhealthy",
            "error": str(e)
        }


@router.post("/build", response_model=EmbeddingBuildResult)
def build_embeddings(pipeline: EmbeddingPipeline = Depends(get_pipeline)) -> EmbeddingBuildResult:
    """Generate all embeddings and upload to Qdrant (full rebuild)."""
    try:
        return pipeline.build()
    except Exception as e:
        logger.error(f"Build failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/update", response_model=SyncResult)
def update_embeddings(pipeline: EmbeddingPipeline = Depends(get_pipeline)) -> SyncResult:
    """Incrementally synchronize embeddings for new/modified/deleted documents."""
    try:
        return pipeline.update()
    except Exception as e:
        logger.error(f"Update failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search", response_model=SearchResponse)
def search_embeddings(
    request: SearchRequest,
    pipeline: EmbeddingPipeline = Depends(get_pipeline)
) -> SearchResponse:
    """Semantic search over the embedded documents."""
    try:
        return pipeline.search_service.search(request)
    except Exception as e:
        logger.error(f"Search failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/statistics")
def get_statistics(pipeline: EmbeddingPipeline = Depends(get_pipeline)) -> dict:
    """Get embedding platform and Qdrant collection statistics."""
    try:
        qdrant_stats = pipeline.collection_mgr.get_statistics()
        doc_stats = pipeline.doc_store.get_statistics()
        
        return {
            "total_documents": doc_stats.get("total_documents", 0),
            "collection_size": qdrant_stats.get("points_count", 0),
            "embedding_model": pipeline.config.embedding_model,
            "dimensions": pipeline.model_mgr.dimensions,
            "collection": pipeline.config.qdrant_collection,
            "qdrant_status": qdrant_stats.get("status", "unknown")
        }
    except Exception as e:
        logger.error(f"Stats failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/models")
def get_models(pipeline: EmbeddingPipeline = Depends(get_pipeline)) -> dict:
    """Get information about the current embedding model."""
    try:
        return pipeline.model_mgr.get_info()
    except Exception as e:
        logger.error(f"Model info failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/rebuild", response_model=EmbeddingBuildResult)
def rebuild_embeddings(pipeline: EmbeddingPipeline = Depends(get_pipeline)) -> EmbeddingBuildResult:
    """Delete collection and regenerate all embeddings (same as /build)."""
    try:
        return pipeline.rebuild()
    except Exception as e:
        logger.error(f"Rebuild failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
