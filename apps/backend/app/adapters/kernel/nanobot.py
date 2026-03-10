from __future__ import annotations

import json
import shlex
from typing import Any
from uuid import uuid4

from nanobot.providers.base import LLMProvider, LLMResponse, ToolCallRequest

from app.adapters.kernel.provider_factory import (
    build_provider,
    missing_api_key_message,
    resolve_provider_api_key,
    resolve_provider_name,
)
from app.kernel.contracts import (
    AgentKernelPort,
    KernelExecutionRequest,
    KernelExecutionResult,
    KernelMessage,
    KernelSkill,
    KernelToolPolicy,
)
from app.tools.base import ToolExecutionPort


class ProductEchoLLMProvider(LLMProvider):
    def __init__(
        self,
        *,
        agent_name: str,
        identity_text: str,
        soul_text: str,
        user_context_text: str,
        policy_base_text: str,
    ):
        super().__init__(api_key=None, api_base=None)
        self.agent_name = agent_name
        self.identity_text = identity_text
        self.soul_text = soul_text
        self.user_context_text = user_context_text
        self.policy_base_text = policy_base_text

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        reasoning_effort: str | None = None,
    ) -> LLMResponse:
        del tools, model, max_tokens, temperature, reasoning_effort

        latest_user = ""
        for message in reversed(messages):
            if message.get("role") == "user":
                latest_user = str(message.get("content", "")).strip()
                break
            if message.get("role") == "tool":
                tool_name = str(message.get("name", "tool"))
                tool_output = str(message.get("content", "")).strip()
                return LLMResponse(
                    content=f"Tool result from {tool_name}:\n{tool_output}".strip(),
                    finish_reason="stop",
                    usage={},
                )

        requested_tool = _parse_tool_directive(latest_user)
        if requested_tool is not None:
            return LLMResponse(
                content=None,
                tool_calls=[requested_tool],
                finish_reason="tool_calls",
                usage={},
            )

        return LLMResponse(
            content=(
                f"Agent: {self.agent_name}\n"
                f"Identity: {self._excerpt(self.identity_text)}\n"
                f"Soul: {self._excerpt(self.soul_text)}\n"
                f"User Context: {self._excerpt(self.user_context_text)}\n"
                f"Policy: {self._excerpt(self.policy_base_text)}\n"
                f"Reply: {latest_user}"
            ).strip(),
            finish_reason="stop",
            usage={},
        )

    def get_default_model(self) -> str:
        return "product-echo/simple"

    @staticmethod
    def _excerpt(value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            return "(none)"
        if len(normalized) <= 96:
            return normalized
        return f"{normalized[:93]}..."


class NanobotPromptBuilder:
    @staticmethod
    def build_system_prompt(request: KernelExecutionRequest) -> str:
        parts = [
            (
                f"# Identity\nName: {request.identity.name}\nSlug: {request.identity.slug}\n"
                f"Description: {request.identity.description or '(none)'}\n"
                f"Profile: {request.identity.identity_text or '(none)'}"
            ),
            f"# Soul\n{request.soul.soul_text or '(none)'}",
            f"# User Context\n{request.soul.user_context_text or '(none)'}",
            f"# Base Policy\n{request.soul.policy_base_text or '(none)'}",
            NanobotPromptBuilder._skills_section(request.skills),
            NanobotPromptBuilder._tools_section(request.tools),
            NanobotPromptBuilder._runtime_section(request),
        ]
        return "\n\n".join(part for part in parts if part)

    @staticmethod
    def build_messages(request: KernelExecutionRequest) -> list[dict[str, Any]]:
        history = [
            NanobotPromptBuilder._message_to_provider_payload(message)
            for message in request.session.messages
        ]
        return [
            {"role": "system", "content": NanobotPromptBuilder.build_system_prompt(request)},
            *history,
            {"role": "user", "content": request.input_text},
        ]

    @staticmethod
    def _message_to_provider_payload(message: KernelMessage) -> dict[str, Any]:
        allowed_roles = {"system", "user", "assistant", "tool"}
        role = message.role if message.role in allowed_roles else "assistant"
        payload: dict[str, Any] = {"role": role, "content": message.content}
        if role == "tool":
            payload["name"] = "product_tool"
            payload["tool_call_id"] = message.message_id
        return payload

    @staticmethod
    def _skills_section(skills: list[KernelSkill]) -> str:
        if not skills:
            return "# Skills\nNo product skills are active for this execution."

        lines = ["# Skills"]
        for skill in skills:
            lines.append(f"## {skill.name}\n{skill.content}")
        return "\n\n".join(lines)

    @staticmethod
    def _tools_section(tools: list[KernelToolPolicy]) -> str:
        if not tools:
            return "# Tools\nNo product tools are enabled for this execution."

        lines = ["# Tool Policies"]
        for tool in tools:
            lines.append(
                f"- {tool.tool_name}: permission={tool.permission_level}, "
                f"approval_required={str(tool.approval_required).lower()}, "
                f"workspace={tool.workspace_path or '(none)'}"
            )
        lines.append("Simple mode does not execute tools yet; these policies are contextual only.")
        return "\n".join(lines)

    @staticmethod
    def _runtime_section(request: KernelExecutionRequest) -> str:
        settings = "\n".join(
            f"- {key}: {value}" for key, value in sorted(request.runtime.settings.items())
        )
        return (
            "# Runtime\n"
            f"Mode: {request.runtime.mode}\n"
            f"Task ID: {request.runtime.task_id}\n"
            f"Task Run ID: {request.runtime.task_run_id}\n"
            f"Started At: {request.runtime.started_at.isoformat()}\n"
            f"Session ID: {request.session.session_id}\n"
            "## Settings\n"
            f"{settings or '- (none)'}"
        )


class NanobotKernelAdapter(AgentKernelPort):
    kernel_name = "nanobot"

    def __init__(self, tool_executor: ToolExecutionPort | None = None):
        self.tool_executor = tool_executor

    async def execute(self, request: KernelExecutionRequest) -> KernelExecutionResult:
        resolved_provider = self._resolve_provider(request)
        provider = resolved_provider.provider
        model_name = request.soul.model_name or provider.get_default_model()
        messages = NanobotPromptBuilder.build_messages(request)
        return await self._execute_messages(
            request=request,
            tool_format=resolved_provider.tool_format,
            provider=provider,
            model_name=model_name,
            messages=messages,
        )

    async def resume_after_tool(
        self,
        request: KernelExecutionRequest,
        *,
        tool_name: str,
        tool_call_id: str,
        tool_arguments: dict[str, object] | None = None,
        tool_output: str,
    ) -> KernelExecutionResult:
        resolved_provider = self._resolve_provider(request)
        provider = resolved_provider.provider
        model_name = request.soul.model_name or provider.get_default_model()
        messages = [
            *NanobotPromptBuilder.build_messages(request),
            _assistant_tool_call_message(
                tool_name=tool_name,
                tool_call_id=tool_call_id,
                arguments=tool_arguments or {},
            ),
            {
                "role": "tool",
                "name": tool_name,
                "tool_call_id": tool_call_id,
                "content": tool_output,
            },
        ]
        return await self._execute_messages(
            request=request,
            tool_format=resolved_provider.tool_format,
            provider=provider,
            model_name=model_name,
            messages=messages,
            available_tools=None,
        )

    async def _execute_messages(
        self,
        *,
        request: KernelExecutionRequest,
        tool_format: str,
        provider: LLMProvider,
        model_name: str,
        messages: list[dict[str, Any]],
        available_tools: list[dict[str, Any]] | None = None,
    ) -> KernelExecutionResult:
        available_tools = (
            self.tool_executor.describe_tools(
                [tool.tool_name for tool in request.tools],
                format=tool_format,
            )
            if self.tool_executor is not None
            and available_tools is None
            else None
        )
        response = await provider.chat(
            messages=messages,
            tools=available_tools,
            model=model_name,
            max_tokens=1024,
            temperature=0.2,
            reasoning_effort=None,
        )
        tool_calls = response.tool_calls or []
        tools_used = [tool_call.name for tool_call in tool_calls]
        output_text = (response.content or "").strip()
        raw_payload_data: dict[str, Any] = {
            "initial_finish_reason": response.finish_reason,
            "usage": response.usage,
            "tools_used": tools_used,
            "tool_calls": [
                {
                    "id": tool_call.id,
                    "name": tool_call.name,
                    "arguments": tool_call.arguments,
                }
                for tool_call in tool_calls
            ],
        }
        execution_status = "completed"
        pending_approval_id: str | None = None
        pending_tool_call_id: str | None = None
        max_iterations = self._resolve_max_iterations(request)

        if tool_calls and self.tool_executor is not None:
            tool_messages = []
            tool_outcomes = []
            for tool_call in tool_calls:
                outcome = self.tool_executor.execute_tool_call(
                    request=request,
                    tool_call=tool_call,
                )
                tool_outcomes.append(
                    {
                        "tool_call_id": tool_call.id,
                        "tool_name": outcome.tool_name,
                        "arguments": tool_call.arguments,
                        "status": outcome.status,
                        "approval_id": outcome.approval_id,
                        "error_message": outcome.error_message,
                    }
                )
                if outcome.status == "awaiting_approval" and pending_approval_id is None:
                    execution_status = "awaiting_approval"
                    pending_approval_id = outcome.approval_id
                    pending_tool_call_id = outcome.tool_call_id
                elif outcome.status == "failed":
                    execution_status = "failed"
                tool_messages.append(
                    _assistant_tool_call_message(
                        tool_name=tool_call.name,
                        tool_call_id=tool_call.id,
                        arguments=tool_call.arguments,
                    )
                )
                tool_messages.append(
                    {
                        "role": "tool",
                        "name": tool_call.name,
                        "tool_call_id": tool_call.id,
                        "content": outcome.output_text,
                    }
                )

            raw_payload_data["tool_outcomes"] = tool_outcomes
            if max_iterations > 1:
                raw_payload_data["follow_up_messages"] = tool_messages
                follow_up = await provider.chat(
                    messages=[*messages, *tool_messages],
                    tools=None,
                    model=model_name,
                    max_tokens=1024,
                    temperature=0.2,
                    reasoning_effort=None,
                )
                output_text = (follow_up.content or "").strip()
                raw_payload_data["follow_up_finish_reason"] = follow_up.finish_reason
                raw_payload_data["follow_up_usage"] = follow_up.usage
            elif tool_messages:
                output_text = str(tool_messages[-1]["content"]).strip()
                raw_payload_data["follow_up_skipped"] = "max_iterations_reached"

        if not output_text and tools_used:
            output_text = (
                "Model requested tools but simple mode does not execute them: "
                + ", ".join(tools_used)
            )
        if not output_text:
            output_text = "The kernel returned an empty response."

        raw_payload = json.dumps(raw_payload_data, ensure_ascii=False)

        return KernelExecutionResult(
            status=execution_status,
            output_text=output_text,
            finish_reason=response.finish_reason,
            kernel_name=self.kernel_name,
            model_name=model_name,
            tools_used=tools_used,
            raw_payload=raw_payload,
            pending_approval_id=pending_approval_id,
            pending_tool_call_id=pending_tool_call_id,
        )

    def _resolve_provider(self, request: KernelExecutionRequest):
        provider_name = resolve_provider_name(request.soul.model_provider)
        model_name = (request.soul.model_name or "").strip()
        if provider_name and provider_name != "product_echo":
            if not model_name:
                msg = f"Provider `{provider_name}` is configured without a model name."
                raise ValueError(msg)
        return build_provider(
            provider_name=provider_name,
            model_name=model_name or ProductEchoLLMProvider(
                agent_name=request.identity.name,
                identity_text=request.identity.identity_text,
                soul_text=request.soul.soul_text,
                user_context_text=request.soul.user_context_text,
                policy_base_text=request.soul.policy_base_text,
            ).get_default_model(),
            product_echo_factory=lambda: ProductEchoLLMProvider(
                agent_name=request.identity.name,
                identity_text=request.identity.identity_text,
                soul_text=request.soul.soul_text,
                user_context_text=request.soul.user_context_text,
                policy_base_text=request.soul.policy_base_text,
            ),
        )

    def _build_provider(self, request: KernelExecutionRequest) -> LLMProvider:
        return self._resolve_provider(request).provider

    @staticmethod
    def _resolve_api_key(provider_name: str) -> str | None:
        return resolve_provider_api_key(provider_name)

    @staticmethod
    def _missing_api_key_message(provider_name: str) -> str:
        return missing_api_key_message(provider_name)

    @staticmethod
    def _resolve_max_iterations(request: KernelExecutionRequest) -> int:
        raw_value = request.runtime.settings.get("runtime.max_iterations_per_execution")
        if raw_value is None:
            return 2
        try:
            return max(int(raw_value), 1)
        except ValueError:
            return 2


def _assistant_tool_call_message(
    *,
    tool_name: str,
    tool_call_id: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    return {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": tool_call_id,
                "type": "function",
                "function": {
                    "name": tool_name,
                    "arguments": json.dumps(arguments, ensure_ascii=False),
                },
            }
        ],
    }


def _parse_tool_directive(latest_user: str) -> ToolCallRequest | None:
    if not latest_user.startswith("tool:"):
        return None

    tokens = shlex.split(latest_user)
    if not tokens:
        return None

    tool_name = tokens[0].split(":", 1)[1].strip()
    arguments: dict[str, Any] = {}
    for token in tokens[1:]:
        if "=" not in token:
            continue
        key, raw_value = token.split("=", 1)
        value: Any = raw_value
        if raw_value.lower() in {"true", "false"}:
            value = raw_value.lower() == "true"
        arguments[key] = value

    return ToolCallRequest(
        id=str(uuid4()),
        name=tool_name,
        arguments=arguments,
    )
