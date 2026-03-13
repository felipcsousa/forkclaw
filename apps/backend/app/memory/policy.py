from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass

from app.memory.contracts import (
    MEMORY_SCOPES,
    MEMORY_SOURCE_KINDS,
    ConversationIdentity,
)

SECRET_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{10,}\b"),
    re.compile(r"\bOPENAI_API_KEY\s*=\s*[^\s]+", re.IGNORECASE),
    re.compile(r"\bANTHROPIC_API_KEY\s*=\s*[^\s]+", re.IGNORECASE),
    re.compile(r"\bapi[_-]?key\b", re.IGNORECASE),
)
INJECTION_PATTERNS = (
    re.compile(r"ignore\s+previous\s+instructions", re.IGNORECASE),
    re.compile(r"system\s+prompt", re.IGNORECASE),
    re.compile(r"developer\s+message", re.IGNORECASE),
    re.compile(r"tool\s+policy", re.IGNORECASE),
)

USER_MANAGED_SOURCE_KINDS = {
    "manual",
    "user_override",
    "promoted_from_session",
    "promoted_from_subagent",
}


@dataclass(frozen=True)
class MemoryTextInspection:
    title: str
    body: str
    summary: str | None
    redaction_state: str
    security_state: str


def validate_scope_type(scope_type: str) -> str:
    if scope_type not in MEMORY_SCOPES:
        msg = f"Unsupported memory scope: {scope_type}."
        raise ValueError(msg)
    return scope_type


def validate_source_kind(source_kind: str) -> str:
    if source_kind not in MEMORY_SOURCE_KINDS:
        msg = f"Unsupported memory source kind: {source_kind}."
        raise ValueError(msg)
    return source_kind


def validate_scope_key(scope_key: str) -> str:
    normalized = " ".join(scope_key.split()).strip()
    if not normalized:
        msg = "Memory scope_key is required."
        raise ValueError(msg)
    valid_prefixes = ("agent:", "session:", "subagent:", "legacy/", "user/")
    if not normalized.startswith(valid_prefixes):
        msg = "Memory scope_key must use an agent:, session:, subagent:, user/, or legacy/ prefix."
        raise ValueError(msg)
    return normalized


def normalize_text_for_dedupe(title: str, body: str, summary: str | None) -> str:
    parts = [title, body, summary or ""]
    normalized_parts: list[str] = []
    for part in parts:
        normalized = unicodedata.normalize("NFKC", part or "").lower()
        normalized_parts.append(" ".join(normalized.split()).strip())
    return "||".join(normalized_parts)


def dedupe_hash_for(title: str, body: str, summary: str | None) -> str:
    normalized = normalize_text_for_dedupe(title=title, body=body, summary=summary)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def inspect_manual_text(*, title: str, body: str, summary: str | None) -> MemoryTextInspection:
    normalized_title = " ".join(title.split()).strip()
    normalized_body = body.strip()
    normalized_summary = summary.strip() if isinstance(summary, str) else None
    if not normalized_title:
        msg = "Memory title is required."
        raise ValueError(msg)
    if not normalized_body:
        msg = "Memory body is required."
        raise ValueError(msg)
    combined = "\n".join(filter(None, [normalized_title, normalized_body, normalized_summary]))
    if _matches_secret(combined):
        msg = "Memory contains a raw secret and cannot be persisted."
        raise ValueError(msg)
    if _matches_injection(combined):
        msg = "Memory contains prompt-injection content and cannot be persisted."
        raise ValueError(msg)
    return MemoryTextInspection(
        title=normalized_title,
        body=normalized_body,
        summary=normalized_summary,
        redaction_state="clean",
        security_state="safe",
    )


def inspect_automatic_text(*, title: str, body: str, summary: str | None) -> MemoryTextInspection:
    normalized_title = " ".join(title.split()).strip() or "Execution memory"
    normalized_body = body.strip()
    normalized_summary = summary.strip() if isinstance(summary, str) else None
    if not normalized_body:
        msg = "Automatic memory body is required."
        raise ValueError(msg)
    redaction_state = "clean"
    security_state = "safe"
    redacted_body = normalized_body
    redacted_summary = normalized_summary
    combined = "\n".join(filter(None, [normalized_title, normalized_body, normalized_summary]))
    for pattern in SECRET_PATTERNS:
        if pattern.search(combined):
            redacted_body = pattern.sub("[REDACTED]", redacted_body)
            if redacted_summary is not None:
                redacted_summary = pattern.sub("[REDACTED]", redacted_summary)
            redaction_state = "redacted"
            security_state = "flagged"
    combined_redacted = "\n".join(filter(None, [normalized_title, redacted_body, redacted_summary]))
    if _matches_injection(combined_redacted):
        security_state = "flagged"
    return MemoryTextInspection(
        title=normalized_title,
        body=redacted_body,
        summary=redacted_summary,
        redaction_state=redaction_state,
        security_state=security_state,
    )


def build_conversation_identity(
    *,
    session_id: str | None,
    conversation_id: str | None,
    run_id: str | None,
    parent_session_id: str | None,
) -> ConversationIdentity:
    session_token = session_id or "detached"
    return ConversationIdentity(
        session_key=f"session:{session_token}",
        conversation_id=conversation_id or f"conversation:{session_token}",
        session_id=session_id,
        run_id=run_id,
        parent_session_id=parent_session_id,
    )


def summarize_text(text: str, *, limit: int = 160) -> str:
    return " ".join(text.split()).strip()[:limit] or "Execution memory"


def is_user_managed_source_kind(source_kind: str) -> bool:
    return source_kind in USER_MANAGED_SOURCE_KINDS


def _matches_secret(text: str) -> bool:
    return any(pattern.search(text) for pattern in SECRET_PATTERNS)


def _matches_injection(text: str) -> bool:
    return any(pattern.search(text) for pattern in INJECTION_PATTERNS)
