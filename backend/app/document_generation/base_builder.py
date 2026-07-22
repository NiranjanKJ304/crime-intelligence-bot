"""
Base Document Builder.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Generator

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.document_generation.config import DocumentConfig
from app.document_generation.schemas import AIDocument

logger = logging.getLogger(__name__)


class BaseDocumentBuilder(ABC):
    """Abstract base class for all document builders."""

    document_type: str = "base"

    def __init__(self, engine: Engine, config: DocumentConfig):
        self.engine = engine
        self.config = config

    @abstractmethod
    def build_batch(self, offset: int, limit: int) -> list[AIDocument]:
        """Build a batch of documents."""
        ...

    def build_all(self) -> Generator[list[AIDocument], None, None]:
        """Build all documents in batches."""
        offset = 0
        limit = self.config.batch_size
        
        while True:
            batch = self.build_batch(offset, limit)
            if not batch:
                break
                
            yield batch
            offset += limit

    def _execute_query(self, query: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Execute a SQL query and return rows as dictionaries."""
        with self.engine.connect() as conn:
            # Use stream_results for large sets, though LIMIT mitigates this
            result = conn.execution_options(stream_results=True).execute(text(query), params or {})
            
            keys = list(result.keys())
            rows = result.fetchall()
            return [dict(zip(keys, row)) for row in rows]
