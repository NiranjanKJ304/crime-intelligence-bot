"""
Query Router.

Orchestrates the tool-calling flow:
1. Run intent detection (for logging/metrics)
2. Call Groq API with tool definitions
3. If the LLM returns tool_calls → execute them, feed results back for synthesis
4. If the LLM returns a direct text response → return None (fall back to existing RAG)
5. Build the final ChatResponse
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from app.core.config import Settings
from app.llm.schemas import ChatRequest, ChatResponse, RetrievalMetrics, Citation
from app.llm.providers.groq_provider import GroqProvider
from app.rag.response_builder import ResponseBuilder
from app.services.tools.schemas import ToolCall, ToolResult
from app.services.tools.tool_registry import ToolRegistry
from app.services.tools.intent_detector import IntentDetector

logger = logging.getLogger(__name__)

TOOL_SYSTEM_PROMPT = """You are an AI Investigation Assistant for Karnataka Police.

You have access to the following tools to retrieve real data from police databases:
- PostgreSQL database tools for exact ID lookups (cases, officers, victims, accused)
- Neo4j knowledge graph tools for relationship queries (co-accused, case networks, timelines)
- Qdrant semantic search for natural language queries about crime types and patterns

RULES:
1. When a user asks about a specific case, officer, victim, or accused by ID or number, ALWAYS use the appropriate tool to look up the real data. Never guess or fabricate records.
2. When a user asks about relationships between entities (who arrested whom, co-accused, etc.), use the Neo4j graph tools.
3. When a user asks about crime types, patterns, or uses descriptive language, use search_similar_cases for semantic search.
4. For mixed queries (e.g., "show case 1 and similar robbery cases"), call MULTIPLE tools.
5. If a tool returns no results, tell the user clearly that no matching records were found.
6. Never fabricate case numbers, officer names, victim details, or any other data.
7. Never expose internal database IDs, SQL queries, or Cypher queries to the user.
8. Present data in a clear, professional format suitable for law enforcement."""


class QueryRouter:
    """Routes queries through tool-calling or falls back to semantic RAG."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.registry = ToolRegistry.get_instance()
        self.provider = GroqProvider(settings)

    async def route(self, request: ChatRequest) -> ChatResponse | None:
        """
        Attempt to route the query through tool calling.
        Returns a ChatResponse if tools were used, or None to fall back to RAG.
        """
        start_time = time.time()

        # 1. Intent detection (for logging/metrics)
        intent = IntentDetector.detect(request.query)
        logger.info(f"QueryRouter | intent={intent.intent} | confidence={intent.confidence} | query={request.query[:80]}")

        # 2. Build messages with tool definitions
        messages = [
            {"role": "system", "content": TOOL_SYSTEM_PROMPT},
            {"role": "user", "content": request.query},
        ]

        tools = self.registry.get_tools_for_llm()

        # 3. First LLM call — let the model decide whether to use tools
        try:
            first_response = await self.provider.generate_with_tools(messages, tools)
        except Exception as e:
            logger.error(f"QueryRouter | LLM call failed: {e}")
            return None  # Fall back to existing RAG pipeline

        first_choice = first_response.choices[0]

        # 4. Check if the LLM wants to call tools
        if not first_choice.message.tool_calls:
            # No tool calls — the LLM wants to answer directly or it's a semantic query
            # Return None to let the existing RAG pipeline handle it
            logger.info("QueryRouter | No tool calls requested, falling back to RAG pipeline")
            return None

        # 5. Execute all tool calls
        tool_results: list[ToolResult] = []
        messages.append(first_choice.message)  # Add assistant message with tool_calls

        for tc in first_choice.message.tool_calls:
            try:
                args = json.loads(tc.function.arguments) if isinstance(tc.function.arguments, str) else tc.function.arguments
            except json.JSONDecodeError:
                args = {}

            tool_call = ToolCall(
                id=tc.id,
                name=tc.function.name,
                arguments=args,
            )

            result = self.registry.execute_tool(tool_call)
            tool_results.append(result)

            # Add tool result to messages for the synthesis call
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result.to_context_string(),
            })

        # 6. Second LLM call — synthesize the tool results into a natural language answer
        try:
            synthesis_response = await self.provider.generate_with_tools(messages, tools)
            answer = synthesis_response.choices[0].message.content or "No response generated."
        except Exception as e:
            logger.error(f"QueryRouter | Synthesis LLM call failed: {e}")
            # Build a basic answer from tool results directly
            answer = self._fallback_answer(tool_results)

        total_time_ms = (time.time() - start_time) * 1000

        # 7. Build metrics
        tool_time_ms = sum(r.execution_time_ms for r in tool_results)
        total_rows = sum(r.rows_returned for r in tool_results)
        sources_used = list(set(r.source for r in tool_results if r.success))
        tool_names_used = [r.tool_name for r in tool_results]

        # Calculate tokens from both LLM calls
        prompt_tokens = getattr(first_response.usage, 'prompt_tokens', 0) or 0
        completion_tokens = getattr(first_response.usage, 'completion_tokens', 0) or 0
        try:
            prompt_tokens += getattr(synthesis_response.usage, 'prompt_tokens', 0) or 0
            completion_tokens += getattr(synthesis_response.usage, 'completion_tokens', 0) or 0
        except NameError:
            pass

        metrics = RetrievalMetrics(
            documents_used=total_rows,
            retrieval_time_ms=round(tool_time_ms, 2),
            prompt_build_time_ms=0,
            llm_time_ms=round(total_time_ms - tool_time_ms, 2),
            model=self.settings.model_name,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        )

        # Build citations from tool results
        citations = []
        for tr in tool_results:
            if tr.success and tr.data:
                citations.append(Citation(
                    document_id=f"tool:{tr.tool_name}",
                    document_type=f"{tr.source}_lookup",
                    score=1.0,
                    text_snippet=f"Retrieved via {tr.tool_name} from {tr.source} ({tr.rows_returned} records)",
                ))

        logger.info(
            f"QueryRouter | COMPLETE | tools={tool_names_used} | "
            f"sources={sources_used} | rows={total_rows} | "
            f"tool_time={tool_time_ms:.1f}ms | total_time={total_time_ms:.1f}ms"
        )

        return ResponseBuilder.build(
            query=request.query,
            answer=answer,
            citations=citations,
            sources=[f"tool:{name}" for name in tool_names_used],
            retrieval_metrics=metrics,
        )

    @staticmethod
    def _fallback_answer(results: list[ToolResult]) -> str:
        """Build a basic answer from tool results when the synthesis LLM call fails."""
        parts = []
        for r in results:
            if r.success:
                parts.append(r.to_context_string())
            else:
                parts.append(f"Error retrieving data from {r.tool_name}: {r.error}")
        return "\n\n".join(parts) if parts else "Unable to retrieve the requested information."
