from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol


@dataclass(frozen=True)
class KernelIdentity:
    agent_id: str
    slug: str
    name: str
    description: str | None
    identity_text: str


@dataclass(frozen=True)
class KernelSoul:
    soul_text: str
    user_context_text: str
    policy_base_text: str
    model_provider: str | None
    model_name: str | None


@dataclass(frozen=True)
class KernelSkill:
    key: str
    name: str
    description: str
    origin: str
    source_path: str
    content: str
    config: dict[str, Any] | None = None


@dataclass(frozen=True)
class KernelSkillSummary:
    key: str
    name: str
    origin: str
    source_path: str
    selected: bool
    eligible: bool
    blocked_reasons: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class KernelSkillResolution:
    strategy: str
    items: list[KernelSkillSummary] = field(default_factory=list)


@dataclass(frozen=True)
class KernelToolPolicy:
    tool_name: str
    permission_level: str
    approval_required: bool
    workspace_path: str | None


@dataclass(frozen=True)
class KernelMemoryRecallItem:
    memory_id: str
    title: str
    kind: str
    scope: str
    source_kind: str
    source_label: str
    importance: str
    reason: str
    origin_session_id: str | None = None
    origin_subagent_session_id: str | None = None


@dataclass(frozen=True)
class KernelMemoryRecall:
    reason_summary: str
    query_text: str | None = None
    items: list[KernelMemoryRecallItem] = field(default_factory=list)


@dataclass(frozen=True)
class KernelMessage:
    message_id: str
    role: str
    content: str
    sequence_number: int
    created_at: datetime


@dataclass(frozen=True)
class KernelSessionState:
    session_id: str
    conversation_id: str
    title: str
    messages: list[KernelMessage]


@dataclass(frozen=True)
class KernelPromptContextEntry:
    memory_id: str | None = None
    namespace: str | None = None
    memory_key: str | None = None
    layer: str = ""
    reason: str = ""
    content: str = ""


@dataclass(frozen=True)
class KernelPromptContextLayer:
    key: str
    title: str
    budget_chars: int
    used_chars: int
    content: str
    entries: list[KernelPromptContextEntry] = field(default_factory=list)


@dataclass(frozen=True)
class KernelPromptContext:
    layers: list[KernelPromptContextLayer] = field(default_factory=list)
    included: list[KernelPromptContextEntry] = field(default_factory=list)
    excluded: list[KernelPromptContextEntry] = field(default_factory=list)


@dataclass(frozen=True)
class KernelRuntime:
    mode: str
    task_id: str
    task_run_id: str
    trigger_message_id: str | None
    skill_resolution: KernelSkillResolution
    settings: dict[str, str]
    started_at: datetime
    environment_overlay: dict[str, str] = field(default_factory=dict, repr=False)


@dataclass(frozen=True)
class KernelExecutionRequest:
    identity: KernelIdentity
    soul: KernelSoul
    skills: list[KernelSkill]
    tools: list[KernelToolPolicy]
    session: KernelSessionState
    runtime: KernelRuntime
    input_text: str
    prompt_context: KernelPromptContext = field(default_factory=KernelPromptContext)
    memory_recall: KernelMemoryRecall | None = None


@dataclass(frozen=True)
class KernelExecutionResult:
    status: str
    output_text: str
    finish_reason: str
    kernel_name: str
    model_name: str | None = None
    tools_used: list[str] = field(default_factory=list)
    raw_payload: str | None = None
    pending_approval_id: str | None = None
    pending_tool_call_id: str | None = None


class AgentKernelPort(Protocol):
    async def execute(self, request: KernelExecutionRequest) -> KernelExecutionResult:
        """Run a single kernel execution and return the normalized result."""

    async def resume_after_tool(
        self,
        request: KernelExecutionRequest,
        *,
        tool_name: str,
        tool_call_id: str,
        tool_arguments: dict[str, object] | None = None,
        tool_output: str,
    ) -> KernelExecutionResult:
        """Resume a paused execution after a tool result is available."""
