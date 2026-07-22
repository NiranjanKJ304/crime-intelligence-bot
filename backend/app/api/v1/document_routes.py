"""
Document API Routes.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException

from app.core.database import get_engine
from app.document_generation.config import build_document_config
from app.document_generation.document_builder import DocumentOrchestrator
from app.document_generation.document_store import DocumentStore
from app.document_generation.schemas import BuildResult

router = APIRouter(prefix="/api/v1/documents", tags=["AI Documents"])
logger = logging.getLogger(__name__)


def _get_orchestrator() -> DocumentOrchestrator:
    """Initialize the DocumentOrchestrator with core dependencies."""
    engine = get_engine()
    config = build_document_config()
    return DocumentOrchestrator(engine, config)


def _get_store() -> DocumentStore:
    """Initialize the DocumentStore."""
    config = build_document_config()
    return DocumentStore(config.document_store_path)


@router.post("/build", summary="Generate all AI documents", response_model=BuildResult)
def build_documents() -> Any:
    """
    Trigger a full generation of AI documents from the clean PostgreSQL schema.
    """
    orchestrator = _get_orchestrator()
    try:
        return orchestrator.build_all()
    except Exception as exc:
        logger.error(f"Document generation failed: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/update", summary="Generate only changed documents", response_model=BuildResult)
def update_documents() -> Any:
    """
    Trigger an incremental update. 
    Currently identical to build_documents for V1 (overwrites existing with identical keys).
    """
    orchestrator = _get_orchestrator()
    try:
        # V1: Same as build, leverages the idempotent save
        return orchestrator.build_all()
    except Exception as exc:
        logger.error(f"Document update failed: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/statistics", summary="Get Document Store statistics")
def get_statistics() -> dict[str, Any]:
    """Return document store stats and index summary."""
    store = _get_store()
    try:
        return store.get_statistics()
    except Exception as exc:
        logger.error(f"Failed to fetch document stats: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/{document_id}", summary="Get a single document")
def get_document(document_id: str) -> dict[str, Any]:
    """Return a single generated document by its ID."""
    store = _get_store()
    try:
        doc = store.get(document_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        return doc.model_dump()
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Failed to fetch document {document_id}: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete("/rebuild", summary="Delete and regenerate all documents", response_model=BuildResult)
def rebuild_documents() -> Any:
    """
    Delete the entire document store and regenerate from scratch.
    """
    orchestrator = _get_orchestrator()
    try:
        return orchestrator.rebuild()
    except Exception as exc:
        logger.error(f"Document rebuild failed: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))
