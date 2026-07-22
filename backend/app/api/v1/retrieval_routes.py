"""
REST API Routes for Retrieval Engine.
"""

from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, HTTPException

from app.core.config import Settings, get_settings
from app.retrieval.schemas import (
    RetrievalRequest, RetrievalResponse, SearchOnlyResponse, ResultExplanation
)
from app.retrieval.retrieval_engine import RetrievalEngine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/retrieval", tags=["Retrieval Engine"])


def get_engine(settings: Settings = Depends(get_settings)) -> RetrievalEngine:
    """Dependency provider for RetrievalEngine."""
    return RetrievalEngine(settings)


@router.post("/query", response_model=RetrievalResponse)
def full_retrieval_query(
    request: RetrievalRequest,
    engine: RetrievalEngine = Depends(get_engine)
) -> RetrievalResponse:
    """Execute the full retrieval pipeline returning LLM-ready context."""
    try:
        return engine.query(request)
    except ValueError as e:
        logger.warning(f"Bad request in query: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Retrieval query failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search", response_model=SearchOnlyResponse)
def semantic_search_only(
    request: RetrievalRequest,
    engine: RetrievalEngine = Depends(get_engine)
) -> SearchOnlyResponse:
    """Execute raw semantic search and ranking (no context)."""
    try:
        return engine.search(request)
    except ValueError as e:
        logger.warning(f"Bad request in search: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Retrieval search failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/explain/{rank_index}", response_model=ResultExplanation)
def explain_result(
    rank_index: int,
    request: RetrievalRequest,
    engine: RetrievalEngine = Depends(get_engine)
) -> ResultExplanation:
    """Explain why a specific result (by rank index 0-based) was ranked as it was."""
    try:
        return engine.explain(rank_index, request)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Explain failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


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


@router.delete("/cache")
def clear_cache(engine: RetrievalEngine = Depends(get_engine)) -> dict:
    """Clear the query cache."""
    try:
        removed = engine.cache.clear()
        return {"status": "success", "items_removed": removed}
    except Exception as e:
        logger.error(f"Cache clear failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
