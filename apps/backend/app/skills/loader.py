from __future__ import annotations

from pathlib import Path

from app.skills.models import (
    ResolvedSkill,
    SkillDefinition,
    SkillEntryConfig,
    SkillOrigin,
    SkillResolution,
)
from app.skills.parser import SkillParseError, parse_skill_document

_ORIGIN_PRIORITY: dict[SkillOrigin, int] = {
    "bundled": 0,
    "user-local": 1,
    "workspace": 2,
}


def resolve_skills(
    *,
    bundled_root: Path,
    user_root: Path,
    workspace_root: Path,
    os_name: str,
    available_tools: set[str],
    available_env: dict[str, str],
    config_by_key: dict[str, SkillEntryConfig],
) -> SkillResolution:
    discovered = _discover_precedence_winners(
        [
            ("bundled", bundled_root),
            ("user-local", user_root),
            ("workspace", workspace_root),
        ]
    )
    items = [
        _resolve_skill(
            definition=definition,
            os_name=os_name,
            available_tools=available_tools,
            available_env=available_env,
            entry_config=config_by_key.get(definition.key, SkillEntryConfig()),
        )
        for definition in sorted(discovered.values(), key=lambda item: item.key)
    ]
    selected = [item for item in items if item.selected]
    return SkillResolution(strategy="all_eligible", items=items, selected=selected)


def _discover_precedence_winners(
    roots: list[tuple[SkillOrigin, Path]],
) -> dict[str, SkillDefinition]:
    chosen: dict[str, SkillDefinition] = {}

    for origin, root in roots:
        for definition in _discover_root(origin, root):
            current = chosen.get(definition.key)
            if current is None:
                chosen[definition.key] = definition
                continue
            current_priority = _ORIGIN_PRIORITY[current.origin]
            candidate_priority = _ORIGIN_PRIORITY[definition.origin]
            if candidate_priority > current_priority:
                chosen[definition.key] = definition
                continue
            if (
                candidate_priority == current_priority
                and definition.source_path < current.source_path
            ):
                chosen[definition.key] = definition

    return chosen


def _discover_root(origin: SkillOrigin, root: Path) -> list[SkillDefinition]:
    if not root.exists() or not root.is_dir():
        return []

    resolved_root = root.resolve()
    discovered: list[SkillDefinition] = []
    for entry in sorted(root.iterdir(), key=lambda item: item.name.lower()):
        if not entry.is_dir():
            continue
        candidate = entry / "SKILL.md"
        if not candidate.exists() or not candidate.is_file():
            continue
        resolved_candidate = candidate.resolve()
        if not _is_within_root(resolved_candidate, resolved_root):
            continue
        try:
            discovered.append(parse_skill_document(resolved_candidate, origin=origin))
        except SkillParseError:
            continue
    return discovered


def _resolve_skill(
    *,
    definition: SkillDefinition,
    os_name: str,
    available_tools: set[str],
    available_env: dict[str, str],
    entry_config: SkillEntryConfig,
) -> ResolvedSkill:
    blocked_reasons: list[str] = []
    effective_enabled = (
        entry_config.enabled
        if entry_config.enabled is not None
        else definition.enabled_by_default
    )
    if not effective_enabled:
        blocked_reasons.append("disabled")

    forkclaw_metadata = definition.metadata.get("forkclaw")
    if not isinstance(forkclaw_metadata, dict):
        forkclaw_metadata = {}

    supported_os = _normalize_string_list(forkclaw_metadata.get("os"))
    if supported_os and os_name.lower() not in supported_os:
        blocked_reasons.append("unsupported_os")

    requires = forkclaw_metadata.get("requires")
    if not isinstance(requires, dict):
        requires = {}
    required_tools = _normalize_string_list(requires.get("tools"))
    missing_tools = [tool for tool in required_tools if tool not in available_tools]
    if missing_tools:
        blocked_reasons.append("missing_tools")

    effective_env = {
        **{key: value for key, value in available_env.items() if value},
        **{key: value for key, value in entry_config.env.items() if value},
    }
    required_env = _normalize_string_list(requires.get("env"))
    missing_env = [name for name in required_env if not effective_env.get(name)]
    if missing_env:
        blocked_reasons.append("missing_env")

    eligible = not blocked_reasons
    return ResolvedSkill(
        key=definition.key,
        name=definition.name,
        description=definition.description,
        origin=definition.origin,
        source_path=definition.source_path,
        content=definition.content,
        metadata=definition.metadata,
        enabled=effective_enabled,
        eligible=eligible,
        selected=eligible,
        blocked_reasons=blocked_reasons,
        config=entry_config.config,
        matched_tools=[tool for tool in required_tools if tool in available_tools],
    )


def _normalize_string_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str) and item]
    return []


def _is_within_root(candidate: Path, root: Path) -> bool:
    return candidate == root or candidate.is_relative_to(root)
