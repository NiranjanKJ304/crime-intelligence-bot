"""
Retrieval Engine facade orchestrating the pipeline.
"""

from __future__ import annotations

import logging
import time
from typing import Any
from qdrant_client import QdrantClient

from app.embeddings.model_manager import ModelManager
from app.embeddings.config import build_embedding_config
from app.core.config import Settings
from app.retrieval.config import RetrievalConfig, build_retrieval_config
from app.retrieval.schemas import (
    RetrievalRequest, RetrievalResponse, SearchOnlyResponse, ResultExplanation,
    HybridResponse, HybridMetadata, HybridStatistics, ContextResponse, SimilarCaseRequest,
    HealthResponse
)
from app.retrieval.utils import generate_cache_key
from app.retrieval.query_processor import QueryProcessor
from app.retrieval.query_embedding import QueryEmbedding
from app.retrieval.metadata_filter import MetadataFilter
from app.retrieval.semantic_search import SemanticSearch
from app.retrieval.ranking_engine import RankingEngine
from app.retrieval.context_builder import ContextBuilder
from app.retrieval.cache_manager import CacheManager
from app.retrieval.analytics import RetrievalAnalytics
from app.retrieval.graph_search import GraphSearch
from app.retrieval.explainability import ExplainabilityBuilder

logger = logging.getLogger(__name__)


class RetrievalEngine:
    """High-level API for the retrieval pipeline."""

    # Singletons for thread-safe global sharing
    _cache_manager: CacheManager | None = None
    _analytics: RetrievalAnalytics | None = None

    def __init__(self, settings: Settings):
        self.config = build_retrieval_config(settings)
        
        # Initialize globally shared singletons if needed
        if RetrievalEngine._cache_manager is None:
            RetrievalEngine._cache_manager = CacheManager(self.config)
        if RetrievalEngine._analytics is None:
            RetrievalEngine._analytics = RetrievalAnalytics()
            
        self.cache = RetrievalEngine._cache_manager
        self.analytics = RetrievalEngine._analytics

        # Initialize Qdrant Client
        self.qdrant_client = QdrantClient(
            host=self.config.qdrant_host,
            port=self.config.qdrant_port
        )
        
        # Re-use Phase 3B ModelManager singleton
        emb_config = build_embedding_config(settings)
        self.model_mgr = ModelManager.get_instance(emb_config)
        
        # Initialize pipeline components
        self.processor = QueryProcessor()
        self.embedding = QueryEmbedding(self.model_mgr)
        self.filter = MetadataFilter()
        self.searcher = SemanticSearch(self.qdrant_client, self.config)
        self.graph_searcher = GraphSearch()
        self.ranking = RankingEngine(self.config)
        self.context_builder = ContextBuilder(self.config)

    def query(self, request: RetrievalRequest) -> RetrievalResponse:
        """Full retrieval pipeline (process -> embed -> search -> rank -> context)."""
        # This keeps backward compatibility
        start_time = time.time()
        
        # 1. Process
        processed_query = self.processor.process(request.query)
        
        # Determine defaults
        top_k = request.top_k or self.config.top_k
        threshold = request.score_threshold if request.score_threshold is not None else self.config.default_score_threshold
        max_res = request.max_results or self.config.default_document_limit
        
        # 2. Check Cache
        cache_key = generate_cache_key(processed_query, request.filters, top_k, threshold)
        cached = self.cache.get(cache_key)
        if cached:
            self.analytics.record_cache_hit()
            cached_copy = cached.model_copy()
            cached_copy.cache_hit = True
            return cached_copy
            
        self.analytics.record_cache_miss()
        
        # 3. Filter Validation
        qdrant_filter = self.filter.validate_and_build(request.filters)
        
        # 4. Embed
        vector = self.embedding.embed(processed_query)
        
        # 5. Search
        search_start = time.time()
        raw_hits = self.searcher.search(vector, qdrant_filter, top_k, threshold)
        search_duration_ms = (time.time() - search_start) * 1000
        
        # 6. Rank
        ranked = self.ranking.rank(raw_hits, include_explanation=request.include_explanation)
        
        if len(ranked) > max_res:
            ranked = ranked[:max_res]
            
        # 7. Context
        context_str = ""
        if request.include_context:
            context_str = self.context_builder.build_context(ranked)
            
        # Analytics
        top_sim = ranked[0].similarity_score if ranked else 0.0
        doc_types = [r.document_type for r in ranked]
        self.analytics.record_query(search_duration_ms, top_sim, doc_types, request.filters)
        
        total_duration_ms = (time.time() - start_time) * 1000
        
        response = RetrievalResponse(
            query=request.query,
            processed_query=processed_query,
            results=ranked,
            context=context_str,
            total_results=len(ranked),
            search_time_ms=round(total_duration_ms, 2),
            model=self.config.embedding_model,
            cache_hit=False
        )
        
        self.cache.put(cache_key, response)
        return response

    def search(self, request: RetrievalRequest) -> SearchOnlyResponse:
        """Raw semantic search (process -> embed -> search -> rank), no context/cache."""
        start_time = time.time()
        
        processed_query = self.processor.process(request.query)
        top_k = request.top_k or self.config.top_k
        threshold = request.score_threshold if request.score_threshold is not None else self.config.default_score_threshold
        max_res = request.max_results or self.config.default_document_limit
        
        qdrant_filter = self.filter.validate_and_build(request.filters)
        vector = self.embedding.embed(processed_query)
        
        search_start = time.time()
        raw_hits = self.searcher.search(vector, qdrant_filter, top_k, threshold)
        search_duration_ms = (time.time() - search_start) * 1000
        
        ranked = self.ranking.rank(raw_hits, include_explanation=request.include_explanation)
        if len(ranked) > max_res:
            ranked = ranked[:max_res]
            
        top_sim = ranked[0].similarity_score if ranked else 0.0
        doc_types = [r.document_type for r in ranked]
        self.analytics.record_query(search_duration_ms, top_sim, doc_types, request.filters)
        
        total_duration_ms = (time.time() - start_time) * 1000
        
        return SearchOnlyResponse(
            query=request.query,
            processed_query=processed_query,
            results=ranked,
            total_results=len(ranked),
            search_time_ms=round(total_duration_ms, 2),
            model=self.config.embedding_model,
            cache_hit=False
        )

    def hybrid(self, request: RetrievalRequest) -> HybridResponse:
        """Enterprise Hybrid Search combining Qdrant and Neo4j."""
        start_time = time.time()
        
        # 1. Process with entities
        processed = self.processor.process_with_entities(request.query)
        
        top_k = request.top_k or self.config.top_k
        threshold = request.score_threshold if request.score_threshold is not None else self.config.default_score_threshold
        max_res = request.max_results or self.config.default_document_limit
        
        # 2. Check Cache
        cache_key = generate_cache_key(f"hybrid:{processed.normalized_query}", request.filters, top_k, threshold)
        cached = self.cache.get(cache_key)
        if cached:
            self.analytics.record_cache_hit()
            return cached
            
        self.analytics.record_cache_miss()
        
        # 3. Filter Validation (auto-inject entity filters if none provided?)
        filters = request.filters or {}
        if not filters:
            if processed.entities.district:
                filters["district"] = processed.entities.district
            if processed.entities.year:
                filters["year"] = processed.entities.year
            if processed.entities.document_type:
                filters["document_type"] = processed.entities.document_type
        
        qdrant_filter = self.filter.validate_and_build(filters)
        
        # 4. Search Parallel-ish
        # Qdrant
        q_start = time.time()
        vector = self.embedding.embed(processed.normalized_query)
        raw_hits = self.searcher.search(vector, qdrant_filter, top_k, threshold)
        q_time_ms = (time.time() - q_start) * 1000
        
        # Neo4j
        g_start = time.time()
        graph_results = self.graph_searcher.search_by_entities(processed.entities)
        g_time_ms = (time.time() - g_start) * 1000
        
        # 5. Rank
        r_start = time.time()
        ranked = self.ranking.rank(raw_hits, include_explanation=request.include_explanation, graph_results=graph_results)
        if len(ranked) > max_res:
            ranked = ranked[:max_res]
            
        # 6. Explain
        if request.include_explanation:
            ExplainabilityBuilder.explain_results(ranked, processed.entities, graph_results)
            
        r_time_ms = (time.time() - r_start) * 1000
        
        # 7. Context
        c_start = time.time()
        context_str = ""
        if request.include_context:
            context_str = self.context_builder.build_hybrid_context(ranked, graph_results)
        c_time_ms = (time.time() - c_start) * 1000
        
        total_time_ms = (time.time() - start_time) * 1000
        
        # Analytics
        top_sim = ranked[0].similarity_score if ranked else 0.0
        doc_types = [r.document_type for r in ranked]
        self.analytics.record_query(
            search_time_ms=q_time_ms, 
            top_similarity=top_sim, 
            results_types=doc_types, 
            filters=filters,
            graph_time_ms=g_time_ms,
            is_hybrid=True
        )
        
        resp = HybridResponse(
            query=request.query,
            metadata=HybridMetadata(
                district=processed.entities.district,
                crime_type=processed.entities.crime_type,
                year=processed.entities.year,
                filters=filters,
                entities_detected=processed.entities.raw_entities
            ),
            retrieved_documents=ranked,
            graph_results=graph_results,
            context=context_str,
            statistics=HybridStatistics(
                documents=len(ranked),
                graph_nodes=len(graph_results),
                graph_relationships=len(graph_results),
                retrieval_time_ms=round(total_time_ms, 2),
                qdrant_search_ms=round(q_time_ms, 2),
                graph_search_ms=round(g_time_ms, 2),
                ranking_ms=round(r_time_ms, 2),
                context_build_ms=round(c_time_ms, 2)
            )
        )
        
        self.cache.put(cache_key, resp)
        return resp

    def context(self, request: RetrievalRequest) -> ContextResponse:
        """Lightweight endpoint returning only the context string for LLM injection."""
        # Use hybrid under the hood, but just return the context
        hybrid_resp = self.hybrid(request)
        return ContextResponse(
            query=request.query,
            context=hybrid_resp.context,
            cache_hit=False # Can't accurately bubble this up easily if grabbed from cache in hybrid
        )

    def similar_case(self, request: SimilarCaseRequest) -> HybridResponse:
        """Find cases similar to a given case ID."""
        # Just use hybrid search with the case ID as a query and filter by case_summary
        req = RetrievalRequest(
            query=f"case {request.case_id}",
            top_k=request.top_k,
            filters={"document_type": "case_summary"}
        )
        return self.hybrid(req)

    def health(self) -> HealthResponse:
        """System health check."""
        # Check qdrant
        try:
            self.qdrant_client.get_collections()
            qdrant_status = "healthy"
        except Exception:
            qdrant_status = "unhealthy"
            
        # Check neo4j
        try:
            from app.core.neo4j_db import get_neo4j_driver
            driver = get_neo4j_driver()
            driver.verify_connectivity()
            neo4j_status = "healthy"
        except Exception:
            neo4j_status = "unhealthy"
            
        overall = "healthy" if qdrant_status == "healthy" and neo4j_status == "healthy" else "degraded"
        
        return HealthResponse(
            status=overall,
            embedding_model=self.config.embedding_model,
            qdrant=qdrant_status,
            neo4j=neo4j_status,
            cache="healthy"
        )

    def get_config(self) -> dict[str, Any]:
        """Return the current retrieval configuration."""
        return {
            "top_k": self.config.top_k,
            "default_score_threshold": self.config.default_score_threshold,
            "max_context_tokens": self.config.max_context_tokens,
            "embedding_model": self.config.embedding_model,
            "query_cache_size": self.config.query_cache_size,
            "ranking_weights": self.ranking.WEIGHTS
        }

    def explain(self, result_index: int, request: RetrievalRequest) -> ResultExplanation:
        """Helper to specifically ask for the explanation of a rank index from a query."""
        req = request.model_copy()
        req.include_explanation = True
        req.include_context = False
        resp = self.query(req)
        
        if not resp.results or result_index >= len(resp.results) or result_index < 0:
            raise ValueError(f"Result index {result_index} out of bounds")
            
        return resp.results[result_index].explanation
