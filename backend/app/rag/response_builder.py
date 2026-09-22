"""
Response Builder.
Assembles the final ChatResponse.
"""

from typing import Any

from app.llm.schemas import ChatResponse, Citation, RetrievalMetrics


class ResponseBuilder:
    """Builds the final ChatResponse."""

    @staticmethod
    def build(
        query: str,
        answer: str,
        citations: list[Citation],
        sources: list[str],
        retrieval_metrics: RetrievalMetrics,
        response_type: str = "answer",
        data: dict[str, Any] | None = None,
    ) -> ChatResponse:
        """Assemble the response and compute confidence."""

        # Simple confidence logic: average score of cited documents
        confidence = 0.0
        if citations:
            total_score = sum(c.score for c in citations)
            confidence = round(total_score / len(citations), 3)

        return ChatResponse(
            query=query,
            answer=answer,
            response_type=response_type,
            data=data,
            citations=citations,
            sources=sources,
            confidence=confidence,
            retrieval=retrieval_metrics,
        )
