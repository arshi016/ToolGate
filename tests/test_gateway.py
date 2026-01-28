from __future__ import annotations

import json
from pathlib import Path

import pytest

from gateway.adapters import CalendarMockAdapter, EmailMockAdapter, FileSystemMockAdapter
from gateway.core.approval import ApprovalGate, ApprovalRequest, ApprovalToken
from gateway.core.control_layer import ControlLayer
from gateway.core.types import ActionType, ToolContext, ToolErrorType


ROOT = Path(__file__).resolve().parents[1]


def _context() -> ToolContext:
    return ToolContext(
        session_id="test-session",
        task_id="test-task",
        agent_id="test-agent",
        user_id="test-user",
        timestamp="2026-01-28T00:00:00Z",
        policy_state={},
    )


def _control_layer(tmp_path: Path, profile: str, monkeypatch: pytest.MonkeyPatch) -> ControlLayer:
    monkeypatch.setenv("GATEWAY_SECRET", "test-secret")
    receipts_path = tmp_path / "receipts.log"
    control = ControlLayer(profile_path=profile, receipts_path=str(receipts_path))
    control.register_adapter(CalendarMockAdapter())
    control.register_adapter(EmailMockAdapter())
    control.register_adapter(FileSystemMockAdapter())
    return control


def _read_receipts(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_classification() -> None:
    email_spec = EmailMockAdapter().spec()
    calendar_spec = CalendarMockAdapter().spec()
    fs_spec = FileSystemMockAdapter().spec()

    assert email_spec.actions["create_draft"] == ActionType.WRITE
    assert calendar_spec.actions["get_free_busy"] == ActionType.READ
    assert fs_spec.actions["write_file"] == ActionType.WRITE


def test_approval_flow_strict(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    control = _control_layer(tmp_path, str(ROOT / "configs/policy_strict.yaml"), monkeypatch)
    context = _context()

    result = control.call_tool(
        "calendar",
        "create_event",
        {"title": "Demo", "start": "2026-01-28T09:00:00Z", "end": "2026-01-28T10:00:00Z"},
        context,
    )
    assert result.ok is False
    assert result.error is not None
    assert result.error.error_type == ToolErrorType.CONFIRMATION_REQUIRED

    approval_data = result.error.details["approval_request"]
    approval_request = ApprovalRequest.model_validate(approval_data)
    gate = ApprovalGate(secret=b"test-secret")
    token = gate.sign(approval_request)
    approved_context = context.model_copy(deep=True)
    approved_context.policy_state["approval_token"] = token.model_dump()

    result = control.call_tool(
        "calendar",
        "create_event",
        {"title": "Demo", "start": "2026-01-28T09:00:00Z", "end": "2026-01-28T10:00:00Z"},
        approved_context,
    )
    assert result.ok is True

    expired_request = ApprovalRequest(
        request_id="expired",
        tool_name="calendar",
        tool_action="create_event",
        canonical_args=approval_request.canonical_args,
        expires_at="2000-01-01T00:00:00Z",
        action_summary="calendar.create_event",
    )
    expired_token = gate.sign(expired_request)
    expired_context = context.model_copy(deep=True)
    expired_context.policy_state["approval_token"] = expired_token.model_dump()

    result = control.call_tool(
        "calendar",
        "create_event",
        {"title": "Demo", "start": "2026-01-28T09:00:00Z", "end": "2026-01-28T10:00:00Z"},
        expired_context,
    )
    assert result.ok is False
    assert result.error is not None
    assert result.error.error_type == ToolErrorType.INVALID_APPROVAL


def test_practical_profile_email_draft_and_send(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    control = _control_layer(tmp_path, str(ROOT / "configs/policy_practical.yaml"), monkeypatch)
    context = _context()

    result = control.call_tool(
        "email",
        "create_draft",
        {"to": "user@example.com", "subject": "Hello", "body": "Draft body"},
        context,
    )
    assert result.ok is True

    result = control.call_tool(
        "email",
        "send_email",
        {"to": "user@example.com", "subject": "Hello", "body": "Draft body"},
        context,
    )
    assert result.ok is False
    assert result.error is not None
    assert result.error.error_type == ToolErrorType.CONFIRMATION_REQUIRED


def test_broad_read_receipt_reason(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    control = _control_layer(tmp_path, str(ROOT / "configs/policy_practical.yaml"), monkeypatch)
    context = _context()

    result = control.call_tool(
        "email",
        "search",
        {"query": "dump all emails"},
        context,
    )
    assert result.ok is False

    receipts = _read_receipts(tmp_path / "receipts.log")
    assert receipts, "Expected at least one receipt entry."
    reason_code = receipts[-1]["reason_code"]
    assert reason_code in {"BROAD_READ_REQUIRES_CONFIRM", "INJECTION_SUSPECTED"}


def test_receipts_privacy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    control = _control_layer(tmp_path, str(ROOT / "configs/policy_practical.yaml"), monkeypatch)
    context = _context()

    control.call_tool(
        "email",
        "create_draft",
        {"to": "user@example.com", "subject": "Hello", "body": "SECRET BODY"},
        context,
    )
    control.call_tool(
        "files",
        "write_file",
        {"path": "secret.txt", "content": "TOP SECRET"},
        context,
    )

    log_path = tmp_path / "receipts.log"
    log_text = log_path.read_text(encoding="utf-8")
    assert "SECRET BODY" not in log_text
    assert "TOP SECRET" not in log_text

    receipts = _read_receipts(log_path)
    assert receipts, "Expected receipts to be logged."
    for entry in receipts:
        assert "arg_fingerprint" in entry
        assert "args" not in entry
        assert "content" not in entry
        assert "body" not in entry
