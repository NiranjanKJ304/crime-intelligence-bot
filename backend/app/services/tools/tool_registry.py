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
from app.services.tools import neo4j_tools, qdrant_tools
from app.services.tools.context_builder import ContextBuilder

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Singleton registry of all available tools for the LLM."""

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
        """Register the minimal set of tools the LLM needs for reasoning."""

        # ── PostgreSQL: Compact Context ───────────────────────────────
        self._register(
            ToolDefinition(
                name="get_case_summary",
                description="Fetch a highly compact text summary of a case, including its status, officers, victims, accused, and chargesheet. Use this to get context for reasoning queries about a case.",
                parameters={
                    "type": "object",
                    "properties": {
                        "case_id": {"type": "integer", "description": "The CaseMasterID"}
                    },
                    "required": ["case_id"],
                },
            ),
            ContextBuilder.build_case_summary_context,
        )

        # ── Neo4j: Relationship Queries ───────────────────────────────
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

        # ── Qdrant: Semantic Search ───────────────────────────────────
        self._register(
            ToolDefinition(
                name="search_similar_cases",
                description="Perform semantic search across all crime documents. Use this for natural language queries about crime types, patterns, modus operandi, or descriptions.",
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
        if name.startswith("find_"):
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
            elif isinstance(result_data, str):
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
