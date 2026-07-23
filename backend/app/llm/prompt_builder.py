"""
Prompt Builder for GraphRAG.
"""

class PromptBuilder:
    """Builds enterprise-grade prompts for investigative RAG."""
    
    SYSTEM_PROMPT = """You are an AI Investigation Assistant for Karnataka Police.

Rules:
- Never fabricate facts.
- Never answer outside supplied evidence.
- If evidence is insufficient, clearly say so.
- Always reference document IDs for every claim.
- Produce concise investigative summaries.
- Preserve factual accuracy.
- Do not expose internal reasoning.
- Do not invent accused names, crime numbers, dates, officers, or locations."""

    @staticmethod
    def build(query: str, context: str, document_ids: list[str]) -> tuple[str, str]:
        """
        Build the system and user prompts.
        Returns: (system_prompt, user_prompt)
        """
        user_prompt = f"""You must answer the following investigation query using ONLY the evidence provided in the context below.

CONTEXT:
{context}

QUERY:
{query}

AVAILABLE DOCUMENT IDS TO CITE:
{', '.join(document_ids) if document_ids else 'None'}

INSTRUCTIONS:
1. Answer the query concisely.
2. If the context does not contain the answer, state that there is no supporting evidence.
3. Every claim you make MUST be followed by the document ID it came from in brackets, e.g., [case_summary_123].
"""
        return PromptBuilder.SYSTEM_PROMPT, user_prompt
