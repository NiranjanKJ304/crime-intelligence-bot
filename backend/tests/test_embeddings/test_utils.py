"""
Tests for Embedding Platform Utils.
"""

from app.document_generation.schemas import AIDocument, DocumentMetadata
from app.embeddings.utils import build_payload, generate_point_id


def test_generate_point_id():
    id1 = generate_point_id("case_summary_1")
    id2 = generate_point_id("case_summary_1")
    id3 = generate_point_id("case_summary_2")
    
    assert id1 == id2
    assert id1 != id3
    assert len(id1) == 36 # UUID length


def test_build_payload():
    doc = AIDocument(
        document_id="case_summary_1",
        document_type="case_summary",
        text="Sample text " * 100,
        metadata=DocumentMetadata(
            document_id="case_summary_1",
            document_type="case_summary",
            entity_id=1,
            case_id=10,
            crime_number="CR-1",
            district_name="Test District",
            police_station_name="Test PS",
            crime_year=2024,
            created_at="2026-07-21T00:00:00Z",
            updated_at="2026-07-21T00:00:00Z"
        )
    )
    
    payload = build_payload(doc)
    assert payload["document_id"] == "case_summary_1"
    assert payload["case_id"] == 10
    assert payload["crime_year"] == 2024
    assert len(payload["text_preview"]) == 500
