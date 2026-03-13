from __future__ import annotations

import platform
import subprocess
from hashlib import sha256
from typing import Any

from app.core.provider_catalog import ToolFormat
from app.tools.base import LocalTool, ToolDescriptor, ToolExecutionContext, ToolResult
from app.tools.shell import ShellExecTool
from app.tools.web.fetch import fetch_web_document
from app.tools.web.providers.brave import BraveWebSearchProvider


class ListFilesTool:
    descriptor = ToolDescriptor(
        name="list_files",
        label="List files",
        description="List files and directories inside the configured workspace.",
        group="group:fs",
        risk="low",
        status="enabled",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative path inside the workspace."}
            },
            "additionalProperties": False,
        },
        output_schema={
            "type": "object",
            "properties": {"count": {"type": "integer"}},
            "additionalProperties": True,
        },
        requires_workspace=True,
    )

    def execute(
        self,
        *,
        context: ToolExecutionContext,
        arguments: dict[str, Any],
    ) -> ToolResult:
        target = context.resolve_path(arguments.get("path"))
        if not target.exists():
            msg = "Target directory does not exist."
            raise FileNotFoundError(msg)
        if not target.is_dir():
            msg = "Target path is not a directory."
            raise NotADirectoryError(msg)

        items = []
        for entry in sorted(target.iterdir(), key=lambda item: item.name.lower())[:200]:
            kind = "dir" if entry.is_dir() else "file"
            items.append(f"{kind}: {entry.relative_to(context.workspace_root)}")

        return ToolResult(
            output_text="\n".join(items) or "(empty directory)",
            output_data={"count": len(items)},
        )


class ReadFileTool:
    descriptor = ToolDescriptor(
        name="read_file",
        label="Read file",
        description="Read a UTF-8 text file inside the configured workspace.",
        group="group:fs",
        risk="medium",
        status="enabled",
        parameters={
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
        output_schema={
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "additionalProperties": True,
        },
        requires_workspace=True,
    )

    def execute(
        self,
        *,
        context: ToolExecutionContext,
        arguments: dict[str, Any],
    ) -> ToolResult:
        target = context.resolve_path(_require_string(arguments, "path"))
        if not target.exists():
            msg = "Target file does not exist."
            raise FileNotFoundError(msg)
        if not target.is_file():
            msg = "Target path is not a file."
            raise IsADirectoryError(msg)

        content = target.read_text(encoding="utf-8")
        return ToolResult(
            output_text=content[:10000],
            output_data={"path": str(target.relative_to(context.workspace_root))},
        )


class WriteFileTool:
    descriptor = ToolDescriptor(
        name="write_file",
        label="Write file",
        description="Write UTF-8 text to a file inside the configured workspace.",
        group="group:fs",
        risk="high",
        status="enabled",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative file path inside the workspace.",
                },
                "content": {"type": "string", "description": "Full replacement content."},
            },
            "required": ["path", "content"],
            "additionalProperties": False,
        },
        output_schema={
            "type": "object",
            "properties": {"bytes": {"type": "integer"}},
            "additionalProperties": True,
        },
        requires_workspace=True,
    )

    def execute(
        self,
        *,
        context: ToolExecutionContext,
        arguments: dict[str, Any],
    ) -> ToolResult:
        target = context.resolve_path(_require_string(arguments, "path"))
        target.parent.mkdir(parents=True, exist_ok=True)
        content = _require_string(arguments, "content")
        target.write_text(content, encoding="utf-8")
        return ToolResult(
            output_text=(
                f"Wrote {len(content)} characters to "
                f"{target.relative_to(context.workspace_root)}."
            ),
            output_data={"bytes": len(content.encode('utf-8'))},
        )


class EditFileTool:
    descriptor = ToolDescriptor(
        name="edit_file",
        label="Edit file",
        description="Find and replace text inside a file in the configured workspace.",
        group="group:fs",
        risk="high",
        status="enabled",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative file path inside the workspace.",
                },
                "find": {"type": "string", "description": "Text to search for."},
                "replace": {"type": "string", "description": "Replacement text."},
                "replace_all": {"type": "boolean", "description": "Replace all occurrences."},
            },
            "required": ["path", "find", "replace"],
            "additionalProperties": False,
        },
        output_schema={
            "type": "object",
            "properties": {"replaced_all": {"type": "boolean"}},
            "additionalProperties": True,
        },
        requires_workspace=True,
    )

    def execute(
        self,
        *,
        context: ToolExecutionContext,
        arguments: dict[str, Any],
    ) -> ToolResult:
        target = context.resolve_path(_require_string(arguments, "path"))
        if not target.exists():
            msg = "Target file does not exist."
            raise FileNotFoundError(msg)

        original = target.read_text(encoding="utf-8")
        needle = _require_string(arguments, "find")
        replacement = _require_string(arguments, "replace")
        replace_all = bool(arguments.get("replace_all", False))

        if needle not in original:
            msg = "Search text was not found in the file."
            raise ValueError(msg)

        updated = (
            original.replace(needle, replacement)
            if replace_all
            else original.replace(needle, replacement, 1)
        )
        target.write_text(updated, encoding="utf-8")
        return ToolResult(
            output_text=f"Updated {target.relative_to(context.workspace_root)} successfully.",
            output_data={"replaced_all": replace_all},
        )


class ClipboardReadTool:
    descriptor = ToolDescriptor(
        name="clipboard_read",
        label="Clipboard read",
        description="Read plain text from the system clipboard.",
        group="group:runtime",
        risk="high",
        status="enabled",
        parameters={"type": "object", "properties": {}, "additionalProperties": False},
        requires_workspace=False,
    )

    def execute(
        self,
        *,
        context: ToolExecutionContext,
        arguments: dict[str, Any],
    ) -> ToolResult:
        del context, arguments
        return ToolResult(output_text=_read_clipboard(), output_data=None)


class ClipboardWriteTool:
    descriptor = ToolDescriptor(
        name="clipboard_write",
        label="Clipboard write",
        description="Write plain text to the system clipboard.",
        group="group:runtime",
        risk="medium",
        status="enabled",
        parameters={
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "Plain text to write to the clipboard.",
                }
            },
            "required": ["content"],
            "additionalProperties": False,
        },
        requires_workspace=False,
    )

    def execute(
        self,
        *,
        context: ToolExecutionContext,
        arguments: dict[str, Any],
    ) -> ToolResult:
        del context
        content = _require_string(arguments, "content")
        _write_clipboard(content)
        return ToolResult(
            output_text=f"Wrote {len(content)} characters to the clipboard.",
            output_data=None,
        )


class WebSearchTool:
    descriptor = ToolDescriptor(
        name="web_search",
        label="Web search",
        description="Search the web with a provider-backed adapter and local TTL cache.",
        group="group:web",
        risk="medium",
        status="experimental",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query."},
                "count": {
                    "type": "integer",
                    "description": "Maximum number of results to return.",
                    "minimum": 1,
                    "maximum": 10,
                },
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        output_schema={
            "type": "object",
            "properties": {
                "provider": {"type": "string"},
                "query": {"type": "string"},
                "results": {"type": "array"},
                "cached": {"type": "boolean"},
            },
            "additionalProperties": True,
        },
    )

    def execute(
        self,
        *,
        context: ToolExecutionContext,
        arguments: dict[str, Any],
    ) -> ToolResult:
        query = _require_string(arguments, "query")
        count = _read_optional_int(arguments, "count", default=5, minimum=1, maximum=10)
        cache_key = _hash_cache_key(f"{query}\n{count}")
        cached_payload = (
            context.cache_store.get_json(tool_name=self.descriptor.name, cache_key=cache_key)
            if context.cache_store is not None
            else None
        )

        if cached_payload is None:
            provider = BraveWebSearchProvider(
                timeout_seconds=float(context.runtime_settings.get("tool_timeout_seconds", 15.0))
            )
            response = provider.search(query, count)
            base_payload = {
                "provider": response.provider,
                "query": response.query,
                "results": [
                    {
                        "title": item.title,
                        "url": item.url,
                        "snippet": item.snippet,
                    }
                    for item in response.results
                ],
            }
            if context.cache_store is not None:
                context.cache_store.set_json(
                    tool_name=self.descriptor.name,
                    cache_key=cache_key,
                    value=base_payload,
                    ttl_seconds=int(
                        context.runtime_settings.get("web_search_cache_ttl_seconds", 900)
                    ),
                )
            payload = {**base_payload, "cached": False}
        else:
            payload = {**cached_payload, "cached": True}

        return ToolResult(
            output_text=_format_search_results(payload["results"]),
            output_data=payload,
        )


class WebFetchTool:
    descriptor = ToolDescriptor(
        name="web_fetch",
        label="Web fetch",
        description="Fetch a web page and extract readable markdown or text with local TTL cache.",
        group="group:web",
        risk="high",
        status="experimental",
        parameters={
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "HTTP or HTTPS URL to fetch."},
                "extract_mode": {
                    "type": "string",
                    "enum": ["markdown", "text"],
                    "description": "Readable extraction mode.",
                },
                "max_chars": {
                    "type": "integer",
                    "description": "Maximum number of output characters.",
                    "minimum": 200,
                    "maximum": 20000,
                },
            },
            "required": ["url"],
            "additionalProperties": False,
        },
        output_schema={
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "final_url": {"type": "string"},
                "extract_mode": {"type": "string"},
                "cached": {"type": "boolean"},
            },
            "additionalProperties": True,
        },
    )

    def execute(
        self,
        *,
        context: ToolExecutionContext,
        arguments: dict[str, Any],
    ) -> ToolResult:
        url = _require_string(arguments, "url")
        extract_mode = _read_extract_mode(arguments.get("extract_mode"))
        max_chars = _read_optional_int(
            arguments,
            "max_chars",
            default=int(context.runtime_settings.get("web_fetch_default_max_chars", 8000)),
            minimum=200,
            maximum=20000,
        )
        cache_key = _hash_cache_key(f"{url}\n{extract_mode}\n{max_chars}")
        cached_payload = (
            context.cache_store.get_json(tool_name=self.descriptor.name, cache_key=cache_key)
            if context.cache_store is not None
            else None
        )

        if cached_payload is None:
            base_payload = fetch_web_document(
                url=url,
                extract_mode=extract_mode,
                max_chars=max_chars,
                timeout_seconds=float(context.runtime_settings.get("tool_timeout_seconds", 15.0)),
                max_response_bytes=int(
                    context.runtime_settings.get("web_fetch_max_response_bytes", 512 * 1024)
                ),
            )
            if context.cache_store is not None:
                context.cache_store.set_json(
                    tool_name=self.descriptor.name,
                    cache_key=cache_key,
                    value=base_payload,
                    ttl_seconds=int(
                        context.runtime_settings.get("web_fetch_cache_ttl_seconds", 900)
                    ),
                )
            payload = {**base_payload, "cached": False}
        else:
            payload = {**cached_payload, "cached": True}

        return ToolResult(
            output_text=str(payload.get("content") or ""),
            output_data=payload,
        )


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, LocalTool] = {}

    def register(self, tool: LocalTool) -> None:
        self._tools[tool.descriptor.name] = tool

    def get(self, name: str) -> LocalTool:
        try:
            return self._tools[name]
        except KeyError as exc:
            msg = f"Unknown tool: {name}"
            raise KeyError(msg) from exc

    def list(self) -> list[LocalTool]:
        return [self._tools[name] for name in sorted(self._tools)]

    def describe(
        self,
        tool_names: list[str] | None = None,
        *,
        format: ToolFormat = "openai",
    ) -> list[dict[str, Any]]:
        names = tool_names or sorted(self._tools)
        items = []
        for name in names:
            tool = self.get(name)
            if format == "anthropic":
                items.append(
                    {
                        "name": tool.descriptor.name,
                        "description": tool.descriptor.description,
                        "input_schema": tool.descriptor.parameters,
                    }
                )
                continue
            items.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool.descriptor.name,
                        "description": tool.descriptor.description,
                        "parameters": tool.descriptor.parameters,
                    },
                }
            )
        return items


def build_tool_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(ListFilesTool())
    registry.register(ReadFileTool())
    registry.register(WriteFileTool())
    registry.register(EditFileTool())
    registry.register(ClipboardReadTool())
    registry.register(ClipboardWriteTool())
    registry.register(ShellExecTool())
    registry.register(WebSearchTool())
    registry.register(WebFetchTool())
    return registry


def _require_string(arguments: dict[str, Any], key: str) -> str:
    value = arguments.get(key)
    if not isinstance(value, str) or not value.strip():
        msg = f"Missing required string argument: {key}"
        raise ValueError(msg)
    return value


def _read_optional_int(
    arguments: dict[str, Any],
    key: str,
    *,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    value = arguments.get(key, default)
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        msg = f"Invalid integer argument: {key}"
        raise ValueError(msg) from exc
    return max(min(parsed, maximum), minimum)


def _read_extract_mode(value: object) -> str:
    if value is None:
        return "markdown"
    if value not in {"markdown", "text"}:
        msg = "extract_mode must be either `markdown` or `text`."
        raise ValueError(msg)
    return str(value)


def _hash_cache_key(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _format_search_results(results: object) -> str:
    if not isinstance(results, list) or not results:
        return "No results found."

    lines: list[str] = []
    for index, item in enumerate(results, start=1):
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip() or "Untitled result"
        url = str(item.get("url") or "").strip()
        snippet = str(item.get("snippet") or "").strip()
        lines.append(f"{index}. {title}")
        if url:
            lines.append(f"   {url}")
        if snippet:
            lines.append(f"   {snippet}")
    return "\n".join(lines).strip() or "No results found."


def _read_clipboard() -> str:
    system = platform.system()
    if system == "Darwin":
        return subprocess.run(
            ["pbpaste"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    if system == "Windows":
        return subprocess.run(
            ["powershell", "-Command", "Get-Clipboard"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout

    msg = "Clipboard read is only implemented for macOS and Windows in this MVP."
    raise NotImplementedError(msg)


def _write_clipboard(content: str) -> None:
    system = platform.system()
    if system == "Darwin":
        subprocess.run(
            ["pbcopy"],
            input=content,
            check=True,
            text=True,
        )
        return
    if system == "Windows":
        subprocess.run(
            ["powershell", "-Command", "Set-Clipboard"],
            input=content,
            check=True,
            text=True,
        )
        return

    msg = "Clipboard write is only implemented for macOS and Windows in this MVP."
    raise NotImplementedError(msg)
