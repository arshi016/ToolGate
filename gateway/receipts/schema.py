"""Receipt schema for audit logging (no raw args or content)."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, StrictStr

from gateway.core.types import ActionType, Decision, RiskLevel


class ReceiptEvent(BaseModel):
    """Minimal receipt event for policy decisions and tool execution."""

    model_config = ConfigDict(extra="forbid", strict=True)

    receipt_id: StrictStr
    timestamp: StrictStr
    session_id: StrictStr
    task_id: StrictStr
    agent_id: StrictStr
    tool_name: StrictStr
    tool_action: StrictStr
    action_type: ActionType
    risk_level: RiskLevel
    decision: Decision
    policy_rule_id: StrictStr
    reason_code: StrictStr
    scope_applied: Optional[StrictStr] = None
    arg_fingerprint: StrictStr
    result_summary: StrictStr
    policy_profile: StrictStr
