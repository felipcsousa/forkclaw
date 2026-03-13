"""Finalize Memory Recall V1 schema, backfills, and FTS indexes."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0010_memory_recall_v1"
down_revision = "0009_memory_runtime_v1"
branch_labels = None
depends_on = None


def _now() -> datetime:
    return datetime.now(UTC)


def _table_exists(table_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table_name in inspector.get_table_names()


def _column_names(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {column["name"] for column in inspector.get_columns(table_name)}


def _index_names(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {index["name"] for index in inspector.get_indexes(table_name)}


def _add_column_if_missing(table_name: str, column: sa.Column[object]) -> None:
    if column.name in _column_names(table_name):
        return
    with op.batch_alter_table(table_name) as batch_op:
        batch_op.add_column(column)


def _create_index_if_missing(
    table_name: str,
    index_name: str,
    columns: list[str],
) -> None:
    if index_name in _index_names(table_name):
        return
    with op.batch_alter_table(table_name) as batch_op:
        batch_op.create_index(index_name, columns, unique=False)


def upgrade() -> None:
    if not _table_exists("memory_entries") or not _table_exists("session_summaries"):
        return

    _upgrade_memory_entries()
    _upgrade_session_summaries()
    _upgrade_memory_recall_log()
    _backfill_session_summaries_from_sessions()
    _rebuild_memory_fts()


def _upgrade_memory_entries() -> None:
    _add_column_if_missing(
        "memory_entries", sa.Column("agent_id", sa.String(length=36), nullable=True)
    )
    _add_column_if_missing(
        "memory_entries",
        sa.Column("root_session_id", sa.String(length=36), nullable=True),
    )
    _add_column_if_missing(
        "memory_entries",
        sa.Column("workspace_path", sa.Text(), nullable=True),
    )
    _add_column_if_missing(
        "memory_entries",
        sa.Column("user_scope_key", sa.String(length=100), nullable=True),
    )
    _add_column_if_missing(
        "memory_entries",
        sa.Column("origin_message_id", sa.String(length=36), nullable=True),
    )
    _add_column_if_missing(
        "memory_entries",
        sa.Column("origin_task_run_id", sa.String(length=36), nullable=True),
    )
    _add_column_if_missing(
        "memory_entries",
        sa.Column("override_target_entry_id", sa.String(length=36), nullable=True),
    )

    op.execute(
        """
        UPDATE memory_entries
        SET root_session_id = (
            SELECT COALESCE(sessions.root_session_id, sessions.id)
            FROM sessions
            WHERE sessions.id = memory_entries.session_id
        )
        WHERE root_session_id IS NULL
          AND session_id IS NOT NULL
        """
    )
    if _table_exists("memories"):
        memory_columns = _column_names("memories")
        if "agent_id" in memory_columns:
            op.execute(
                """
                UPDATE memory_entries
                SET agent_id = (
                    SELECT memories.agent_id
                    FROM memories
                    WHERE memories.id = memory_entries.id
                )
                WHERE agent_id IS NULL
                  AND EXISTS (
                    SELECT 1
                    FROM memories
                    WHERE memories.id = memory_entries.id
                  )
                """
            )
    op.execute(
        """
        UPDATE memory_entries
        SET user_scope_key = 'local-user'
        WHERE user_scope_key IS NULL
          AND created_by = 'user'
        """
    )

    _create_index_if_missing("memory_entries", "ix_memory_entries_agent_id", ["agent_id"])
    _create_index_if_missing(
        "memory_entries",
        "ix_memory_entries_root_session_id",
        ["root_session_id"],
    )
    _create_index_if_missing(
        "memory_entries",
        "ix_memory_entries_override_target_entry_id",
        ["override_target_entry_id"],
    )


def _upgrade_session_summaries() -> None:
    summary_columns = _column_names("session_summaries")
    if "summary_text" not in summary_columns and "summary" in summary_columns:
        _add_column_if_missing(
            "session_summaries", sa.Column("summary_text", sa.Text(), nullable=True)
        )
        op.execute(
            """
            UPDATE session_summaries
            SET summary_text = summary
            WHERE summary_text IS NULL
            """
        )

    _add_column_if_missing(
        "session_summaries", sa.Column("agent_id", sa.String(length=36), nullable=True)
    )
    _add_column_if_missing(
        "session_summaries",
        sa.Column("root_session_id", sa.String(length=36), nullable=True),
    )
    _add_column_if_missing(
        "session_summaries",
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    _add_column_if_missing(
        "session_summaries",
        sa.Column("importance", sa.Float(), nullable=True),
    )
    _add_column_if_missing(
        "session_summaries",
        sa.Column("workspace_path", sa.Text(), nullable=True),
    )
    _add_column_if_missing(
        "session_summaries",
        sa.Column("user_scope_key", sa.String(length=100), nullable=True),
    )
    _add_column_if_missing(
        "session_summaries",
        sa.Column("hidden_from_recall", sa.Boolean(), nullable=True, server_default=sa.text("0")),
    )
    _add_column_if_missing(
        "session_summaries",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    _add_column_if_missing(
        "session_summaries",
        sa.Column("origin_message_id", sa.String(length=36), nullable=True),
    )
    _add_column_if_missing(
        "session_summaries",
        sa.Column("origin_task_run_id", sa.String(length=36), nullable=True),
    )
    _add_column_if_missing(
        "session_summaries",
        sa.Column("override_target_summary_id", sa.String(length=36), nullable=True),
    )

    op.execute(
        """
        UPDATE session_summaries
        SET updated_at = created_at
        WHERE updated_at IS NULL
        """
    )
    op.execute(
        """
        UPDATE session_summaries
        SET importance = 0.0
        WHERE importance IS NULL
        """
    )
    op.execute(
        """
        UPDATE session_summaries
        SET hidden_from_recall = 0
        WHERE hidden_from_recall IS NULL
        """
    )
    op.execute(
        """
        UPDATE session_summaries
        SET root_session_id = (
            SELECT COALESCE(sessions.root_session_id, sessions.id)
            FROM sessions
            WHERE sessions.id = session_summaries.session_id
        )
        WHERE root_session_id IS NULL
          AND session_id IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE session_summaries
        SET agent_id = (
            SELECT sessions.agent_id
            FROM sessions
            WHERE sessions.id = session_summaries.session_id
        )
        WHERE agent_id IS NULL
          AND session_id IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE session_summaries
        SET conversation_id = (
            SELECT sessions.conversation_id
            FROM sessions
            WHERE sessions.id = session_summaries.session_id
        )
        WHERE conversation_id IS NULL
          AND session_id IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE session_summaries
        SET user_scope_key = 'local-user'
        WHERE user_scope_key IS NULL
          AND created_by = 'user'
        """
    )

    _create_index_if_missing("session_summaries", "ix_session_summaries_agent_id", ["agent_id"])
    _create_index_if_missing(
        "session_summaries",
        "ix_session_summaries_root_session_id",
        ["root_session_id"],
    )
    _create_index_if_missing(
        "session_summaries",
        "ix_session_summaries_override_target_summary_id",
        ["override_target_summary_id"],
    )


def _upgrade_memory_recall_log() -> None:
    if not _table_exists("memory_recall_log"):
        return

    _add_column_if_missing(
        "memory_recall_log",
        sa.Column("assistant_message_id", sa.String(length=36), nullable=True),
    )
    _add_column_if_missing(
        "memory_recall_log",
        sa.Column("record_type", sa.String(length=50), nullable=True),
    )
    _add_column_if_missing(
        "memory_recall_log",
        sa.Column("record_id", sa.String(length=36), nullable=True),
    )
    _add_column_if_missing(
        "memory_recall_log",
        sa.Column("query_text", sa.Text(), nullable=True),
    )
    _add_column_if_missing(
        "memory_recall_log",
        sa.Column("score", sa.Float(), nullable=True),
    )
    _add_column_if_missing(
        "memory_recall_log",
        sa.Column("reason_json", sa.Text(), nullable=True),
    )
    _add_column_if_missing(
        "memory_recall_log",
        sa.Column("reason_summary", sa.Text(), nullable=True),
    )
    _add_column_if_missing(
        "memory_recall_log",
        sa.Column("source_kind", sa.String(length=50), nullable=True),
    )
    _add_column_if_missing(
        "memory_recall_log",
        sa.Column("override_status", sa.String(length=50), nullable=True),
    )
    _add_column_if_missing(
        "memory_recall_log",
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.execute(
        """
        UPDATE memory_recall_log
        SET updated_at = created_at
        WHERE updated_at IS NULL
        """
    )
    op.execute(
        """
        UPDATE memory_recall_log
        SET record_type = COALESCE(
            record_type,
            CASE WHEN memory_id IS NOT NULL THEN 'memory_entry' END
        )
        WHERE record_type IS NULL
        """
    )
    op.execute(
        """
        UPDATE memory_recall_log
        SET record_id = COALESCE(record_id, memory_id)
        WHERE record_id IS NULL
          AND memory_id IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE memory_recall_log
        SET reason_json = '{}'
        WHERE reason_json IS NULL
        """
    )
    op.execute(
        """
        UPDATE memory_recall_log
        SET override_status = 'none'
        WHERE override_status IS NULL
        """
    )

    _create_index_if_missing(
        "memory_recall_log",
        "ix_memory_recall_log_assistant_message_id",
        ["assistant_message_id"],
    )
    _create_index_if_missing("memory_recall_log", "ix_memory_recall_log_run_id", ["run_id"])
    _create_index_if_missing(
        "memory_recall_log",
        "ix_memory_recall_log_record_type",
        ["record_type"],
    )
    _create_index_if_missing(
        "memory_recall_log",
        "ix_memory_recall_log_record_id",
        ["record_id"],
    )


def _backfill_session_summaries_from_sessions() -> None:
    connection = op.get_bind()
    rows = connection.execute(
        sa.text(
            """
            SELECT
                sessions.id,
                sessions.agent_id,
                sessions.root_session_id,
                sessions.conversation_id,
                sessions.parent_session_id,
                sessions.summary,
                sessions.created_at,
                sessions.updated_at
            FROM sessions
            WHERE sessions.summary IS NOT NULL
              AND trim(sessions.summary) != ''
            """
        )
    ).mappings()
    now = _now()
    for row in rows:
        exists = connection.execute(
            sa.text(
                """
                SELECT 1
                FROM session_summaries
                WHERE session_id = :session_id
                LIMIT 1
                """
            ),
            {"session_id": row["id"]},
        ).scalar()
        if exists:
            continue

        connection.execute(
            sa.text(
                """
                INSERT INTO session_summaries (
                    id,
                    agent_id,
                    scope_key,
                    session_id,
                    root_session_id,
                    conversation_id,
                    parent_session_id,
                    task_run_id,
                    source_kind,
                    summary_text,
                    importance,
                    created_by,
                    workspace_path,
                    user_scope_key,
                    hidden_from_recall,
                    deleted_at,
                    origin_message_id,
                    origin_task_run_id,
                    override_target_summary_id,
                    created_at,
                    updated_at
                )
                VALUES (
                    :id,
                    :agent_id,
                    :scope_key,
                    :session_id,
                    :root_session_id,
                    :conversation_id,
                    :parent_session_id,
                    NULL,
                    :source_kind,
                    :summary_text,
                    0.0,
                    'migration',
                    NULL,
                    'local-user',
                    0,
                    NULL,
                    NULL,
                    NULL,
                    NULL,
                    :created_at,
                    :updated_at
                )
                """
            ),
            {
                "id": str(uuid4()),
                "agent_id": row["agent_id"],
                "scope_key": f"session:{row['id']}",
                "session_id": row["id"],
                "root_session_id": row["root_session_id"] or row["id"],
                "conversation_id": row["conversation_id"],
                "parent_session_id": row["parent_session_id"],
                "source_kind": "summary",
                "summary_text": row["summary"],
                "created_at": row["created_at"] or now,
                "updated_at": row["updated_at"] or row["created_at"] or now,
            },
        )


def _rebuild_memory_fts() -> None:
    op.execute("DROP TRIGGER IF EXISTS session_summaries_au")
    op.execute("DROP TRIGGER IF EXISTS session_summaries_ad")
    op.execute("DROP TRIGGER IF EXISTS session_summaries_ai")
    op.execute("DROP TRIGGER IF EXISTS memory_entries_au")
    op.execute("DROP TRIGGER IF EXISTS memory_entries_ad")
    op.execute("DROP TRIGGER IF EXISTS memory_entries_ai")
    op.execute("DROP TABLE IF EXISTS session_summaries_fts")
    op.execute("DROP TABLE IF EXISTS memory_entries_fts")

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
            summary_text,
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
            INSERT INTO session_summaries_fts(rowid, summary_text)
            VALUES (new.rowid, coalesce(new.summary_text, ''));
        END
        """
    )
    op.execute(
        """
        CREATE TRIGGER session_summaries_ad AFTER DELETE ON session_summaries BEGIN
            INSERT INTO session_summaries_fts(session_summaries_fts, rowid, summary_text)
            VALUES ('delete', old.rowid, coalesce(old.summary_text, ''));
        END
        """
    )
    op.execute(
        """
        CREATE TRIGGER session_summaries_au AFTER UPDATE ON session_summaries BEGIN
            INSERT INTO session_summaries_fts(session_summaries_fts, rowid, summary_text)
            VALUES ('delete', old.rowid, coalesce(old.summary_text, ''));
            INSERT INTO session_summaries_fts(rowid, summary_text)
            VALUES (new.rowid, coalesce(new.summary_text, ''));
        END
        """
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
