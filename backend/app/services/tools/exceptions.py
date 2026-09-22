"""
Exceptions raised by the deterministic tools layer.

These are caught at the router / API boundary and converted into
user-safe messages — never into raw tracebacks.
"""

from __future__ import annotations


class ToolError(Exception):
    """Base class for tool-layer failures."""

    user_message: str = "The request could not be completed."


class MappingError(ToolError):
    """A logical table/column could not be resolved to the physical schema."""

    user_message = "Database schema configuration error."

    def __init__(self, message: str, diagnostics: dict | None = None):
        super().__init__(message)
        self.diagnostics = diagnostics or {}


class DatabaseQueryError(ToolError):
    """A parameterised SQL query failed to execute."""

    user_message = "Database query failed."


class IdentifierValidationError(ToolError, ValueError):
    """A user-supplied identifier does not match the physical column type."""

    user_message = "The identifier provided is not valid."

    def __init__(self, message: str):
        super().__init__(message)
        self.user_message = message
