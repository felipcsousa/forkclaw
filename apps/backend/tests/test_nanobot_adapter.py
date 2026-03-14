from __future__ import annotations

import asyncio
import json
from dataclasses import replace
from datetime import UTC, datetime

import httpx
import pytest
from nanobot.providers import LiteLLMProvider

from app.adapters.kernel.kimi_coding import KimiCodingProvider
from app.adapters.kernel.nanobot import NanobotKernelAdapter, NanobotPromptBuilder
from app.adapters.kernel.provider_factory import build_provider
from app.core.config import clear_settings_cache
from app.core.secrets import clear_secret_store_cache, get_secret_store
from app.kernel.contracts import (
    KernelExecutionRequest,
    KernelIdentity,
    KernelMessage,
    KernelPromptContext,
    KernelPromptContextLayer,
    KernelRuntime,
    KernelSessionState,
    KernelSkill,
    KernelSkillResolution,
    KernelSkillSummary,
    KernelSoul,
    KernelToolPolicy,
)
from app.skills.runtime import runtime_env_overlay
from app.tools.base import ToolExecutionOutcome
from app.tools.registry import build_tool_registry


def _build_request(
    *,
    provider: str,
    model_name: str,
    skills: list[KernelSkill] | None = None,
    skill_resolution: KernelSkillResolution | None = None,
    tools: list[KernelToolPolicy] | None = None,
    history: list[KernelMessage] | None = None,
    input_text: str = "hello",
) -> KernelExecutionRequest:
    return KernelExecutionRequest(
        identity=KernelIdentity(
            agent_id="agent-1",
            slug="main",
            name="Primary Agent",
            description="Default agent",
            identity_text="identity",
        ),
        soul=KernelSoul(
            soul_text="soul",
            user_context_text="user",
            policy_base_text="policy",
            model_provider=provider,
            model_name=model_name,
        ),
        skills=skills or [],
        tools=tools or [],
        session=KernelSessionState(
            session_id="session-1",
            conversation_id="conversation-1",
            title="Test",
            messages=history or [],
        ),
        runtime=KernelRuntime(
            mode="simple",
            task_id="task-1",
            task_run_id="run-1",
            trigger_message_id=None,
            skill_resolution=skill_resolution
            or KernelSkillResolution(strategy="all_eligible", items=[]),
            settings={},
            started_at=datetime.now(UTC),
        ),
        prompt_context=KernelPromptContext(),
        input_text=input_text,
    )


def _http_response(payload: dict, *, status_code: int = 200) -> httpx.Response:
    request = httpx.Request("POST", "https://api.kimi.com/coding/v1/messages")
    return httpx.Response(status_code, json=payload, request=request)


def _fake_async_client(calls: list[dict], responses: list[object]):
    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            self.timeout = kwargs.get("timeout")

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url: str, *, headers=None, json=None):
            calls.append(
                {
                    "url": url,
                    "headers": headers,
                    "json": json,
                    "timeout": self.timeout,
                }
            )
            response = responses.pop(0)
            if isinstance(response, Exception):
                raise response
            return response

    return FakeAsyncClient


class FakeToolExecutor:
    def __init__(self):
        self.formats: list[str] = []
        self.calls: list[object] = []

    def describe_tools(self, tool_names=None, *, format="openai"):
        self.formats.append(format)
        if format == "anthropic":
            return [
                {
                    "name": "read_file",
                    "description": "Read a file.",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                        },
                        "required": ["path"],
                    },
                }
            ]
        return [
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "Read a file.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                        },
                        "required": ["path"],
                    },
                },
            }
        ]

    def execute_tool_call(self, *, request, tool_call, approval_override=False):
        del request, approval_override
        self.calls.append(tool_call)
        return ToolExecutionOutcome(
            tool_call_id="persisted-tool-call",
            tool_name=tool_call.name,
            status="completed",
            output_text="file contents",
        )


@pytest.fixture(autouse=True)
def _clear_secret_state(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_SECRET_BACKEND", "memory")
    for key in (
        "NANOBOT_API_KEY",
        "KIMI_CODING_API_KEY",
        "KIMI_API_KEY",
        "OPENAI_API_KEY",
    ):
        monkeypatch.delenv(key, raising=False)
    clear_settings_cache()
    clear_secret_store_cache()
    yield
    clear_settings_cache()
    clear_secret_store_cache()


def test_prompt_builder_renders_sorted_skill_block_with_strategy_and_config() -> None:
    prompt = NanobotPromptBuilder.build_system_prompt(
        _build_request(
            provider="product_echo",
            model_name="product-echo/simple",
            skills=[
                KernelSkill(
                    key="zebra-skill",
                    name="Zebra Skill",
                    description="Later alphabetically.",
                    origin="workspace",
                    source_path="/tmp/zebra/SKILL.md",
                    content="Use zebra behavior.",
                    config=None,
                ),
                KernelSkill(
                    key="alpha-skill",
                    name="Alpha Skill",
                    description="Earlier alphabetically.",
                    origin="bundled",
                    source_path="/tmp/alpha/SKILL.md",
                    content="Use alpha behavior.",
                    config={"mode": "strict"},
                ),
            ],
        )
    )

    alpha_index = prompt.index("## Alpha Skill")
    zebra_index = prompt.index("## Zebra Skill")

    assert "# Skills" in prompt
    assert "Strategy: all_eligible" in prompt
    assert alpha_index < zebra_index
    assert 'Config: {"mode": "strict"}' in prompt


def test_prompt_builder_reports_absence_of_selected_skills_but_keeps_resolution_summary() -> None:
    request = _build_request(
        provider="product_echo",
        model_name="product-echo/simple",
        skill_resolution=KernelSkillResolution(
            strategy="all_eligible",
            items=[
                KernelSkillSummary(
                    key="blocked-skill",
                    name="Blocked Skill",
                    origin="workspace",
                    source_path="/tmp/blocked/SKILL.md",
                    selected=False,
                    eligible=False,
                    blocked_reasons=["missing_env"],
                )
            ],
        ),
    )

    prompt = NanobotPromptBuilder.build_system_prompt(request)

    assert "Strategy: all_eligible" in prompt
    assert "No eligible skills are active for this execution." in prompt


def test_prompt_builder_renders_prompt_context_before_skills() -> None:
    request = replace(
        _build_request(
            provider="product_echo",
            model_name="product-echo/simple",
        ),
        prompt_context=KernelPromptContext(
            layers=[
                KernelPromptContextLayer(
                    key="stable_manual",
                    title="Stable Manual Memory",
                    budget_chars=2000,
                    used_chars=26,
                    content="Remember the manual rule.",
                )
            ]
        ),
    )

    prompt = NanobotPromptBuilder.build_system_prompt(request)

    context_index = prompt.index("# Context")
    skills_index = prompt.index("# Skills")

    assert context_index < skills_index
    assert "## Stable Manual Memory" in prompt
    assert "Remember the manual rule." in prompt


def test_build_provider_uses_native_kimi_provider() -> None:
    get_secret_store().set_provider_api_key("kimi-coding", "keychain-secret")
    adapter = NanobotKernelAdapter()

    provider = adapter._build_provider(_build_request(provider="kimi-coding", model_name="k2p5"))

    assert isinstance(provider, KimiCodingProvider)
    assert provider.get_default_model() == "k2p5"


def test_provider_factory_falls_back_to_existing_providers() -> None:
    get_secret_store().set_provider_api_key("openai", "openai-secret")

    product_echo = object()
    resolved_echo = build_provider(
        provider_name="product_echo",
        model_name="product-echo/simple",
        product_echo_factory=lambda: product_echo,
    )
    resolved_openai = build_provider(
        provider_name="openai",
        model_name="gpt-4o-mini",
        product_echo_factory=lambda: product_echo,
    )

    assert resolved_echo.provider is product_echo
    assert resolved_echo.tool_format == "openai"
    assert isinstance(resolved_openai.provider, LiteLLMProvider)
    assert resolved_openai.tool_format == "openai"


def test_kimi_secret_resolution_prefers_runtime_env_over_keychain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    get_secret_store().set_provider_api_key("kimi-coding", "keychain-secret")
    monkeypatch.setenv("KIMI_CODING_API_KEY", "env-secret")
    monkeypatch.setenv("KIMI_API_KEY", "env-alias-secret")

    assert NanobotKernelAdapter._resolve_api_key("kimi-coding") == "env-secret"


def test_provider_factory_prefers_runtime_overlay_secret_over_keychain() -> None:
    get_secret_store().set_provider_api_key("openai", "keychain-secret")

    with runtime_env_overlay({"OPENAI_API_KEY": "overlay-secret"}):
        resolved_openai = build_provider(
            provider_name="openai",
            model_name="gpt-4o-mini",
            product_echo_factory=lambda: object(),
        )

    assert isinstance(resolved_openai.provider, LiteLLMProvider)
    assert resolved_openai.provider.api_key == "overlay-secret"


def test_provider_factory_falls_back_to_keychain_without_runtime_overlay() -> None:
    get_secret_store().set_provider_api_key("openai", "keychain-secret")

    resolved_openai = build_provider(
        provider_name="openai",
        model_name="gpt-4o-mini",
        product_echo_factory=lambda: object(),
    )

    assert isinstance(resolved_openai.provider, LiteLLMProvider)
    assert resolved_openai.provider.api_key == "keychain-secret"


def test_kimi_secret_resolution_uses_explicit_env_fallbacks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("KIMI_CODING_API_KEY", "env-secret")
    monkeypatch.setenv("KIMI_API_KEY", "env-alias-secret")

    assert NanobotKernelAdapter._resolve_api_key("kimi-coding") == "env-secret"

    monkeypatch.delenv("KIMI_CODING_API_KEY", raising=False)

    assert NanobotKernelAdapter._resolve_api_key("kimi-coding") == "env-alias-secret"


def test_kimi_secret_resolution_normalizes_legacy_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KIMI_API_KEY", "env-alias-secret")

    assert NanobotKernelAdapter._resolve_api_key("kimi-for-coding") == "env-alias-secret"


def test_kimi_missing_api_key_error_is_explicit() -> None:
    adapter = NanobotKernelAdapter()

    with pytest.raises(ValueError) as exc_info:
        adapter._build_provider(_build_request(provider="kimi-coding", model_name="k2p5"))

    message = str(exc_info.value)
    assert "kimi-coding" in message
    assert "KIMI_CODING_API_KEY" in message
    assert "KIMI_API_KEY" in message


def test_tool_registry_describes_anthropic_tools() -> None:
    registry = build_tool_registry()

    tools = registry.describe(["read_file"], format="anthropic")

    assert tools == [
        {
            "name": "read_file",
            "description": "Read a UTF-8 text file inside the configured workspace.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative file path inside the workspace.",
                    }
                },
                "required": ["path"],
                "additionalProperties": False,
            },
        }
    ]


def test_kimi_provider_sends_anthropic_payload_and_parses_text_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict] = []
    responses = [
        _http_response(
            {
                "content": [{"type": "text", "text": "Done"}],
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 12, "output_tokens": 4},
            }
        )
    ]
    monkeypatch.setattr(
        "app.adapters.kernel.kimi_coding.httpx.AsyncClient",
        _fake_async_client(calls, responses),
    )

    provider = KimiCodingProvider(api_key="kimi-secret")
    result = asyncio.run(
        provider.chat(
            messages=[
                {"role": "system", "content": "System prompt"},
                {"role": "user", "content": "Solve this"},
            ],
            tools=[
                {
                    "name": "read_file",
                    "description": "Read a file.",
                    "input_schema": {"type": "object"},
                }
            ],
            model="k2p5",
            max_tokens=128,
            temperature=0.2,
        )
    )

    assert result.content == "Done"
    assert result.finish_reason == "stop"
    assert result.usage == {
        "prompt_tokens": 12,
        "completion_tokens": 4,
        "total_tokens": 16,
    }
    assert calls == [
        {
            "url": "https://api.kimi.com/coding/v1/messages",
            "headers": {
                "content-type": "application/json",
                "anthropic-version": "2023-06-01",
                "authorization": "Bearer kimi-secret",
                "x-api-key": "kimi-secret",
            },
            "json": {
                "model": "k2p5",
                "messages": [
                    {
                        "role": "user",
                        "content": [{"type": "text", "text": "Solve this"}],
                    }
                ],
                "max_tokens": 128,
                "temperature": 0.2,
                "system": "System prompt",
                "tools": [
                    {
                        "name": "read_file",
                        "description": "Read a file.",
                        "input_schema": {"type": "object"},
                    }
                ],
            },
            "timeout": 60.0,
        }
    ]


def test_kimi_provider_parses_tool_call_response(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict] = []
    responses = [
        _http_response(
            {
                "content": [
                    {
                        "type": "tool_use",
                        "id": "call-1",
                        "name": "read_file",
                        "input": {"path": "todo.txt"},
                    }
                ],
                "stop_reason": "tool_use",
                "usage": {"input_tokens": 9, "output_tokens": 2},
            }
        )
    ]
    monkeypatch.setattr(
        "app.adapters.kernel.kimi_coding.httpx.AsyncClient",
        _fake_async_client(calls, responses),
    )

    provider = KimiCodingProvider(api_key="kimi-secret")
    result = asyncio.run(provider.chat(messages=[{"role": "user", "content": "Read todo.txt"}]))

    assert result.content is None
    assert result.finish_reason == "tool_calls"
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].id == "call-1"
    assert result.tool_calls[0].name == "read_file"
    assert result.tool_calls[0].arguments == {"path": "todo.txt"}


def test_kimi_provider_returns_diagnostic_error_on_http_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict] = []
    responses = [
        _http_response({"error": {"message": "bad request"}}, status_code=400),
    ]
    monkeypatch.setattr(
        "app.adapters.kernel.kimi_coding.httpx.AsyncClient",
        _fake_async_client(calls, responses),
    )

    provider = KimiCodingProvider(api_key="kimi-secret")
    result = asyncio.run(provider.chat(messages=[{"role": "user", "content": "Hi"}]))

    assert result.finish_reason == "error"
    assert "HTTP 400" in (result.content or "")


def test_kimi_provider_returns_diagnostic_error_on_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict] = []
    request = httpx.Request("POST", "https://api.kimi.com/coding/v1/messages")
    responses = [httpx.ReadTimeout("timed out", request=request)]
    monkeypatch.setattr(
        "app.adapters.kernel.kimi_coding.httpx.AsyncClient",
        _fake_async_client(calls, responses),
    )

    provider = KimiCodingProvider(api_key="kimi-secret")
    result = asyncio.run(provider.chat(messages=[{"role": "user", "content": "Hi"}]))

    assert result.finish_reason == "error"
    assert "timed out" in (result.content or "")


def test_kimi_execute_multi_turn_preserves_tool_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict] = []
    responses = [
        _http_response(
            {
                "content": [
                    {
                        "type": "tool_use",
                        "id": "call-1",
                        "name": "read_file",
                        "input": {"path": "todo.txt"},
                    }
                ],
                "stop_reason": "tool_use",
                "usage": {"input_tokens": 30, "output_tokens": 5},
            }
        ),
        _http_response(
            {
                "content": [{"type": "text", "text": "Final answer"}],
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 45, "output_tokens": 7},
            }
        ),
    ]
    monkeypatch.setattr(
        "app.adapters.kernel.kimi_coding.httpx.AsyncClient",
        _fake_async_client(calls, responses),
    )
    get_secret_store().set_provider_api_key("kimi-coding", "kimi-secret")

    adapter = NanobotKernelAdapter(tool_executor=FakeToolExecutor())
    result = asyncio.run(
        adapter.execute(
            _build_request(
                provider="kimi-coding",
                model_name="k2p5",
                tools=[
                    KernelToolPolicy(
                        tool_name="read_file",
                        permission_level="allow",
                        approval_required=False,
                        workspace_path="/workspace",
                    )
                ],
                history=[
                    KernelMessage(
                        message_id="m1",
                        role="user",
                        content="Earlier question",
                        sequence_number=1,
                        created_at=datetime.now(UTC),
                    ),
                    KernelMessage(
                        message_id="m2",
                        role="assistant",
                        content="Earlier answer",
                        sequence_number=2,
                        created_at=datetime.now(UTC),
                    ),
                ],
                input_text="Read todo.txt",
            )
        )
    )

    follow_up_messages = calls[1]["json"]["messages"]
    assistant_tool_turn = follow_up_messages[-2]
    tool_result_turn = follow_up_messages[-1]
    raw_payload = json.loads(result.raw_payload or "{}")

    assert result.output_text == "Final answer"
    assert calls[0]["json"]["tools"] == [
        {
            "name": "read_file",
            "description": "Read a file.",
            "input_schema": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        }
    ]
    assert assistant_tool_turn == {
        "role": "assistant",
        "content": [
            {
                "type": "tool_use",
                "id": "call-1",
                "name": "read_file",
                "input": {"path": "todo.txt"},
            }
        ],
    }
    assert tool_result_turn == {
        "role": "user",
        "content": [
            {
                "type": "tool_result",
                "tool_use_id": "call-1",
                "content": "file contents",
            }
        ],
    }
    assert raw_payload["tool_calls"] == [
        {
            "id": "call-1",
            "name": "read_file",
            "arguments": {"path": "todo.txt"},
        }
    ]
    assert raw_payload["tool_outcomes"][0]["tool_call_id"] == "call-1"
    assert raw_payload["tool_outcomes"][0]["arguments"] == {"path": "todo.txt"}
    assert raw_payload["follow_up_finish_reason"] == "stop"


def test_kimi_resume_after_tool_preserves_passed_arguments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict] = []
    responses = [
        _http_response(
            {
                "content": [{"type": "text", "text": "Summarized result"}],
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 20, "output_tokens": 6},
            }
        )
    ]
    monkeypatch.setattr(
        "app.adapters.kernel.kimi_coding.httpx.AsyncClient",
        _fake_async_client(calls, responses),
    )
    get_secret_store().set_provider_api_key("kimi-coding", "kimi-secret")

    adapter = NanobotKernelAdapter()
    result = asyncio.run(
        adapter.resume_after_tool(
            _build_request(provider="kimi-coding", model_name="k2p5"),
            tool_name="read_file",
            tool_call_id="call-1",
            tool_arguments={"path": "todo.txt"},
            tool_output="file contents",
        )
    )

    messages = calls[0]["json"]["messages"]
    assert result.output_text == "Summarized result"
    assert messages[-2] == {
        "role": "assistant",
        "content": [
            {
                "type": "tool_use",
                "id": "call-1",
                "name": "read_file",
                "input": {"path": "todo.txt"},
            }
        ],
    }
    assert messages[-1] == {
        "role": "user",
        "content": [
            {
                "type": "tool_result",
                "tool_use_id": "call-1",
                "content": "file contents",
            }
        ],
    }


def test_existing_providers_keep_openai_tool_format() -> None:
    executor = FakeToolExecutor()

    tools = executor.describe_tools(["read_file"], format="openai")

    assert executor.formats == ["openai"]
    assert tools[0]["type"] == "function"
