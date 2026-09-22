"""
Query Router — Hybrid Retrieval + Tool Planning Architecture.

Orchestrates the decision flow:
1. Intent Detection (regex, no LLM)
2. Deterministic planning + tool execution (PostgreSQL / Neo4j / Qdrant)
3. Factual queries → Template Engine (0 LLM calls)
4. Reasoning queries → single LLM call over the pre-fetched compact context

Tool-layer failures (schema mapping, SQL errors) are re-raised as ToolError
so the API layer can return a structured, traceback-free error.
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

from app.core.config import Settings
from app.llm.providers.groq_provider import GroqProvider
from app.llm.schemas import ChatRequest, ChatResponse, Citation, RetrievalMetrics
from app.rag.response_builder import ResponseBuilder
from app.services.tools.exceptions import ToolError
from app.services.tools.intent_detector import DetectedIntent, IntentDetector
from app.services.tools.planner import QueryPlanner
from app.services.tools.planner_context import PlannerContext
from app.services.tools.template_engine import TemplateEngine
from app.services.tools.tool_registry import ToolRegistry
from app.services.tools.tracing import trace

logger = logging.getLogger(__name__)

HISTORY_CASE_RE = re.compile(
    r"\b(?:case\s*(?:number|no\.?)?|caseno)\s*[:#\-*\s]*(\d+)\b", re.IGNORECASE
)

REASONING_SYSTEM_PROMPT = (
    "You are an AI Investigation Assistant for Karnataka Police.\n"
    "Use ONLY the provided context to answer the user's query. The context was "
    "retrieved from the police records database and knowledge graph.\n"
    "If the context does not contain the answer, say so clearly. Never invent "
    "names, identifiers, dates or outcomes.\n\n"
    "Context:\n\n"
)


def _dump(obj: Any) -> Any:
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    if isinstance(obj, list):
        return [_dump(o) for o in obj]
    return obj


class QueryRouter:
    """Routes queries through the hybrid pipeline."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.registry = ToolRegistry.get_instance()
        self.provider = GroqProvider(settings)

    async def route(self, request: ChatRequest) -> ChatResponse | None:
        """Main entry point for routing."""
        start_time = time.time()

        intent = IntentDetector.detect(request.query)
        self._resolve_history_identifiers(intent, request.history)

        identifier_type, identifier_value = next(iter(intent.identifiers.items()), (None, None))
        trace(
            logger, "Query received",
            user_query=request.query, intent=intent.intent, sub_intent=intent.sub_intent,
            identifier_type=identifier_type, identifier_value=identifier_value,
            confidence=intent.confidence,
        )
        logger.info(
            "QueryRouter | intent=%s | sub=%s | identifiers=%s | query=%s",
            intent.intent, intent.sub_intent, intent.identifiers, request.query[:80],
        )

        try:
            ctx = QueryPlanner.execute(intent)
        except ToolError:
            logger.exception("Planner failed for query=%r intent=%s", request.query[:80], intent.sub_intent)
            raise

        if intent.intent in ("factual_query", "identifier_lookup"):
            logger.info("Routing to Factual/Template Path (0 LLM calls)")
            response = self._handle_factual(intent, ctx, request.query, start_time)
            trace(logger, "Response", path="factual", groq_called="NO", tools=ctx.tools_executed,
                  answer_preview=response.answer[:120])
            return response

        logger.info("Routing to LLM Reasoning Path")
        return await self._handle_reasoning(intent, ctx, request, start_time)

    # ── History resolution ────────────────────────────────────────────

    @staticmethod
    def _resolve_history_identifiers(intent: DetectedIntent, history: list[dict] | None) -> None:
        """Fill a missing case reference ("that case") from the conversation history."""
        if not history or intent.identifiers:
            return
        for msg in reversed(history):
            match = HISTORY_CASE_RE.search(msg.get("content", ""))
            if match:
                intent.identifiers["case_number"] = int(match.group(1))
                logger.info("Resolved case_number=%s from conversation history.", intent.identifiers["case_number"])
                return

    # ── Factual path ──────────────────────────────────────────────────

    @staticmethod
    def _case_label(ctx: PlannerContext) -> str:
        if ctx.case_lookup:
            return f"CaseNo {ctx.case_lookup.case_number}"
        if ctx.case_number is not None:
            return f"CaseNo {ctx.case_number}"
        if ctx.crime_number is not None:
            return f"CrimeNo {ctx.crime_number}"
        return f"CaseMasterID {ctx.case_id}"

    def _handle_factual(self, intent: DetectedIntent, ctx: PlannerContext, query: str, start_time: float) -> ChatResponse:
        """Handle simple facts deterministically with 0 LLM calls."""
        if ctx.has_error():
            answer = "\n".join(ctx.errors)
            return ResponseBuilder.build(query, answer, [], list(dict.fromkeys(ctx.tools_executed)),
                                         self._build_metrics(start_time, 0, 0, 0))

        if not intent.identifiers:
            answer = "I couldn't identify which case or person you are asking about. Please include a CaseNo, CrimeNo or ID."
            return ResponseBuilder.build(query, answer, [], [], self._build_metrics(start_time, 0, 0, 0))

        sub = intent.sub_intent or ""
        data: Any = None

        if intent.intent == "factual_query":
            data = {
                "officer_for_case": ctx.officer,
                "victim_for_case": ctx.victims,
                "accused_for_case": ctx.accused,
                "chargesheet_for_case": ctx.chargesheet,
                "status_for_case": ctx.case_lookup,
            }.get(sub)
            answer = TemplateEngine.render_factual_response(sub, data, self._case_label(ctx))
        else:
            data = {
                "case_by_number": ctx.case_lookup,
                "case_by_crime": ctx.case_lookup,
                "case_by_id": ctx.case_lookup,
                "officer": ctx.officer,
                "victim": ctx.victims[0] if ctx.victims else None,
                "accused": ctx.accused[0] if ctx.accused else None,
                "accused_by_name": ctx.accused_matches,
            }.get(sub)
            answer = TemplateEngine.render_identifier_response(sub, data)

        tool_time_ms = (time.time() - start_time) * 1000
        found = bool(data)
        metrics = self._build_metrics(start_time, tool_time_ms, 0, 0, docs=1 if found else 0)
        citations = (
            [Citation(document_id="db", document_type="postgresql", score=1.0, text_snippet="Database lookup")]
            if found else []
        )
        response_type, payload = self._structured_payload(sub, ctx) if found else ("answer", None)
        return ResponseBuilder.build(query, answer, citations, list(dict.fromkeys(ctx.tools_executed)), metrics,
                                     response_type=response_type, data=payload)

    @staticmethod
    def _structured_payload(sub: str, ctx: PlannerContext) -> tuple[str, dict[str, Any] | None]:
        """Same result as the Markdown answer, as structured data for rich clients."""
        case = ctx.case_lookup.to_dict() if ctx.case_lookup else None

        if sub in ("case_by_number", "case_by_crime", "case_by_id", "status_for_case"):
            return "case_details", {"case": case, "chargesheet": None}
        if sub == "chargesheet_for_case":
            return "case_details", {"case": case, "chargesheet": ctx.chargesheet.to_dict() if ctx.chargesheet else None}
        if sub in ("officer", "officer_for_case") and ctx.officer:
            return "officer_details", {"officer": ctx.officer.to_dict(), "case": case}
        if sub in ("victim", "victim_for_case"):
            return "person_details", {"role": "victim", "persons": _dump(ctx.victims), "case": case}
        if sub in ("accused", "accused_for_case"):
            return "person_details", {"role": "accused", "persons": _dump(ctx.accused), "case": case}
        if sub == "accused_by_name":
            return "search_results", {
                "entity": "accused",
                "query": ctx.accused_name,
                "total": len(ctx.accused_matches),
                "results": _dump(ctx.accused_matches),
                "note": (
                    "A name is not a unique identity. Specify a CaseMasterID, AccusedMasterID or PersonID to narrow this down."
                    if len(ctx.accused_matches) > 1 else None
                ),
            }
        return "answer", None

    # ── Reasoning path ────────────────────────────────────────────────

    @staticmethod
    def _build_context(ctx: PlannerContext) -> str:
        parts = []
        if ctx.case_summary_text:
            parts.append(f"### Case Summary\n{ctx.case_summary_text}")
        if ctx.case_lookup and not ctx.case_summary_text:
            parts.append(f"### Case\n{json.dumps(ctx.case_lookup.to_dict(), indent=2, default=str)}")
        if ctx.officer:
            parts.append(f"### Investigating Officer\n{json.dumps(ctx.officer.to_dict(), indent=2, default=str)}")
        if ctx.network:
            parts.append(f"### Case Network\n{json.dumps(ctx.network, indent=2, default=str)}")
        if ctx.co_accused:
            parts.append(f"### Co-Accused (graph)\n{json.dumps(ctx.co_accused, indent=2, default=str)}")
        if ctx.accused:
            parts.append(f"### Accused\n{json.dumps(_dump(ctx.accused), indent=2, default=str)}")
        if ctx.accused_matches:
            parts.append(f"### Accused records matching name\n{json.dumps(_dump(ctx.accused_matches), indent=2, default=str)}")
        if ctx.victims:
            parts.append(f"### Victims\n{json.dumps(_dump(ctx.victims), indent=2, default=str)}")
        if ctx.timeline:
            parts.append(f"### Timeline\n{json.dumps(ctx.timeline, indent=2, default=str)}")
        if ctx.semantic_results:
            parts.append(f"### Semantic Search Results\n{json.dumps(ctx.semantic_results, indent=2, default=str)}")
        return "\n\n".join(parts) or "No specific context could be retrieved for this query."

    async def _handle_reasoning(self, intent: DetectedIntent, ctx: PlannerContext, request: ChatRequest, start_time: float) -> ChatResponse | None:
        """Handle reasoning queries using pre-fetched context (1 LLM call)."""
        if ctx.has_error():
            answer = "\n".join(ctx.errors)
            trace(logger, "Response", path="reasoning", groq_called="NO", reason="planner error", errors=ctx.errors)
            return ResponseBuilder.build(request.query, answer, [], list(dict.fromkeys(ctx.tools_executed)),
                                         self._build_metrics(start_time, 0, 0, 0))

        context_str = self._build_context(ctx)
        trace(logger, "Context built", tools=ctx.tools_executed, context_chars=len(context_str),
              context_preview=context_str[:200])

        messages = [{"role": "system", "content": REASONING_SYSTEM_PROMPT + context_str}]
        for msg in (request.history or [])[-6:]:
            if msg.get("role") in ("user", "assistant") and msg.get("content"):
                messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": request.query})

        tool_time_ms = (time.time() - start_time) * 1000
        trace(logger, "LLM call", groq_called="YES", model=self.provider.model_name, messages=len(messages))

        try:
            raw_response = await self.provider.client.chat.completions.create(
                model=self.provider.model_name,
                messages=messages,
                temperature=self.provider.temperature,
                max_tokens=self.provider.max_tokens,
                stream=False,
            )
            prompt_tok = raw_response.usage.prompt_tokens if raw_response.usage else 0
            comp_tok = raw_response.usage.completion_tokens if raw_response.usage else 0
            answer = raw_response.choices[0].message.content or "No response generated."
        except Exception:
            logger.exception("LLM call failed")
            return None

        metrics = self._build_metrics(start_time, tool_time_ms, prompt_tok, comp_tok, docs=len(ctx.raw_tool_results))
        citations = [
            Citation(document_id=f"tool:{name}", document_type="backend_tool", score=1.0,
                     text_snippet=f"Retrieved via {name}")
            for name in dict.fromkeys(ctx.tools_executed)
        ]
        return ResponseBuilder.build(
            query=request.query, answer=answer, citations=citations,
            sources=list(dict.fromkeys(ctx.tools_executed)), retrieval_metrics=metrics,
        )

    def _build_metrics(self, start_time: float, tool_time_ms: float, prompt_tok: int, comp_tok: int, docs: int = 0) -> RetrievalMetrics:
        total_time_ms = (time.time() - start_time) * 1000
        return RetrievalMetrics(
            documents_used=docs,
            retrieval_time_ms=round(tool_time_ms, 2),
            prompt_build_time_ms=0,
            llm_time_ms=round(max(total_time_ms - tool_time_ms, 0), 2),
            model=self.settings.model_name,
            prompt_tokens=prompt_tok,
            completion_tokens=comp_tok,
            total_tokens=prompt_tok + comp_tok,
        )
