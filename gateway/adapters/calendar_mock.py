"""Deterministic mock calendar adapter."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from gateway.core.types import (
    ActionType,
    ToolError,
    ToolErrorType,
    ToolRequest,
    ToolResult,
    ToolSpec,
)


class CalendarMockAdapter:
    """In-memory calendar adapter with deterministic responses."""

    def __init__(self) -> None:
        self._events: List[Dict[str, Any]] = []
        self._event_counter = 1

    def spec(self) -> ToolSpec:
        """Return the tool specification for the calendar adapter."""
        return ToolSpec(
            tool_name="calendar",
            description="Deterministic mock calendar adapter.",
            actions={
                "get_free_busy": ActionType.READ,
                "list_events": ActionType.READ,
                "create_event": ActionType.WRITE,
            },
            sensitive_arg_keys=["title", "attendees", "description"],
            read_scopes=["free_busy_only", "event_metadata"],
            default_read_scope="free_busy_only",
        )

    def supports_scope(self, scope: str) -> bool:
        """Return True if the scope is supported."""
        return scope in self.spec().read_scopes

    def execute(self, request: ToolRequest, scope: Optional[str]) -> ToolResult:
        """Dispatch the requested action."""
        if request.tool_action == "get_free_busy":
            return self._get_free_busy()
        if request.tool_action == "list_events":
            return self._list_events(scope)
        if request.tool_action == "create_event":
            return self._create_event(request.args)
        return ToolResult(
            ok=False,
            error=ToolError(
                error_type=ToolErrorType.TOOL_EXECUTION_ERROR,
                human_message="Unknown action.",
                agent_guidance="Verify the tool_action.",
                details={"tool_action": request.tool_action},
            ),
        )

    def _get_free_busy(self) -> ToolResult:
        """Return time blocks for all events."""
        blocks = [self._free_busy_block(event) for event in self._events]
        return ToolResult(ok=True, data={"busy": blocks})

    def _list_events(self, scope: Optional[str]) -> ToolResult:
        """List events with scope-specific detail."""
        scope = scope or self.spec().default_read_scope
        if not self.supports_scope(scope):
            return self._unsupported_scope(scope)
        if scope == "free_busy_only":
            blocks = [self._free_busy_block(event) for event in self._events]
            return ToolResult(ok=True, data={"events": blocks})
        events = [self._event_metadata(event) for event in self._events]
        return ToolResult(ok=True, data={"events": events})

    def _create_event(self, args: Dict[str, Any]) -> ToolResult:
        """Create an in-memory calendar event."""
        title = args.get("title") or "Untitled"
        start = args.get("start")
        end = args.get("end")
        if not start or not end:
            return ToolResult(
                ok=False,
                error=ToolError(
                    error_type=ToolErrorType.TOOL_EXECUTION_ERROR,
                    human_message="Missing start or end.",
                    agent_guidance="Provide start and end.",
                    details={"start": start, "end": end},
                ),
            )
        event = {
            "id": f"event_{self._event_counter}",
            "title": title,
            "start": start,
            "end": end,
        }
        self._event_counter += 1
        self._events.append(event)
        return ToolResult(ok=True, data={"event_id": event["id"], "status": "created"})

    def _free_busy_block(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Return a minimal time block for an event."""
        return {"start": event["start"], "end": event["end"]}

    def _event_metadata(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Return event metadata for list views."""
        return {
            "id": event["id"],
            "title": event["title"],
            "start": event["start"],
            "end": event["end"],
        }

    def _unsupported_scope(self, scope: str) -> ToolResult:
        """Return an error for unsupported scope requests."""
        return ToolResult(
            ok=False,
            error=ToolError(
                error_type=ToolErrorType.TOOL_EXECUTION_ERROR,
                human_message="Unsupported scope.",
                agent_guidance="Use a supported read scope.",
                details={"scope": scope},
            ),
        )
