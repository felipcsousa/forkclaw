from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.tools.base import ToolDescriptor, ToolGroup, ToolRisk, ToolStatus
from app.tools.registry import build_tool_registry

GROUP_LABELS: dict[ToolGroup, str] = {
    "group:fs": "Filesystem",
    "group:runtime": "Runtime",
    "group:web": "Web",
    "group:sessions": "Sessions",
    "group:memory": "Memory",
    "group:automation": "Automation",
}


@dataclass(frozen=True)
class ToolCatalogEntry:
    id: str
    label: str
    description: str
    group: ToolGroup
    group_label: str
    risk: ToolRisk
    status: ToolStatus
    input_schema: dict[str, Any]
    output_schema: dict[str, Any] | None
    requires_workspace: bool


def catalog_entry_from_descriptor(descriptor: ToolDescriptor) -> ToolCatalogEntry:
    return ToolCatalogEntry(
        id=descriptor.name,
        label=descriptor.label,
        description=descriptor.description,
        group=descriptor.group,
        group_label=GROUP_LABELS[descriptor.group],
        risk=descriptor.risk,
        status=descriptor.status,
        input_schema=descriptor.parameters,
        output_schema=descriptor.output_schema,
        requires_workspace=descriptor.requires_workspace,
    )


def build_tool_catalog() -> list[ToolCatalogEntry]:
    registry = build_tool_registry()
    items = [catalog_entry_from_descriptor(tool.descriptor) for tool in registry.list()]
    return sorted(items, key=lambda item: item.id)
