"""Add conversation identifiers and runtime memory metadata."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0009_memory_runtime_v1"
down_revision = "0008_memory_v1_admin_core"
branch_labels = None
depends_on = None


def _column_names(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {column["name"] for column in inspector.get_columns(table_name)}


def _index_names(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {index["name"] for index in inspector.get_indexes(table_name)}


def upgrade() -> None:
    session_columns = _column_names("sessions")
    session_indexes = _index_names("sessions")
    if "conversation_id" not in session_columns:
        with op.batch_alter_table("sessions") as batch_op:
            batch_op.add_column(sa.Column("conversation_id", sa.String(length=36), nullable=True))
    if "ix_sessions_conversation_id" not in session_indexes:
        with op.batch_alter_table("sessions") as batch_op:
            batch_op.create_index("ix_sessions_conversation_id", ["conversation_id"], unique=False)

    op.execute(
        """
        UPDATE sessions
        SET conversation_id = id
        WHERE conversation_id IS NULL OR trim(conversation_id) = ''
        """
    )

    with op.batch_alter_table("sessions") as batch_op:
        batch_op.alter_column("conversation_id", existing_type=sa.String(length=36), nullable=False)

    message_columns = _column_names("messages")
    message_indexes = _index_names("messages")
    if "conversation_id" not in message_columns:
        with op.batch_alter_table("messages") as batch_op:
            batch_op.add_column(sa.Column("conversation_id", sa.String(length=36), nullable=True))
    if "ix_messages_conversation_id" not in message_indexes:
        with op.batch_alter_table("messages") as batch_op:
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

    memory_columns = _column_names("memories")
    memory_indexes = _index_names("memories")
    missing_memory_columns = [
        sa.Column("memory_class", sa.String(length=50), nullable=True),
        sa.Column("scope_kind", sa.String(length=50), nullable=True),
        sa.Column("scope_ref", sa.String(length=255), nullable=True),
        sa.Column("session_id", sa.String(length=36), nullable=True),
        sa.Column("conversation_id", sa.String(length=36), nullable=True),
        sa.Column("parent_session_id", sa.String(length=36), nullable=True),
        sa.Column("source_memory_id", sa.String(length=36), nullable=True),
    ]
    for column in missing_memory_columns:
        if column.name not in memory_columns:
            with op.batch_alter_table("memories") as batch_op:
                batch_op.add_column(column)
    op.execute(
        """
        UPDATE memories
        SET memory_class = COALESCE(memory_class, 'stable'),
            scope_kind = COALESCE(scope_kind, 'agent')
        """
    )
    op.execute(
        """
        UPDATE memories
        SET conversation_id = (
            SELECT sessions.conversation_id
            FROM sessions
            WHERE sessions.id = memories.session_id
        )
        WHERE conversation_id IS NULL
          AND session_id IS NOT NULL
        """
    )
    memory_columns = _column_names("memories")
    memory_indexes = _index_names("memories")
    if "conversation_id" in memory_columns and "ix_memories_conversation_id" not in memory_indexes:
        op.create_index(
            "ix_memories_conversation_id", "memories", ["conversation_id"], unique=False
        )


def downgrade() -> None:
    memory_columns = _column_names("memories")
    memory_indexes = _index_names("memories")
    if "conversation_id" in memory_columns and "ix_memories_conversation_id" in memory_indexes:
        op.drop_index("ix_memories_conversation_id", table_name="memories")

    message_columns = _column_names("messages")
    message_indexes = _index_names("messages")
    if "conversation_id" in message_columns:
        with op.batch_alter_table("messages") as batch_op:
            if "ix_messages_conversation_id" in message_indexes:
                batch_op.drop_index("ix_messages_conversation_id")
            batch_op.drop_column("conversation_id")

    session_columns = _column_names("sessions")
    session_indexes = _index_names("sessions")
    if "conversation_id" in session_columns:
        with op.batch_alter_table("sessions") as batch_op:
            if "ix_sessions_conversation_id" in session_indexes:
                batch_op.drop_index("ix_sessions_conversation_id")
            batch_op.drop_column("conversation_id")
