"""
Tests for the Tool schemas.
"""

import pytest
from app.services.tools.schemas import ToolDefinition, ToolCall, ToolResult


class TestToolDefinition:
    def test_to_openai_tool(self):
        defn = ToolDefinition(
            name="test_tool",
            description="A test tool",
            parameters={
                "type": "object",
                "properties": {"id": {"type": "integer"}},
                "required": ["id"],
            },
        )
        result = defn.to_openai_tool()
        assert result["type"] == "function"
        assert result["function"]["name"] == "test_tool"
        assert result["function"]["description"] == "A test tool"
        assert "properties" in result["function"]["parameters"]


class TestToolResult:
    def test_success_property(self):
        ok = ToolResult(tool_name="t", source="pg", data={"a": 1})
        assert ok.success is True

        err = ToolResult(tool_name="t", source="pg", error="fail")
        assert err.success is False

    def test_to_context_string_with_data(self):
        r = ToolResult(tool_name="get_case", source="pg", data={"id": 1})
        ctx = r.to_context_string()
        assert "get_case" in ctx
        assert "1" in ctx

    def test_to_context_string_with_error(self):
        r = ToolResult(tool_name="get_case", source="pg", error="not found")
        ctx = r.to_context_string()
        assert "Error" in ctx

    def test_to_context_string_empty(self):
        r = ToolResult(tool_name="get_case", source="pg", data=None)
        ctx = r.to_context_string()
        assert "No results" in ctx

    def test_to_context_string_empty_list(self):
        r = ToolResult(tool_name="get_case", source="pg", data=[])
        ctx = r.to_context_string()
        assert "No results" in ctx

    def test_to_context_string_list(self):
        r = ToolResult(tool_name="get_case", source="pg", data=[{"id": 1}, {"id": 2}])
        ctx = r.to_context_string()
        assert "2 items" in ctx
