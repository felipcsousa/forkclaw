import time
from app.services.memory import MemoryService
from sqlmodel import Session, select
from app.models.entities import MemoryRecallLog, MemoryEntry, Agent, SessionSummary, Message
import pytest
from app.db.seed import seed_default_data
from uuid import uuid4


def test_recall_performance(test_client):
    from sqlalchemy import create_engine
    from sqlmodel import Session
    from app.core.config import get_settings

    settings = get_settings()
    engine = create_engine(settings.database_url)

    with Session(engine) as db_session:
        agent = db_session.exec(select(Agent).where(Agent.is_default == True)).first()
        if not agent:
            seed_default_data(db_session)
            agent = db_session.exec(select(Agent).where(Agent.is_default == True)).first()

        service = MemoryService(db_session)

        # Create entries
        entries = []
        for i in range(1000):
            entry = MemoryEntry(
                agent_id=agent.id,
                scope_type="episodic",
                scope_key="test",
                source_kind="manual",
                lifecycle_state="active",
                title=f"test {i}",
                body=f"test body {i}",
                summary="summary",
                importance=0.5,
                confidence=1.0,
                dedupe_hash=f"hash{i}",
                created_by="user",
                updated_by="user",
            )
            db_session.add(entry)
            entries.append(entry)

        db_session.commit()

        message_id = str(uuid4())
        msg = Message(
            id=message_id,
            conversation_id="conv",
            session_id="session",
            role="assistant",
            content_text="test",
            sequence_number=1,
            status="committed",
        )
        db_session.add(msg)

        # Create recall logs
        for i, entry in enumerate(entries):
            log = MemoryRecallLog(
                assistant_message_id=message_id,
                memory_id=entry.id,
                scope_type="episodic",
                scope_key="test",
                conversation_id="conv",
                session_id="session",
                run_id="run",
                recall_reason="test",
                decision="included",
                rank=i,
                record_type="memory_entry",
                record_id=entry.id,
                reason_json="{}",
            )
            db_session.add(log)

        db_session.commit()

        # Measure baseline
        start = time.perf_counter()
        res = service.recall_for_message(message_id)
        end = time.perf_counter()

        print(
            f"\nTime taken for recall_for_message with 1000 entries: {(end - start) * 1000:.2f}ms"
        )
