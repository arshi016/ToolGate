"""JSONL receipt logger."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from gateway.receipts.schema import ReceiptEvent


class ReceiptLogger:
    """Write receipt events to JSONL with a minimal schema."""

    def __init__(self, secret: bytes, path: str = "./receipts.log") -> None:
        self._secret = secret
        self._path = Path(path)
        if self._path.parent != Path("."):
            self._path.parent.mkdir(parents=True, exist_ok=True)

    def ensure_no_raw_args(self, payload: Dict[str, Any]) -> None:
        """Sanity check that payload contains no raw args or content."""
        # Keep this check in place; tests should exercise it to ensure no raw
        # args or content fields are ever logged.
        forbidden = {"args", "raw_args", "content"}
        if self._contains_forbidden_key(payload, forbidden):
            raise ValueError("Receipt payload contains raw args or content.")

    def log_event(self, event: ReceiptEvent) -> None:
        """Append a receipt event as JSONL."""
        payload = event.model_dump()
        self.ensure_no_raw_args(payload)
        line = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")

    def _contains_forbidden_key(
        self, payload: Dict[str, Any], forbidden: set[str]
    ) -> bool:
        for key, value in payload.items():
            if key in forbidden:
                return True
            if isinstance(value, dict):
                if self._contains_forbidden_key(value, forbidden):
                    return True
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        if self._contains_forbidden_key(item, forbidden):
                            return True
        return False
