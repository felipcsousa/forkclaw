from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy import or_
from sqlmodel import Session, select

from app.core.config import get_settings
from app.kernel.contracts import (
    KernelPromptContext,
    KernelPromptContextEntry,
    KernelPromptContextLayer,
)
from app.memory.policy import dedupe_hash_for, inspect_automatic_text, summarize_text
from app.models.entities import (
    MemoryEntry,
    Message,
    SessionRecord,
    SessionSummary,
    Setting,
    utc_now,
)

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
    "promoted_from_session": 2,
    "promoted_from_subagent": 2,
    "autosaved": 3,
    "summary": 4,
}
SOURCE_REASON = {
    "manual": "manual",
    "user_override": "override",
    "promoted_from_session": "promotion",
    "promoted_from_subagent": "promotion",
    "autosaved": "autosaved",
    "summary": "summary",
}
WORD_RE = re.compile(r"[a-z0-9]{2,}")
USER_SCOPE_KEY = "local-user"


@dataclass(frozen=True)
class _Candidate:
    memory_id: str
    namespace: str
    memory_key: str
    layer: str
    reason: str
    content: str
    rendered: str
    updated_at_epoch: float
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
        entries = self._load_entries(agent_id=agent_id, session_record=session_record)
        summaries = self._load_summaries(agent_id=agent_id, session_record=session_record)

        included: list[KernelPromptContextEntry] = []
        excluded: list[KernelPromptContextEntry] = []
        by_layer: dict[str, list[_Candidate]] = {key: [] for key in LAYER_ORDER}

        for candidate, reasons in self._resolve_entry_candidates(
            entries=entries,
            session_record=session_record,
            current_input=current_input,
        ):
            if candidate is None:
                excluded.extend(reasons)
                continue
            by_layer[candidate.layer].append(candidate)
            excluded.extend(reasons)

        for candidate, reasons in self._resolve_summary_candidates(
            summaries=summaries,
            session_record=session_record,
        ):
            if candidate is None:
                excluded.extend(reasons)
                continue
            by_layer[candidate.layer].append(candidate)
            excluded.extend(reasons)

        if by_layer["episodic"]:
            by_layer["episodic"] = sorted(
                by_layer["episodic"],
                key=lambda item: (
                    -(item.score[0] if item.score else 0),
                    -(item.score[1] if item.score else 0.0),
                    -item.updated_at_epoch,
                    item.memory_id,
                ),
            )[:4]

        layers: list[KernelPromptContextLayer] = []
        for layer_key in LAYER_ORDER:
            layer, layer_included, layer_excluded = self._build_layer(
                layer_key=layer_key,
                candidates=by_layer[layer_key],
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
    ) -> SessionSummary | None:
        del parent_session_id
        messages = self._messages_for_summary(session_record, cutoff_sequence=cutoff_sequence)
        statement = (
            select(SessionSummary)
            .where(
                SessionSummary.session_id == session_record.id,
                SessionSummary.source_kind == "summary",
            )
            .order_by(SessionSummary.updated_at.desc(), SessionSummary.created_at.desc())
        )
        existing = self.session.exec(statement).first()

        if not messages:
            session_record.summary = None
            session_record.updated_at = utc_now()
            self.session.add(session_record)
            if existing is not None:
                existing.hidden_from_recall = True
                existing.deleted_at = utc_now()
                existing.updated_at = utc_now()
                self.session.add(existing)
            self.session.flush()
            return None

        summary_text = self._summarize_messages(messages)
        session_record.summary = summary_text
        session_record.updated_at = utc_now()
        self.session.add(session_record)

        root_session_id = session_record.root_session_id or session_record.id
        if existing is None:
            existing = SessionSummary(
                agent_id=agent_id,
                scope_key=f"session:{session_record.id}",
                session_id=session_record.id,
                root_session_id=root_session_id,
                conversation_id=session_record.conversation_id,
                parent_session_id=session_record.parent_session_id,
                task_run_id=None,
                source_kind="summary",
                summary_text=summary_text,
                importance=0.0,
                created_by="system",
                workspace_path=self._workspace_scope_ref(),
                user_scope_key=USER_SCOPE_KEY,
                hidden_from_recall=False,
                deleted_at=None,
                origin_message_id=None,
                origin_task_run_id=None,
                override_target_summary_id=None,
            )
        else:
            existing.agent_id = agent_id
            existing.scope_key = f"session:{session_record.id}"
            existing.root_session_id = root_session_id
            existing.conversation_id = session_record.conversation_id
            existing.parent_session_id = session_record.parent_session_id
            existing.summary_text = summary_text
            existing.hidden_from_recall = False
            existing.deleted_at = None
            existing.workspace_path = self._workspace_scope_ref()
            existing.user_scope_key = USER_SCOPE_KEY
            existing.updated_at = utc_now()
        self.session.add(existing)
        self.session.flush()
        self.session.refresh(existing)
        return existing

    def persist_episodic_memory(
        self,
        *,
        agent_id: str,
        session_record: SessionRecord,
        current_input: str,
        output_text: str,
        episode_key: str,
        parent_session_id: str | None = None,
    ) -> MemoryEntry:
        body = (
            f"Input: {self._excerpt(current_input, 280)}\nOutput: {self._excerpt(output_text, 420)}"
        ).strip()
        title = summarize_text(output_text or current_input, limit=120)
        summary = summarize_text(body)
        inspected = inspect_automatic_text(title=title, body=body, summary=summary)
        dedupe_hash = dedupe_hash_for(inspected.title, inspected.body, inspected.summary)

        existing = self.session.exec(
            select(MemoryEntry).where(
                MemoryEntry.dedupe_hash == dedupe_hash,
                MemoryEntry.deleted_at.is_(None),
            )
        ).first()
        if existing is not None:
            return existing

        entry = MemoryEntry(
            agent_id=agent_id,
            scope_type="episodic",
            scope_key=f"session:{episode_key}",
            conversation_id=session_record.conversation_id,
            session_id=session_record.id,
            root_session_id=session_record.root_session_id or session_record.id,
            parent_session_id=parent_session_id or session_record.parent_session_id,
            source_kind="autosaved",
            lifecycle_state="active",
            title=inspected.title,
            body=inspected.body,
            summary=inspected.summary,
            importance=0.4,
            confidence=0.5,
            dedupe_hash=dedupe_hash,
            created_by="system",
            updated_by="system",
            workspace_path=self._workspace_scope_ref(),
            user_scope_key=USER_SCOPE_KEY,
            expires_at=None,
            redaction_state=inspected.redaction_state,
            security_state=inspected.security_state,
            hidden_from_recall=False,
            deleted_at=None,
            origin_message_id=None,
            origin_task_run_id=None,
            override_target_entry_id=None,
        )
        self.session.add(entry)
        self.session.flush()
        self.session.refresh(entry)
        return entry

    def promote_memory(self, *, memory_id: str) -> MemoryEntry:
        memory = self.session.get(MemoryEntry, memory_id)
        if memory is None:
            msg = "Memory not found."
            raise ValueError(msg)
        memory.scope_type = "stable"
        memory.source_kind = (
            "promoted_from_subagent"
            if memory.parent_session_id is not None
            else "promoted_from_session"
        )
        memory.updated_by = "system"
        memory.updated_at = utc_now()
        self.session.add(memory)
        self.session.flush()
        self.session.refresh(memory)
        return memory

    def _load_entries(
        self,
        *,
        agent_id: str,
        session_record: SessionRecord,
    ) -> list[MemoryEntry]:
        root_session_id = session_record.root_session_id or session_record.id
        statement = (
            select(MemoryEntry)
            .where(
                or_(
                    MemoryEntry.agent_id == agent_id,
                    MemoryEntry.session_id == session_record.id,
                    MemoryEntry.root_session_id == root_session_id,
                    MemoryEntry.conversation_id == session_record.conversation_id,
                    MemoryEntry.user_scope_key == USER_SCOPE_KEY,
                    MemoryEntry.workspace_path == self._workspace_scope_ref(),
                )
            )
            .order_by(MemoryEntry.updated_at.desc(), MemoryEntry.created_at.desc())
        )
        return list(self.session.exec(statement))

    def _load_summaries(
        self,
        *,
        agent_id: str,
        session_record: SessionRecord,
    ) -> list[SessionSummary]:
        root_session_id = session_record.root_session_id or session_record.id
        statement = (
            select(SessionSummary)
            .where(
                or_(
                    SessionSummary.agent_id == agent_id,
                    SessionSummary.session_id == session_record.id,
                    SessionSummary.root_session_id == root_session_id,
                    SessionSummary.conversation_id == session_record.conversation_id,
                    SessionSummary.user_scope_key == USER_SCOPE_KEY,
                )
            )
            .order_by(SessionSummary.updated_at.desc(), SessionSummary.created_at.desc())
        )
        return list(self.session.exec(statement))

    def _resolve_entry_candidates(
        self,
        *,
        entries: list[MemoryEntry],
        session_record: SessionRecord,
        current_input: str,
    ) -> list[tuple[_Candidate | None, list[KernelPromptContextEntry]]]:
        visible_by_key: dict[tuple[str, ...], list[MemoryEntry]] = defaultdict(list)
        results: list[tuple[_Candidate | None, list[KernelPromptContextEntry]]] = []

        overridden_targets = {
            entry.override_target_entry_id
            for entry in entries
            if entry.override_target_entry_id is not None
            and entry.deleted_at is None
            and not entry.hidden_from_recall
        }
        for entry in entries:
            if entry.hidden_from_recall:
                results.append((None, [self._entry_row(entry, layer="", reason="hidden")]))
                continue
            if entry.deleted_at is not None:
                results.append((None, [self._entry_row(entry, layer="", reason="deleted")]))
                continue
            if entry.id in overridden_targets:
                results.append((None, [self._entry_row(entry, layer="", reason="overridden")]))
                continue
            visible_by_key[self._natural_entry_key(entry)].append(entry)

        for group in visible_by_key.values():
            ordered = sorted(
                group,
                key=lambda item: (
                    SOURCE_PRIORITY.get(item.source_kind, 99),
                    -item.updated_at.timestamp(),
                    item.id,
                ),
            )
            winner = ordered[0]
            layer = self._resolve_entry_layer(winner, session_record)
            if layer is None:
                continue
            score = self._episodic_score(winner, current_input) if layer == "episodic" else None
            candidate = _Candidate(
                memory_id=winner.id,
                namespace=winner.scope_type,
                memory_key=winner.title,
                layer=layer,
                reason=SOURCE_REASON.get(winner.source_kind, winner.source_kind),
                content=winner.body,
                rendered=self._render_entry(winner),
                updated_at_epoch=winner.updated_at.timestamp(),
                score=score,
            )
            losers = [self._entry_row(item, layer="", reason="overridden") for item in ordered[1:]]
            results.append((candidate, losers))

        return results

    def _resolve_summary_candidates(
        self,
        *,
        summaries: list[SessionSummary],
        session_record: SessionRecord,
    ) -> list[tuple[_Candidate | None, list[KernelPromptContextEntry]]]:
        visible_by_key: dict[tuple[str, ...], list[SessionSummary]] = defaultdict(list)
        results: list[tuple[_Candidate | None, list[KernelPromptContextEntry]]] = []

        overridden_targets = {
            summary.override_target_summary_id
            for summary in summaries
            if summary.override_target_summary_id is not None
            and summary.deleted_at is None
            and not summary.hidden_from_recall
        }
        for summary in summaries:
            if summary.hidden_from_recall:
                results.append((None, [self._summary_row(summary, layer="", reason="hidden")]))
                continue
            if summary.deleted_at is not None:
                results.append((None, [self._summary_row(summary, layer="", reason="deleted")]))
                continue
            if summary.id in overridden_targets:
                results.append((None, [self._summary_row(summary, layer="", reason="overridden")]))
                continue
            visible_by_key[self._natural_summary_key(summary)].append(summary)

        for group in visible_by_key.values():
            ordered = sorted(
                group,
                key=lambda item: (
                    SOURCE_PRIORITY.get(item.source_kind, 99),
                    -item.updated_at.timestamp(),
                    item.id,
                ),
            )
            winner = ordered[0]
            layer = self._resolve_summary_layer(winner, session_record)
            if layer is None:
                continue
            candidate = _Candidate(
                memory_id=winner.id,
                namespace="summary",
                memory_key=(winner.session_id or winner.scope_key or "conversation-summary"),
                layer=layer,
                reason=SOURCE_REASON.get(winner.source_kind, winner.source_kind),
                content=winner.summary_text,
                rendered=self._render_summary(winner),
                updated_at_epoch=winner.updated_at.timestamp(),
            )
            losers = [
                self._summary_row(item, layer="", reason="overridden") for item in ordered[1:]
            ]
            results.append((candidate, losers))

        return results

    def _build_layer(
        self,
        *,
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

        ordered = sorted(
            candidates,
            key=lambda item: (-item.updated_at_epoch, item.memory_id),
        )
        for index, candidate in enumerate(ordered):
            separator = "\n" if content else ""
            cost = len(separator) + len(candidate.rendered)
            remaining = budget - len(content)
            if cost <= remaining:
                content = f"{content}{separator}{candidate.rendered}"
                included.append(self._candidate_row(candidate, reason=candidate.reason))
                continue

            available = remaining - len(separator)
            if available > 3:
                truncated = candidate.rendered[: max(0, available - 3)].rstrip()
                content = f"{content}{separator}{truncated}..."
                included.append(self._candidate_row(candidate, reason=candidate.reason))
                excluded.append(self._candidate_row(candidate, reason="budget"))
            else:
                excluded.append(self._candidate_row(candidate, reason="budget"))
            for leftover in ordered[index + 1 :]:
                excluded.append(self._candidate_row(leftover, reason="budget"))
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
    def _natural_entry_key(entry: MemoryEntry) -> tuple[str, ...]:
        if entry.override_target_entry_id is not None:
            return ("override", entry.override_target_entry_id)
        return (
            "entry",
            entry.scope_type,
            entry.scope_key,
            " ".join(entry.title.lower().split()),
        )

    @staticmethod
    def _natural_summary_key(summary: SessionSummary) -> tuple[str, ...]:
        if summary.override_target_summary_id is not None:
            return ("override", summary.override_target_summary_id)
        return (
            "summary",
            summary.scope_key,
            summary.session_id or "",
            summary.conversation_id or "",
        )

    def _resolve_entry_layer(
        self,
        entry: MemoryEntry,
        session_record: SessionRecord,
    ) -> str | None:
        if entry.scope_type == "episodic":
            if session_record.kind == "subagent" and entry.session_id != session_record.id:
                return None
            return "episodic"
        if entry.workspace_path and entry.workspace_path == self._workspace_scope_ref():
            return "workspace_project"
        if entry.source_kind == "autosaved":
            return "stable_autosaved"
        return "stable_manual"

    @staticmethod
    def _resolve_summary_layer(
        summary: SessionSummary,
        session_record: SessionRecord,
    ) -> str | None:
        if (
            summary.conversation_id == session_record.conversation_id
            or summary.session_id == session_record.id
        ):
            return "conversation_summary"
        return None

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
    def _render_entry(entry: MemoryEntry) -> str:
        return f"- [{entry.scope_type}/{entry.title}] {entry.body.strip()}"

    @staticmethod
    def _render_summary(summary: SessionSummary) -> str:
        return f"- [summary/{summary.scope_key}] {summary.summary_text.strip()}"

    @staticmethod
    def _candidate_row(candidate: _Candidate, *, reason: str) -> KernelPromptContextEntry:
        return KernelPromptContextEntry(
            memory_id=candidate.memory_id,
            namespace=candidate.namespace,
            memory_key=candidate.memory_key,
            layer=candidate.layer,
            reason=reason,
            content=candidate.content,
        )

    @staticmethod
    def _entry_row(entry: MemoryEntry, *, layer: str, reason: str) -> KernelPromptContextEntry:
        return KernelPromptContextEntry(
            memory_id=entry.id,
            namespace=entry.scope_type,
            memory_key=entry.title,
            layer=layer,
            reason=reason,
            content=entry.body,
        )

    @staticmethod
    def _summary_row(
        summary: SessionSummary, *, layer: str, reason: str
    ) -> KernelPromptContextEntry:
        return KernelPromptContextEntry(
            memory_id=summary.id,
            namespace="summary",
            memory_key=summary.session_id or summary.scope_key,
            layer=layer,
            reason=reason,
            content=summary.summary_text,
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

    @staticmethod
    def _episodic_score(entry: MemoryEntry, current_input: str) -> tuple[int, float, str]:
        memory_tokens = set(
            WORD_RE.findall(
                " ".join(filter(None, [entry.title, entry.body, entry.summary or ""])).lower()
            )
        )
        input_tokens = set(WORD_RE.findall(current_input.lower()))
        overlap = len(memory_tokens & input_tokens)
        density = overlap / max(len(memory_tokens), 1)
        return overlap, density, entry.id

    @staticmethod
    def _excerpt(value: str, limit: int) -> str:
        normalized = " ".join(value.split())
        if len(normalized) <= limit:
            return normalized
        return normalized[: max(0, limit - 3)].rstrip() + "..."
