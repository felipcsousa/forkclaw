from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal, TypeAlias

MemoryScope: TypeAlias = Literal["operational", "stable", "episodic", "manual"]
MemorySourceKind: TypeAlias = Literal[
    "manual",
    "autosaved",
    "summary",
    "promoted_from_session",
    "promoted_from_subagent",
    "user_override",
]
MemoryLifecycleState: TypeAlias = Literal["active", "superseded", "soft_deleted"]
MemoryRecallReason: TypeAlias = Literal[
    "runtime_context",
    "explicit_search",
    "session_summary",
    "promotion_review",
    "subagent_context",
    "manual_inspection",
]

MEMORY_SCOPES = {"operational", "stable", "episodic", "manual"}
MEMORY_SOURCE_KINDS = {
    "manual",
    "autosaved",
    "summary",
    "promoted_from_session",
    "promoted_from_subagent",
    "user_override",
}
MEMORY_LIFECYCLE_STATES = {"active", "superseded", "soft_deleted"}
MEMORY_RECALL_REASONS = {
    "runtime_context",
    "explicit_search",
    "session_summary",
    "promotion_review",
    "subagent_context",
    "manual_inspection",
}


@dataclass(frozen=True)
class ConversationIdentity:
    session_key: str
    conversation_id: str
    session_id: str | None
    run_id: str | None
    parent_session_id: str | None

    def to_dict(self) -> dict[str, str | None]:
        return asdict(self)
