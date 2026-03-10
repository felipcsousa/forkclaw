from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

SkillOrigin = Literal["bundled", "user-local", "workspace"]


@dataclass(frozen=True)
class SkillDefinition:
    key: str
    name: str
    description: str
    origin: SkillOrigin
    source_path: str
    content: str
    metadata: dict[str, Any]
    enabled_by_default: bool = True


@dataclass(frozen=True)
class SkillEntryConfig:
    enabled: bool | None = None
    config: dict[str, Any] | None = None
    env: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ResolvedSkill:
    key: str
    name: str
    description: str
    origin: SkillOrigin
    source_path: str
    content: str
    metadata: dict[str, Any]
    enabled: bool
    eligible: bool
    selected: bool
    blocked_reasons: list[str]
    config: dict[str, Any] | None = None
    matched_tools: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SkillResolution:
    strategy: str
    items: list[ResolvedSkill]
    selected: list[ResolvedSkill]
