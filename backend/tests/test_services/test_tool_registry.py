"""
Tests for the Tool Registry.
"""

import pytest
from app.services.tools.tool_registry import ToolRegistry
from app.services.tools.schemas import ToolCall


class TestToolRegistry:
    """Test suite for the Tool Registry."""

    def setup_method(self):
        # Reset singleton for clean tests
        ToolRegistry._instance = None
        self.registry = ToolRegistry.get_instance()

    def test_singleton(self):
        """Registry should be a singleton."""
        r2 = ToolRegistry.get_instance()
        assert self.registry is r2

    def test_tools_registered(self):
        """Should have all expected tools registered."""
        names = self.registry.get_tool_names()
        assert "get_case_by_id" in names
        assert "get_officer" in names
        assert "get_victim" in names
        assert "get_accused" in names
        assert "search_similar_cases" in names
        assert "find_related_accused" in names
        assert "find_officer_cases" in names

    def test_get_tools_for_llm_format(self):
        """Tools array should be in OpenAI-compatible format."""
        tools = self.registry.get_tools_for_llm()
        assert isinstance(tools, list)
        assert len(tools) > 0

        first = tools[0]
        assert first["type"] == "function"
        assert "function" in first
        assert "name" in first["function"]
        assert "description" in first["function"]
        assert "parameters" in first["function"]

    def test_execute_unknown_tool(self):
        """Executing an unknown tool should return an error result."""
        call = ToolCall(name="nonexistent_tool", arguments={})
        result = self.registry.execute_tool(call)
        assert result.error is not None
        assert not result.success

    def test_execute_postgres_tool_returns_result(self):
        """PostgreSQL tool should execute and return a ToolResult (even if empty)."""
        call = ToolCall(name="get_case_by_id", arguments={"case_id": 999999})
        result = self.registry.execute_tool(call)
        # May or may not find data, but should not error on the function itself
        assert result.tool_name == "get_case_by_id"
        assert result.source == "postgresql"
        assert result.execution_time_ms >= 0

    def test_tool_source_classification(self):
        """Tools should be classified to the correct source."""
        # PostgreSQL
        call = ToolCall(name="get_officer", arguments={"officer_id": 1})
        result = self.registry.execute_tool(call)
        assert result.source == "postgresql"

        # Neo4j
        call = ToolCall(name="find_related_accused", arguments={"accused_id": 1})
        result = self.registry.execute_tool(call)
        assert result.source == "neo4j"
