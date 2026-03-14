"""Deactivate legacy agent tools that no longer exist in the current catalog."""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "0012_deprecate_legacy_agent_tools"
down_revision = "0011_runtime_iteration_default_four"
branch_labels = None
depends_on = None

_LEGACY_TOOL_NAMES = (
    "spawn_subagent",
    "list_subagents",
    "get_subagent",
    "cancel_subagent",
)


def upgrade() -> None:
    placeholders = ", ".join(f"'{name}'" for name in _LEGACY_TOOL_NAMES)
    op.execute(
        f"""
        UPDATE tool_permissions
        SET status = 'inactive',
            updated_at = CURRENT_TIMESTAMP
        WHERE status = 'active'
          AND tool_name IN ({placeholders})
        """
    )
    op.execute(
        f"""
        UPDATE tool_policy_overrides
        SET status = 'inactive',
            updated_at = CURRENT_TIMESTAMP
        WHERE status = 'active'
          AND tool_name IN ({placeholders})
        """
    )


def downgrade() -> None:
    # One-way deprecation. Legacy tools stay inactive on downgrade.
    return None

