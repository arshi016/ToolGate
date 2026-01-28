"""Registry for tool adapters."""

from __future__ import annotations

from typing import Dict, List

from gateway.core.adapter import ToolAdapter
from gateway.core.types import ToolError, ToolErrorType, ToolSpec


class ToolNotFoundError(LookupError):
    """Raised when a tool adapter cannot be found."""

    def __init__(self, tool_name: str) -> None:
        self.error = ToolError(
            error_type=ToolErrorType.TOOL_NOT_FOUND,
            human_message=f"Tool adapter not found: {tool_name}",
            agent_guidance="Verify the tool name or register the adapter.",
            details={"tool_name": tool_name},
        )
        super().__init__(self.error.human_message)


class AdapterRegistry:
    """Registry for ToolAdapter implementations."""

    def __init__(self) -> None:
        self._adapters: Dict[str, ToolAdapter] = {}

    def register(self, adapter: ToolAdapter) -> None:
        """Register a tool adapter by its ToolSpec tool_name."""
        spec = adapter.spec()
        tool_name = spec.tool_name
        if tool_name in self._adapters:
            raise ValueError(
                f"Tool adapter already registered for '{tool_name}'."
            )
        self._adapters[tool_name] = adapter

    def get(self, tool_name: str) -> ToolAdapter:
        """Return the adapter for tool_name or raise ToolNotFoundError."""
        adapter = self._adapters.get(tool_name)
        if adapter is None:
            raise ToolNotFoundError(tool_name)
        return adapter

    def list_specs(self) -> List[ToolSpec]:
        """Return ToolSpec for all registered adapters."""
        return [self._adapters[name].spec() for name in sorted(self._adapters)]
