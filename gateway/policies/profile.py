"""Policy profile models and loader."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import yaml
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, StrictStr


class ToolPolicy(BaseModel):
    """Per-tool policy settings."""

    model_config = ConfigDict(extra="forbid", strict=True)

    read_default_scope: StrictStr = ""
    safe_writes_without_confirm: List[StrictStr] = Field(default_factory=list)
    always_confirm_writes: List[StrictStr] = Field(default_factory=list)
    always_confirm_reads_if_broad: StrictBool = True


class GlobalPolicy(BaseModel):
    """Global policy thresholds for read breadth."""

    model_config = ConfigDict(extra="forbid", strict=True)

    broad_read_range_days_threshold: StrictInt = 30
    broad_read_keywords: List[StrictStr] = Field(default_factory=list)


class PolicyProfile(BaseModel):
    """Policy profile parsed from YAML."""

    model_config = ConfigDict(extra="forbid", strict=True)

    profile: StrictStr
    tools: Dict[StrictStr, ToolPolicy] = Field(default_factory=dict)
    global_policy: GlobalPolicy = Field(default_factory=GlobalPolicy, alias="global")


def load_profile(path: str) -> PolicyProfile:
    """Load a policy profile from YAML with defaults for missing fields."""
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return PolicyProfile.model_validate(raw)
