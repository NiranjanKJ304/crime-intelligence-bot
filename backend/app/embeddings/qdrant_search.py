"""
Semantic Search for Qdrant.
"""

from __future__ import annotations

import logging
import time

from qdrant_client import QdrantClient

from app.embeddings.config import EmbeddingConfig
from app.embeddings.model_manager import ModelManager
from app.embeddings.schemas import SearchRequest, SearchResponse, SearchResult
from app.embeddings.filters import FilterBuilder

logger = logging.getLogger(__name__)


class QdrantSearch:
    """Provides semantic search capabilities."""

    def __init__(self, client: QdrantClient, config: EmbeddingConfig, model_mgr: ModelManager):
        self.client = client
        self.config = config
        self.model_mgr = model_mgr
        self.collection_name = config.qdrant_collection

    def search(self, request: SearchRequest) -> SearchResponse:
        """Execute a semantic search query with optional filters."""
        start_time = time.time()
        
        top_k = request.top_k or self.config.top_k
        query_filter = FilterBuilder.build_filter(request.filters)
        
        # 1. Embed the query
        query_vector = self.model_mgr.encode([request.query])[0]
        
        # 2. Search Qdrant
        try:
            results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_vector.tolist(),
                query_filter=query_filter,
                limit=top_k,
                with_payload=True
            )
        except Exception as e:
            logger.error(f"Qdrant search failed: {e}")
            raise RuntimeError(f"Search failed: {e}")
            
        # 3. Format results
        search_results = []
        for rank, point in enumerate(results, 1):
            payload = point.payload or {}
            
            search_results.append(SearchResult(
                rank=rank,
                score=point.score,
                document_id=payload.get("document_id", ""),
                document_type=payload.get("document_type", ""),
                text_preview=payload.get("text_preview", ""),
                metadata={
                    k: v for k, v in payload.items() 
                    if k not in ["document_id", "document_type", "text_preview"]
                },
                vector_id=str(point.id)
            ))
            
        duration_ms = (time.time() - start_time) * 1000
        
        return SearchResponse(
            query=request.query,
            results=search_results,
            total_results=len(search_results),
            search_time_ms=round(duration_ms, 2),
            model=self.model_mgr.model_name
        )
