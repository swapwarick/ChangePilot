"""Add auth tables (users, sessions) and user ownership columns to data tables.

Revision ID: 003_auth_and_user_ownership
Revises: 002_real_analysis_schema
Create Date: 2026-08-14
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003_auth_and_user_ownership"
down_revision: Union[str, None] = "002_real_analysis_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Create users table --------------------------------------------------
    op.create_table(
        "users",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("username", sa.String(80), nullable=False),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("hashed_password", sa.Text, nullable=True),
        sa.Column("tier", sa.String(20), nullable=False, server_default="guest"),
        sa.Column("storage_used_bytes", sa.Integer, server_default="0", nullable=False),
        sa.Column("storage_quota_bytes", sa.Integer, server_default="0", nullable=False),
        sa.Column("email_verified", sa.Boolean, server_default="false", nullable=False),
        sa.Column("is_active", sa.Boolean, server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # --- Create sessions table ------------------------------------------------
    op.create_table(
        "sessions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("refresh_token_hash", sa.String(128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])
    op.create_index("uq_sessions_token_hash", "sessions", ["refresh_token_hash"], unique=True)

    # --- Add ownership columns to repositories --------------------------------
    op.add_column("repositories", sa.Column("user_id", sa.String(64), nullable=True))
    op.add_column("repositories", sa.Column("is_ephemeral", sa.Boolean, server_default="false", nullable=False))
    op.create_index("ix_repositories_user_id", "repositories", ["user_id"])

    # --- Add ownership columns to analyses ------------------------------------
    op.add_column("analyses", sa.Column("user_id", sa.String(64), nullable=True))
    op.add_column("analyses", sa.Column("is_ephemeral", sa.Boolean, server_default="false", nullable=False))
    op.create_index("ix_analyses_user_id", "analyses", ["user_id"])

    # --- Add ownership columns to analysis_jobs --------------------------------
    op.add_column("analysis_jobs", sa.Column("user_id", sa.String(64), nullable=True))
    op.add_column("analysis_jobs", sa.Column("is_ephemeral", sa.Boolean, server_default="false", nullable=False))
    op.create_index("ix_analysis_jobs_user_id", "analysis_jobs", ["user_id"])

    # --- Add ownership columns to repo_knowledge_graphs -----------------------
    op.add_column("repo_knowledge_graphs", sa.Column("user_id", sa.String(64), nullable=True))
    op.add_column("repo_knowledge_graphs", sa.Column("is_ephemeral", sa.Boolean, server_default="false", nullable=False))
    op.create_index("ix_repo_knowledge_graphs_user_id", "repo_knowledge_graphs", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_repo_knowledge_graphs_user_id", "repo_knowledge_graphs")
    op.drop_column("repo_knowledge_graphs", "is_ephemeral")
    op.drop_column("repo_knowledge_graphs", "user_id")

    op.drop_index("ix_analysis_jobs_user_id", "analysis_jobs")
    op.drop_column("analysis_jobs", "is_ephemeral")
    op.drop_column("analysis_jobs", "user_id")

    op.drop_index("ix_analyses_user_id", "analyses")
    op.drop_column("analyses", "is_ephemeral")
    op.drop_column("analyses", "user_id")

    op.drop_index("ix_repositories_user_id", "repositories")
    op.drop_column("repositories", "is_ephemeral")
    op.drop_column("repositories", "user_id")

    op.drop_index("uq_sessions_token_hash", "sessions")
    op.drop_index("ix_sessions_user_id", "sessions")
    op.drop_table("sessions")

    op.drop_index("ix_users_email", "users")
    op.drop_index("ix_users_username", "users")
    op.drop_table("users")
