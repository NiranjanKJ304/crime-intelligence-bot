"""
Citation Builder.
Extracts citations from LLM responses based on retrieved documents.
"""

from app.retrieval.schemas import RankedResult
from app.llm.schemas import Citation

class CitationBuilder:
    """Builds citations by mapping LLM responses back to source documents."""
    
    @staticmethod
    def build(ranked_results: list[RankedResult], llm_answer: str) -> tuple[list[Citation], list[str]]:
        """
        Identify which documents the LLM actually cited.
        Returns: (citations, sources_list)
        """
        citations = []
        sources = []
        
        if not llm_answer:
            return citations, sources
            
        seen_docs = set()
        
        for result in ranked_results:
            # Check if the document ID appears in the answer
            doc_id = result.document_id
            if doc_id in llm_answer and doc_id not in seen_docs:
                seen_docs.add(doc_id)
                
                citations.append(Citation(
                    document_id=doc_id,
                    document_type=result.document_type,
                    score=result.final_score,
                    text_snippet=result.text_preview[:200] + "..." if len(result.text_preview) > 200 else result.text_preview
                ))
                sources.append(doc_id)
                
        return citations, sources
