"""
Retrieval Engine facade orchestrating the pipeline.
"""

from __future__ import annotations

import logging
import time
from qdrant_client import QdrantClient

from app.embeddings.model_manager import ModelManager
from app.embeddings.config import build_embedding_config
from app.core.config import Settings
from app.retrieval.config import RetrievalConfig, build_retrieval_config
from app.retrieval.schemas import (
    RetrievalRequest, RetrievalResponse, SearchOnlyResponse, ResultExplanation
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
        self.ranking = RankingEngine(self.config)
        self.context = ContextBuilder(self.config)

    def query(self, request: RetrievalRequest) -> RetrievalResponse:
        """Full retrieval pipeline (process -> embed -> search -> rank -> context)."""
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
            # Must set cache_hit to true on returned object
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
        
        # Enforce max results limit after ranking
        if len(ranked) > max_res:
            ranked = ranked[:max_res]
            
        # 7. Context
        context_str = ""
        if request.include_context:
            context_str = self.context.build_context(ranked)
            
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
        
        # 8. Cache Put
        self.cache.put(cache_key, response)
        
        return response

    def search(self, request: RetrievalRequest) -> SearchOnlyResponse:
        """Raw semantic search (process -> embed -> search -> rank), no context/cache."""
        start_time = time.time()
        
        # 1. Process
        processed_query = self.processor.process(request.query)
        
        # Determine defaults
        top_k = request.top_k or self.config.top_k
        threshold = request.score_threshold if request.score_threshold is not None else self.config.default_score_threshold
        max_res = request.max_results or self.config.default_document_limit
        
        # 2. Filter Validation
        qdrant_filter = self.filter.validate_and_build(request.filters)
        
        # 3. Embed
        vector = self.embedding.embed(processed_query)
        
        # 4. Search
        search_start = time.time()
        raw_hits = self.searcher.search(vector, qdrant_filter, top_k, threshold)
        search_duration_ms = (time.time() - search_start) * 1000
        
        # 5. Rank
        ranked = self.ranking.rank(raw_hits, include_explanation=False)
        if len(ranked) > max_res:
            ranked = ranked[:max_res]
            
        # Analytics
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

    def explain(self, result_index: int, request: RetrievalRequest) -> ResultExplanation:
        """Helper to specifically ask for the explanation of a rank index from a query."""
        # For simplicity, we just run the query and extract the explanation
        req = request.model_copy()
        req.include_explanation = True
        req.include_context = False
        resp = self.query(req)
        
        if not resp.results or result_index >= len(resp.results) or result_index < 0:
            raise ValueError(f"Result index {result_index} out of bounds")
            
        return resp.results[result_index].explanation
