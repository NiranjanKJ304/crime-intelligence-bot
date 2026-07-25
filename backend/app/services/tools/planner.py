"""
Deterministic Tool Planner.

Executes required tools sequentially and builds the PlannerContext.
Replaces the LLM's dynamic tool-calling loop.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from app.services.tools.intent_detector import DetectedIntent
from app.services.tools.planner_context import PlannerContext
from app.services.tools import postgres_tools, neo4j_tools, qdrant_tools
from app.services.tools.context_builder import ContextBuilder
from app.services.tools.tool_registry import ToolRegistry

logger = logging.getLogger(__name__)


class QueryPlanner:
    """Orchestrates tool execution deterministically."""

    @staticmethod
    def execute(intent: DetectedIntent) -> PlannerContext:
        """
        Builds and populates a PlannerContext based on the detected intent.
        Executes all required tools directly without LLM decision-making.
        """
        ctx = PlannerContext()
        registry = ToolRegistry.get_instance()
        
        # 1. Populate initial identifiers from intent
        ctx.case_id = intent.identifiers.get("case_id")
        
        if "case_number" in intent.identifiers:
            try:
                ctx.case_number = str(intent.identifiers["case_number"])
            except ValueError:
                pass
                
        if "crime_number" in intent.identifiers:
            ctx.crime_number = str(intent.identifiers["crime_number"])
            
        if "officer_id" in intent.identifiers:
            try:
                ctx.officer_id = int(intent.identifiers["officer_id"])
            except ValueError:
                pass
                
        # Handle victim/accused ids if they are in identifiers
        if "victim_id" in intent.identifiers:
             try:
                 ctx.victim_ids.append(int(intent.identifiers["victim_id"]))
             except ValueError:
                 pass
                 
        if "accused_id" in intent.identifiers:
             try:
                 ctx.accused_ids.append(int(intent.identifiers["accused_id"]))
             except ValueError:
                 pass

        logger.info(f"QueryPlanner executing for intent={intent.intent}, sub_intent={intent.sub_intent}")

        # 2. Base Case Resolution (always required if we have a case number/crime number but no ID)
        if (ctx.case_number or ctx.crime_number) and not ctx.case_id:
            start = time.time()
            if ctx.case_number:
                ctx.case_lookup = postgres_tools.get_case_lookup(case_number=ctx.case_number)
            elif ctx.crime_number:
                ctx.case_lookup = postgres_tools.get_case_lookup(crime_number=ctx.crime_number)
            
            exec_ms = (time.time() - start) * 1000
            ctx.tools_executed.append("get_case_lookup")
            logger.info(f"[Planner] get_case_lookup took {exec_ms:.1f}ms")
            
            if ctx.case_lookup:
                ctx.case_id = ctx.case_lookup.case_id
                # Only log raw tool results for metrics/citations if needed
                ctx.raw_tool_results.append(ctx.case_lookup)
            else:
                ctx.errors.append(f"Could not find case matching identifiers.")
                return ctx

        # 3. Handle Semantic Search
        if intent.intent == "semantic_search" or intent.sub_intent == "similar_cases":
            start = time.time()
            results = qdrant_tools.search_similar_cases(query=intent.raw_query, top_k=10)
            exec_ms = (time.time() - start) * 1000
            ctx.tools_executed.append("search_similar_cases")
            logger.info(f"[Planner] search_similar_cases took {exec_ms:.1f}ms")
            
            ctx.semantic_results = results
            ctx.raw_tool_results.append(results)
            return ctx

        # 4. Handle Sub-Intents (Factual & Reasoning)
        sub = intent.sub_intent

        if sub == "case_by_number" or sub == "case_by_crime" or sub == "status_for_case":
            # Already handled by Base Case Resolution
            if not ctx.case_lookup and ctx.case_id:
                start = time.time()
                ctx.case_lookup = postgres_tools.get_case_lookup(case_id=ctx.case_id)
                exec_ms = (time.time() - start) * 1000
                ctx.tools_executed.append("get_case_lookup")
                logger.info(f"[Planner] get_case_lookup took {exec_ms:.1f}ms")
                if ctx.case_lookup:
                    ctx.raw_tool_results.append(ctx.case_lookup)

        elif sub == "officer_for_case" and ctx.case_id:
            # Need to get case first to find officer_id
            if not ctx.case_lookup:
                ctx.case_lookup = postgres_tools.get_case_lookup(case_id=ctx.case_id)
                ctx.tools_executed.append("get_case_lookup")
                
            if ctx.case_lookup and ctx.case_lookup.officer_id:
                start = time.time()
                ctx.officer = postgres_tools.get_officer_compact(ctx.case_lookup.officer_id)
                exec_ms = (time.time() - start) * 1000
                ctx.tools_executed.append("get_officer_compact")
                logger.info(f"[Planner] get_officer_compact took {exec_ms:.1f}ms")
                if ctx.officer:
                    ctx.raw_tool_results.append(ctx.officer)

        elif sub == "victim_for_case" and ctx.case_id:
            start = time.time()
            victims = postgres_tools.get_case_victims_list(ctx.case_id)
            exec_ms = (time.time() - start) * 1000
            ctx.tools_executed.append("get_case_victims_list")
            logger.info(f"[Planner] get_case_victims_list took {exec_ms:.1f}ms")
            
            if victims:
                ctx.victims = victims
                ctx.raw_tool_results.append(victims)

        elif sub == "accused_for_case" and ctx.case_id:
            start = time.time()
            accused = postgres_tools.get_case_accused_list(ctx.case_id)
            exec_ms = (time.time() - start) * 1000
            ctx.tools_executed.append("get_case_accused_list")
            logger.info(f"[Planner] get_case_accused_list took {exec_ms:.1f}ms")
            
            if accused:
                ctx.accused = accused
                ctx.raw_tool_results.append(accused)

        elif sub == "chargesheet_for_case" and ctx.case_id:
            start = time.time()
            cs = postgres_tools.get_chargesheet_status(ctx.case_id)
            exec_ms = (time.time() - start) * 1000
            ctx.tools_executed.append("get_chargesheet_status")
            logger.info(f"[Planner] get_chargesheet_status took {exec_ms:.1f}ms")
            
            if cs:
                ctx.chargesheet = cs
                ctx.raw_tool_results.append(cs)

        elif sub == "summarize_case" and ctx.case_id:
            start = time.time()
            ctx.case_summary_text = ContextBuilder.build_case_summary_context(ctx.case_id)
            exec_ms = (time.time() - start) * 1000
            ctx.tools_executed.append("get_case_summary")
            logger.info(f"[Planner] get_case_summary took {exec_ms:.1f}ms")
            if ctx.case_summary_text:
                ctx.raw_tool_results.append({"summary": ctx.case_summary_text})

        elif sub == "case_network" and ctx.case_id:
            start = time.time()
            network = neo4j_tools.find_case_network(ctx.case_id)
            exec_ms = (time.time() - start) * 1000
            ctx.tools_executed.append("find_case_network")
            logger.info(f"[Planner] find_case_network took {exec_ms:.1f}ms")
            if network:
                ctx.network = network
                ctx.raw_tool_results.append(network)

        elif sub == "co_accused" and ctx.case_id:
            start = time.time()
            co_accused = neo4j_tools.find_co_accused(ctx.case_id)
            exec_ms = (time.time() - start) * 1000
            ctx.tools_executed.append("find_co_accused")
            logger.info(f"[Planner] find_co_accused took {exec_ms:.1f}ms")
            if co_accused:
                ctx.accused = co_accused  # Storing in accused field for template/LLM
                ctx.raw_tool_results.append(co_accused)

        elif sub == "case_timeline" and ctx.case_id:
            start = time.time()
            timeline = neo4j_tools.get_case_timeline(ctx.case_id)
            exec_ms = (time.time() - start) * 1000
            ctx.tools_executed.append("get_case_timeline")
            logger.info(f"[Planner] get_case_timeline took {exec_ms:.1f}ms")
            if timeline:
                ctx.timeline = timeline
                ctx.raw_tool_results.append(timeline)

        elif sub == "officer" and ctx.officer_id:
            start = time.time()
            ctx.officer = postgres_tools.get_officer_compact(ctx.officer_id)
            exec_ms = (time.time() - start) * 1000
            ctx.tools_executed.append("get_officer_compact")
            logger.info(f"[Planner] get_officer_compact took {exec_ms:.1f}ms")
            if ctx.officer:
                ctx.raw_tool_results.append(ctx.officer)

        elif sub == "victim" and ctx.victim_ids:
            start = time.time()
            v = postgres_tools.get_victim_compact(ctx.victim_ids[0])
            exec_ms = (time.time() - start) * 1000
            ctx.tools_executed.append("get_victim_compact")
            logger.info(f"[Planner] get_victim_compact took {exec_ms:.1f}ms")
            if v:
                ctx.victims.append(v)
                ctx.raw_tool_results.append(v)

        elif sub == "accused" and ctx.accused_ids:
            start = time.time()
            a = postgres_tools.get_accused_compact(ctx.accused_ids[0])
            exec_ms = (time.time() - start) * 1000
            ctx.tools_executed.append("get_accused_compact")
            logger.info(f"[Planner] get_accused_compact took {exec_ms:.1f}ms")
            if a:
                ctx.accused.append(a)
                ctx.raw_tool_results.append(a)

        return ctx
