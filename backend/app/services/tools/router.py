"""
Query Router — Hybrid Retrieval + Tool Planning Architecture.

Orchestrates the decision flow:
1. Intent Detection
2. Factual Queries → Direct DB Lookup + Template Engine (0 LLM calls)
3. Reasoning Queries → LLM Tool Chaining with compact context
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
from app.services.tools.intent_detector import IntentDetector, DetectedIntent
from app.services.tools import postgres_tools
from app.services.tools.template_engine import TemplateEngine

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 3  # Reduced from 5 since we use less tools now

TOOL_SYSTEM_PROMPT = """You are an AI Investigation Assistant for Karnataka Police.

You have access to the following tools:
- get_case_summary: Get a highly compact summary of a case to answer reasoning questions.
- search_similar_cases: Find cases by description or modus operandi.
- find_case_network / find_related_accused: Find graph relationships.

RULES:
1. When asked to summarize or reason about a specific case, ALWAYS call get_case_summary first.
2. If a tool returns no results, tell the user clearly.
3. Present data in a clear, professional format suitable for law enforcement.
4. When the user refers to "that case", resolve the reference from the conversation history."""


class QueryRouter:
    """Routes queries through the hybrid pipeline."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.registry = ToolRegistry.get_instance()
        self.provider = GroqProvider(settings)

    async def route(self, request: ChatRequest) -> ChatResponse | None:
        """
        Main entry point for routing.
        """
        start_time = time.time()

        # 1. Intent detection
        intent = IntentDetector.detect(request.query)
        logger.info(f"QueryRouter | intent={intent.intent} | sub={intent.sub_intent} | query={request.query[:80]}")

        # Try to resolve missing identifiers from conversation history
        self._resolve_history_identifiers(intent, request.history)

        # 2. Planning and Execution
        from app.services.tools.planner import QueryPlanner
        ctx = QueryPlanner.execute(intent)

        # 3. Decision Engine
        if intent.intent in ("factual_query", "identifier_lookup"):
            logger.info("Routing to Factual/Template Path (0 LLM calls)")
            return self._handle_factual(intent, ctx, request.query, start_time)

        # 4. LLM Reasoning Path
        logger.info("Routing to LLM Reasoning Path")
        return await self._handle_reasoning(intent, ctx, request, start_time)

    def _resolve_history_identifiers(self, intent: DetectedIntent, history: list[dict] | None):
        """Extract missing identifiers from history (e.g., 'that case')."""
        if not history or intent.identifiers:
            return
            
        import re
        for msg in reversed(history):
            content = msg.get("content", "")
            match = re.search(r'\b(?:Case Number|Case No|Case)\s*[:#\-\s]*(\d+)', content, re.IGNORECASE)
            if match:
                intent.identifiers["case_number"] = str(match.group(1))
                logger.info(f"Resolved missing case_number={intent.identifiers['case_number']} from history.")
                return

    def _handle_factual(self, intent: DetectedIntent, ctx: Any, query: str, start_time: float) -> ChatResponse:
        """Handle simple facts deterministically with 0 LLM calls."""
        
        if ctx.has_error():
            answer = "\n".join(ctx.errors)
            metrics = self._build_metrics(start_time, 0, 0, 0)
            return ResponseBuilder.build(query, answer, [], [], metrics)

        if not intent.identifiers:
            answer = "I'm sorry, I couldn't identify which case or person you are asking about."
            metrics = self._build_metrics(start_time, 0, 0, 0)
            return ResponseBuilder.build(query, answer, [], [], metrics)

        case_id = str(ctx.case_id) if ctx.case_id else ""
        data = None

        if intent.intent == "factual_query":
            sub = intent.sub_intent
            if sub == "officer_for_case":
                data = ctx.officer
            elif sub == "victim_for_case":
                data = ctx.victims
            elif sub == "accused_for_case":
                data = ctx.accused
            elif sub == "chargesheet_for_case":
                data = ctx.chargesheet
            elif sub == "status_for_case":
                data = ctx.case_lookup
                
            answer = TemplateEngine.render_factual_response(intent.sub_intent or "", data, case_id)

        elif intent.intent == "identifier_lookup":
            sub = intent.sub_intent
            if sub in ("case_by_number", "case_by_crime"):
                data = ctx.case_lookup
            elif sub == "officer":
                data = ctx.officer
            elif sub == "victim":
                data = ctx.victims[0] if ctx.victims else None
            elif sub == "accused":
                data = ctx.accused[0] if ctx.accused else None
                
            answer = TemplateEngine.render_identifier_response(intent.sub_intent or "", data)
            
        else:
            answer = "I could not process this factual query."

        tool_time_ms = (time.time() - start_time) * 1000

        # Build response with 0 prompt/completion tokens
        metrics = self._build_metrics(start_time, tool_time_ms, 0, 0, docs=1 if data else 0)
        citations = [Citation(document_id="db", document_type="postgresql", score=1.0, text_snippet="Database lookup")] if data else []
        
        return ResponseBuilder.build(query, answer, citations, ctx.tools_executed, metrics)

    async def _handle_reasoning(self, intent: DetectedIntent, ctx: Any, request: ChatRequest, start_time: float) -> ChatResponse | None:
        """Handle reasoning queries using pre-fetched context (1 LLM call)."""
        
        if ctx.has_error():
            answer = "\n".join(ctx.errors)
            metrics = self._build_metrics(start_time, 0, 0, 0)
            return ResponseBuilder.build(request.query, answer, [], [], metrics)

        # 1. Build the context string from PlannerContext
        context_parts = []
        if ctx.case_summary_text:
            context_parts.append(f"### Case Summary\n{ctx.case_summary_text}")
        if ctx.network:
            import json
            context_parts.append(f"### Case Network\n{json.dumps(ctx.network, indent=2)}")
        if ctx.accused:
            import json
            # Just grab dicts if they are from neo4j or DTOs if from postgres
            clean_accused = [a if isinstance(a, dict) else a.__dict__ for a in ctx.accused]
            context_parts.append(f"### Co-Accused\n{json.dumps(clean_accused, indent=2)}")
        if ctx.timeline:
            import json
            context_parts.append(f"### Timeline\n{json.dumps(ctx.timeline, indent=2)}")
        if ctx.semantic_results:
            import json
            context_parts.append(f"### Semantic Search Results\n{json.dumps(ctx.semantic_results, indent=2)}")
            
        context_str = "\n\n".join(context_parts)
        if not context_str:
            context_str = "No specific context could be retrieved for this query."

        # 2. Build Messages
        # The prompt is simpler now because it doesn't need to instruct on tool usage.
        system_prompt = (
            "You are an AI Investigation Assistant for Karnataka Police.\n"
            "Use the provided context to answer the user's query.\n"
            "If the context doesn't contain the answer, say so clearly.\n"
            "Context:\n\n" + context_str
        )
        
        messages = [{"role": "system", "content": system_prompt}]

        if request.history:
            for msg in request.history[-6:]:
                if msg.get("role") in ("user", "assistant") and msg.get("content"):
                    messages.append({"role": msg["role"], "content": msg["content"]})

        messages.append({"role": "user", "content": request.query})

        # 3. Call LLM (No tools passed)
        tool_time_ms = (time.time() - start_time) * 1000
        
        try:
            # Reusing generate_with_tools without tools just calls the normal completion
            # We can use the simple generate method for speed
            response = await self.provider.generate(system_prompt, request.query) # simplified, ideally pass history
            
            # Since generate takes system and user strings, let's just format the prompt for the base generate method
            # Actually our provider.generate doesn't take history list easily, 
            # let's just use generate_with_tools with an empty tools list to support history
            raw_response = await self.provider.client.chat.completions.create(
                model=self.provider.model_name,
                messages=messages,
                temperature=self.provider.temperature,
                max_tokens=self.provider.max_tokens,
                stream=False
            )
            
            prompt_tok = raw_response.usage.prompt_tokens if raw_response.usage else 0
            comp_tok = raw_response.usage.completion_tokens if raw_response.usage else 0
            answer = raw_response.choices[0].message.content or "No response generated."
            
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return None

        # 4. Build Response
        metrics = self._build_metrics(start_time, tool_time_ms, prompt_tok, comp_tok, docs=len(ctx.raw_tool_results))

        citations = []
        for i, tool_name in enumerate(ctx.tools_executed):
             citations.append(Citation(
                 document_id=f"tool:{tool_name}",
                 document_type="backend_tool",
                 score=1.0,
                 text_snippet=f"Retrieved via {tool_name}"
             ))

        return ResponseBuilder.build(
            query=request.query,
            answer=answer,
            citations=citations,
            sources=list(set(ctx.tools_executed)),
            retrieval_metrics=metrics,
        )

    def _build_metrics(self, start_time: float, tool_time_ms: float, prompt_tok: int, comp_tok: int, docs: int = 0) -> RetrievalMetrics:
        total_time_ms = (time.time() - start_time) * 1000
        return RetrievalMetrics(
            documents_used=docs,
            retrieval_time_ms=round(tool_time_ms, 2),
            prompt_build_time_ms=0,
            llm_time_ms=round(total_time_ms - tool_time_ms, 2),
            model=self.settings.model_name,
            prompt_tokens=prompt_tok,
            completion_tokens=comp_tok,
            total_tokens=prompt_tok + comp_tok,
        )
