"""Add Memory Recall V1 tables, FTS indexes, and recall logging."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0008_memory_recall_v1"
down_revision = "0007_subagent_runtime_hardening"
branch_labels = None
depends_on = None


def _now() -> datetime:
    return datetime.now(UTC)


def upgrade() -> None:
    op.create_table(
        "memory_entries",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("agent_id", sa.String(length=36), nullable=True),
        sa.Column("session_id", sa.String(length=36), nullable=True),
        sa.Column("root_session_id", sa.String(length=36), nullable=True),
        sa.Column("workspace_path", sa.Text(), nullable=True),
        sa.Column("user_scope_key", sa.String(length=100), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("source_kind", sa.String(length=50), nullable=False),
        sa.Column("importance", sa.Float(), nullable=False, server_default="0"),
        sa.Column("hidden_from_recall", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("origin_message_id", sa.String(length=36), nullable=True),
        sa.Column("origin_task_run_id", sa.String(length=36), nullable=True),
        sa.Column("override_target_entry_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["root_session_id"], ["sessions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["origin_message_id"], ["messages.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["origin_task_run_id"], ["task_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["override_target_entry_id"],
            ["memory_entries.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_memory_entries_agent_id", "memory_entries", ["agent_id"])
    op.create_index("ix_memory_entries_session_id", "memory_entries", ["session_id"])
    op.create_index("ix_memory_entries_root_session_id", "memory_entries", ["root_session_id"])
    op.create_index("ix_memory_entries_source_kind", "memory_entries", ["source_kind"])
    op.execute(
        """
        CREATE UNIQUE INDEX uq_memory_entries_active_manual_override_target
        ON memory_entries (override_target_entry_id)
        WHERE override_target_entry_id IS NOT NULL
          AND source_kind = 'manual'
          AND deleted_at IS NULL
        """
    )

    op.create_table(
        "session_summaries",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("agent_id", sa.String(length=36), nullable=True),
        sa.Column("session_id", sa.String(length=36), nullable=True),
        sa.Column("root_session_id", sa.String(length=36), nullable=True),
        sa.Column("workspace_path", sa.Text(), nullable=True),
        sa.Column("user_scope_key", sa.String(length=100), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("source_kind", sa.String(length=50), nullable=False),
        sa.Column("importance", sa.Float(), nullable=False, server_default="0"),
        sa.Column("hidden_from_recall", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("origin_message_id", sa.String(length=36), nullable=True),
        sa.Column("origin_task_run_id", sa.String(length=36), nullable=True),
        sa.Column("override_target_summary_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["root_session_id"], ["sessions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["origin_message_id"], ["messages.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["origin_task_run_id"], ["task_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["override_target_summary_id"],
            ["session_summaries.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_session_summaries_agent_id", "session_summaries", ["agent_id"])
    op.create_index("ix_session_summaries_session_id", "session_summaries", ["session_id"])
    op.create_index(
        "ix_session_summaries_root_session_id",
        "session_summaries",
        ["root_session_id"],
    )
    op.create_index("ix_session_summaries_source_kind", "session_summaries", ["source_kind"])
    op.execute(
        """
        CREATE UNIQUE INDEX uq_session_summaries_active_manual_override_target
        ON session_summaries (override_target_summary_id)
        WHERE override_target_summary_id IS NOT NULL
          AND source_kind = 'manual'
          AND deleted_at IS NULL
        """
    )

    op.create_table(
        "memory_recall_log",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("run_id", sa.String(length=100), nullable=True),
        sa.Column("record_type", sa.String(length=50), nullable=False),
        sa.Column("record_id", sa.String(length=36), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("reason_json", sa.Text(), nullable=False),
        sa.Column("source_kind", sa.String(length=50), nullable=False),
        sa.Column("override_status", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_memory_recall_log_run_id", "memory_recall_log", ["run_id"])
    op.create_index("ix_memory_recall_log_record_type", "memory_recall_log", ["record_type"])
    op.create_index("ix_memory_recall_log_record_id", "memory_recall_log", ["record_id"])

    op.execute(
        """
        CREATE VIRTUAL TABLE memory_entries_fts USING fts5(
            body,
            summary,
            content='memory_entries',
            content_rowid='rowid'
        )
        """
    )
    op.execute(
        """
        CREATE VIRTUAL TABLE session_summaries_fts USING fts5(
            summary,
            content='session_summaries',
            content_rowid='rowid'
        )
        """
    )

    op.execute(
        """
        CREATE TRIGGER memory_entries_ai AFTER INSERT ON memory_entries BEGIN
            INSERT INTO memory_entries_fts(rowid, body, summary)
            VALUES (new.rowid, coalesce(new.body, ''), coalesce(new.summary, ''));
        END
        """
    )
    op.execute(
        """
        CREATE TRIGGER memory_entries_ad AFTER DELETE ON memory_entries BEGIN
            INSERT INTO memory_entries_fts(memory_entries_fts, rowid, body, summary)
            VALUES ('delete', old.rowid, coalesce(old.body, ''), coalesce(old.summary, ''));
        END
        """
    )
    op.execute(
        """
        CREATE TRIGGER memory_entries_au AFTER UPDATE ON memory_entries BEGIN
            INSERT INTO memory_entries_fts(memory_entries_fts, rowid, body, summary)
            VALUES ('delete', old.rowid, coalesce(old.body, ''), coalesce(old.summary, ''));
            INSERT INTO memory_entries_fts(rowid, body, summary)
            VALUES (new.rowid, coalesce(new.body, ''), coalesce(new.summary, ''));
        END
        """
    )
    op.execute(
        """
        CREATE TRIGGER session_summaries_ai AFTER INSERT ON session_summaries BEGIN
            INSERT INTO session_summaries_fts(rowid, summary)
            VALUES (new.rowid, coalesce(new.summary, ''));
        END
        """
    )
    op.execute(
        """
        CREATE TRIGGER session_summaries_ad AFTER DELETE ON session_summaries BEGIN
            INSERT INTO session_summaries_fts(session_summaries_fts, rowid, summary)
            VALUES ('delete', old.rowid, coalesce(old.summary, ''));
        END
        """
    )
    op.execute(
        """
        CREATE TRIGGER session_summaries_au AFTER UPDATE ON session_summaries BEGIN
            INSERT INTO session_summaries_fts(session_summaries_fts, rowid, summary)
            VALUES ('delete', old.rowid, coalesce(old.summary, ''));
            INSERT INTO session_summaries_fts(rowid, summary)
            VALUES (new.rowid, coalesce(new.summary, ''));
        END
        """
    )

    connection = op.get_bind()
    session_rows = connection.execute(
        sa.text(
            """
            SELECT id, agent_id, root_session_id, summary, created_at, updated_at
            FROM sessions
            WHERE summary IS NOT NULL AND trim(summary) != ''
            """
        )
    ).mappings()
    now = _now()
    for row in session_rows:
        connection.execute(
            sa.text(
                """
                INSERT INTO session_summaries (
                    id,
                    agent_id,
                    session_id,
                    root_session_id,
                    workspace_path,
                    user_scope_key,
                    summary,
                    source_kind,
                    importance,
                    hidden_from_recall,
                    deleted_at,
                    origin_message_id,
                    origin_task_run_id,
                    override_target_summary_id,
                    created_at,
                    updated_at
                ) VALUES (
                    :id,
                    :agent_id,
                    :session_id,
                    :root_session_id,
                    :workspace_path,
                    :user_scope_key,
                    :summary,
                    :source_kind,
                    :importance,
                    :hidden_from_recall,
                    :deleted_at,
                    :origin_message_id,
                    :origin_task_run_id,
                    :override_target_summary_id,
                    :created_at,
                    :updated_at
                )
                """
            ),
            {
                "id": str(uuid4()),
                "agent_id": row["agent_id"],
                "session_id": row["id"],
                "root_session_id": row["root_session_id"] or row["id"],
                "workspace_path": None,
                "user_scope_key": "local-user",
                "summary": row["summary"],
                "source_kind": "automatic",
                "importance": 0.0,
                "hidden_from_recall": 0,
                "deleted_at": None,
                "origin_message_id": None,
                "origin_task_run_id": None,
                "override_target_summary_id": None,
                "created_at": row["created_at"] or now,
                "updated_at": row["updated_at"] or now,
            },
        )

    op.execute("INSERT INTO memory_entries_fts(memory_entries_fts) VALUES ('rebuild')")
    op.execute("INSERT INTO session_summaries_fts(session_summaries_fts) VALUES ('rebuild')")


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS session_summaries_au")
    op.execute("DROP TRIGGER IF EXISTS session_summaries_ad")
    op.execute("DROP TRIGGER IF EXISTS session_summaries_ai")
    op.execute("DROP TRIGGER IF EXISTS memory_entries_au")
    op.execute("DROP TRIGGER IF EXISTS memory_entries_ad")
    op.execute("DROP TRIGGER IF EXISTS memory_entries_ai")

    op.execute("DROP TABLE IF EXISTS session_summaries_fts")
    op.execute("DROP TABLE IF EXISTS memory_entries_fts")

    op.drop_index("ix_memory_recall_log_record_id", table_name="memory_recall_log")
    op.drop_index("ix_memory_recall_log_record_type", table_name="memory_recall_log")
    op.drop_index("ix_memory_recall_log_run_id", table_name="memory_recall_log")
    op.drop_table("memory_recall_log")

    op.drop_index(
        "uq_session_summaries_active_manual_override_target",
        table_name="session_summaries",
    )
    op.drop_index("ix_session_summaries_source_kind", table_name="session_summaries")
    op.drop_index("ix_session_summaries_root_session_id", table_name="session_summaries")
    op.drop_index("ix_session_summaries_session_id", table_name="session_summaries")
    op.drop_index("ix_session_summaries_agent_id", table_name="session_summaries")
    op.drop_table("session_summaries")

    op.drop_index(
        "uq_memory_entries_active_manual_override_target",
        table_name="memory_entries",
    )
    op.drop_index("ix_memory_entries_source_kind", table_name="memory_entries")
    op.drop_index("ix_memory_entries_root_session_id", table_name="memory_entries")
    op.drop_index("ix_memory_entries_session_id", table_name="memory_entries")
    op.drop_index("ix_memory_entries_agent_id", table_name="memory_entries")
    op.drop_table("memory_entries")
