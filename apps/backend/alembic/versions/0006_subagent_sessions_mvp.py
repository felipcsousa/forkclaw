"""Add persisted subagent sessions and lifecycle runs."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0006_subagent_sessions_mvp"
down_revision = "0005_tool_catalog_policy_and_cache"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("sessions") as batch_op:
        batch_op.add_column(
            sa.Column("kind", sa.String(length=50), nullable=False, server_default="main")
        )
        batch_op.add_column(sa.Column("parent_session_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("root_session_id", sa.String(length=36), nullable=True))
        batch_op.add_column(
            sa.Column("spawn_depth", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.add_column(sa.Column("delegated_goal", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("delegated_context_snapshot", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("tool_profile", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("model_override", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("max_iterations", sa.Integer(), nullable=True))
        batch_op.create_index("ix_sessions_kind", ["kind"], unique=False)
        batch_op.create_index("ix_sessions_parent_session_id", ["parent_session_id"], unique=False)
        batch_op.create_index("ix_sessions_root_session_id", ["root_session_id"], unique=False)

    op.execute("UPDATE sessions SET kind = 'main' WHERE kind IS NULL OR kind = ''")
    op.execute("UPDATE sessions SET spawn_depth = 0 WHERE spawn_depth IS NULL")
    op.execute("UPDATE sessions SET parent_session_id = NULL")
    op.execute("UPDATE sessions SET root_session_id = id WHERE root_session_id IS NULL")

    op.create_table(
        "session_subagent_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("launcher_session_id", sa.String(length=36), nullable=False),
        sa.Column("child_session_id", sa.String(length=36), nullable=False),
        sa.Column("launcher_message_id", sa.String(length=36), nullable=True),
        sa.Column("launcher_task_run_id", sa.String(length=36), nullable=True),
        sa.Column("task_id", sa.String(length=36), nullable=True),
        sa.Column("task_run_id", sa.String(length=36), nullable=True),
        sa.Column("lifecycle_status", sa.String(length=50), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancellation_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("final_summary", sa.Text(), nullable=True),
        sa.Column("final_output_json", sa.Text(), nullable=True),
        sa.Column("estimated_cost_usd", sa.Float(), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["child_session_id"], ["sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["launcher_session_id"], ["sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["launcher_message_id"], ["messages.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["launcher_task_run_id"], ["task_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["task_run_id"], ["task_runs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_session_subagent_runs_lifecycle_status",
        "session_subagent_runs",
        ["lifecycle_status"],
    )
    op.create_index(
        "ix_session_subagent_runs_launcher_session_id",
        "session_subagent_runs",
        ["launcher_session_id"],
    )
    op.create_index(
        "ix_session_subagent_runs_child_session_id",
        "session_subagent_runs",
        ["child_session_id"],
    )

    with op.batch_alter_table("sessions") as batch_op:
        batch_op.alter_column("kind", server_default=None)
        batch_op.alter_column("spawn_depth", server_default=None)


def downgrade() -> None:
    op.drop_index(
        "ix_session_subagent_runs_child_session_id",
        table_name="session_subagent_runs",
    )
    op.drop_index(
        "ix_session_subagent_runs_launcher_session_id",
        table_name="session_subagent_runs",
    )
    op.drop_index(
        "ix_session_subagent_runs_lifecycle_status",
        table_name="session_subagent_runs",
    )
    op.drop_table("session_subagent_runs")

    with op.batch_alter_table("sessions") as batch_op:
        batch_op.drop_index("ix_sessions_root_session_id")
        batch_op.drop_index("ix_sessions_parent_session_id")
        batch_op.drop_index("ix_sessions_kind")
        batch_op.drop_column("max_iterations")
        batch_op.drop_column("model_override")
        batch_op.drop_column("tool_profile")
        batch_op.drop_column("delegated_context_snapshot")
        batch_op.drop_column("delegated_goal")
        batch_op.drop_column("spawn_depth")
        batch_op.drop_column("root_session_id")
        batch_op.drop_column("parent_session_id")
        batch_op.drop_column("kind")
