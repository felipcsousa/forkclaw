from __future__ import annotations

from dataclasses import dataclass

from app.models.entities import ToolPermission

SUBAGENT_TOOLSET_ALIASES = {
    "group:fs": "file",
    "group:web": "web",
    "group:runtime": "terminal",
}

SUBAGENT_TOOLSET_MAPPING = {
    "file": ["list_files", "read_file", "write_file", "edit_file"],
    "terminal": ["shell_exec"],
    "web": ["web_search", "web_fetch"],
    "local_product_tools": [],
}


@dataclass(frozen=True)
class SubagentToolScopeResolution:
    requested_toolsets: list[str]
    effective_permissions: list[ToolPermission]
    allowed_tool_names: list[str]
    denied_tool_names: list[str]
    empty_groups: list[str]


def resolve_subagent_tool_scope(
    *,
    requested_toolsets: list[str],
    tool_permissions: list[ToolPermission],
) -> SubagentToolScopeResolution:
    normalized_toolsets = _normalize_requested_toolsets(requested_toolsets)
    requested_tool_names = []
    empty_groups = []
    for toolset in normalized_toolsets:
        mapped = SUBAGENT_TOOLSET_MAPPING[toolset]
        if not mapped:
            empty_groups.append(toolset)
            continue
        for tool_name in mapped:
            if tool_name not in requested_tool_names:
                requested_tool_names.append(tool_name)

    effective_permissions = [
        permission
        for permission in sorted(tool_permissions, key=lambda item: item.tool_name)
        if permission.status == "active" and permission.tool_name in requested_tool_names
    ]
    allowed_tool_names = [
        permission.tool_name
        for permission in effective_permissions
        if permission.permission_level != "deny"
    ]
    denied_tool_names = [
        permission.tool_name
        for permission in effective_permissions
        if permission.permission_level == "deny"
    ]

    return SubagentToolScopeResolution(
        requested_toolsets=normalized_toolsets,
        effective_permissions=effective_permissions,
        allowed_tool_names=allowed_tool_names,
        denied_tool_names=denied_tool_names,
        empty_groups=empty_groups,
    )


def _normalize_requested_toolsets(requested_toolsets: list[str]) -> list[str]:
    normalized: list[str] = []
    for raw_toolset in requested_toolsets:
        candidate = SUBAGENT_TOOLSET_ALIASES.get(raw_toolset.strip(), raw_toolset.strip())
        if not candidate:
            continue
        if candidate not in SUBAGENT_TOOLSET_MAPPING:
            supported = ", ".join(sorted(SUBAGENT_TOOLSET_MAPPING))
            msg = f"Unsupported toolset: {raw_toolset}. Supported toolsets: {supported}."
            raise ValueError(msg)
        if candidate not in normalized:
            normalized.append(candidate)
    return normalized
