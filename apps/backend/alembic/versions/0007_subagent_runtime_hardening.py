"""Harden subagent runtime persistence for timeout and idempotent completion."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0007_subagent_runtime_hardening"
down_revision = "0006_subagent_sessions_mvp"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("sessions") as batch_op:
        batch_op.add_column(sa.Column("timeout_seconds", sa.Float(), nullable=True))

    with op.batch_alter_table("session_subagent_runs") as batch_op:
        batch_op.add_column(
            sa.Column("parent_summary_message_id", sa.String(length=36), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_session_subagent_runs_parent_summary_message_id_messages",
            "messages",
            ["parent_summary_message_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("session_subagent_runs") as batch_op:
        batch_op.drop_constraint(
            "fk_session_subagent_runs_parent_summary_message_id_messages",
            type_="foreignkey",
        )
        batch_op.drop_column("parent_summary_message_id")

    with op.batch_alter_table("sessions") as batch_op:
        batch_op.drop_column("timeout_seconds")
