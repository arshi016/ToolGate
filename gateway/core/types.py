"""Core types for tool policy enforcement and execution."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictStr


class ActionType(str, Enum):
    """Tool action semantics.

    READ: data retrieval with no external side effects.
    WRITE: any action that changes external state or triggers outbound effects.
    """

    READ = "READ"
    WRITE = "WRITE"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MED = "MED"
    HIGH = "HIGH"


class Decision(str, Enum):
    ALLOW = "ALLOW"
    BLOCK = "BLOCK"
    REQUIRE_CONFIRM = "REQUIRE_CONFIRM"
    ALLOW_WITH_REDACTIONS = "ALLOW_WITH_REDACTIONS"


class ToolErrorType(str, Enum):
    TOOL_NOT_FOUND = "TOOL_NOT_FOUND"
    POLICY_BLOCKED = "POLICY_BLOCKED"
    CONFIRMATION_REQUIRED = "CONFIRMATION_REQUIRED"
    INJECTION_SUSPECTED = "INJECTION_SUSPECTED"
    TOOL_EXECUTION_ERROR = "TOOL_EXECUTION_ERROR"
    INVALID_APPROVAL = "INVALID_APPROVAL"


class ToolContext(BaseModel):
    """Execution context for a tool request."""

    model_config = ConfigDict(extra="forbid", strict=True)

    session_id: StrictStr
    task_id: StrictStr
    agent_id: StrictStr
    user_id: Optional[StrictStr] = None
    timestamp: StrictStr
    policy_state: Dict[str, Any] = Field(default_factory=dict)


class ToolRequest(BaseModel):
    """Normalized tool request with context and arguments."""

    model_config = ConfigDict(extra="forbid", strict=True)

    tool_name: StrictStr
    tool_action: StrictStr
    args: Dict[str, Any]
    context: ToolContext


class ToolError(BaseModel):
    """Error payload for tool execution or policy blocks."""

    model_config = ConfigDict(extra="forbid", strict=True)

    error_type: ToolErrorType
    human_message: StrictStr
    agent_guidance: StrictStr
    details: Optional[Dict[str, Any]] = None


class ToolResult(BaseModel):
    """Result wrapper for tool execution outcomes."""

    model_config = ConfigDict(extra="forbid", strict=True)

    ok: StrictBool
    data: Optional[Any] = None
    error: Optional[ToolError] = None


class ToolSpec(BaseModel):
    """Static tool capabilities and scope metadata."""

    model_config = ConfigDict(extra="forbid", strict=True)

    tool_name: StrictStr
    description: StrictStr
    actions: Dict[StrictStr, ActionType]
    sensitive_arg_keys: List[StrictStr]
    read_scopes: List[StrictStr]
    default_read_scope: StrictStr


class PolicyDecision(BaseModel):
    """Decision outcome for a tool request.

    scope_applied is the concrete data scope enforced after policy evaluation
    (for example, a reduced date range or metadata-only read scope).
    """

    model_config = ConfigDict(extra="forbid", strict=True)

    decision: Decision
    action_type: ActionType
    risk_level: RiskLevel
    policy_rule_id: StrictStr
    reason_code: StrictStr
    scope_applied: Optional[StrictStr] = None
    redactions: Optional[Dict[str, Any]] = None
