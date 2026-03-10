"""Add tool policy overrides and generic tool cache tables."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0005_tool_catalog_policy_and_cache"
down_revision = "0004_activity_observability_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tool_policy_overrides",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("agent_id", sa.String(length=36), nullable=False),
        sa.Column("tool_name", sa.String(length=100), nullable=False),
        sa.Column("permission_level", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agent_id", "tool_name"),
    )
    op.create_index(
        "ix_tool_policy_overrides_agent_id",
        "tool_policy_overrides",
        ["agent_id"],
        unique=False,
    )

    op.create_table(
        "tool_cache_entries",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tool_name", sa.String(length=100), nullable=False),
        sa.Column("cache_key", sa.String(length=255), nullable=False),
        sa.Column("value_json", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tool_name", "cache_key"),
    )
    op.create_index("ix_tool_cache_entries_tool_name", "tool_cache_entries", ["tool_name"])


def downgrade() -> None:
    op.drop_index("ix_tool_cache_entries_tool_name", table_name="tool_cache_entries")
    op.drop_table("tool_cache_entries")

    op.drop_index(
        "ix_tool_policy_overrides_agent_id",
        table_name="tool_policy_overrides",
    )
    op.drop_table("tool_policy_overrides")
