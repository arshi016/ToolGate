"""Control layer orchestrating policy, security, and tool execution."""

from __future__ import annotations

import logging
import os
import secrets
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional dependency for local dev
    load_dotenv = None

from gateway.core.adapter import ToolAdapter
from gateway.core.approval import ApprovalGate, ApprovalToken
from gateway.core.registry import AdapterRegistry, ToolNotFoundError
from gateway.core.types import (
    ActionType,
    Decision,
    PolicyDecision,
    RiskLevel,
    ToolContext,
    ToolError,
    ToolErrorType,
    ToolRequest,
    ToolResult,
)
from gateway.policies.policy_engine import PolicyEngine
from gateway.policies.profile import PolicyProfile, load_profile
from gateway.receipts.fingerprint import canonicalize_args, hmac_fingerprint
from gateway.receipts.logger import ReceiptLogger
from gateway.receipts.schema import ReceiptEvent
from gateway.security.injection_filter import InjectionFilter

logger = logging.getLogger(__name__)


class ControlLayer:
    """Policy-enforced gateway for tool calls."""

    def __init__(
        self, profile_path: str, receipts_path: str = "./receipts.log"
    ) -> None:
        if load_dotenv is not None:
            load_dotenv()
        secret_value = os.getenv("GATEWAY_SECRET")
        if secret_value:
            secret = secret_value.encode("utf-8")
        else:
            secret = secrets.token_bytes(32)
            logger.warning("GATEWAY_SECRET not set. Using an insecure dev secret!")

        self._secret = secret
        self._profile: PolicyProfile = load_profile(profile_path)
        self._policy_engine = PolicyEngine(self._profile)
        self._injection_filter = InjectionFilter()
        self._registry = AdapterRegistry()
        self._receipt_logger = ReceiptLogger(secret=secret, path=receipts_path)
        self._approval_gate = ApprovalGate(secret=secret)

    def register_adapter(self, adapter: ToolAdapter) -> None:
        """Register a tool adapter with the registry."""
        self._registry.register(adapter)

    def call_tool(
        self,
        tool_name: str,
        tool_action: str,
        args: Dict[str, Any],
        context: ToolContext,
    ) -> ToolResult:
        """Execute a tool call through the policy and security pipeline."""
        request = ToolRequest(
            tool_name=tool_name, tool_action=tool_action, args=args, context=context
        )

        try:
            adapter = self._registry.get(tool_name)
        except ToolNotFoundError as exc:
            result = ToolResult(ok=False, error=exc.error)
            self._log_receipt(
                request,
                decision=Decision.BLOCK,
                action_type=ActionType.WRITE,
                risk_level=RiskLevel.HIGH,
                policy_rule_id="POLICY_TOOL_NOT_FOUND_V0",
                reason_code="TOOL_NOT_FOUND",
                scope_applied=None,
                result_summary=self._result_summary(result),
            )
            return result

        spec = adapter.spec()

        allowed, inspected = self._injection_filter.inspect(request)
        if not allowed:
            decision = inspected
            result = ToolResult(
                ok=False,
                error=ToolError(
                    error_type=ToolErrorType.INJECTION_SUSPECTED,
                    human_message="Request blocked.",
                    agent_guidance="Remove suspicious input and retry.",
                    details={"reason_code": decision.reason_code},
                ),
            )
            self._log_receipt(
                request,
                decision=decision.decision,
                action_type=decision.action_type,
                risk_level=decision.risk_level,
                policy_rule_id=decision.policy_rule_id,
                reason_code=decision.reason_code,
                scope_applied=decision.scope_applied,
                result_summary=self._result_summary(result),
            )
            return result

        policy_decision = self._policy_engine.decide(request, spec)
        if policy_decision.decision == Decision.BLOCK:
            result = ToolResult(
                ok=False,
                error=ToolError(
                    error_type=ToolErrorType.POLICY_BLOCKED,
                    human_message="Blocked by policy.",
                    agent_guidance="Adjust the request and retry.",
                    details={"reason_code": policy_decision.reason_code},
                ),
            )
            self._log_receipt(
                request,
                decision=policy_decision.decision,
                action_type=policy_decision.action_type,
                risk_level=policy_decision.risk_level,
                policy_rule_id=policy_decision.policy_rule_id,
                reason_code=policy_decision.reason_code,
                scope_applied=policy_decision.scope_applied,
                result_summary=self._result_summary(result),
            )
            return result

        decision_for_log = policy_decision
        if policy_decision.decision == Decision.REQUIRE_CONFIRM:
            token = self._approval_token_from_context(context)
            if token is None:
                approval_request = self._approval_gate.create_approval_request(request)
                result = ToolResult(
                    ok=False,
                    error=ToolError(
                        error_type=ToolErrorType.CONFIRMATION_REQUIRED,
                        human_message="Confirmation required.",
                        agent_guidance="Provide approval and retry.",
                        details={"approval_request": approval_request.model_dump()},
                    ),
                )
                self._log_receipt(
                    request,
                    decision=policy_decision.decision,
                    action_type=policy_decision.action_type,
                    risk_level=policy_decision.risk_level,
                    policy_rule_id=policy_decision.policy_rule_id,
                    reason_code=policy_decision.reason_code,
                    scope_applied=policy_decision.scope_applied,
                    result_summary=self._result_summary(result),
                )
                return result
            if not self._approval_gate.verify(token, request):
                result = ToolResult(
                    ok=False,
                    error=self._approval_gate.invalid_approval_error(
                        "invalid_or_expired"
                    ),
                )
                self._log_receipt(
                    request,
                    decision=Decision.BLOCK,
                    action_type=policy_decision.action_type,
                    risk_level=RiskLevel.HIGH,
                    policy_rule_id="POLICY_APPROVAL_INVALID_V0",
                    reason_code="INVALID_APPROVAL",
                    scope_applied=policy_decision.scope_applied,
                    result_summary=self._result_summary(result),
                )
                return result
            decision_for_log = self._confirmed_decision(policy_decision)

        scope_applied = (
            policy_decision.scope_applied
            if policy_decision.action_type == ActionType.READ
            else None
        )
        try:
            result = adapter.execute(request, scope_applied)
        except Exception as exc:  # pragma: no cover - adapter failure path
            result = ToolResult(
                ok=False,
                error=ToolError(
                    error_type=ToolErrorType.TOOL_EXECUTION_ERROR,
                    human_message="Tool execution failed.",
                    agent_guidance="Retry or check tool configuration.",
                    details={"error": str(exc)},
                ),
            )

        self._log_receipt(
            request,
            decision=decision_for_log.decision,
            action_type=decision_for_log.action_type,
            risk_level=decision_for_log.risk_level,
            policy_rule_id=decision_for_log.policy_rule_id,
            reason_code=decision_for_log.reason_code,
            scope_applied=policy_decision.scope_applied,
            result_summary=self._result_summary(result),
        )
        return result

    def _approval_token_from_context(
        self, context: ToolContext
    ) -> Optional[ApprovalToken]:
        """Extract an approval token from the tool context."""
        token_data = context.policy_state.get("approval_token")
        if not isinstance(token_data, dict):
            return None
        try:
            return ApprovalToken.model_validate(token_data)
        except Exception:
            return None

    def _confirmed_decision(self, decision: PolicyDecision) -> PolicyDecision:
        """Return a decision representing verified confirmation."""
        confirmed_decision = (
            Decision.ALLOW_WITH_REDACTIONS
            if decision.action_type == ActionType.READ
            else Decision.ALLOW
        )
        return PolicyDecision(
            decision=confirmed_decision,
            action_type=decision.action_type,
            risk_level=decision.risk_level,
            policy_rule_id="POLICY_CONFIRMATION_VERIFIED_V0",
            reason_code="CONFIRMATION_VERIFIED",
            scope_applied=decision.scope_applied,
            redactions=decision.redactions,
        )

    def _log_receipt(
        self,
        request: ToolRequest,
        decision: Decision,
        action_type: ActionType,
        risk_level: RiskLevel,
        policy_rule_id: str,
        reason_code: str,
        scope_applied: Optional[str],
        result_summary: str,
    ) -> None:
        """Emit a receipt event for a tool attempt."""
        receipt = ReceiptEvent(
            receipt_id=uuid.uuid4().hex,
            timestamp=self._utc_now(),
            session_id=request.context.session_id,
            task_id=request.context.task_id,
            agent_id=request.context.agent_id,
            tool_name=request.tool_name,
            tool_action=request.tool_action,
            action_type=action_type,
            risk_level=risk_level,
            decision=decision,
            policy_rule_id=policy_rule_id,
            reason_code=reason_code,
            scope_applied=scope_applied,
            arg_fingerprint=self._arg_fingerprint(request.args),
            result_summary=result_summary,
            policy_profile=self._profile.profile,
        )
        self._receipt_logger.log_event(receipt)

    def _arg_fingerprint(self, args: Dict[str, Any]) -> str:
        """Return a stable HMAC fingerprint for request args."""
        try:
            canonical = canonicalize_args(args)
        except (TypeError, ValueError):
            canonical = "{}"
        return hmac_fingerprint(self._secret, canonical)

    def _result_summary(self, result: ToolResult) -> str:
        """Return a minimal result summary for receipts."""
        if result.ok:
            return "ok"
        if result.error is None:
            return "error"
        return f"error:{result.error.error_type.value}"

    def _utc_now(self) -> str:
        """Return the current UTC time as RFC3339."""
        return (
            datetime.now(timezone.utc)
            .isoformat(timespec="seconds")
            .replace("+00:00", "Z")
        )
