from __future__ import annotations

from sqlmodel import select

from app.db.session import get_db_session
from app.models.entities import Agent, Memory, SessionRecord
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


def _memory(
    *,
    agent_id: str,
    namespace: str,
    memory_key: str,
    value_text: str,
    source: str,
    memory_class: str = "stable",
    scope_kind: str = "agent",
    scope_ref: str | None = None,
    session_id: str | None = None,
    conversation_id: str | None = None,
    parent_session_id: str | None = None,
    status: str = "active",
) -> Memory:
    return Memory(
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
        status=status,
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
                _memory(
                    agent_id=agent.id,
                    namespace="preferences",
                    memory_key="reply-style",
                    value_text="Manual reply style",
                    source="manual",
                ),
                _memory(
                    agent_id=agent.id,
                    namespace="preferences",
                    memory_key="reply-style",
                    value_text="Override reply style",
                    source="user_override",
                ),
                _memory(
                    agent_id=agent.id,
                    namespace="preferences",
                    memory_key="reply-style",
                    value_text="Promoted reply style",
                    source="promoted",
                ),
                _memory(
                    agent_id=agent.id,
                    namespace="preferences",
                    memory_key="reply-style",
                    value_text="Autosaved reply style",
                    source="autosaved",
                ),
                _memory(
                    agent_id=agent.id,
                    namespace="preferences",
                    memory_key="timezone",
                    value_text="Override timezone",
                    source="user_override",
                ),
                _memory(
                    agent_id=agent.id,
                    namespace="preferences",
                    memory_key="timezone",
                    value_text="Autosaved timezone",
                    source="autosaved",
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
                _memory(
                    agent_id=agent.id,
                    namespace="preferences",
                    memory_key="favorite-color",
                    value_text="green",
                    source="manual",
                    status="hidden",
                ),
                _memory(
                    agent_id=agent.id,
                    namespace="preferences",
                    memory_key="favorite-food",
                    value_text="pizza",
                    source="manual",
                    status="deleted",
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
                _memory(
                    agent_id=agent.id,
                    namespace="notes",
                    memory_key=f"manual-{index}",
                    value_text=("M" * 950) + str(index),
                    source="manual",
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
