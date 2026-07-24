"""
Qdrant Tool Functions.

Thin wrapper around the existing RetrievalEngine for semantic search.
This allows the LLM to explicitly request semantic search as a tool call.
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.config import get_settings
from app.retrieval.retrieval_engine import RetrievalEngine
from app.retrieval.schemas import RetrievalRequest

logger = logging.getLogger(__name__)


def search_similar_cases(query: str, top_k: int = 10) -> list[dict[str, Any]]:
    """
    Perform semantic search via Qdrant using the existing retrieval engine.
    Returns ranked results with scores and text previews.
    """
    try:
        settings = get_settings()
        engine = RetrievalEngine(settings)

        request = RetrievalRequest(
            query=query,
            top_k=top_k,
            include_context=False,
            include_explanation=False,
        )

        response = engine.search(request)

        results = []
        for r in response.results:
            results.append({
                "document_id": r.document_id,
                "document_type": r.document_type,
                "similarity_score": round(r.similarity_score, 4),
                "final_score": round(r.final_score, 4),
                "text_preview": r.text_preview[:500] if r.text_preview else "",
            })

        return results

    except Exception as e:
        logger.error(f"Qdrant semantic search error: {e}")
        return []
