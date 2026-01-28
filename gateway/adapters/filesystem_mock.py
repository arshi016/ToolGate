"""Deterministic mock filesystem adapter."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from gateway.core.types import (
    ActionType,
    ToolError,
    ToolErrorType,
    ToolRequest,
    ToolResult,
    ToolSpec,
)


class FileSystemMockAdapter:
    """Filesystem adapter backed by a deterministic local folder."""

    def __init__(self, base_dir: str | Path = "./mock_fs") -> None:
        self._base_dir = Path(base_dir).resolve()
        self._base_dir.mkdir(parents=True, exist_ok=True)

    def spec(self) -> ToolSpec:
        """Return the tool specification for the filesystem adapter."""
        return ToolSpec(
            tool_name="files",
            description="Deterministic mock filesystem adapter.",
            actions={
                "list_dir": ActionType.READ,
                "read_file": ActionType.READ,
                "write_file": ActionType.WRITE,
                "delete_file": ActionType.WRITE,
            },
            sensitive_arg_keys=["content"],
            read_scopes=["metadata_only", "full_content"],
            default_read_scope="metadata_only",
        )

    def supports_scope(self, scope: str) -> bool:
        """Return True if the scope is supported."""
        return scope in self.spec().read_scopes

    def execute(self, request: ToolRequest, scope: Optional[str]) -> ToolResult:
        """Dispatch the requested action."""
        if request.tool_action == "list_dir":
            return self._list_dir(request.args)
        if request.tool_action == "read_file":
            return self._read_file(request.args, scope)
        if request.tool_action == "write_file":
            return self._write_file(request.args)
        if request.tool_action == "delete_file":
            return self._delete_file(request.args)
        return ToolResult(
            ok=False,
            error=ToolError(
                error_type=ToolErrorType.TOOL_EXECUTION_ERROR,
                human_message="Unknown action.",
                agent_guidance="Verify the tool_action.",
                details={"tool_action": request.tool_action},
            ),
        )

    def _list_dir(self, args: Dict[str, Any]) -> ToolResult:
        """List entries in a directory."""
        try:
            target = self._resolve_path(args.get("path", "."))
        except ValueError as exc:
            return self._path_error(str(exc))
        if not target.exists() or not target.is_dir():
            return self._path_error("Directory not found.")
        entries = sorted(path.name for path in target.iterdir())
        return ToolResult(
            ok=True, data={"path": self._relative(target), "entries": entries}
        )

    def _read_file(self, args: Dict[str, Any], scope: Optional[str]) -> ToolResult:
        """Read a file with the requested scope."""
        scope = scope or self.spec().default_read_scope
        if not self.supports_scope(scope):
            return self._unsupported_scope(scope)
        try:
            target = self._resolve_path(args.get("path"))
        except ValueError as exc:
            return self._path_error(str(exc))
        if not target.exists() or not target.is_file():
            return self._path_error("File not found.")
        if scope == "metadata_only":
            return ToolResult(
                ok=True,
                data={"path": self._relative(target), "size": target.stat().st_size},
            )
        content = target.read_text(encoding="utf-8")
        return ToolResult(
            ok=True, data={"path": self._relative(target), "content": content}
        )

    def _write_file(self, args: Dict[str, Any]) -> ToolResult:
        """Write content to a file in the mock filesystem."""
        try:
            target = self._resolve_path(args.get("path"))
        except ValueError as exc:
            return self._path_error(str(exc))
        content = args.get("content", "")
        if content is None:
            content = ""
        if not isinstance(content, str):
            content = str(content)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return ToolResult(
            ok=True,
            data={"path": self._relative(target), "bytes_written": len(content)},
        )

    def _delete_file(self, args: Dict[str, Any]) -> ToolResult:
        """Delete a file in the mock filesystem."""
        try:
            target = self._resolve_path(args.get("path"))
        except ValueError as exc:
            return self._path_error(str(exc))
        if not target.exists() or not target.is_file():
            return self._path_error("File not found.")
        target.unlink()
        return ToolResult(
            ok=True, data={"path": self._relative(target), "status": "deleted"}
        )

    def _resolve_path(self, path_value: Any) -> Path:
        """Resolve a user-supplied path within the base directory."""
        if not path_value:
            raise ValueError("Path is required.")
        path = Path(str(path_value))
        if path.is_absolute():
            raise ValueError("Absolute paths are not allowed.")
        resolved = (self._base_dir / path).resolve()
        if resolved != self._base_dir and self._base_dir not in resolved.parents:
            raise ValueError("Path escapes base directory.")
        return resolved

    def _relative(self, path: Path) -> str:
        """Return path relative to the adapter base directory."""
        return str(path.relative_to(self._base_dir))

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

    def _path_error(self, message: str) -> ToolResult:
        """Return an error for invalid filesystem paths."""
        return ToolResult(
            ok=False,
            error=ToolError(
                error_type=ToolErrorType.TOOL_EXECUTION_ERROR,
                human_message=message,
                agent_guidance="Verify the path and retry.",
            ),
        )
