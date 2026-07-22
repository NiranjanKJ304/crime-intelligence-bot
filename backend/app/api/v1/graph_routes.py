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
from app.graph.builder import GraphBuilder

router = APIRouter(prefix="/api/v1/graph", tags=["Graph"])
logger = logging.getLogger(__name__)


def _get_builder() -> GraphBuilder:
    """Initialize the GraphBuilder with core dependencies."""
    engine = get_engine()
    config = build_graph_config()
    return GraphBuilder(engine, config)


@router.post("/build", summary="Build full knowledge graph")
def build_graph() -> dict[str, Any]:
    """
    Trigger a full Neo4j graph generation from the clean PostgreSQL schema.
    Uses MERGE to prevent duplicates if interrupted.
    """
    builder = _get_builder()
    try:
        return builder.build()
    except Exception as exc:
        logger.error(f"Graph build failed: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/update", summary="Incrementally update knowledge graph")
def update_graph() -> dict[str, Any]:
    """
    Trigger an incremental update of the Neo4j graph.
    Currently, this re-runs the MERGE logic which acts as an upsert.
    """
    # Because we use MERGE, build() acts as a safe incremental upsert
    # for existing nodes, while adding any new ones.
    builder = _get_builder()
    try:
        return builder.build()
    except Exception as exc:
        logger.error(f"Graph update failed: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/statistics", summary="Get Neo4j graph statistics")
def get_statistics() -> dict[str, Any]:
    """Return live node and relationship counts directly from Neo4j."""
    builder = _get_builder()
    try:
        return builder.get_statistics()
    except Exception as exc:
        logger.error(f"Failed to fetch graph stats: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))
