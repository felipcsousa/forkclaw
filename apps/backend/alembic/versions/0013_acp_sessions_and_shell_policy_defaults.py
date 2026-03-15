"""Add ACP session mappings and runtime defaults for unrestricted shell policy."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0013_acp_sessions_and_shell_policy_defaults"
down_revision = "0012_deprecate_legacy_agent_tools"
branch_labels = None
depends_on = None

_SQLITE_UUID_V4_EXPR = (
    "lower(hex(randomblob(4))) || '-' || lower(hex(randomblob(2))) || '-4' || "
    "substr(lower(hex(randomblob(2))),2) || '-' || "
    "substr('89ab', 1 + (abs(random()) % 4), 1) || "
    "substr(lower(hex(randomblob(2))),2) || '-' || "
    "lower(hex(randomblob(6)))"
)


def _setting_exists(scope: str, key: str) -> sa.sql.elements.TextClause:
    return sa.text(
        """
        SELECT 1
        FROM settings
        WHERE scope = :scope
          AND key = :key
        LIMIT 1
        """
    ).bindparams(scope=scope, key=key)


def upgrade() -> None:
    op.create_table(
        "acp_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("session_key", sa.String(length=120), nullable=False),
        sa.Column("label", sa.String(length=200), nullable=False),
        sa.Column("runtime", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("parent_session_id", sa.String(length=36), nullable=True),
        sa.Column("backend_session_id", sa.String(length=36), nullable=True),
        sa.Column("child_session_id", sa.String(length=36), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("last_prompt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["parent_session_id"], ["sessions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["backend_session_id"], ["sessions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["child_session_id"], ["sessions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_key"),
    )
    op.create_index("ix_acp_sessions_runtime", "acp_sessions", ["runtime"], unique=False)
    op.create_index("ix_acp_sessions_status", "acp_sessions", ["status"], unique=False)
    op.create_index(
        "ix_acp_sessions_parent_session_id",
        "acp_sessions",
        ["parent_session_id"],
        unique=False,
    )
    op.create_index(
        "ix_acp_sessions_backend_session_id",
        "acp_sessions",
        ["backend_session_id"],
        unique=False,
    )
    op.create_index(
        "ix_acp_sessions_child_session_id",
        "acp_sessions",
        ["child_session_id"],
        unique=False,
    )

    conn = op.get_bind()
    if conn.execute(_setting_exists("runtime", "shell_exec_policy_mode")).first() is None:
        conn.execute(
            sa.text(
                f"""
                INSERT INTO settings (
                    id,
                    scope,
                    key,
                    value_type,
                    value_text,
                    value_json,
                    status,
                    created_at,
                    updated_at
                ) VALUES (
                    {_SQLITE_UUID_V4_EXPR},
                    'runtime',
                    'shell_exec_policy_mode',
                    'string',
                    'unrestricted',
                    NULL,
                    'active',
                    CURRENT_TIMESTAMP,
                    CURRENT_TIMESTAMP
                )
                """
            )
        )

    if conn.execute(_setting_exists("features", "acp_bridge_enabled")).first() is None:
        conn.execute(
            sa.text(
                f"""
                INSERT INTO settings (
                    id,
                    scope,
                    key,
                    value_type,
                    value_text,
                    value_json,
                    status,
                    created_at,
                    updated_at
                ) VALUES (
                    {_SQLITE_UUID_V4_EXPR},
                    'features',
                    'acp_bridge_enabled',
                    'boolean',
                    'false',
                    NULL,
                    'active',
                    CURRENT_TIMESTAMP,
                    CURRENT_TIMESTAMP
                )
                """
            )
        )


def downgrade() -> None:
    op.drop_index("ix_acp_sessions_child_session_id", table_name="acp_sessions")
    op.drop_index("ix_acp_sessions_backend_session_id", table_name="acp_sessions")
    op.drop_index("ix_acp_sessions_parent_session_id", table_name="acp_sessions")
    op.drop_index("ix_acp_sessions_status", table_name="acp_sessions")
    op.drop_index("ix_acp_sessions_runtime", table_name="acp_sessions")
    op.drop_table("acp_sessions")
