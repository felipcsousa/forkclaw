"""Add Memory V1 canonical admin-core tables."""

from __future__ import annotations

import hashlib
import unicodedata
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0008_memory_v1_admin_core"
down_revision = "0007_subagent_runtime_hardening"
branch_labels = None
depends_on = None


def _dedupe_hash(title: str, body: str, summary: str | None) -> str:
    parts = [title, body, summary or ""]
    normalized = []
    for part in parts:
        value = unicodedata.normalize("NFKC", part or "").lower()
        normalized.append(" ".join(value.split()).strip())
    payload = "||".join(normalized)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def upgrade() -> None:
    op.create_table(
        "memory_entries",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("scope_type", sa.String(length=50), nullable=False),
        sa.Column("scope_key", sa.String(length=255), nullable=False),
        sa.Column("conversation_id", sa.String(length=100), nullable=True),
        sa.Column("session_id", sa.String(length=36), nullable=True),
        sa.Column("parent_session_id", sa.String(length=36), nullable=True),
        sa.Column("source_kind", sa.String(length=50), nullable=False),
        sa.Column("lifecycle_state", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("importance", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("dedupe_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(length=100), nullable=False),
        sa.Column("updated_by", sa.String(length=100), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("redaction_state", sa.String(length=20), nullable=False),
        sa.Column("security_state", sa.String(length=20), nullable=False),
        sa.Column("hidden_from_recall", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_memory_entries_scope_type_scope_key",
        "memory_entries",
        ["scope_type", "scope_key"],
    )
    op.create_index("ix_memory_entries_dedupe_hash", "memory_entries", ["dedupe_hash"])
    op.create_index("ix_memory_entries_conversation_id", "memory_entries", ["conversation_id"])
    op.create_index("ix_memory_entries_session_id", "memory_entries", ["session_id"])
    op.create_index(
        "ix_memory_entries_parent_session_id",
        "memory_entries",
        ["parent_session_id"],
    )
    op.create_index("ix_memory_entries_source_kind", "memory_entries", ["source_kind"])
    op.create_index(
        "ix_memory_entries_lifecycle_state",
        "memory_entries",
        ["lifecycle_state"],
    )
    op.create_index(
        "ix_memory_entries_hidden_from_recall",
        "memory_entries",
        ["hidden_from_recall"],
    )

    op.create_table(
        "memory_relations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("from_memory_id", sa.String(length=36), nullable=False),
        sa.Column("to_memory_id", sa.String(length=36), nullable=False),
        sa.Column("relation_kind", sa.String(length=100), nullable=False),
        sa.Column("created_by", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_memory_relations_from_memory_id", "memory_relations", ["from_memory_id"])
    op.create_index("ix_memory_relations_to_memory_id", "memory_relations", ["to_memory_id"])

    op.create_table(
        "memory_recall_log",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("memory_id", sa.String(length=36), nullable=False),
        sa.Column("scope_type", sa.String(length=50), nullable=False),
        sa.Column("scope_key", sa.String(length=255), nullable=False),
        sa.Column("conversation_id", sa.String(length=100), nullable=True),
        sa.Column("session_id", sa.String(length=36), nullable=True),
        sa.Column("run_id", sa.String(length=36), nullable=True),
        sa.Column("recall_reason", sa.String(length=100), nullable=False),
        sa.Column("decision", sa.String(length=50), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_memory_recall_log_memory_id", "memory_recall_log", ["memory_id"])

    op.create_table(
        "session_summaries",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("scope_key", sa.String(length=255), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=True),
        sa.Column("conversation_id", sa.String(length=100), nullable=True),
        sa.Column("parent_session_id", sa.String(length=36), nullable=True),
        sa.Column("task_run_id", sa.String(length=36), nullable=True),
        sa.Column("source_kind", sa.String(length=50), nullable=False),
        sa.Column("summary_text", sa.Text(), nullable=False),
        sa.Column("created_by", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["parent_session_id"], ["sessions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["task_run_id"], ["task_runs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_session_summaries_scope_key", "session_summaries", ["scope_key"])
    op.create_index("ix_session_summaries_session_id", "session_summaries", ["session_id"])
    op.create_index(
        "ix_session_summaries_parent_session_id",
        "session_summaries",
        ["parent_session_id"],
    )
    op.create_index("ix_session_summaries_task_run_id", "session_summaries", ["task_run_id"])

    op.create_table(
        "memory_change_log",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("memory_id", sa.String(length=36), nullable=False),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("actor_type", sa.String(length=50), nullable=False),
        sa.Column("actor_id", sa.String(length=100), nullable=True),
        sa.Column("before_snapshot", sa.Text(), nullable=True),
        sa.Column("after_snapshot", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_memory_change_log_memory_id", "memory_change_log", ["memory_id"])
    op.create_index("ix_memory_change_log_created_at", "memory_change_log", ["created_at"])

    connection = op.get_bind()
    rows = connection.execute(
        sa.text(
            """
            SELECT id, namespace, memory_key, value_text, source, status, created_at, updated_at
            FROM memories
            """
        )
    ).mappings()
    now = datetime.now(UTC)
    for row in rows:
        title = str(row["memory_key"] or "").strip() or "Legacy memory"
        body = str(row["value_text"] or "").strip()
        summary = body[:160] or None
        scope_type = "stable" if str(row["status"] or "active") == "active" else "manual"
        scope_key = f"legacy/{row['namespace']}/{row['memory_key']}"
        dedupe_hash = _dedupe_hash(title=title, body=body, summary=summary)
        connection.execute(
            sa.text(
                """
                INSERT INTO memory_entries (
                    id, scope_type, scope_key, conversation_id, session_id, parent_session_id,
                    source_kind, lifecycle_state, title, body, summary, importance, confidence,
                    dedupe_hash, created_at, updated_at, created_by, updated_by, expires_at,
                    redaction_state, security_state, hidden_from_recall, deleted_at
                )
                VALUES (
                    :id, :scope_type, :scope_key, NULL, NULL, NULL,
                    :source_kind, 'active', :title, :body, :summary, 0.8, 1.0,
                    :dedupe_hash, :created_at, :updated_at, 'migration', 'migration', NULL,
                    'clean', 'safe', 0, NULL
                )
                """
            ),
            {
                "id": row["id"],
                "scope_type": scope_type,
                "scope_key": scope_key,
                "source_kind": str(row["source"] or "manual"),
                "title": title,
                "body": body,
                "summary": summary,
                "dedupe_hash": dedupe_hash,
                "created_at": row["created_at"] or now,
                "updated_at": row["updated_at"] or now,
            },
        )
        connection.execute(
            sa.text(
                """
                INSERT INTO memory_change_log (
                    id,
                    memory_id,
                    action,
                    actor_type,
                    actor_id,
                    before_snapshot,
                    after_snapshot,
                    created_at
                )
                VALUES (
                    :id,
                    :memory_id,
                    'create',
                    'system',
                    'migration',
                    NULL,
                    :after_snapshot,
                    :created_at
                )
                """
            ),
            {
                "id": f"chg-{row['id']}",
                "memory_id": row["id"],
                "after_snapshot": (
                    "{"
                    f'"scope_type": "{scope_type}", '
                    f'"scope_key": "{scope_key}", '
                    f'"source_kind": "{str(row["source"] or "manual")}"'
                    "}"
                ),
                "created_at": row["created_at"] or now,
            },
        )

    with op.batch_alter_table("memory_entries") as batch_op:
        batch_op.alter_column("hidden_from_recall", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_memory_change_log_created_at", table_name="memory_change_log")
    op.drop_index("ix_memory_change_log_memory_id", table_name="memory_change_log")
    op.drop_table("memory_change_log")

    op.drop_index("ix_session_summaries_task_run_id", table_name="session_summaries")
    op.drop_index("ix_session_summaries_parent_session_id", table_name="session_summaries")
    op.drop_index("ix_session_summaries_session_id", table_name="session_summaries")
    op.drop_index("ix_session_summaries_scope_key", table_name="session_summaries")
    op.drop_table("session_summaries")

    op.drop_index("ix_memory_recall_log_memory_id", table_name="memory_recall_log")
    op.drop_table("memory_recall_log")

    op.drop_index("ix_memory_relations_to_memory_id", table_name="memory_relations")
    op.drop_index("ix_memory_relations_from_memory_id", table_name="memory_relations")
    op.drop_table("memory_relations")

    op.drop_index("ix_memory_entries_hidden_from_recall", table_name="memory_entries")
    op.drop_index("ix_memory_entries_lifecycle_state", table_name="memory_entries")
    op.drop_index("ix_memory_entries_source_kind", table_name="memory_entries")
    op.drop_index("ix_memory_entries_parent_session_id", table_name="memory_entries")
    op.drop_index("ix_memory_entries_session_id", table_name="memory_entries")
    op.drop_index("ix_memory_entries_conversation_id", table_name="memory_entries")
    op.drop_index("ix_memory_entries_dedupe_hash", table_name="memory_entries")
    op.drop_index("ix_memory_entries_scope_type_scope_key", table_name="memory_entries")
    op.drop_table("memory_entries")
