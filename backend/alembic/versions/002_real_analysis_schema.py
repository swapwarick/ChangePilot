"""Real repository analysis schema — jobs, knowledge graph, AST cache, audit fields

Revision ID: 002_real_analysis_schema
Revises: 001_initial_schema
Create Date: 2026-08-05
"""

from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "002_real_analysis_schema"
down_revision: Union[str, None] = "001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add owner and full_name to repositories
    op.add_column("repositories", sa.Column("owner", sa.String(120), server_default="", nullable=False))
    op.add_column("repositories", sa.Column("full_name", sa.String(255), server_default="", nullable=False))

    # Add audit versioning & refs to analyses
    op.add_column("analyses", sa.Column("base_ref", sa.String(120), nullable=True))
    op.add_column("analyses", sa.Column("head_ref", sa.String(120), nullable=True))
    op.add_column("analyses", sa.Column("parser_version", sa.String(30), server_default="1.0.0-treesitter", nullable=False))
    op.add_column("analyses", sa.Column("graph_version", sa.String(30), server_default="1.0.0", nullable=False))
    op.add_column("analyses", sa.Column("risk_engine_version", sa.String(30), server_default="1.0.0-deterministic", nullable=False))
    op.add_column("analyses", sa.Column("ai_prompt_version", sa.String(30), server_default="1.0.0", nullable=False))
    op.add_column("analyses", sa.Column("ai_provider", sa.String(120), nullable=True))
    op.add_column("analyses", sa.Column("ai_model", sa.String(120), nullable=True))

    # Create analysis_jobs table
    op.create_table(
        "analysis_jobs",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("repository_id", sa.String(64), nullable=False, index=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="PENDING"),
        sa.Column("step", sa.String(60), nullable=False, server_default="Queued"),
        sa.Column("progress", sa.Integer, server_default="0"),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("analysis_id", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Create repo_knowledge_graphs table
    op.create_table(
        "repo_knowledge_graphs",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("repository_id", sa.String(64), nullable=False, index=True),
        sa.Column("commit_sha", sa.String(64), nullable=False),
        sa.Column("graph_hash", sa.String(64), nullable=False),
        sa.Column("nodes", sa.JSON, nullable=False),
        sa.Column("edges", sa.JSON, nullable=False),
        sa.Column("health_metrics", sa.JSON, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Create file_ast_cache table
    op.create_table(
        "file_ast_cache",
        sa.Column("file_hash", sa.String(64), primary_key=True),
        sa.Column("file_path", sa.String(512), nullable=False),
        sa.Column("language", sa.String(40), nullable=False),
        sa.Column("parsed_ast", sa.JSON, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("file_ast_cache")
    op.drop_table("repo_knowledge_graphs")
    op.drop_table("analysis_jobs")
    op.drop_column("analyses", "ai_model")
    op.drop_column("analyses", "ai_provider")
    op.drop_column("analyses", "ai_prompt_version")
    op.drop_column("analyses", "risk_engine_version")
    op.drop_column("analyses", "graph_version")
    op.drop_column("analyses", "parser_version")
    op.drop_column("analyses", "head_ref")
    op.drop_column("analyses", "base_ref")
    op.drop_column("repositories", "full_name")
    op.drop_column("repositories", "owner")
