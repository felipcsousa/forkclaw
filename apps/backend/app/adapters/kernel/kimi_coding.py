from __future__ import annotations

import json
from typing import Any
from urllib.parse import urljoin

import httpx
from nanobot.providers.base import LLMProvider, LLMResponse, ToolCallRequest

from app.core.provider_catalog import get_provider_metadata

_ANTHROPIC_VERSION = "2023-06-01"
_REQUEST_TIMEOUT_SECONDS = 60.0
_KIMI_CODING = get_provider_metadata("kimi-coding")
_STOP_REASON_MAP = {
    "end_turn": "stop",
    "max_tokens": "length",
    "tool_use": "tool_calls",
}


class KimiCodingProvider(LLMProvider):
    def __init__(
        self,
        *,
        api_key: str,
        api_base: str | None = None,
        default_model: str = "k2p5",
    ):
        super().__init__(api_key=api_key, api_base=api_base or _KIMI_CODING.api_base)
        self.default_model = default_model

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        reasoning_effort: str | None = None,
    ) -> LLMResponse:
        del reasoning_effort

        system_prompt, anthropic_messages = _convert_messages(messages)
        body: dict[str, Any] = {
            "model": model or self.default_model,
            "messages": anthropic_messages,
            "max_tokens": max(1, max_tokens),
            "temperature": temperature,
        }
        if system_prompt:
            body["system"] = system_prompt
        if tools:
            body["tools"] = tools

        headers = {
            "content-type": "application/json",
            "anthropic-version": _ANTHROPIC_VERSION,
            "authorization": f"Bearer {self.api_key}",
            "x-api-key": self.api_key or "",
        }

        try:
            async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT_SECONDS) as client:
                response = await client.post(
                    _messages_url(self.api_base),
                    headers=headers,
                    json=body,
                )
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text.strip() or str(exc)
            return LLMResponse(
                content=f"Error calling Kimi Coding: HTTP {exc.response.status_code}: {detail}",
                finish_reason="error",
            )
        except Exception as exc:
            return LLMResponse(
                content=f"Error calling Kimi Coding: {str(exc)}",
                finish_reason="error",
            )

        return _parse_response(response.json())

    def get_default_model(self) -> str:
        return self.default_model


def _messages_url(api_base: str | None) -> str:
    base = api_base or _KIMI_CODING.api_base or "https://api.kimi.com/coding/"
    return urljoin(base, "v1/messages")


def _convert_messages(messages: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    system_parts: list[str] = []
    anthropic_messages: list[dict[str, Any]] = []

    for message in messages:
        role = message.get("role")
        if role == "system":
            system_parts.append(_stringify_content(message.get("content")))
            continue

        converted = _convert_message(message)
        if converted is not None:
            anthropic_messages.append(converted)

    return "\n\n".join(part for part in system_parts if part), anthropic_messages


def _convert_message(message: dict[str, Any]) -> dict[str, Any] | None:
    role = message.get("role")
    if role == "user":
        content = _text_blocks(message.get("content"))
        if not content:
            content = [{"type": "text", "text": "(empty)"}]
        return {"role": "user", "content": content}

    if role == "assistant":
        content = _assistant_blocks(message)
        if not content:
            return None
        return {"role": "assistant", "content": content}

    if role == "tool":
        tool_result = {
            "type": "tool_result",
            "tool_use_id": str(message.get("tool_call_id") or ""),
            "content": _stringify_content(message.get("content")),
        }
        return {"role": "user", "content": [tool_result]}

    return None


def _text_blocks(content: Any) -> list[dict[str, Any]]:
    if isinstance(content, str):
        return [{"type": "text", "text": content}]

    if isinstance(content, list):
        blocks: list[dict[str, Any]] = []
        for item in content:
            if not isinstance(item, dict):
                continue
            item_type = item.get("type")
            if item_type == "text":
                blocks.append({"type": "text", "text": str(item.get("text") or "")})
            elif item_type == "tool_result":
                blocks.append(item)
        return blocks

    return []


def _assistant_blocks(message: dict[str, Any]) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    content = message.get("content")
    if isinstance(content, str) and content.strip():
        blocks.append({"type": "text", "text": content})
    elif isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                blocks.append({"type": "text", "text": str(item.get("text") or "")})

    for tool_call in message.get("tool_calls") or []:
        normalized = _normalize_tool_call(tool_call)
        if normalized is None:
            continue
        blocks.append(
            {
                "type": "tool_use",
                "id": normalized["id"],
                "name": normalized["name"],
                "input": normalized["arguments"],
            }
        )

    return blocks


def _normalize_tool_call(tool_call: Any) -> dict[str, Any] | None:
    if not isinstance(tool_call, dict):
        return None

    if "name" in tool_call and "arguments" in tool_call:
        return {
            "id": str(tool_call.get("id") or ""),
            "name": str(tool_call["name"]),
            "arguments": tool_call.get("arguments") or {},
        }

    function = tool_call.get("function")
    if not isinstance(function, dict):
        return None

    raw_arguments = function.get("arguments")
    if isinstance(raw_arguments, str):
        try:
            arguments = json.loads(raw_arguments)
        except json.JSONDecodeError:
            arguments = {"raw": raw_arguments}
    elif isinstance(raw_arguments, dict):
        arguments = raw_arguments
    else:
        arguments = {}

    return {
        "id": str(tool_call.get("id") or ""),
        "name": str(function.get("name") or ""),
        "arguments": arguments,
    }


def _parse_response(payload: dict[str, Any]) -> LLMResponse:
    text_parts: list[str] = []
    tool_calls: list[ToolCallRequest] = []
    thinking_parts: list[str] = []

    for block in payload.get("content") or []:
        if not isinstance(block, dict):
            continue
        block_type = block.get("type")
        if block_type == "text":
            text_parts.append(str(block.get("text") or ""))
        elif block_type == "tool_use":
            tool_calls.append(
                ToolCallRequest(
                    id=str(block.get("id") or ""),
                    name=str(block.get("name") or ""),
                    arguments=block.get("input") or {},
                )
            )
        elif block_type == "thinking":
            thinking_parts.append(str(block.get("thinking") or ""))

    usage = payload.get("usage") or {}
    stop_reason = str(payload.get("stop_reason") or "end_turn")
    return LLMResponse(
        content="".join(text_parts) or None,
        tool_calls=tool_calls,
        finish_reason=_STOP_REASON_MAP.get(stop_reason, stop_reason),
        usage={
            "prompt_tokens": int(usage.get("input_tokens") or 0),
            "completion_tokens": int(usage.get("output_tokens") or 0),
            "total_tokens": int(usage.get("input_tokens") or 0)
            + int(usage.get("output_tokens") or 0),
        },
        reasoning_content="\n".join(part for part in thinking_parts if part) or None,
    )


def _stringify_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text") or ""))
        return "\n".join(part for part in parts if part)
    if content is None:
        return ""
    return json.dumps(content, ensure_ascii=False)
