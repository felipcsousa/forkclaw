from __future__ import annotations

from app.adapters.kernel.nanobot import NanobotKernelAdapter
from app.kernel.contracts import AgentKernelPort
from app.tools.base import ToolExecutionPort


def create_agent_kernel(tool_executor: ToolExecutionPort | None = None) -> AgentKernelPort:
    return NanobotKernelAdapter(tool_executor=tool_executor)
