from __future__ import annotations

from sqlmodel import select

from app.db.session import get_db_session
from app.models.entities import Agent, MemoryEntry, Message, SessionRecord, SessionSummary, utc_now
from app.services.prompt_context_service import PromptContextService


def _seed_session(agent_id: str, *, title: str = "Memory Session") -> SessionRecord:
    with get_db_session() as session:
        record = SessionRecord(
            agent_id=agent_id,
            kind="main",
            title=title,
            conversation_id="conversation-current",
            status="active",
            root_session_id=None,
            spawn_depth=0,
        )
        record.root_session_id = record.id
        session.add(record)
        session.commit()
        session.refresh(record)
        return record


def _entry(
    *,
    agent_id: str,
    title: str,
    body: str,
    scope_key: str = "user/preferences",
    scope_type: str = "stable",
    source_kind: str = "manual",
    hidden_from_recall: bool = False,
    deleted: bool = False,
) -> MemoryEntry:
    return MemoryEntry(
        agent_id=agent_id,
        scope_type=scope_type,
        scope_key=scope_key,
        source_kind=source_kind,
        lifecycle_state="active",
        title=title,
        body=body,
        summary=body[:80],
        importance=0.5,
        confidence=1.0,
        dedupe_hash=f"dedupe-{title}-{source_kind}",
        created_by="user" if source_kind != "autosaved" else "system",
        updated_by="user" if source_kind != "autosaved" else "system",
        user_scope_key="local-user",
        hidden_from_recall=hidden_from_recall,
        deleted_at=utc_now() if deleted else None,
    )


def test_prompt_context_prioritizes_manual_and_user_override_over_automatic_memories(
    test_client,
) -> None:
    del test_client
    with get_db_session() as session:
        agent = session.exec(select(Agent)).one()
        session_record = _seed_session(agent.id)
        session.add_all(
            [
                _entry(
                    agent_id=agent.id,
                    title="reply-style",
                    body="Manual reply style",
                    source_kind="manual",
                ),
                _entry(
                    agent_id=agent.id,
                    title="reply-style",
                    body="Override reply style",
                    source_kind="user_override",
                ),
                _entry(
                    agent_id=agent.id,
                    title="reply-style",
                    body="Promoted reply style",
                    source_kind="promoted_from_session",
                ),
                _entry(
                    agent_id=agent.id,
                    title="reply-style",
                    body="Autosaved reply style",
                    source_kind="autosaved",
                ),
                _entry(
                    agent_id=agent.id,
                    title="timezone",
                    body="Override timezone",
                    source_kind="user_override",
                ),
                _entry(
                    agent_id=agent.id,
                    title="timezone",
                    body="Autosaved timezone",
                    source_kind="autosaved",
                ),
            ]
        )
        session.commit()

        resolved = PromptContextService(session).build_context(
            agent_id=agent.id,
            session_record=session_record,
            current_input="How should you answer me?",
        )

    included_text = "\n".join(layer.content for layer in resolved.layers)
    excluded = {(item.memory_key, item.reason) for item in resolved.excluded}

    assert "Manual reply style" in included_text
    assert "Override timezone" in included_text
    assert "Autosaved timezone" not in included_text
    assert "Autosaved reply style" not in included_text
    assert ("reply-style", "overridden") in excluded
    assert ("timezone", "overridden") in excluded


def test_prompt_context_never_includes_hidden_or_deleted_memories(test_client) -> None:
    del test_client
    with get_db_session() as session:
        agent = session.exec(select(Agent)).one()
        session_record = _seed_session(agent.id, title="Visibility Session")
        session.add_all(
            [
                _entry(
                    agent_id=agent.id,
                    title="favorite-color",
                    body="green",
                    hidden_from_recall=True,
                ),
                _entry(
                    agent_id=agent.id,
                    title="favorite-food",
                    body="pizza",
                    deleted=True,
                ),
            ]
        )
        session.commit()

        resolved = PromptContextService(session).build_context(
            agent_id=agent.id,
            session_record=session_record,
            current_input="What do I like?",
        )

    included_text = "\n".join(layer.content for layer in resolved.layers)
    excluded = {(item.memory_key, item.reason) for item in resolved.excluded}

    assert "green" not in included_text
    assert "pizza" not in included_text
    assert ("favorite-color", "hidden") in excluded
    assert ("favorite-food", "deleted") in excluded


def test_prompt_context_applies_fixed_layer_budgets_and_truncates_last_entry(test_client) -> None:
    del test_client
    with get_db_session() as session:
        agent = session.exec(select(Agent)).one()
        session_record = _seed_session(agent.id, title="Budget Session")
        session.add_all(
            [
                _entry(
                    agent_id=agent.id,
                    title=f"manual-{index}",
                    body=("M" * 950) + str(index),
                )
                for index in range(3)
            ]
        )
        session.commit()

        resolved = PromptContextService(session).build_context(
            agent_id=agent.id,
            session_record=session_record,
            current_input="Summarize what matters.",
        )

    manual_layer = next(layer for layer in resolved.layers if layer.key == "stable_manual")

    assert manual_layer.used_chars <= manual_layer.budget_chars == 2000
    assert manual_layer.content.endswith("...")
    assert any(item.reason == "budget" for item in resolved.excluded)


def test_update_conversation_summary_persists_current_conversation_summary(test_client) -> None:
    del test_client
    with get_db_session() as session:
        agent = session.exec(select(Agent)).one()
        agent_id = agent.id
        session_record = _seed_session(agent.id, title="Summary Session")
        session.add_all(
            [
                Message(
                    session_id=session_record.id,
                    conversation_id=session_record.conversation_id,
                    role="user",
                    status="committed",
                    sequence_number=1,
                    content_text="Remember the user prefers short answers.",
                ),
                Message(
                    session_id=session_record.id,
                    conversation_id=session_record.conversation_id,
                    role="assistant",
                    status="committed",
                    sequence_number=2,
                    content_text="Acknowledged. I will keep answers compact.",
                ),
            ]
        )
        session.commit()

        service = PromptContextService(session)
        summary = service.update_conversation_summary(
            agent_id=agent.id,
            session_record=session_record,
        )
        session.commit()

        persisted = session.exec(
            select(SessionSummary).where(SessionSummary.session_id == session_record.id)
        ).one()

    assert summary is not None
    assert persisted.agent_id == agent_id
    assert persisted.conversation_id == session_record.conversation_id
    assert persisted.source_kind == "summary"
    assert "user: Remember the user prefers short answers." in persisted.summary_text
