"""
Graph API Routes.

REST endpoints for triggering and monitoring Neo4j graph construction.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException

from app.core.database import get_engine
from app.graph.config import build_graph_config
from app.graph.builder import GraphBuildError, GraphBuilder

router = APIRouter(prefix="/api/v1/graph", tags=["Graph"])
logger = logging.getLogger(__name__)


def _get_builder() -> GraphBuilder:
    """Initialize the GraphBuilder with core dependencies."""
    engine = get_engine()
    config = build_graph_config()
    return GraphBuilder(engine, config)


def _run_build(action: str) -> dict[str, Any]:
    builder = _get_builder()
    try:
        return builder.build()
    except GraphBuildError as exc:
        # Nothing was loaded: a configuration / ETL problem, not a partial success.
        logger.error("Graph %s failed: %s | %s", action, exc, exc.stats.get("errors"))
        raise HTTPException(status_code=500, detail={"message": str(exc), **exc.stats})
    except Exception as exc:
        logger.error(f"Graph {action} failed: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Graph {action} failed: {exc}")


@router.post("/build", summary="Build full knowledge graph")
def build_graph() -> dict[str, Any]:
    """
    Trigger a full Neo4j graph generation from PostgreSQL. Source tables are
    resolved to the ETL clean schema when present, otherwise the source schema.
    Uses MERGE to prevent duplicates if interrupted.
    """
    return _run_build("build")


@router.post("/update", summary="Incrementally update knowledge graph")
def update_graph() -> dict[str, Any]:
    """
    Trigger an incremental update of the Neo4j graph.
    Because we use MERGE, build() acts as a safe upsert.
    """
    return _run_build("update")


@router.get("/statistics", summary="Get Neo4j graph statistics")
def get_statistics() -> dict[str, Any]:
    """Return live node and relationship counts directly from Neo4j."""
    builder = _get_builder()
    try:
        return builder.get_statistics()
    except Exception as exc:
        logger.error(f"Failed to fetch graph stats: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))
