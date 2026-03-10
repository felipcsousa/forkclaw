from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.tools.base import ToolGroup

ToolPolicyProfileId = Literal["minimal", "coding", "research", "full"]
ToolPermissionLevel = Literal["deny", "ask", "allow"]


@dataclass(frozen=True)
class ToolPolicyProfile:
    id: ToolPolicyProfileId
    label: str
    description: str
    defaults: dict[ToolGroup, ToolPermissionLevel]


_PROFILES: dict[ToolPolicyProfileId, ToolPolicyProfile] = {
    "minimal": ToolPolicyProfile(
        id="minimal",
        label="Minimal",
        description="Conservative local-first defaults with web access disabled.",
        defaults={
            "group:fs": "ask",
            "group:runtime": "ask",
            "group:web": "deny",
            "group:sessions": "ask",
            "group:memory": "ask",
            "group:automation": "ask",
        },
    ),
    "coding": ToolPolicyProfile(
        id="coding",
        label="Coding",
        description="Filesystem-oriented profile with web access available.",
        defaults={
            "group:fs": "ask",
            "group:runtime": "ask",
            "group:web": "allow",
            "group:sessions": "ask",
            "group:memory": "ask",
            "group:automation": "ask",
        },
    ),
    "research": ToolPolicyProfile(
        id="research",
        label="Research",
        description="Research profile with web access enabled by default.",
        defaults={
            "group:fs": "ask",
            "group:runtime": "ask",
            "group:web": "allow",
            "group:sessions": "ask",
            "group:memory": "allow",
            "group:automation": "ask",
        },
    ),
    "full": ToolPolicyProfile(
        id="full",
        label="Full",
        description="Broad local execution profile with permissive defaults.",
        defaults={
            "group:fs": "allow",
            "group:runtime": "allow",
            "group:web": "allow",
            "group:sessions": "allow",
            "group:memory": "allow",
            "group:automation": "allow",
        },
    ),
}


def list_tool_policy_profiles() -> list[ToolPolicyProfile]:
    return [_PROFILES[profile_id] for profile_id in ("minimal", "coding", "research", "full")]


def get_tool_policy_profile(profile_id: ToolPolicyProfileId | str) -> ToolPolicyProfile:
    try:
        return _PROFILES[profile_id]  # type: ignore[index]
    except KeyError as exc:
        msg = f"Unknown tool policy profile: {profile_id}"
        raise ValueError(msg) from exc


def resolve_effective_permission_level(
    *,
    profile_id: ToolPolicyProfileId | str,
    tool_group: ToolGroup,
    override_level: ToolPermissionLevel | None,
) -> ToolPermissionLevel:
    if override_level is not None:
        return override_level
    profile = get_tool_policy_profile(profile_id)
    return profile.defaults[tool_group]
