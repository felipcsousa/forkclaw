from __future__ import annotations

import json
from dataclasses import dataclass

from app.models.entities import Message, TaskRun, ToolCall


@dataclass(frozen=True)
class SubagentCompletionSummary:
    summary_text: str
    output_json: str


class SubagentCompletionSummaryBuilder:
    def build(
        self,
        *,
        status: str,
        goal: str,
        task_run: TaskRun | None,
        assistant_message: Message | None,
        tool_calls: list[ToolCall],
        error_summary: str | None = None,
    ) -> SubagentCompletionSummary:
        tools_used = self._tools_used(tool_calls)
        files_touched = self._files_touched(tool_calls)
        summary = self._summary_text(
            status=status,
            assistant_message=assistant_message,
            error_summary=error_summary,
        )
        key_findings = [summary] if summary else []
        payload = {
            "status": status,
            "goal": goal,
            "summary": summary,
            "key_findings": key_findings,
            "files_touched": files_touched,
            "tools_used": tools_used,
            "estimated_cost_usd": task_run.estimated_cost_usd if task_run else 0.0,
            "started_at": (
                task_run.started_at.isoformat() if task_run and task_run.started_at else None
            ),
            "finished_at": (
                task_run.finished_at.isoformat() if task_run and task_run.finished_at else None
            ),
        }
        return SubagentCompletionSummary(
            summary_text=summary,
            output_json=json.dumps(payload, ensure_ascii=False),
        )

    def parent_message_text(self, *, child_title: str, payload: dict[str, object]) -> str:
        status = str(payload.get("status") or "unknown")
        summary = str(payload.get("summary") or "").strip() or "No summary provided."
        findings = payload.get("key_findings")
        findings_text = ""
        if isinstance(findings, list) and findings:
            findings_text = f" Key finding: {findings[0]}."
        return f"Subagent `{child_title}` {status}: {summary}.{findings_text}".strip()

    @staticmethod
    def _summary_text(
        *,
        status: str,
        assistant_message: Message | None,
        error_summary: str | None,
    ) -> str:
        if status == "completed" and assistant_message is not None:
            return _single_line(assistant_message.content_text)[:240]
        if status == "cancelled":
            return "Execution was interrupted before a normal completion."
        if status == "timed_out":
            return "Execution timed out before producing a normal conclusion."
        if error_summary:
            return _single_line(error_summary)[:240]
        return "Execution finished without a structured summary."

    @staticmethod
    def _tools_used(tool_calls: list[ToolCall]) -> list[str]:
        names: list[str] = []
        for tool_call in tool_calls:
            if tool_call.tool_name not in names:
                names.append(tool_call.tool_name)
        return names

    @staticmethod
    def _files_touched(tool_calls: list[ToolCall]) -> list[str]:
        paths: list[str] = []
        for tool_call in tool_calls:
            for raw_json in (tool_call.input_json, tool_call.output_json):
                if not raw_json:
                    continue
                try:
                    payload = json.loads(raw_json)
                except json.JSONDecodeError:
                    continue
                for key in ("path",):
                    value = payload.get(key) if isinstance(payload, dict) else None
                    if isinstance(value, str) and value not in paths:
                        paths.append(value)
                data = payload.get("data") if isinstance(payload, dict) else None
                path_from_data = data.get("path") if isinstance(data, dict) else None
                if isinstance(path_from_data, str) and path_from_data not in paths:
                    paths.append(path_from_data)
        return paths


def _single_line(value: str) -> str:
    return " ".join(value.split())
