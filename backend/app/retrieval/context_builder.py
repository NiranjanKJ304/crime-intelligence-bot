"""
Context Builder for LLM consumption.
"""

from __future__ import annotations

import logging
from collections import defaultdict

from app.retrieval.config import RetrievalConfig
from app.retrieval.schemas import RankedResult, GraphResult
from app.retrieval.utils import estimate_tokens

logger = logging.getLogger(__name__)


class ContextBuilder:
    """Builds a consolidated context string from ranked results."""

    def __init__(self, config: RetrievalConfig):
        self.config = config

    def build_context(self, results: list[RankedResult]) -> str:
        """Group, deduplicate, format, and trim results into an LLM context."""
        if not results:
            return ""

        # 1. Deduplicate (keep highest rank)
        unique_results = self._deduplicate(results)
        
        # 2. Group by type
        grouped = self._group_by_type(unique_results)
        
        # 3. Format
        lines = ["=== RETRIEVED CONTEXT ===\n"]
        current_tokens = estimate_tokens(lines[0])
        
        # Order of types to render
        type_order = [
            "case_summary",
            "accused_profile", 
            "victim_profile",
            "officer_profile",
            "district_summary",
            "court_summary"
        ]
        
        # Ensure all groups are processed (even if type isn't in order list)
        for doc_type in set(type_order + list(grouped.keys())):
            if doc_type not in grouped or not grouped[doc_type]:
                continue
                
            group_docs = grouped[doc_type]
            
            # Format the title
            title_base = doc_type.replace('_', ' ').title()
            if title_base.endswith('y'):
                title_plural = title_base[:-1] + 'ies'
            else:
                title_plural = title_base + 's'
                
            header = f"--- {title_plural} ({len(group_docs)} document{'s' if len(group_docs) > 1 else ''}) ---\n"
            
            header_tokens = estimate_tokens(header)
            if current_tokens + header_tokens >= self.config.max_context_tokens:
                break
                
            lines.append(header)
            current_tokens += header_tokens
            
            for doc in group_docs:
                doc_text = f"[{doc.rank}] (Score: {doc.final_score}) {doc_type.replace('_', ' ').title()} {doc.document_id}\n{doc.text_preview}\n\n"
                doc_tokens = estimate_tokens(doc_text)
                
                if current_tokens + doc_tokens >= self.config.max_context_tokens:
                    # Try truncating the document to fit remaining tokens
                    remaining_tokens = self.config.max_context_tokens - current_tokens
                    # We need at least enough tokens for the header and a bit of text
                    if remaining_tokens > 20: 
                        allowed_chars = remaining_tokens * 4
                        truncated = f"[{doc.rank}] (Score: {doc.final_score}) {doc_type.replace('_', ' ').title()} {doc.document_id}\n{doc.text_preview[:allowed_chars]}... [TRUNCATED]\n\n"
                        lines.append(truncated)
                    logger.warning("Context truncated to respect MAX_CONTEXT_TOKENS.")
                    break # Stop adding to this group
                    
                lines.append(doc_text)
                current_tokens += doc_tokens

            # Break outer if we hit the limit during truncation
            if current_tokens >= self.config.max_context_tokens:
                break

        lines.append("=== END CONTEXT ===")
        return "\n".join(lines)

    def build_hybrid_context(self, results: list[RankedResult], graph_results: list[GraphResult]) -> str:
        """Merge semantic search results and graph results into a single context string."""
        context = self.build_context(results)
        
        if not graph_results:
            return context
            
        # We need to inject graph results before === END CONTEXT ===
        # Or append them after. Let's insert them before.
        lines = context.split("\n")
        if lines[-1] == "=== END CONTEXT ===":
            lines = lines[:-1]
            
        lines.append("\n--- Graph Relationships ---")
        
        # Deduplicate graph results by node and connected_to to avoid spam
        seen = set()
        for gr in graph_results:
            sig = f"{gr.node}-{gr.relationship}-{gr.connected_to}"
            if sig not in seen:
                seen.add(sig)
                lines.append(f"• {gr.node} -[{gr.relationship}]-> {gr.connected_to}")
                
        lines.append("\n=== END CONTEXT ===")
        return "\n".join(lines)

    def _deduplicate(self, results: list[RankedResult]) -> list[RankedResult]:
        """Keep only the first occurrence of each document_id."""
        seen = set()
        unique = []
        for res in results:
            if res.document_id not in seen:
                seen.add(res.document_id)
                unique.append(res)
        return unique

    def _group_by_type(self, results: list[RankedResult]) -> dict[str, list[RankedResult]]:
        """Group results by document_type."""
        grouped = defaultdict(list)
        for res in results:
            grouped[res.document_type].append(res)
        return dict(grouped)
