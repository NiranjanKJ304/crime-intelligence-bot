"""
Tests for Citation Builder.
"""

from app.rag.citation_builder import CitationBuilder
from app.retrieval.schemas import RankedResult

def test_citation_builder():
    results = [
        RankedResult(
            rank=1,
            similarity_score=0.9,
            final_score=0.95,
            document_id="doc_1",
            document_type="case",
            text_preview="Snippet 1",
            metadata={},
            vector_id="v1"
        ),
        RankedResult(
            rank=2,
            similarity_score=0.8,
            final_score=0.85,
            document_id="doc_2",
            document_type="case",
            text_preview="Snippet 2",
            metadata={},
            vector_id="v2"
        )
    ]
    
    # Answer citing doc_1
    citations, sources = CitationBuilder.build(results, "Here is the answer [doc_1].")
    assert len(citations) == 1
    assert citations[0].document_id == "doc_1"
    assert sources == ["doc_1"]
    
    # Answer citing both
    citations, sources = CitationBuilder.build(results, "Answer from [doc_1] and [doc_2].")
    assert len(citations) == 2
    assert "doc_1" in sources
    assert "doc_2" in sources
    
    # Answer citing neither
    citations, sources = CitationBuilder.build(results, "No sources cited.")
    assert len(citations) == 0
    assert len(sources) == 0
