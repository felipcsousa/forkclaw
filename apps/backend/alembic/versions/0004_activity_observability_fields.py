"""Add observability fields for task runs and audit events."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0004_activity_observability_fields"
down_revision = "0003_link_tasks_to_cron_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("task_runs") as batch_op:
        batch_op.add_column(sa.Column("duration_ms", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("estimated_cost_usd", sa.Float(), nullable=True))

    with op.batch_alter_table("audit_events") as batch_op:
        batch_op.add_column(
            sa.Column("level", sa.String(length=20), nullable=False, server_default="info")
        )
        batch_op.add_column(sa.Column("summary_text", sa.Text(), nullable=True))
        batch_op.create_index("ix_audit_events_level", ["level"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("audit_events") as batch_op:
        batch_op.drop_index("ix_audit_events_level")
        batch_op.drop_column("summary_text")
        batch_op.drop_column("level")

    with op.batch_alter_table("task_runs") as batch_op:
        batch_op.drop_column("estimated_cost_usd")
        batch_op.drop_column("duration_ms")
