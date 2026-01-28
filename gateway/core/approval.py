"""Approval request and verification for WRITE actions."""

from __future__ import annotations

import hmac
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from pydantic import BaseModel, ConfigDict, StrictStr

from gateway.core.types import ToolError, ToolErrorType, ToolRequest
from gateway.receipts.fingerprint import canonicalize_args


class ApprovalRequest(BaseModel):
    """Approval request details for a pending WRITE action."""

    model_config = ConfigDict(extra="forbid", strict=True)

    request_id: StrictStr
    tool_name: StrictStr
    tool_action: StrictStr
    canonical_args: StrictStr
    expires_at: StrictStr
    action_summary: StrictStr


class ApprovalToken(BaseModel):
    """Signed approval token for a WRITE action."""

    model_config = ConfigDict(extra="forbid", strict=True)

    request_id: StrictStr
    signature: StrictStr
    expires_at: StrictStr


class ApprovalGate:
    """Create and verify approvals for WRITE actions.

    Approval context storage:
      context.policy_state["approval_token"] = {
          "request_id": "...",
          "signature": "...",
          "expires_at": "..."
      }

    Guarantee: No WRITE executes unless verify() returns True.
    """

    _DEFAULT_TTL_SECONDS = 15 * 60

    def __init__(self, secret: bytes, ttl_seconds: int | None = None) -> None:
        self._secret = secret
        self._ttl_seconds = ttl_seconds or self._DEFAULT_TTL_SECONDS

    def create_approval_request(self, request: ToolRequest) -> ApprovalRequest:
        canonical_args = canonicalize_args(request.args)
        request_id = uuid.uuid4().hex
        expires_at = self._expires_at()
        action_summary = f"{request.tool_name}.{request.tool_action}"
        return ApprovalRequest(
            request_id=request_id,
            tool_name=request.tool_name,
            tool_action=request.tool_action,
            canonical_args=canonical_args,
            expires_at=expires_at,
            action_summary=action_summary,
        )

    def sign(self, approval_request: ApprovalRequest) -> ApprovalToken:
        signature = self._sign_payload(
            approval_request.request_id,
            approval_request.canonical_args,
            approval_request.expires_at,
        )
        return ApprovalToken(
            request_id=approval_request.request_id,
            signature=signature,
            expires_at=approval_request.expires_at,
        )

    def verify(self, token: ApprovalToken, request: ToolRequest) -> bool:
        if self._is_expired(token.expires_at):
            return False
        canonical_args = canonicalize_args(request.args)
        expected = self._sign_payload(token.request_id, canonical_args, token.expires_at)
        return hmac.compare_digest(token.signature, expected)

    def invalid_approval_error(self, reason: str) -> ToolError:
        """Construct a ToolError for invalid or expired approvals."""
        return ToolError(
            error_type=ToolErrorType.INVALID_APPROVAL,
            human_message="Approval token invalid or expired.",
            agent_guidance="Request approval again for this action.",
            details={"reason": reason},
        )

    def _sign_payload(self, request_id: str, canonical_args: str, expires_at: str) -> str:
        payload = f"{request_id}:{canonical_args}:{expires_at}".encode("utf-8")
        return hmac.new(self._secret, payload, "sha256").hexdigest()

    def _expires_at(self) -> str:
        timestamp = datetime.now(timezone.utc) + timedelta(seconds=self._ttl_seconds)
        return timestamp.isoformat(timespec="seconds").replace("+00:00", "Z")

    def _is_expired(self, expires_at: str) -> bool:
        parsed = self._parse_timestamp(expires_at)
        if parsed is None:
            return True
        return parsed <= datetime.now(timezone.utc)

    def _parse_timestamp(self, value: str) -> Optional[datetime]:
        try:
            if value.endswith("Z"):
                value = value[:-1] + "+00:00"
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
