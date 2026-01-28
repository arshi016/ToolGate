"""Policy engine for tool requests (v0 rules)."""

from __future__ import annotations

from typing import Any, Dict, Iterable

from gateway.core.types import (
    ActionType,
    Decision,
    PolicyDecision,
    RiskLevel,
    ToolRequest,
    ToolSpec,
)
from gateway.policies.profile import PolicyProfile, ToolPolicy


class PolicyEngine:
    """Evaluate tool requests against a policy profile."""

    def __init__(self, profile: PolicyProfile) -> None:
        self._profile = profile

    def decide(self, request: ToolRequest, spec: ToolSpec) -> PolicyDecision:
        """Evaluate a tool request against the profile."""
        action_type = spec.actions.get(request.tool_action)
        if action_type is None:
            return PolicyDecision(
                decision=Decision.BLOCK,
                action_type=ActionType.WRITE,
                risk_level=RiskLevel.HIGH,
                policy_rule_id="POLICY_UNKNOWN_ACTION_V0",
                reason_code="UNKNOWN_ACTION",
            )

        tool_policy = self._profile.tools.get(request.tool_name, ToolPolicy())
        global_policy = self._profile.global_policy

        if action_type == ActionType.READ:
            scope_applied = tool_policy.read_default_scope or spec.default_read_scope
            if self._is_broad_read(
                request.args,
                global_policy.broad_read_keywords,
                global_policy.broad_read_range_days_threshold,
            ):
                return PolicyDecision(
                    decision=Decision.REQUIRE_CONFIRM,
                    action_type=action_type,
                    risk_level=RiskLevel.HIGH,
                    policy_rule_id="POLICY_READ_BROAD_CONFIRM_V0",
                    reason_code="BROAD_READ_REQUIRES_CONFIRM",
                    scope_applied=scope_applied,
                )
            return PolicyDecision(
                decision=Decision.ALLOW_WITH_REDACTIONS,
                action_type=action_type,
                risk_level=RiskLevel.LOW,
                policy_rule_id="POLICY_READ_SCOPED_V0",
                reason_code="READ_SCOPED",
                scope_applied=scope_applied,
            )

        safe_writes = set(tool_policy.safe_writes_without_confirm)
        confirm_writes = set(tool_policy.always_confirm_writes)
        if request.tool_action in confirm_writes:
            return PolicyDecision(
                decision=Decision.REQUIRE_CONFIRM,
                action_type=action_type,
                risk_level=RiskLevel.HIGH,
                policy_rule_id="POLICY_WRITE_CONFIRM_V0",
                reason_code="WRITE_REQUIRES_CONFIRM",
            )
        if request.tool_action in safe_writes:
            return PolicyDecision(
                decision=Decision.ALLOW,
                action_type=action_type,
                risk_level=RiskLevel.MED,
                policy_rule_id="POLICY_WRITE_SAFE_V0",
                reason_code="SAFE_WRITE_ALLOWED",
            )
        return PolicyDecision(
            decision=Decision.REQUIRE_CONFIRM,
            action_type=action_type,
            risk_level=RiskLevel.HIGH,
            policy_rule_id="POLICY_WRITE_CONFIRM_V0",
            reason_code="WRITE_REQUIRES_CONFIRM",
        )

    def _is_broad_read(
        self,
        args: Dict[str, Any],
        keywords: Iterable[str],
        range_threshold_days: int,
    ) -> bool:
        """Return True if args indicate a broad read request."""
        if self._contains_keyword(args, keywords):
            return True
        range_days = args.get("range_days")
        if isinstance(range_days, (int, float)) and range_days > range_threshold_days:
            return True
        if self._contains_all_true(args):
            return True
        return False

    def _contains_keyword(self, args: Dict[str, Any], keywords: Iterable[str]) -> bool:
        """Return True if any keyword appears in string args."""
        lowered_keywords = [value.lower() for value in keywords if value]
        if not lowered_keywords:
            return False
        for value in self._iter_string_values(args):
            value_lower = value.lower()
            if any(keyword in value_lower for keyword in lowered_keywords):
                return True
        return False

    def _contains_all_true(self, args: Dict[str, Any]) -> bool:
        """Return True if args include all=true."""
        if "all" not in args:
            return False
        value = args["all"]
        if isinstance(value, bool):
            return value is True
        if isinstance(value, str):
            return value.strip().lower() == "true"
        if isinstance(value, (int, float)):
            return value == 1
        return False

    def _iter_string_values(self, payload: Any) -> Iterable[str]:
        """Yield all string values from nested structures."""
        if isinstance(payload, str):
            yield payload
            return
        if isinstance(payload, dict):
            for value in payload.values():
                yield from self._iter_string_values(value)
            return
        if isinstance(payload, list):
            for item in payload:
                yield from self._iter_string_values(item)
