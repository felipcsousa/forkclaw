import os
import sys
import time

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from app.db.session import get_db_session, get_engine
from app.services.subagents import SubagentDelegationService
from app.repositories.subagents import SubagentRepository
from app.models.entities import SessionRecord, SessionSubagentRun, generate_id, utc_now, Agent
from sqlmodel import SQLModel, select

SQLModel.metadata.create_all(get_engine())

def setup_data(num_runs):
    with get_db_session() as session:
        repo = SubagentRepository(session)

        # Create an agent first to satisfy foreign key constraint
        agent = Agent(
            id="test_agent",
            name="Test Agent",
            slug="test_agent",
            status="active"
        )
        session.add(agent)
        session.flush()

        main_session = SessionRecord(
            agent_id=agent.id,
            kind="main",
            parent_session_id=None,
            root_session_id=None,
            spawn_depth=0,
            title="Main",
            summary=None,
            conversation_id=generate_id(),
            status="active",
            delegated_goal=None,
            delegated_context_snapshot=None,
            tool_profile=None,
            model_override=None,
            max_iterations=None,
            timeout_seconds=None,
            started_at=utc_now()
        )
        session.add(main_session)
        session.flush()

        for i in range(num_runs):
            child = repo.create_subagent_session(
                agent_id=agent.id,
                parent_session=main_session,
                delegated_goal=f"Goal {i}",
                delegated_context_snapshot=None,
                tool_profile=None,
                model_override=None,
                max_iterations=None,
                timeout_seconds=None
            )

            run = repo.create_subagent_run(
                launcher_session_id=main_session.id,
                child_session_id=child.id
            )
            session.add(run)

        session.commit()

def benchmark_baseline():
    num_runs = 1000
    setup_data(num_runs)

    with get_db_session() as session:
        repo = SubagentRepository(session)
        runs = session.exec(select(SessionSubagentRun)).all()

        start_time = time.perf_counter()

        for run in runs:
            child = repo.get_session(run.child_session_id)
            parent = repo.get_session(run.launcher_session_id)

        end_time = time.perf_counter()

        elapsed = end_time - start_time
        print(f"Baseline for {num_runs} runs (N+1 queries): {elapsed:.4f} seconds")

def benchmark_optimized():
    num_runs = 1000

    with get_db_session() as session:
        repo = SubagentRepository(session)
        runs = session.exec(select(SessionSubagentRun)).all()

        start_time = time.perf_counter()

        for run in runs:
            sessions = repo.get_sessions([run.child_session_id, run.launcher_session_id])
            child = next((s for s in sessions if s.id == run.child_session_id), None)
            parent = next((s for s in sessions if s.id == run.launcher_session_id), None)

        end_time = time.perf_counter()

        elapsed = end_time - start_time
        print(f"Optimized for {num_runs} runs (single IN query): {elapsed:.4f} seconds")


if __name__ == "__main__":
    benchmark_baseline()

    # We will only run optimized benchmark later
    try:
        benchmark_optimized()
    except AttributeError:
        print("get_sessions not implemented yet. Skipping optimized benchmark.")
