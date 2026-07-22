"""
Ranking Engine.
"""

from __future__ import annotations

import datetime
import logging
from typing import Callable

from app.retrieval.config import RetrievalConfig
from app.retrieval.schemas import RawSearchHit, RankedResult, ResultExplanation

logger = logging.getLogger(__name__)


class RankingEngine:
    """Computes a multi-signal composite score and ranks results."""

    # Configurable type priorities (0.0 to 1.0)
    TYPE_PRIORITY_MAP = {
        "case_summary": 1.0,
        "accused_profile": 0.9,
        "victim_profile": 0.85,
        "officer_profile": 0.7,
        "district_summary": 0.6,
        "court_summary": 0.5,
    }

    # Signal Weights (must sum to 1.0)
    WEIGHTS = {
        "similarity": 0.70,
        "freshness": 0.10,
        "type_priority": 0.10,
        "metadata_richness": 0.10,
    }

    def __init__(self, config: RetrievalConfig):
        self.config = config

    def rank(self, hits: list[RawSearchHit], include_explanation: bool = False) -> list[RankedResult]:
        """Rank raw hits using a composite score."""
        if not hits:
            return []

        ranked = []
        now = datetime.datetime.now(datetime.timezone.utc)

        for i, hit in enumerate(hits):
            # Compute signals
            sim_score = self._similarity_score(hit)
            fresh_score = self._freshness_score(hit, now)
            type_score = self._type_priority_score(hit)
            meta_score = self._metadata_richness_score(hit)

            # Apply weights
            sim_contrib = self.WEIGHTS["similarity"] * sim_score
            fresh_contrib = self.WEIGHTS["freshness"] * fresh_score
            type_contrib = self.WEIGHTS["type_priority"] * type_score
            meta_contrib = self.WEIGHTS["metadata_richness"] * meta_score

            final_score = sim_contrib + fresh_contrib + type_contrib + meta_contrib

            # Explanation
            explanation = None
            if include_explanation:
                reason = f"Cosine similarity ({sim_score:.3f})"
                if type_score > 0.8:
                    reason += f" + high priority type ({hit.document_type})"
                if fresh_score > 0.8:
                    reason += f" + recently updated"
                    
                explanation = ResultExplanation(
                    similarity_contribution=round(sim_contrib, 3),
                    freshness_contribution=round(fresh_contrib, 3),
                    type_priority_contribution=round(type_contrib, 3),
                    metadata_richness_contribution=round(meta_contrib, 3),
                    ranking_reason=reason
                )

            ranked.append(RankedResult(
                rank=0, # will set after sort
                similarity_score=round(hit.score, 3),
                final_score=round(final_score, 3),
                document_id=hit.document_id,
                document_type=hit.document_type,
                text_preview=hit.text_preview,
                metadata=hit.metadata,
                vector_id=hit.vector_id,
                explanation=explanation
            ))

        # Sort by final score descending
        ranked.sort(key=lambda r: r.final_score, reverse=True)
        
        # Update rank
        for i, r in enumerate(ranked, 1):
            r.rank = i
            
        return ranked

    def rerank(self, results: list[RankedResult], reranker: Callable) -> list[RankedResult]:
        """Future hook for Phase 4/5 ML reranking models (e.g. Cohere)."""
        return reranker(results)

    def _similarity_score(self, hit: RawSearchHit) -> float:
        """Similarity score (assume cosine, clamped [0,1])."""
        return max(0.0, min(1.0, hit.score))

    def _freshness_score(self, hit: RawSearchHit, now: datetime.datetime) -> float:
        """Freshness based on updated_at, [0,1]. Older than 1 year gets 0."""
        updated_at_str = hit.metadata.get("updated_at")
        if not updated_at_str:
            return 0.5 # Neutral
            
        try:
            # Parse ISO8601
            updated_at = datetime.datetime.fromisoformat(updated_at_str.replace("Z", "+00:00"))
            days_old = (now - updated_at).days
            score = 1.0 - (days_old / 365.0)
            return max(0.0, min(1.0, score))
        except Exception:
            return 0.5

    def _type_priority_score(self, hit: RawSearchHit) -> float:
        """Type priority [0,1]."""
        return self.TYPE_PRIORITY_MAP.get(hit.document_type, 0.3)

    def _metadata_richness_score(self, hit: RawSearchHit) -> float:
        """Fraction of non-null metadata fields."""
        if not hit.metadata:
            return 0.0
        
        total = len(hit.metadata)
        populated = sum(1 for v in hit.metadata.values() if v is not None and v != "")
        return populated / total
