"""
Pydantic schemas shared by the tool-calling layer.
"""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class ToolParameter(BaseModel):
    """Single parameter in a tool's JSON schema."""
    name: str
    type: str  # "string", "integer", "number"
    description: str
    required: bool = True


class ToolDefinition(BaseModel):
    """
    OpenAI-compatible tool definition.
    Passed directly to the LLM ``tools`` array.
    """
    name: str
    description: str
    parameters: dict[str, Any] = Field(default_factory=dict)

    def to_openai_tool(self) -> dict[str, Any]:
        """Serialize to the format expected by the Groq / OpenAI API."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolCall(BaseModel):
    """Parsed tool call from an LLM response."""
    id: str = ""
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolResult(BaseModel):
    """Structured output from executing a tool."""
    tool_name: str
    source: str  # "postgresql", "neo4j", "qdrant"
    data: Any = None
    error: str | None = None
    execution_time_ms: float = 0.0
    rows_returned: int = 0

    @property
    def success(self) -> bool:
        return self.error is None

    def to_context_string(self) -> str:
        """Format tool result as a context string for the LLM."""
        if self.error:
            return f"[Tool {self.tool_name}] Error: {self.error}"
        if self.data is None:
            return f"[Tool {self.tool_name}] No results found."
        if isinstance(self.data, list):
            if not self.data:
                return f"[Tool {self.tool_name}] No results found."
            import json
            return f"[Tool {self.tool_name}] Results ({len(self.data)} items):\n{json.dumps(self.data, indent=2, default=str)}"
        import json
        return f"[Tool {self.tool_name}] Result:\n{json.dumps(self.data, indent=2, default=str)}"
