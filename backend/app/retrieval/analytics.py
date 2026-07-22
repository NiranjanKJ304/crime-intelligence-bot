"""
Retrieval Analytics.
"""

from __future__ import annotations

import threading
from collections import defaultdict
from typing import Any


class RetrievalAnalytics:
    """Thread-safe in-memory analytics for the retrieval engine."""

    def __init__(self):
        self._lock = threading.Lock()
        
        self.total_queries = 0
        self.total_search_time_ms = 0.0
        self.total_similarity = 0.0
        self.cache_hits = 0
        self.cache_misses = 0
        self.document_type_counts: dict[str, int] = defaultdict(int)
        self.filter_usage_counts: dict[str, int] = defaultdict(int)

    def record_query(self, search_time_ms: float, top_similarity: float, results_types: list[str], filters: dict[str, Any] | None) -> None:
        """Record metrics for a successful search query."""
        with self._lock:
            self.total_queries += 1
            self.total_search_time_ms += search_time_ms
            self.total_similarity += top_similarity
            
            for dt in results_types:
                self.document_type_counts[dt] += 1
                
            if filters:
                for fk in filters.keys():
                    self.filter_usage_counts[fk] += 1

    def record_cache_hit(self) -> None:
        """Record a cache hit."""
        with self._lock:
            self.cache_hits += 1
            self.total_queries += 1

    def record_cache_miss(self) -> None:
        """Record a cache miss."""
        with self._lock:
            self.cache_misses += 1

    def summary(self) -> dict[str, Any]:
        """Return computed analytics summary."""
        with self._lock:
            q_count = self.total_queries
            
            avg_search = 0.0
            avg_sim = 0.0
            if q_count - self.cache_hits > 0: # only average real searches
                real_searches = q_count - self.cache_hits
                avg_search = self.total_search_time_ms / real_searches
                avg_sim = self.total_similarity / real_searches
                
            total_cache = self.cache_hits + self.cache_misses
            hit_ratio = (self.cache_hits / total_cache) if total_cache > 0 else 0.0
            
            return {
                "total_queries": q_count,
                "avg_search_time_ms": round(avg_search, 2),
                "avg_similarity": round(avg_sim, 3),
                "top_document_types": dict(self.document_type_counts),
                "most_used_filters": dict(self.filter_usage_counts),
                "cache_stats": {
                    "hits": self.cache_hits,
                    "misses": self.cache_misses,
                    "hit_ratio": round(hit_ratio, 3)
                }
            }
