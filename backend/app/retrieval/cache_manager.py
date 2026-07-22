"""
LRU + TTL Cache Manager.
"""

from __future__ import annotations

import time
import threading
from collections import OrderedDict
from dataclasses import dataclass

from app.retrieval.config import RetrievalConfig
from app.retrieval.schemas import RetrievalResponse


@dataclass
class CacheEntry:
    response: RetrievalResponse
    expires_at: float


class CacheManager:
    """Thread-safe LRU cache with TTL expiration."""

    def __init__(self, config: RetrievalConfig):
        self.config = config
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.Lock()
        self.max_size = config.query_cache_size
        self.ttl = config.query_cache_ttl

    def get(self, key: str) -> RetrievalResponse | None:
        """Get an item from cache, returning None if expired or missing."""
        with self._lock:
            if key not in self._cache:
                return None
                
            entry = self._cache[key]
            
            # Check TTL
            if time.time() > entry.expires_at:
                del self._cache[key]
                return None
                
            # LRU: move to end (most recently used)
            self._cache.move_to_end(key)
            return entry.response

    def put(self, key: str, response: RetrievalResponse) -> None:
        """Put an item in the cache, evicting oldest if full."""
        if self.max_size <= 0:
            return
            
        with self._lock:
            # If exists, remove it first to update position
            if key in self._cache:
                del self._cache[key]
            
            # Evict if full
            if len(self._cache) >= self.max_size:
                self._cache.popitem(last=False) # pop oldest
                
            expires = time.time() + self.ttl
            self._cache[key] = CacheEntry(response=response, expires_at=expires)

    def clear(self) -> int:
        """Clear the cache and return number of items removed."""
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            return count

    def stats(self) -> dict[str, int]:
        """Return cache size."""
        with self._lock:
            return {"size": len(self._cache)}
