"""
Explainability Builder.
Provides human-readable explanations for why results were retrieved and ranked.
"""

from __future__ import annotations

from app.retrieval.schemas import RankedResult, ExtractedEntities, GraphResult


class ExplainabilityBuilder:
    """Builds explanations for the retrieval results."""

    @staticmethod
    def explain_results(
        results: list[RankedResult], 
        entities: ExtractedEntities,
        graph_results: list[GraphResult]
    ) -> None:
        """Add detailed natural language explanations to each result (in-place)."""
        for result in results:
            if not result.explanation:
                continue
                
            # Start with the ranking reason
            reason_parts = []
            
            # 1. Similarity
            if result.explanation.similarity_contribution > 0.4:
                reason_parts.append("High semantic similarity to query")
            elif result.explanation.similarity_contribution > 0.2:
                reason_parts.append("Moderate semantic match")
            
            # 2. Entity matches (Metadata)
            matched_entities = []
            if entities.district and entities.district == result.metadata.get("district"):
                matched_entities.append(f"District ({entities.district})")
            if entities.year and entities.year == result.metadata.get("year"):
                matched_entities.append(f"Year ({entities.year})")
            if entities.crime_type and entities.crime_type == result.metadata.get("crime_type"):
                matched_entities.append(f"Crime Type ({entities.crime_type})")
                
            if matched_entities:
                reason_parts.append("Matched entities: " + ", ".join(matched_entities))
                
            # 3. Graph confirmation
            if result.explanation.graph_confidence_contribution > 0:
                doc_id = result.document_id.lower()
                for gr in graph_results:
                    if doc_id in gr.node.lower() or doc_id in gr.connected_to.lower():
                        reason_parts.append(f"Corroborated by graph relationship ({gr.relationship})")
                        break
                        
            # Combine
            if reason_parts:
                result.explanation.ranking_reason = ". ".join(reason_parts) + "."
