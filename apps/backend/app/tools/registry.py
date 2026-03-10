from __future__ import annotations

import platform
import subprocess
from typing import Any

from app.tools.base import LocalTool, ToolDescriptor, ToolExecutionContext, ToolResult


class ListFilesTool:
    descriptor = ToolDescriptor(
        name="list_files",
        description="List files and directories inside the configured workspace.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative path inside the workspace."}
            },
            "additionalProperties": False,
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
        description="Read a UTF-8 text file inside the configured workspace.",
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
        description="Write UTF-8 text to a file inside the configured workspace.",
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
        description="Find and replace text inside a file in the configured workspace.",
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
        description="Read plain text from the system clipboard.",
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
        description="Write plain text to the system clipboard.",
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

    def describe(self, tool_names: list[str] | None = None) -> list[dict[str, Any]]:
        names = tool_names or sorted(self._tools)
        items = []
        for name in names:
            tool = self.get(name)
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
    return registry


def _require_string(arguments: dict[str, Any], key: str) -> str:
    value = arguments.get(key)
    if not isinstance(value, str) or not value.strip():
        msg = f"Missing required string argument: {key}"
        raise ValueError(msg)
    return value


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
