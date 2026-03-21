from __future__ import annotations

import pytest

from app.db.session import get_db_session
from app.services.agent_os import AgentOSService


def test_agent_os_service_error_handling(test_client):
    with get_db_session() as session:
        service = AgentOSService(session)

        # We need to temporarily remove the default agent to trigger this
        from sqlmodel import select

        from app.models.entities import Agent

        agents = session.exec(select(Agent)).all()
        for agent in agents:
            session.delete(agent)
        session.commit()

        # get_default_agent_bundle without an agent
        agent, profile = service.get_default_agent_bundle()
        assert agent is None
        assert profile is None

        with pytest.raises(ValueError, match="Default agent not found."):
            service.create_session("Test")

        with pytest.raises(ValueError, match="Session not found."):
            service.reset_session_conversation("invalid-id")

def test_agent_os_service_success_paths(test_client):
    with get_db_session() as session:
        service = AgentOSService(session)

        # Create a session
        created = service.create_session("My Session")
        assert created.title == "My Session"

        # Create a session without title
        created_default = service.create_session(None)
        assert created_default.title == "New Session"

        # Get session
        retrieved = service.get_session(created.id)
        assert retrieved.id == created.id

        # List sessions
        sessions = service.list_sessions()
        assert len(sessions) >= 2
        assert any(s.id == created.id for s in sessions)

        # Reset conversation
        reset = service.reset_session_conversation(created.id)
        assert reset.id == created.id

        # Check list session messages with valid ID
        import uuid

        from app.models.entities import Message

        # Add a test message to the session
        msg = Message(
            id=str(uuid.uuid4()),
            session_id=created.id,
            sequence=1,
            sequence_number=1,
            role="user",
            content_text="Hello",
            conversation_id=reset.conversation_id
        )
        session.add(msg)
        session.commit()

        record, messages, has_more, next_seq = service.list_session_messages(
            created.id,
            limit=10,
            before_sequence=None
        )
        assert record.id == created.id
        assert len(messages) >= 1
        assert has_more is False
        assert next_seq is None

        # Test again without limit to cover another branch
        record2, messages2, has_more2, next_seq2 = service.list_session_messages(
            created.id
        )
        assert record2.id == created.id
        assert len(messages2) >= 1
        assert has_more2 is None
        assert next_seq2 is None

        # Check list session messages with invalid ID
        record, messages, has_more, next_seq = service.list_session_messages("invalid")
        assert record is None
        assert messages == []

        # Check list settings
        settings = service.list_settings()
        assert isinstance(settings, list)

def test_agent_os_service_reset_wrong_kind(test_client):
    with get_db_session() as session:
        service = AgentOSService(session)

        # Create a subagent session
        import uuid

        from app.models.entities import SessionRecord

        agent, _ = service.get_default_agent_bundle()

        sub_session = SessionRecord(
            id=str(uuid.uuid4()),
            agent_id=agent.id,
            title="Sub Session",
            kind="subagent",
            conversation_id=str(uuid.uuid4())
        )
        session.add(sub_session)
        session.commit()

        with pytest.raises(ValueError, match="Only main sessions can reset conversation state."):
            service.reset_session_conversation(sub_session.id)
