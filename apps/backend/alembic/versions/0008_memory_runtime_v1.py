"""Add conversation identifiers and memory runtime V1 fields."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0008_memory_runtime_v1"
down_revision = "0007_subagent_runtime_hardening"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("sessions") as batch_op:
        batch_op.add_column(sa.Column("conversation_id", sa.String(length=36), nullable=True))
        batch_op.create_index("ix_sessions_conversation_id", ["conversation_id"], unique=False)

    op.execute("UPDATE sessions SET conversation_id = id WHERE conversation_id IS NULL")

    with op.batch_alter_table("sessions") as batch_op:
        batch_op.alter_column("conversation_id", existing_type=sa.String(length=36), nullable=False)

    with op.batch_alter_table("messages") as batch_op:
        batch_op.add_column(sa.Column("conversation_id", sa.String(length=36), nullable=True))
        batch_op.create_index("ix_messages_conversation_id", ["conversation_id"], unique=False)

    op.execute(
        """
        UPDATE messages
        SET conversation_id = (
            SELECT sessions.conversation_id
            FROM sessions
            WHERE sessions.id = messages.session_id
        )
        WHERE conversation_id IS NULL
        """
    )

    with op.batch_alter_table("messages") as batch_op:
        batch_op.alter_column("conversation_id", existing_type=sa.String(length=36), nullable=False)

    op.create_table(
        "memories_v2",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("agent_id", sa.String(length=36), nullable=False),
        sa.Column("namespace", sa.String(length=100), nullable=False),
        sa.Column("memory_key", sa.String(length=150), nullable=False),
        sa.Column("value_text", sa.Text(), nullable=False),
        sa.Column("memory_class", sa.String(length=50), nullable=False),
        sa.Column("scope_kind", sa.String(length=50), nullable=False),
        sa.Column("scope_ref", sa.String(length=255), nullable=True),
        sa.Column("session_id", sa.String(length=36), nullable=True),
        sa.Column("conversation_id", sa.String(length=36), nullable=True),
        sa.Column("parent_session_id", sa.String(length=36), nullable=True),
        sa.Column("source_memory_id", sa.String(length=36), nullable=True),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_session_id"], ["sessions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_memory_id"], ["memories_v2.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "agent_id",
            "namespace",
            "memory_key",
            "memory_class",
            "scope_kind",
            "scope_ref",
            "source",
        ),
    )
    op.create_index(
        "ix_memories_v2_conversation_id",
        "memories_v2",
        ["conversation_id"],
        unique=False,
    )

    op.execute(
        """
        INSERT INTO memories_v2 (
            id, agent_id, namespace, memory_key, value_text,
            memory_class, scope_kind, scope_ref, session_id, conversation_id,
            parent_session_id, source_memory_id, source, status, created_at, updated_at
        )
        SELECT
            id, agent_id, namespace, memory_key, value_text,
            'stable', 'agent', NULL, NULL, NULL,
            NULL, NULL, source, status, created_at, updated_at
        FROM memories
        """
    )

    op.drop_table("memories")
    op.rename_table("memories_v2", "memories")
    op.create_index("ix_memories_conversation_id", "memories", ["conversation_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_memories_conversation_id", table_name="memories")
    op.create_table(
        "memories_legacy",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("agent_id", sa.String(length=36), nullable=False),
        sa.Column("namespace", sa.String(length=100), nullable=False),
        sa.Column("memory_key", sa.String(length=150), nullable=False),
        sa.Column("value_text", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agent_id", "namespace", "memory_key"),
    )
    op.execute(
        """
        INSERT INTO memories_legacy (
            id, agent_id, namespace, memory_key, value_text,
            source, status, created_at, updated_at
        )
        SELECT
            id, agent_id, namespace, memory_key, value_text,
            source, status, created_at, updated_at
        FROM memories
        """
    )
    op.drop_table("memories")
    op.rename_table("memories_legacy", "memories")

    with op.batch_alter_table("messages") as batch_op:
        batch_op.drop_index("ix_messages_conversation_id")
        batch_op.drop_column("conversation_id")

    with op.batch_alter_table("sessions") as batch_op:
        batch_op.drop_index("ix_sessions_conversation_id")
        batch_op.drop_column("conversation_id")
