"""Initial schema — repositories, analyses, ai_provider_configs

Revision ID: 001_initial_schema
Revises: None
Create Date: 2026-08-05
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "repositories",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("source", sa.String(120), nullable=False),
        sa.Column("url", sa.Text, nullable=True),
        sa.Column("default_branch", sa.String(120), server_default="main"),
        sa.Column("language", sa.String(60), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "analyses",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("repository_id", sa.String(64), nullable=False, index=True),
        sa.Column("trigger", sa.String(40), nullable=False),
        sa.Column("changed_files", sa.JSON, nullable=False),
        sa.Column("impacted_modules", sa.JSON, nullable=False),
        sa.Column("dependency_graph", sa.JSON, nullable=False),
        sa.Column("risk_score", sa.Float, nullable=False),
        sa.Column("risk_level", sa.String(20), nullable=False),
        sa.Column("risk_confidence", sa.Float, nullable=False),
        sa.Column("risk_evidence", sa.JSON, nullable=False),
        sa.Column("risk_reasons", sa.JSON, nullable=False),
        sa.Column("ai_report", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "ai_provider_configs",
        sa.Column("id", sa.String(120), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("base_url", sa.Text, nullable=True),
        sa.Column("api_key", sa.Text, nullable=True),
        sa.Column("model", sa.String(255), nullable=False),
        sa.Column("enabled", sa.Boolean, default=True),
        sa.Column("is_default", sa.Boolean, default=False),
        sa.Column("priority", sa.Integer, default=100),
        sa.Column("task_categories", sa.JSON, nullable=False),
        sa.Column("fallback_provider_ids", sa.JSON, nullable=False),
        sa.Column("custom_headers", sa.JSON, nullable=False),
        sa.Column("temperature", sa.Float, default=0.2),
        sa.Column("max_tokens", sa.Integer, default=1600),
        sa.Column("timeout_seconds", sa.Float, default=30),
        sa.Column("retry_max_attempts", sa.Integer, default=2),
        sa.Column("retry_backoff", sa.Float, default=0.5),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("ai_provider_configs")
    op.drop_table("analyses")
    op.drop_table("repositories")
