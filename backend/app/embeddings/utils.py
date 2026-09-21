"""
Utilities for the Embedding Platform.
"""

from __future__ import annotations

import uuid
from typing import Any
from app.document_generation.schemas import AIDocument


def generate_point_id(document_id: str) -> str:
    """
    Generate a deterministic UUID point ID for Qdrant from a document ID.
    Using UUID5 with a DNS namespace ensures consistency.
    """
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, document_id))


def build_payload(doc: AIDocument) -> dict[str, Any]:
    """
    Extract filterable payload from an AIDocument.
    Matches the schema defined in the design document.
    """
    m = doc.metadata
    return {
        "document_id": m.document_id,
        "document_type": m.document_type,
        "case_id": m.case_id,
        "crime_number": m.crime_number,
        "district": m.district_name,
        "police_station": m.police_station_name,
        "crime_year": m.crime_year,
        "crime_month": m.crime_month,
        "crime_category": m.crime_category_id,
        "major_crime": m.major_crime_id,
        "minor_crime": m.minor_crime_id,
        "court": m.court_name,
        "officer": m.officer_id,
        "created_at": m.created_at,
        "updated_at": m.updated_at,
        "text_preview": doc.text[:500] if doc.text else "",
    }


def get_qdrant_client(config: Any) -> Any:
    """
    Initialize a QdrantClient supporting embedded local storage or standalone server.
    """
    from qdrant_client import QdrantClient
    path = getattr(config, "qdrant_path", None)
    if path:
        return QdrantClient(path=path)
    host = getattr(config, "qdrant_host", "localhost")
    port = getattr(config, "qdrant_port", 6333)
    try:
        return QdrantClient(host=host, port=port, timeout=5.0)
    except Exception:
        return QdrantClient(path="./qdrant_storage")
