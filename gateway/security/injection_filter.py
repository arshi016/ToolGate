"""Injection filter for tool requests."""

from __future__ import annotations

from typing import Any, Iterable

from gateway.core.types import (
    ActionType,
    Decision,
    PolicyDecision,
    RiskLevel,
    ToolRequest,
)


class InjectionFilter:
    """Detect suspicious prompt injection patterns in tool requests."""

    _SUSPICIOUS_PATTERNS = (
        "ignore previous",
        "dump all",
        "reveal secrets",
        "exfiltrate",
        "override policy",
    )

    def inspect(
        self, request: ToolRequest
    ) -> tuple[bool, ToolRequest | PolicyDecision]:
        """Inspect a request and block if suspicious patterns are found."""
        if self._contains_suspicious_pattern(request.args):
            return False, self._blocked_decision()
        if request.tool_name == "web" and self._url_contains_secrets(request.args):
            return False, self._blocked_decision()
        return True, request

    def _blocked_decision(self) -> PolicyDecision:
        """Return a policy decision that blocks the request."""
        return PolicyDecision(
            decision=Decision.BLOCK,
            action_type=ActionType.WRITE,
            risk_level=RiskLevel.HIGH,
            policy_rule_id="POLICY_INJECTION_BLOCK_V0",
            reason_code="INJECTION_SUSPECTED",
        )

    def _contains_suspicious_pattern(self, args: dict[str, Any]) -> bool:
        """Return True if args include injection patterns."""
        patterns = [value.lower() for value in self._SUSPICIOUS_PATTERNS]
        for text in self._iter_string_values(args):
            lowered = text.lower()
            if any(pattern in lowered for pattern in patterns):
                return True
        return False

    def _url_contains_secrets(self, args: dict[str, Any]) -> bool:
        """Return True if a URL arg contains secret-like tokens."""
        for key, value in self._iter_items(args):
            if not isinstance(value, str):
                continue
            if key.lower() != "url":
                continue
            lowered = value.lower()
            if "token=" in lowered or "apikey=" in lowered:
                return True
        return False

    def _iter_items(self, payload: Any) -> Iterable[tuple[str, Any]]:
        """Yield nested key/value pairs from args."""
        if isinstance(payload, dict):
            for key, value in payload.items():
                if isinstance(key, str):
                    yield key, value
                yield from self._iter_items(value)
        elif isinstance(payload, list):
            for item in payload:
                yield from self._iter_items(item)

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
