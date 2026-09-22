"""
Deterministic Tool Planner.

Executes required tools sequentially and builds the PlannerContext.
Replaces the LLM's dynamic tool-calling loop.

PostgreSQL is the source of truth for factual records; Neo4j for
relationships; Qdrant for semantic similarity. The LLM never decides
which tool to call.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable

from app.services.tools import neo4j_tools, postgres_tools, qdrant_tools
from app.services.tools.context_builder import ContextBuilder
from app.services.tools.exceptions import IdentifierValidationError
from app.services.tools.intent_detector import DetectedIntent
from app.services.tools.planner_context import PlannerContext
from app.services.tools.tracing import trace

logger = logging.getLogger(__name__)

_CASE_LABELS = {"case_id": "CaseMasterID", "case_number": "CaseNo", "crime_number": "CrimeNo"}


def _run_tool(ctx: PlannerContext, name: str, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Execute a tool, record it in the context, and time it."""
    start = time.time()
    result = fn(*args, **kwargs)
    exec_ms = (time.time() - start) * 1000
    ctx.tools_executed.append(name)
    rows = len(result) if isinstance(result, list) else (0 if result is None else 1)
    logger.info("[Planner] %s took %.1fms | rows=%d", name, exec_ms, rows)
    if result:
        ctx.raw_tool_results.append(result)
    return result


class QueryPlanner:
    """Orchestrates tool execution deterministically."""

    @staticmethod
    def execute(intent: DetectedIntent) -> PlannerContext:
        """
        Build and populate a PlannerContext based on the detected intent.
        Executes all required tools directly without LLM decision-making.
        """
        ctx = PlannerContext()
        ids = intent.identifiers

        ctx.case_id = ids.get("case_id")
        ctx.case_number = ids.get("case_number")
        ctx.crime_number = ids.get("crime_number")
        ctx.officer_id = ids.get("officer_id")
        ctx.accused_name = ids.get("accused_name")
        if "victim_id" in ids:
            ctx.victim_ids.append(ids["victim_id"])
        if "accused_id" in ids:
            ctx.accused_ids.append(ids["accused_id"])

        identifier_key = next((k for k in ("case_id", "case_number", "crime_number", "officer_id",
                                            "victim_id", "accused_id", "accused_name") if k in ids), None)
        trace(
            logger, "Planner decision",
            intent=intent.intent, sub_intent=intent.sub_intent,
            identifier_type=identifier_key, identifier_value=ids.get(identifier_key) if identifier_key else None,
        )

        try:
            QueryPlanner._execute_plan(intent, ctx)
        except IdentifierValidationError as exc:
            logger.warning("[Planner] Invalid identifier: %s", exc)
            ctx.errors.append(str(exc))
        return ctx

    # ── Plan steps ────────────────────────────────────────────────────

    @staticmethod
    def _case_label(ctx: PlannerContext) -> str:
        if ctx.case_number is not None:
            return f"CaseNo {ctx.case_number}"
        if ctx.crime_number is not None:
            return f"CrimeNo {ctx.crime_number}"
        return f"CaseMasterID {ctx.case_id}"

    @staticmethod
    def _resolve_case(ctx: PlannerContext) -> bool:
        """Resolve the case row from whichever identifier the user supplied."""
        if ctx.case_lookup:
            return True
        if ctx.case_id is None and ctx.case_number is None and ctx.crime_number is None:
            return False

        if ctx.case_id is not None:
            lookup = _run_tool(ctx, "get_case_lookup", postgres_tools.get_case_lookup, case_id=ctx.case_id)
        elif ctx.case_number is not None:
            lookup = _run_tool(ctx, "get_case_lookup", postgres_tools.get_case_lookup, case_number=ctx.case_number)
        else:
            lookup = _run_tool(ctx, "get_case_lookup", postgres_tools.get_case_lookup, crime_number=ctx.crime_number)

        if not lookup:
            ctx.not_found = True
            ctx.errors.append(f"No case was found for {QueryPlanner._case_label(ctx)}.")
            return False

        ctx.case_lookup = lookup
        ctx.case_id = lookup.case_id
        return True

    @staticmethod
    def _execute_plan(intent: DetectedIntent, ctx: PlannerContext) -> None:
        sub = intent.sub_intent

        # Semantic search does not need a case.
        if intent.intent == "semantic_search" or sub == "similar_cases":
            ctx.semantic_results = _run_tool(ctx, "search_similar_cases", qdrant_tools.search_similar_cases,
                                             query=intent.raw_query, top_k=10)
            return

        # Every case-scoped sub-intent starts by resolving the case row.
        case_scoped = sub in (
            "case_by_id", "case_by_number", "case_by_crime", "status_for_case", "officer_for_case",
            "victim_for_case", "accused_for_case", "chargesheet_for_case", "summarize_case",
            "case_network", "co_accused", "case_timeline",
        )
        if case_scoped:
            if not QueryPlanner._resolve_case(ctx):
                return
            case_id = ctx.case_id

            if sub in ("case_by_id", "case_by_number", "case_by_crime", "status_for_case"):
                return

            if sub == "officer_for_case":
                officer_id = ctx.case_lookup.police_person_id
                if officer_id is None:
                    ctx.errors.append(f"No investigating officer is recorded for {QueryPlanner._case_label(ctx)}.")
                    return
                ctx.officer = _run_tool(ctx, "get_officer_compact", postgres_tools.get_officer_compact, officer_id)
                if not ctx.officer:
                    ctx.not_found = True
                    ctx.errors.append(
                        f"{QueryPlanner._case_label(ctx)} references PolicePersonID {officer_id}, "
                        f"but no matching Employee record was found."
                    )
                return

            if sub == "victim_for_case":
                ctx.victims = _run_tool(ctx, "get_case_victims_list", postgres_tools.get_case_victims_list, case_id)
                return

            if sub == "accused_for_case":
                ctx.accused = _run_tool(ctx, "get_case_accused_list", postgres_tools.get_case_accused_list, case_id)
                return

            if sub == "chargesheet_for_case":
                ctx.chargesheet = _run_tool(ctx, "get_chargesheet_status", postgres_tools.get_chargesheet_status, case_id)
                return

            if sub == "summarize_case":
                ctx.case_summary_text = _run_tool(ctx, "get_case_summary", ContextBuilder.build_case_summary_context, case_id)
                return

            if sub == "case_network":
                ctx.network = _run_tool(ctx, "find_case_network", neo4j_tools.find_case_network, case_id) or None
                return

            if sub == "co_accused":
                ctx.co_accused = _run_tool(ctx, "find_co_accused", neo4j_tools.find_co_accused, case_id) or None
                return

            if sub == "case_timeline":
                ctx.timeline = _run_tool(ctx, "get_case_timeline", neo4j_tools.get_case_timeline, case_id) or None
                return

        # Direct entity lookups
        if sub == "officer" and ctx.officer_id is not None:
            ctx.officer = _run_tool(ctx, "get_officer_compact", postgres_tools.get_officer_compact, ctx.officer_id)
            if not ctx.officer:
                ctx.not_found = True
                ctx.errors.append(f"No officer was found with EmployeeID {ctx.officer_id}.")
            return

        if sub == "victim" and ctx.victim_ids:
            victim = _run_tool(ctx, "get_victim_compact", postgres_tools.get_victim_compact, ctx.victim_ids[0])
            if victim:
                ctx.victims.append(victim)
            else:
                ctx.not_found = True
                ctx.errors.append(f"No victim was found with VictimMasterID {ctx.victim_ids[0]}.")
            return

        if sub == "accused" and ctx.accused_ids:
            accused = _run_tool(ctx, "get_accused_compact", postgres_tools.get_accused_compact, ctx.accused_ids[0])
            if accused:
                ctx.accused.append(accused)
            else:
                ctx.not_found = True
                ctx.errors.append(f"No accused was found with AccusedMasterID {ctx.accused_ids[0]}.")
            return

        if sub == "accused_by_name" and ctx.accused_name:
            ctx.accused_matches = _run_tool(ctx, "find_accused_by_name", postgres_tools.find_accused_by_name, ctx.accused_name)
            if not ctx.accused_matches:
                ctx.not_found = True
                ctx.errors.append(f"No accused records were found for the name '{ctx.accused_name}'.")
            return
