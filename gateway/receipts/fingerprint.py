"""Fingerprint helpers for receipt logging."""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any, Dict


def canonicalize_args(args: Dict[str, Any]) -> str:
    """Return stable JSON for args using sorted keys and compact separators."""
    return json.dumps(args, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def hmac_fingerprint(secret: bytes, canonical_args: str) -> str:
    """Return a hex digest HMAC fingerprint of canonical args."""
    return hmac.new(secret, canonical_args.encode("utf-8"), hashlib.sha256).hexdigest()
