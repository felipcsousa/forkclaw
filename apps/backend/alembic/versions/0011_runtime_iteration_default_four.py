"""Compatibility revision for legacy databases stamped at 0011."""

from __future__ import annotations

# revision identifiers, used by Alembic.
revision = "0011_runtime_iteration_default_four"
down_revision = "0010_memory_recall_v1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Compatibility-only migration. Some legacy installations are already
    # stamped with this revision id, so we keep this node in the chain.
    return None


def downgrade() -> None:
    return None
