"""Adapter interface for tool integrations."""

from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

from gateway.core.types import ToolRequest, ToolResult, ToolSpec


@runtime_checkable
class ToolAdapter(Protocol):
    """Interface for tool adapters used by the control layer."""

    def spec(self) -> ToolSpec:
        """Return the tool's static specification."""

    def execute(self, request: ToolRequest, scope: Optional[str]) -> ToolResult:
        """Execute the tool action using the provided scope."""

    def supports_scope(self, scope: str) -> bool:
        """Return True if the adapter supports the provided scope."""
