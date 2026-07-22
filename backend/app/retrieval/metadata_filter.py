"""
Metadata Filter validator and builder.
"""

from __future__ import annotations

import logging
from typing import Any
from qdrant_client.http import models as rest

from app.embeddings.filters import FilterBuilder

logger = logging.getLogger(__name__)


class MetadataFilter:
    """Validates and builds Qdrant filters for retrieval."""

    ALLOWED_KEYS = {
        "document_type",
        "district",
        "police_station",
        "crime_year",
        "crime_month",
        "crime_category",
        "major_crime",
        "minor_crime",
        "court",
        "officer",
    }

    def validate_and_build(self, filters: dict[str, Any] | None) -> rest.Filter | None:
        """Validate filter keys against ALLOWED_KEYS, then build."""
        if not filters:
            return None

        # Validation
        invalid_keys = [k for k in filters.keys() if k not in self.ALLOWED_KEYS]
        if invalid_keys:
            logger.warning(f"Invalid filter keys rejected: {invalid_keys}")
            raise ValueError(f"Invalid filter keys: {invalid_keys}")

        # Delegate to Phase 3B FilterBuilder
        return FilterBuilder.build_filter(filters)
