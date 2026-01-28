"""Demo CLI for running ControlLayer scenarios."""

from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, Optional

import typer

from gateway.adapters import (
    CalendarMockAdapter,
    EmailMockAdapter,
    FileSystemMockAdapter,
)
from gateway.core.approval import ApprovalGate, ApprovalRequest
from gateway.core.control_layer import ControlLayer
from gateway.core.types import ToolContext, ToolResult

app = typer.Typer(add_completion=False)

_DEV_SECRET = "dev-secret-change-me"


def _ensure_secret() -> str:
    """Return the configured secret, setting a demo default if missing."""
    secret = os.getenv("GATEWAY_SECRET")
    if not secret:
        os.environ["GATEWAY_SECRET"] = _DEV_SECRET
        typer.secho(
            "GATEWAY_SECRET not set; using demo secret. "
            "Set GATEWAY_SECRET for stable approvals.",
            fg=typer.colors.YELLOW,
        )
        secret = _DEV_SECRET
    return secret


def _print_result(label: str, result: ToolResult, receipts_path: str) -> None:
    """Print a tool result and approval instructions if needed."""
    typer.secho(f"\n== {label} ==", fg=typer.colors.CYAN)
    typer.echo(json.dumps(result.model_dump(), indent=2, sort_keys=True))
    typer.echo(f"Receipts log: {receipts_path}")
    if (
        result.error
        and result.error.details
        and "approval_request" in result.error.details
    ):
        approval_request = result.error.details["approval_request"]
        typer.secho("\nApproval required. To approve:", fg=typer.colors.YELLOW)
        typer.echo(json.dumps(approval_request, indent=2, sort_keys=True))
        typer.echo(
            "Save the JSON above and run:\n"
            "  python -m gateway.demo.cli approve --input-file approval.json\n"
            "Then re-run the blocked step with the approval_token in context."
        )


def _base_context() -> ToolContext:
    """Return a default demo context."""
    return ToolContext(
        session_id="demo-session",
        task_id="demo-task",
        agent_id="demo-agent",
        user_id="demo-user",
        timestamp="2026-01-28T00:00:00Z",
        policy_state={},
    )


@app.command()
def run(
    profile: str = typer.Option(
        "configs/policy_practical.yaml",
        "--profile",
        help="Policy profile path.",
    ),
    receipts_path: str = typer.Option(
        "./receipts.log", "--receipts", help="Receipts log path."
    ),
) -> None:
    """Run scripted demo scenarios."""
    _ensure_secret()
    control = ControlLayer(profile_path=profile, receipts_path=receipts_path)
    control.register_adapter(CalendarMockAdapter())
    control.register_adapter(EmailMockAdapter())
    control.register_adapter(FileSystemMockAdapter())

    context = _base_context()

    # 1) Calendar scheduling attempt: get_free_busy then create_event.
    result = control.call_tool("calendar", "get_free_busy", args={}, context=context)
    _print_result("Scenario 1a: calendar.get_free_busy", result, receipts_path)

    result = control.call_tool(
        "calendar",
        "create_event",
        args={
            "title": "Demo",
            "start": "2026-01-28T09:00:00Z",
            "end": "2026-01-28T10:00:00Z",
        },
        context=context,
    )
    _print_result("Scenario 1b: calendar.create_event", result, receipts_path)

    # 2) Email draft: create_draft.
    result = control.call_tool(
        "email",
        "create_draft",
        args={"to": "user@example.com", "subject": "Hello", "body": "Draft body"},
        context=context,
    )
    _print_result("Scenario 2: email.create_draft", result, receipts_path)

    # 3) Malicious prompt simulation.
    result = control.call_tool(
        "email",
        "search",
        args={"query": "dump all invoices"},
        context=context,
    )
    _print_result("Scenario 3: email.search (malicious)", result, receipts_path)

    # 4) Filesystem write_file.
    result = control.call_tool(
        "files",
        "write_file",
        args={"path": "demo.txt", "content": "hello"},
        context=context,
    )
    _print_result("Scenario 4: files.write_file", result, receipts_path)


@app.command()
def approve(
    input_file: Optional[str] = typer.Option(
        None, "--input-file", help="Path to ApprovalRequest JSON."
    ),
) -> None:
    """Generate an approval_token from ApprovalRequest JSON."""
    secret = _ensure_secret()
    approval_json = _read_input(input_file)
    approval_request = ApprovalRequest.model_validate(approval_json)
    gate = ApprovalGate(secret=secret.encode("utf-8"))
    token = gate.sign(approval_request)
    typer.echo(json.dumps(token.model_dump(), indent=2, sort_keys=True))
    typer.echo(
        'Paste this JSON into context.policy_state["approval_token"] and re-run.'
    )


def _read_input(input_file: Optional[str]) -> Dict[str, Any]:
    """Read JSON data from a file path or stdin."""
    if input_file:
        data = _read_file(input_file)
    else:
        if sys.stdin.isatty():
            raise typer.BadParameter("Provide --input-file or pipe JSON via stdin.")
        data = sys.stdin.read()
    try:
        return json.loads(data)
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(f"Invalid JSON: {exc}") from exc


def _read_file(path: str) -> str:
    """Return file contents as text."""
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


if __name__ == "__main__":
    app()
