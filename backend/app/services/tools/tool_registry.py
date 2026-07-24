"""
Tool Registry.

Central registry for all tool functions. Handles:
1. Registration of tools with their OpenAI-compatible JSON schemas
2. Providing the ``tools`` array for the Groq API
3. Dispatching tool calls to the correct function
4. Logging every tool execution (name, time, rows returned)
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Callable

from app.services.tools.schemas import ToolDefinition, ToolCall, ToolResult
from app.services.tools import postgres_tools, neo4j_tools, qdrant_tools

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Singleton registry of all available tools."""

    _instance: ToolRegistry | None = None

    def __init__(self):
        self._tools: dict[str, ToolDefinition] = {}
        self._functions: dict[str, Callable] = {}
        self._register_all()

    @classmethod
    def get_instance(cls) -> ToolRegistry:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ── Registration ──────────────────────────────────────────────────

    def _register(self, definition: ToolDefinition, func: Callable) -> None:
        self._tools[definition.name] = definition
        self._functions[definition.name] = func

    def _register_all(self) -> None:
        """Register every tool with its schema and implementation."""

        # ── PostgreSQL: Case Lookups ──────────────────────────────────
        self._register(
            ToolDefinition(
                name="get_case_by_id",
                description="Fetch a criminal case by its CaseMasterID number. Returns full case details including accused, victims, arrests, and chargesheets.",
                parameters={
                    "type": "object",
                    "properties": {
                        "case_id": {"type": "integer", "description": "The CaseMasterID of the case to look up"}
                    },
                    "required": ["case_id"],
                },
            ),
            postgres_tools.get_case_by_id,
        )

        self._register(
            ToolDefinition(
                name="get_case_by_crime_number",
                description="Fetch a criminal case by its CrimeNumber or FIR number string. Returns full case details.",
                parameters={
                    "type": "object",
                    "properties": {
                        "crime_number": {"type": "string", "description": "The CrimeNumber / FIR number string"}
                    },
                    "required": ["crime_number"],
                },
            ),
            postgres_tools.get_case_by_crime_number,
        )

        # ── PostgreSQL: Entity Lookups ────────────────────────────────
        self._register(
            ToolDefinition(
                name="get_officer",
                description="Fetch details of a police officer or employee by their EmployeeID.",
                parameters={
                    "type": "object",
                    "properties": {
                        "officer_id": {"type": "integer", "description": "The EmployeeID of the officer"}
                    },
                    "required": ["officer_id"],
                },
            ),
            postgres_tools.get_officer,
        )

        self._register(
            ToolDefinition(
                name="get_victim",
                description="Fetch details of a victim by their VictimMasterID.",
                parameters={
                    "type": "object",
                    "properties": {
                        "victim_id": {"type": "integer", "description": "The VictimMasterID of the victim"}
                    },
                    "required": ["victim_id"],
                },
            ),
            postgres_tools.get_victim,
        )

        self._register(
            ToolDefinition(
                name="get_accused",
                description="Fetch details of an accused person by their AccusedMasterID.",
                parameters={
                    "type": "object",
                    "properties": {
                        "accused_id": {"type": "integer", "description": "The AccusedMasterID of the accused"}
                    },
                    "required": ["accused_id"],
                },
            ),
            postgres_tools.get_accused,
        )

        self._register(
            ToolDefinition(
                name="get_complainant",
                description="Fetch details of a complainant by their ComplainantID.",
                parameters={
                    "type": "object",
                    "properties": {
                        "complainant_id": {"type": "integer", "description": "The ComplainantID"}
                    },
                    "required": ["complainant_id"],
                },
            ),
            postgres_tools.get_complainant,
        )

        # ── PostgreSQL: Relationship Lookups ──────────────────────────
        self._register(
            ToolDefinition(
                name="get_case_accused_list",
                description="Fetch all accused persons associated with a specific case.",
                parameters={
                    "type": "object",
                    "properties": {
                        "case_id": {"type": "integer", "description": "The CaseMasterID of the case"}
                    },
                    "required": ["case_id"],
                },
            ),
            postgres_tools.get_case_accused_list,
        )

        self._register(
            ToolDefinition(
                name="get_case_victims_list",
                description="Fetch all victims associated with a specific case.",
                parameters={
                    "type": "object",
                    "properties": {
                        "case_id": {"type": "integer", "description": "The CaseMasterID of the case"}
                    },
                    "required": ["case_id"],
                },
            ),
            postgres_tools.get_case_victims_list,
        )

        self._register(
            ToolDefinition(
                name="get_arrest_details",
                description="Fetch arrest and surrender records for a case.",
                parameters={
                    "type": "object",
                    "properties": {
                        "case_id": {"type": "integer", "description": "The CaseMasterID of the case"}
                    },
                    "required": ["case_id"],
                },
            ),
            postgres_tools.get_arrest_details,
        )

        self._register(
            ToolDefinition(
                name="get_chargesheet",
                description="Fetch chargesheet details filed for a case.",
                parameters={
                    "type": "object",
                    "properties": {
                        "case_id": {"type": "integer", "description": "The CaseMasterID of the case"}
                    },
                    "required": ["case_id"],
                },
            ),
            postgres_tools.get_chargesheet,
        )

        self._register(
            ToolDefinition(
                name="get_cases_by_station",
                description="Fetch cases registered at a specific police station.",
                parameters={
                    "type": "object",
                    "properties": {
                        "station_id": {"type": "integer", "description": "The UnitID of the police station"}
                    },
                    "required": ["station_id"],
                },
            ),
            postgres_tools.get_cases_by_station,
        )

        self._register(
            ToolDefinition(
                name="get_act_sections",
                description="Fetch the IPC act and section associations for a case.",
                parameters={
                    "type": "object",
                    "properties": {
                        "case_id": {"type": "integer", "description": "The CaseMasterID of the case"}
                    },
                    "required": ["case_id"],
                },
            ),
            postgres_tools.get_act_sections,
        )

        # ── Neo4j: Relationship Queries ───────────────────────────────
        self._register(
            ToolDefinition(
                name="find_related_accused",
                description="Find all cases that involve a specific accused person. Uses the knowledge graph.",
                parameters={
                    "type": "object",
                    "properties": {
                        "accused_id": {"type": "integer", "description": "The AccusedMasterID"}
                    },
                    "required": ["accused_id"],
                },
            ),
            neo4j_tools.find_related_accused,
        )

        self._register(
            ToolDefinition(
                name="find_officer_cases",
                description="Find all cases investigated by a specific officer. Uses the knowledge graph.",
                parameters={
                    "type": "object",
                    "properties": {
                        "officer_id": {"type": "integer", "description": "The EmployeeID of the officer"}
                    },
                    "required": ["officer_id"],
                },
            ),
            neo4j_tools.find_officer_cases,
        )

        self._register(
            ToolDefinition(
                name="find_co_accused",
                description="Find all accused persons on the same case. Uses the knowledge graph.",
                parameters={
                    "type": "object",
                    "properties": {
                        "case_id": {"type": "integer", "description": "The CaseMasterID"}
                    },
                    "required": ["case_id"],
                },
            ),
            neo4j_tools.find_co_accused,
        )

        self._register(
            ToolDefinition(
                name="find_case_network",
                description="Find the full network of a case — accused, victims, officers, stations. Uses the knowledge graph.",
                parameters={
                    "type": "object",
                    "properties": {
                        "case_id": {"type": "integer", "description": "The CaseMasterID"}
                    },
                    "required": ["case_id"],
                },
            ),
            neo4j_tools.find_case_network,
        )

        self._register(
            ToolDefinition(
                name="get_case_timeline",
                description="Get the chronological timeline of events for a case (arrests, chargesheets). Uses the knowledge graph.",
                parameters={
                    "type": "object",
                    "properties": {
                        "case_id": {"type": "integer", "description": "The CaseMasterID"}
                    },
                    "required": ["case_id"],
                },
            ),
            neo4j_tools.get_case_timeline,
        )

        self._register(
            ToolDefinition(
                name="find_accused_who_appear_together",
                description="Find other accused who frequently appear on the same cases (potential gang members). Uses the knowledge graph.",
                parameters={
                    "type": "object",
                    "properties": {
                        "accused_id": {"type": "integer", "description": "The AccusedMasterID"}
                    },
                    "required": ["accused_id"],
                },
            ),
            neo4j_tools.find_accused_who_appear_together,
        )

        # ── Qdrant: Semantic Search ───────────────────────────────────
        self._register(
            ToolDefinition(
                name="search_similar_cases",
                description="Perform semantic search across all crime documents. Use this for natural language queries about crime types, patterns, modus operandi, or descriptions. Returns ranked similar documents.",
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "The natural language search query"},
                        "top_k": {"type": "integer", "description": "Number of results to return (default 10)"},
                    },
                    "required": ["query"],
                },
            ),
            qdrant_tools.search_similar_cases,
        )

    # ── Public API ────────────────────────────────────────────────────

    def get_tools_for_llm(self) -> list[dict[str, Any]]:
        """Return the tools array in the format expected by the Groq/OpenAI API."""
        return [defn.to_openai_tool() for defn in self._tools.values()]

    def get_tool_names(self) -> list[str]:
        """Return a list of all registered tool names."""
        return list(self._tools.keys())

    def execute_tool(self, tool_call: ToolCall) -> ToolResult:
        """
        Execute a tool by name with the given arguments.
        Logs the tool name, execution time, and results count.
        """
        name = tool_call.name
        args = tool_call.arguments

        if name not in self._functions:
            logger.error(f"Unknown tool requested: {name}")
            return ToolResult(
                tool_name=name,
                source="unknown",
                error=f"Unknown tool: {name}",
            )

        func = self._functions[name]

        # Determine source
        source = "postgresql"
        if name.startswith("find_") or name == "get_case_timeline":
            source = "neo4j"
        if name == "search_similar_cases":
            source = "qdrant"

        start = time.time()
        try:
            result_data = func(**args)
            exec_time = (time.time() - start) * 1000

            rows = 0
            if isinstance(result_data, list):
                rows = len(result_data)
            elif isinstance(result_data, dict):
                rows = 1
            elif result_data is None:
                rows = 0

            logger.info(
                f"Tool executed: {name} | source={source} | "
                f"time={exec_time:.1f}ms | rows={rows} | args={args}"
            )

            return ToolResult(
                tool_name=name,
                source=source,
                data=result_data,
                execution_time_ms=round(exec_time, 2),
                rows_returned=rows,
            )

        except Exception as e:
            exec_time = (time.time() - start) * 1000
            logger.error(f"Tool execution failed: {name} | error={e} | args={args}")
            return ToolResult(
                tool_name=name,
                source=source,
                error=str(e),
                execution_time_ms=round(exec_time, 2),
            )
