"""Deterministic mock email adapter."""

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


class EmailMockAdapter:
    """In-memory email adapter with deterministic responses."""

    _MESSAGES = [
        {
            "id": "msg_1",
            "subject": "Welcome",
            "from": "noreply@example.com",
            "body": "Thanks for signing up.",
        },
        {
            "id": "msg_2",
            "subject": "Meeting",
            "from": "alice@example.com",
            "body": "Can we meet at 10?",
        },
        {
            "id": "msg_3",
            "subject": "Invoice",
            "from": "billing@example.com",
            "body": "Your invoice is attached.",
        },
    ]

    def __init__(self) -> None:
        self._drafts: List[Dict[str, Any]] = []
        self._draft_counter = 1

    def spec(self) -> ToolSpec:
        return ToolSpec(
            tool_name="email",
            description="Deterministic mock email adapter.",
            actions={
                "search": ActionType.READ,
                "get_headers": ActionType.READ,
                "create_draft": ActionType.WRITE,
                "send_email": ActionType.WRITE,
            },
            sensitive_arg_keys=["body", "content", "to", "cc", "bcc"],
            read_scopes=["headers_only", "full_body"],
            default_read_scope="headers_only",
        )

    def supports_scope(self, scope: str) -> bool:
        return scope in self.spec().read_scopes

    def execute(self, request: ToolRequest, scope: Optional[str]) -> ToolResult:
        if request.tool_action == "search":
            return self._search(request.args, scope)
        if request.tool_action == "get_headers":
            return self._get_headers(request.args, scope)
        if request.tool_action == "create_draft":
            return self._create_draft(request.args)
        if request.tool_action == "send_email":
            return ToolResult(ok=True, data={"status": "sent"})
        return ToolResult(
            ok=False,
            error=ToolError(
                error_type=ToolErrorType.TOOL_EXECUTION_ERROR,
                human_message="Unknown action.",
                agent_guidance="Verify the tool_action.",
                details={"tool_action": request.tool_action},
            ),
        )

    def _search(self, args: Dict[str, Any], scope: Optional[str]) -> ToolResult:
        scope = scope or self.spec().default_read_scope
        if not self.supports_scope(scope):
            return self._unsupported_scope(scope)
        query = str(args.get("query", "")).lower()
        results = []
        for message in self._MESSAGES:
            if query and not self._matches_query(message, query):
                continue
            results.append(self._apply_scope(message, scope))
        return ToolResult(ok=True, data={"messages": results})

    def _get_headers(self, args: Dict[str, Any], scope: Optional[str]) -> ToolResult:
        scope = scope or self.spec().default_read_scope
        if not self.supports_scope(scope):
            return self._unsupported_scope(scope)
        message_id = args.get("message_id")
        for message in self._MESSAGES:
            if message["id"] == message_id:
                return ToolResult(ok=True, data=self._apply_scope(message, scope))
        return ToolResult(
            ok=False,
            error=ToolError(
                error_type=ToolErrorType.TOOL_EXECUTION_ERROR,
                human_message="Message not found.",
                agent_guidance="Check the message_id.",
                details={"message_id": message_id},
            ),
        )

    def _create_draft(self, args: Dict[str, Any]) -> ToolResult:
        draft = {
            "id": f"draft_{self._draft_counter}",
            "to": args.get("to"),
            "subject": args.get("subject"),
            "body": args.get("body"),
        }
        self._draft_counter += 1
        self._drafts.append(draft)
        return ToolResult(ok=True, data={"draft_id": draft["id"], "status": "drafted"})

    def _apply_scope(self, message: Dict[str, Any], scope: str) -> Dict[str, Any]:
        if scope == "headers_only":
            return {"id": message["id"], "subject": message["subject"], "from": message["from"]}
        return {
            "id": message["id"],
            "subject": message["subject"],
            "from": message["from"],
            "body": message["body"],
        }

    def _matches_query(self, message: Dict[str, Any], query: str) -> bool:
        return (
            query in message["subject"].lower()
            or query in message["from"].lower()
            or query in message["body"].lower()
        )

    def _unsupported_scope(self, scope: str) -> ToolResult:
        return ToolResult(
            ok=False,
            error=ToolError(
                error_type=ToolErrorType.TOOL_EXECUTION_ERROR,
                human_message="Unsupported scope.",
                agent_guidance="Use a supported read scope.",
                details={"scope": scope},
            ),
        )
