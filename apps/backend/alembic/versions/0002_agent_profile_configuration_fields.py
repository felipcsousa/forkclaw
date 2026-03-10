"""Add canonical configuration fields to agent profiles."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0002_agent_profile_configuration_fields"
down_revision = "0001_initial_agent_os"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("agent_profiles") as batch_op:
        batch_op.add_column(
            sa.Column(
                "identity_text",
                sa.Text(),
                nullable=False,
                server_default="",
            )
        )
        batch_op.add_column(
            sa.Column(
                "soul_text",
                sa.Text(),
                nullable=False,
                server_default="",
            )
        )
        batch_op.add_column(
            sa.Column(
                "user_context_text",
                sa.Text(),
                nullable=False,
                server_default="",
            )
        )
        batch_op.add_column(
            sa.Column(
                "policy_base_text",
                sa.Text(),
                nullable=False,
                server_default="",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("agent_profiles") as batch_op:
        batch_op.drop_column("policy_base_text")
        batch_op.drop_column("user_context_text")
        batch_op.drop_column("soul_text")
        batch_op.drop_column("identity_text")
