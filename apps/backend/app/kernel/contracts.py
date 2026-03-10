from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol


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
    name: str
    content: str
    source_document_id: str


@dataclass(frozen=True)
class KernelToolPolicy:
    tool_name: str
    permission_level: str
    approval_required: bool
    workspace_path: str | None


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
    title: str
    messages: list[KernelMessage]


@dataclass(frozen=True)
class KernelRuntime:
    mode: str
    task_id: str
    task_run_id: str
    trigger_message_id: str | None
    settings: dict[str, str]
    started_at: datetime


@dataclass(frozen=True)
class KernelExecutionRequest:
    identity: KernelIdentity
    soul: KernelSoul
    skills: list[KernelSkill]
    tools: list[KernelToolPolicy]
    session: KernelSessionState
    runtime: KernelRuntime
    input_text: str


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
        tool_output: str,
    ) -> KernelExecutionResult:
        """Resume a paused execution after a tool result is available."""
