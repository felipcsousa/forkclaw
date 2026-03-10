"""Link tasks to cron jobs for durable scheduler history."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0003_link_tasks_to_cron_jobs"
down_revision = "0002_agent_profile_configuration_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.add_column(sa.Column("cron_job_id", sa.String(length=36), nullable=True))
        batch_op.create_index("ix_tasks_cron_job_id", ["cron_job_id"], unique=False)
        batch_op.create_foreign_key(
            "fk_tasks_cron_job_id_cron_jobs",
            "cron_jobs",
            ["cron_job_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.drop_constraint("fk_tasks_cron_job_id_cron_jobs", type_="foreignkey")
        batch_op.drop_index("ix_tasks_cron_job_id")
        batch_op.drop_column("cron_job_id")
