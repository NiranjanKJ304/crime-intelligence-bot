"""
Filter Builder for Qdrant queries.
"""

from __future__ import annotations

from typing import Any
from qdrant_client.http import models as rest


class FilterBuilder:
    """Builds Qdrant Filter objects from simple dictionaries."""

    @staticmethod
    def build_filter(filters_dict: dict[str, Any] | None) -> rest.Filter | None:
        """
        Convert a dictionary of key-value pairs into a Qdrant Filter.
        Uses 'must' (AND logic) for all conditions.
        """
        if not filters_dict:
            return None

        must_conditions = []
        for key, value in filters_dict.items():
            if value is None:
                # IsEmpty condition
                must_conditions.append(
                    rest.IsEmptyCondition(
                        is_empty=rest.PayloadField(key=key)
                    )
                )
            elif isinstance(value, list):
                # Any condition (IN)
                must_conditions.append(
                    rest.FieldCondition(
                        key=key,
                        match=rest.MatchAny(any=value)
                    )
                )
            else:
                # Value condition (==)
                must_conditions.append(
                    rest.FieldCondition(
                        key=key,
                        match=rest.MatchValue(value=value)
                    )
                )

        return rest.Filter(must=must_conditions)
