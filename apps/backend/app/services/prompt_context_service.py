from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass

from sqlmodel import Session, select

from app.core.config import get_settings
from app.kernel.contracts import (
    KernelPromptContext,
    KernelPromptContextEntry,
    KernelPromptContextLayer,
)
from app.models.entities import Memory, Message, SessionRecord, Setting, utc_now

LAYER_ORDER = (
    "stable_manual",
    "stable_autosaved",
    "workspace_project",
    "conversation_summary",
    "episodic",
)
LAYER_TITLES = {
    "stable_manual": "Stable Manual Memory",
    "stable_autosaved": "Stable Autosaved Memory",
    "workspace_project": "Workspace And Project Memory",
    "conversation_summary": "Current Conversation Summary",
    "episodic": "Recalled Episodic Memory",
}
LAYER_BUDGETS = {
    "stable_manual": 2000,
    "stable_autosaved": 1500,
    "workspace_project": 1500,
    "conversation_summary": 1200,
    "episodic": 1500,
}
SOURCE_PRIORITY = {
    "manual": 0,
    "user_override": 1,
    "promoted": 2,
    "autosaved": 3,
    "session_summary": 4,
}
SOURCE_REASON = {
    "manual": "manual",
    "user_override": "override",
    "promoted": "promotion",
    "autosaved": "autosaved",
    "session_summary": "summary",
}
WORD_RE = re.compile(r"[a-z0-9]{2,}")


@dataclass(frozen=True)
class _Candidate:
    memory: Memory
    layer: str
    reason: str
    score: tuple[int, float, str] | None = None


class PromptContextService:
    def __init__(self, session: Session):
        self.session = session

    def build_context(
        self,
        *,
        agent_id: str,
        session_record: SessionRecord,
        current_input: str,
    ) -> KernelPromptContext:
        statement = (
            select(Memory)
            .where(Memory.agent_id == agent_id)
            .order_by(Memory.updated_at.desc())
        )
        memories = list(self.session.exec(statement))
        included: list[KernelPromptContextEntry] = []
        excluded: list[KernelPromptContextEntry] = []

        visible_by_key: dict[tuple[str, str, str, str, str | None], list[Memory]] = (
            defaultdict(list)
        )
        for memory in memories:
            if memory.status == "hidden":
                excluded.append(self._entry(memory, layer="", reason="hidden"))
                continue
            if memory.status == "deleted":
                excluded.append(self._entry(memory, layer="", reason="deleted"))
                continue
            visible_by_key[self._natural_key(memory)].append(memory)

        winners: list[Memory] = []
        for group in visible_by_key.values():
            ordered = sorted(
                group,
                key=lambda item: (
                    SOURCE_PRIORITY.get(item.source, 99),
                    -item.updated_at.timestamp(),
                    item.id,
                ),
            )
            winners.append(ordered[0])
            for loser in ordered[1:]:
                excluded.append(self._entry(loser, layer="", reason="overridden"))

        by_layer: dict[str, list[_Candidate]] = {key: [] for key in LAYER_ORDER}
        for memory in winners:
            layer = self._resolve_layer(memory, session_record)
            if layer is None:
                continue
            reason = SOURCE_REASON.get(memory.source, memory.source)
            score = None
            if layer == "episodic":
                score = self._episodic_score(memory, current_input)
            by_layer[layer].append(
                _Candidate(
                    memory=memory,
                    layer=layer,
                    reason=reason,
                    score=score,
                )
            )

        if by_layer["episodic"]:
            by_layer["episodic"] = sorted(
                by_layer["episodic"],
                key=lambda item: (
                    -(item.score[0] if item.score else 0),
                    -(item.score[1] if item.score else 0.0),
                    -item.memory.updated_at.timestamp(),
                    item.memory.id,
                ),
            )[:4]

        layers: list[KernelPromptContextLayer] = []
        for layer_key in LAYER_ORDER:
            layer, layer_included, layer_excluded = self._build_layer(
                layer_key,
                by_layer[layer_key],
            )
            layers.append(layer)
            included.extend(layer_included)
            excluded.extend(layer_excluded)

        return KernelPromptContext(layers=layers, included=included, excluded=excluded)

    def update_conversation_summary(
        self,
        *,
        agent_id: str,
        session_record: SessionRecord,
        cutoff_sequence: int | None = None,
        parent_session_id: str | None = None,
    ) -> Memory | None:
        messages = self._messages_for_summary(session_record, cutoff_sequence=cutoff_sequence)
        if not messages:
            session_record.summary = None
            session_record.updated_at = utc_now()
            self.session.add(session_record)
            self.session.flush()
            return None

        summary = self._summarize_messages(messages)
        session_record.summary = summary
        session_record.updated_at = utc_now()
        self.session.add(session_record)
        memory = self._upsert_memory(
            agent_id=agent_id,
            namespace="conversation",
            memory_key="summary",
            value_text=summary,
            source="session_summary",
            memory_class="summary",
            scope_kind="conversation",
            scope_ref=session_record.id,
            session_id=session_record.id,
            conversation_id=session_record.conversation_id,
            parent_session_id=parent_session_id,
        )
        self.session.flush()
        return memory

    def persist_episodic_memory(
        self,
        *,
        agent_id: str,
        session_record: SessionRecord,
        current_input: str,
        output_text: str,
        episode_key: str,
        parent_session_id: str | None = None,
    ) -> Memory:
        body = (
            f"Input: {self._excerpt(current_input, 280)}\n"
            f"Output: {self._excerpt(output_text, 420)}"
        ).strip()
        return self._upsert_memory(
            agent_id=agent_id,
            namespace="episode",
            memory_key=f"episode:{episode_key}",
            value_text=body,
            source="autosaved",
            memory_class="episodic",
            scope_kind="conversation",
            scope_ref=session_record.id,
            session_id=session_record.id,
            conversation_id=session_record.conversation_id,
            parent_session_id=parent_session_id,
        )

    def promote_memory(self, *, memory_id: str) -> Memory:
        memory = self.session.get(Memory, memory_id)
        if memory is None:
            msg = "Memory not found."
            raise ValueError(msg)
        promoted = Memory(
            agent_id=memory.agent_id,
            namespace=memory.namespace,
            memory_key=memory.memory_key,
            value_text=memory.value_text,
            source="promoted",
            memory_class="stable",
            scope_kind=memory.scope_kind,
            scope_ref=memory.scope_ref,
            session_id=memory.session_id,
            conversation_id=memory.conversation_id,
            parent_session_id=memory.parent_session_id,
            source_memory_id=memory.id,
            status="active",
        )
        self.session.add(promoted)
        self.session.flush()
        return promoted

    def _build_layer(
        self,
        layer_key: str,
        candidates: list[_Candidate],
    ) -> tuple[
        KernelPromptContextLayer,
        list[KernelPromptContextEntry],
        list[KernelPromptContextEntry],
    ]:
        budget = LAYER_BUDGETS[layer_key]
        content = ""
        included: list[KernelPromptContextEntry] = []
        excluded: list[KernelPromptContextEntry] = []

        for index, candidate in enumerate(candidates):
            rendered = self._render_memory(candidate.memory)
            separator = "\n" if content else ""
            cost = len(separator) + len(rendered)
            remaining = budget - len(content)
            if cost <= remaining:
                content = f"{content}{separator}{rendered}"
                included.append(
                    self._entry(
                        candidate.memory,
                        layer=layer_key,
                        reason=candidate.reason,
                    )
                )
                continue

            available = remaining - len(separator)
            if available > 3:
                truncated = rendered[: max(0, available - 3)].rstrip()
                content = f"{content}{separator}{truncated}..."
                included.append(
                    self._entry(
                        candidate.memory,
                        layer=layer_key,
                        reason=candidate.reason,
                    )
                )
                excluded.append(self._entry(candidate.memory, layer=layer_key, reason="budget"))
            else:
                excluded.append(self._entry(candidate.memory, layer=layer_key, reason="budget"))
            for leftover in candidates[index + 1 :]:
                excluded.append(self._entry(leftover.memory, layer=layer_key, reason="budget"))
            break

        return (
            KernelPromptContextLayer(
                key=layer_key,
                title=LAYER_TITLES[layer_key],
                budget_chars=budget,
                used_chars=len(content),
                content=content,
                entries=included,
            ),
            included,
            excluded,
        )

    @staticmethod
    def _natural_key(memory: Memory) -> tuple[str, str, str, str, str | None]:
        return (
            memory.namespace,
            memory.memory_key,
            memory.memory_class,
            memory.scope_kind,
            memory.scope_ref,
        )

    def _resolve_layer(self, memory: Memory, session_record: SessionRecord) -> str | None:
        if memory.memory_class == "summary":
            if (
                memory.namespace == "conversation"
                and memory.memory_key == "summary"
                and memory.conversation_id == session_record.conversation_id
            ):
                return "conversation_summary"
            return None

        if memory.memory_class == "episodic":
            if session_record.kind == "subagent" and memory.session_id != session_record.id:
                return None
            return "episodic"

        if memory.memory_class != "stable":
            return None

        if memory.scope_kind in {"workspace", "project"}:
            if memory.scope_ref != self._workspace_scope_ref():
                return None
            return "workspace_project"

        if memory.source == "autosaved":
            return "stable_autosaved"
        return "stable_manual"

    def _workspace_scope_ref(self) -> str:
        setting = self.session.exec(
            select(Setting).where(
                Setting.scope == "security",
                Setting.key == "workspace_root",
                Setting.status == "active",
            )
        ).first()
        if setting and setting.value_text:
            return setting.value_text
        return str(get_settings().default_workspace_root)

    @staticmethod
    def _render_memory(memory: Memory) -> str:
        return f"- [{memory.namespace}/{memory.memory_key}] {memory.value_text.strip()}"

    @staticmethod
    def _entry(memory: Memory, *, layer: str, reason: str) -> KernelPromptContextEntry:
        return KernelPromptContextEntry(
            memory_id=memory.id,
            namespace=memory.namespace,
            memory_key=memory.memory_key,
            layer=layer,
            reason=reason,
            content=memory.value_text,
        )

    def _messages_for_summary(
        self,
        session_record: SessionRecord,
        *,
        cutoff_sequence: int | None,
    ) -> list[Message]:
        statement = select(Message).where(
            Message.session_id == session_record.id,
            Message.conversation_id == session_record.conversation_id,
        )
        if cutoff_sequence is not None:
            statement = statement.where(Message.sequence_number < cutoff_sequence)
        statement = statement.order_by(Message.sequence_number.asc())
        return list(self.session.exec(statement))

    @staticmethod
    def _summarize_messages(messages: list[Message]) -> str:
        recent = messages[-6:]
        parts = [
            f"{message.role}: {PromptContextService._excerpt(message.content_text, 140)}"
            for message in recent
        ]
        return "\n".join(parts)

    def _upsert_memory(
        self,
        *,
        agent_id: str,
        namespace: str,
        memory_key: str,
        value_text: str,
        source: str,
        memory_class: str,
        scope_kind: str,
        scope_ref: str | None,
        session_id: str | None,
        conversation_id: str | None,
        parent_session_id: str | None,
    ) -> Memory:
        statement = select(Memory).where(
            Memory.agent_id == agent_id,
            Memory.namespace == namespace,
            Memory.memory_key == memory_key,
            Memory.source == source,
            Memory.memory_class == memory_class,
            Memory.scope_kind == scope_kind,
            Memory.scope_ref == scope_ref,
        )
        memory = self.session.exec(statement).first()
        if memory is None:
            memory = Memory(
                agent_id=agent_id,
                namespace=namespace,
                memory_key=memory_key,
                value_text=value_text,
                source=source,
                memory_class=memory_class,
                scope_kind=scope_kind,
                scope_ref=scope_ref,
                session_id=session_id,
                conversation_id=conversation_id,
                parent_session_id=parent_session_id,
                status="active",
            )
        else:
            memory.value_text = value_text
            memory.session_id = session_id
            memory.conversation_id = conversation_id
            memory.parent_session_id = parent_session_id
            memory.status = "active"
            memory.updated_at = utc_now()
        self.session.add(memory)
        self.session.flush()
        return memory

    @staticmethod
    def _episodic_score(memory: Memory, current_input: str) -> tuple[int, float, str]:
        memory_tokens = set(WORD_RE.findall(memory.value_text.lower()))
        input_tokens = set(WORD_RE.findall(current_input.lower()))
        overlap = len(memory_tokens & input_tokens)
        density = overlap / max(len(memory_tokens), 1)
        return overlap, density, memory.id

    @staticmethod
    def _excerpt(value: str, limit: int) -> str:
        normalized = " ".join(value.split())
        if len(normalized) <= limit:
            return normalized
        return normalized[: max(0, limit - 3)].rstrip() + "..."
