import pytest
from app.retrieval.explainability import ExplainabilityBuilder
from app.retrieval.schemas import RankedResult, ExtractedEntities, GraphResult, ResultExplanation

def test_explain_results():
    results = [
        RankedResult(
            rank=1,
            similarity_score=0.9,
            final_score=0.9,
            document_id="d1",
            document_type="case_summary",
            text_preview="",
            metadata={"district": "Mysuru", "crime_type": "theft"},
            vector_id="",
            explanation=ResultExplanation(
                similarity_contribution=0.5,
                freshness_contribution=0.1,
                type_priority_contribution=0.1,
                metadata_richness_contribution=0.1,
                graph_confidence_contribution=0.15,
                ranking_reason=""
            )
        )
    ]
    
    entities = ExtractedEntities(district="Mysuru", crime_type="theft")
    graph_results = [
        GraphResult(node="Case: d1", relationship="HAS_ACCUSED", connected_to="John")
    ]
    
    ExplainabilityBuilder.explain_results(results, entities, graph_results)
    
    reason = results[0].explanation.ranking_reason
    assert "High semantic similarity" in reason
    assert "Mysuru" in reason
    assert "theft" in reason
    assert "Corroborated by graph" in reason
