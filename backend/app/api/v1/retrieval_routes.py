"""
REST API Routes for Retrieval Engine.
"""

from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, HTTPException

from app.core.config import Settings, get_settings
from app.retrieval.schemas import HealthResponse
from app.retrieval.retrieval_engine import RetrievalEngine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/retrieval", tags=["Retrieval Engine"])


def get_engine(settings: Settings = Depends(get_settings)) -> RetrievalEngine:
    """Dependency provider for RetrievalEngine."""
    return RetrievalEngine(settings)


@router.get("/statistics")
def get_statistics(engine: RetrievalEngine = Depends(get_engine)) -> dict:
    """Get retrieval analytics and cache metrics."""
    try:
        analytics_summary = engine.analytics.summary()
        cache_stats = engine.cache.stats()
        
        # Merge cache size into the cache_stats section
        if "cache_stats" in analytics_summary:
            analytics_summary["cache_stats"]["size"] = cache_stats["size"]
            
        return analytics_summary
    except Exception as e:
        logger.error(f"Statistics failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health", response_model=HealthResponse)
def health_check(engine: RetrievalEngine = Depends(get_engine)) -> HealthResponse:
    """Get the health status of the retrieval subsystems."""
    try:
        return engine.health()
    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/config")
def get_configuration(engine: RetrievalEngine = Depends(get_engine)) -> dict:
    """Get the current configuration of the retrieval engine."""
    try:
        return engine.get_config()
    except Exception as e:
        logger.error(f"Config check failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

