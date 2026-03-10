from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Mapping, Protocol

from nanobot.providers.base import ToolCallRequest

from app.core.provider_catalog import ToolFormat
from app.kernel.contracts import KernelExecutionRequest

ToolGroup = Literal[
    "group:fs",
    "group:runtime",
    "group:web",
    "group:sessions",
    "group:memory",
    "group:automation",
]
ToolRisk = Literal["low", "medium", "high"]
ToolStatus = Literal["enabled", "experimental", "disabled"]


@dataclass(frozen=True)
class ToolDescriptor:
    name: str
    label: str
    description: str
    group: ToolGroup
    risk: ToolRisk
    status: ToolStatus
    parameters: dict[str, Any]
    output_schema: dict[str, Any] | None = None
    requires_workspace: bool = False


class ToolCachePort(Protocol):
    def get_json(self, *, tool_name: str, cache_key: str) -> dict[str, Any] | None:
        """Return a non-expired cached payload for the tool."""

    def set_json(
        self,
        *,
        tool_name: str,
        cache_key: str,
        value: dict[str, Any],
        ttl_seconds: int,
    ) -> None:
        """Persist a cached payload with a time-to-live."""


@dataclass(frozen=True)
class ToolExecutionContext:
    workspace_root: Path
    cache_store: ToolCachePort | None = None
    runtime_settings: Mapping[str, Any] = field(default_factory=dict)

    def resolve_path(self, value: str | None) -> Path:
        raw = Path((value or ".").strip() or ".")
        candidate = raw if raw.is_absolute() else self.workspace_root / raw
        resolved = candidate.resolve()
        if resolved != self.workspace_root and not resolved.is_relative_to(self.workspace_root):
            msg = "Path escapes the configured workspace."
            raise PermissionError(msg)
        return resolved


@dataclass(frozen=True)
class ToolResult:
    output_text: str
    output_data: dict[str, Any] | None = None


@dataclass(frozen=True)
class ToolExecutionOutcome:
    tool_call_id: str
    tool_name: str
    status: str
    output_text: str
    output_data: dict[str, Any] | None = None
    approval_id: str | None = None
    error_message: str | None = None


class LocalTool(Protocol):
    descriptor: ToolDescriptor

    def execute(
        self,
        *,
        context: ToolExecutionContext,
        arguments: dict[str, Any],
    ) -> ToolResult:
        """Execute a local tool inside the configured workspace boundary."""


class ToolExecutionPort(Protocol):
    def describe_tools(
        self,
        tool_names: list[str] | None = None,
        *,
        format: ToolFormat = "openai",
    ) -> list[dict[str, Any]]:
        """Return provider-facing tool schemas."""

    def execute_tool_call(
        self,
        *,
        request: KernelExecutionRequest,
        tool_call: ToolCallRequest,
        approval_override: bool = False,
    ) -> ToolExecutionOutcome:
        """Authorize, persist, and execute a requested local tool."""
