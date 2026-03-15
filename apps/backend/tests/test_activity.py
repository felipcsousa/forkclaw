from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlmodel import Session

from app.db.session import get_db_session
from app.models.entities import Task, TaskRun
from app.repositories.activity import ActivityRepository
from app.repositories.cron_jobs import CronJobRepository


def _suppress_scheduler_heartbeat(session: Session) -> None:
    CronJobRepository(session).upsert_setting(
        scope="heartbeat",
        key="last_run_at",
        value_type="string",
        value_text=datetime.now(UTC).isoformat(),
    )


def test_get_activity_timeline_empty(test_client: TestClient):
    with get_db_session() as session:
        # Delete any seeded data
        session.execute(text("DELETE FROM audit_events"))
        session.execute(text("DELETE FROM task_runs"))
        session.execute(text("DELETE FROM tasks"))
        _suppress_scheduler_heartbeat(session)
        session.commit()

    response = test_client.get("/activity/timeline")
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    # FastAPI may omit `next_cursor` when it is None.
    assert "next_cursor" not in data or data["next_cursor"] is None


def test_get_activity_timeline_with_items(test_client: TestClient):
    with get_db_session() as session:
        # Delete any seeded data
        session.execute(text("DELETE FROM audit_events"))
        session.execute(text("DELETE FROM task_runs"))
        session.execute(text("DELETE FROM tasks"))
        _suppress_scheduler_heartbeat(session)
        session.commit()

        repo = ActivityRepository(session)
        agent = repo.get_default_agent()

        # Create test data
        task1 = Task(agent_id=agent.id, title="Task 1", kind="agent_execution", status="completed")
        session.add(task1)
        session.commit()

        task_run1 = TaskRun(task_id=task1.id, status="completed", attempt=1)
        session.add(task_run1)
        session.commit()

        task2 = Task(agent_id=agent.id, title="Task 2", kind="agent_execution", status="completed")
        session.add(task2)
        session.commit()

        task_run2 = TaskRun(task_id=task2.id, status="completed", attempt=1)
        session.add(task_run2)
        session.commit()

        task3 = Task(agent_id=agent.id, title="Task 3", kind="agent_execution", status="completed")
        session.add(task3)
        session.commit()

        task_run3 = TaskRun(task_id=task3.id, status="completed", attempt=1)
        session.add(task_run3)
        session.commit()

    # Default request, no limit
    response = test_client.get("/activity/timeline")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 3
    assert "next_cursor" not in data or data["next_cursor"] is None

    # Pagination: first page
    response_page1 = test_client.get("/activity/timeline?limit=2")
    assert response_page1.status_code == 200
    data_page1 = response_page1.json()
    assert len(data_page1["items"]) == 2
    assert "next_cursor" in data_page1 and data_page1["next_cursor"] is not None

    # Pagination: second page
    cursor = data_page1["next_cursor"]
    response_page2 = test_client.get(f"/activity/timeline?limit=2&cursor={cursor}")
    assert response_page2.status_code == 200
    data_page2 = response_page2.json()
    # If there are exactly 3 items and limit=2, the second page should have 1 item
    assert len(data_page2["items"]) == 1
    assert "next_cursor" not in data_page2 or data_page2["next_cursor"] is None


def test_get_activity_timeline_invalid_cursor(test_client: TestClient):
    response = test_client.get("/activity/timeline?cursor=invalid_cursor_string")
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == "Invalid activity cursor."
