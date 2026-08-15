"""Add calibration roadmap, audit versioning fields, and risk_policies table.

Revision ID: 004_calibration_and_audit_fields
Revises: 003_auth_and_user_ownership
Create Date: 2026-08-15
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004_calibration_and_audit_fields"
down_revision: Union[str, None] = "003_auth_and_user_ownership"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- 1. Create risk_policies table if it does not exist -------------------
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if "risk_policies" not in inspector.get_table_names():
        op.create_table(
            "risk_policies",
            sa.Column("id", sa.String(64), primary_key=True),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("organization_id", sa.String(64), nullable=False, server_default="default-org"),
            sa.Column("version", sa.String(40), nullable=False, server_default="1.0.0"),
            sa.Column("description", sa.Text, nullable=True),
            sa.Column("is_active", sa.Boolean, server_default="true", nullable=False),
            sa.Column("rules", sa.JSON, nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )

    # --- 2. Add calibration & audit columns to analyses table -----------------
    analyses_cols = {col["name"] for col in inspector.get_columns("analyses")}

    new_analyses_columns = [
        ("risk_policy_version", sa.Column("risk_policy_version", sa.String(30), server_default="1.0.0", nullable=False)),
        ("analysis_version", sa.Column("analysis_version", sa.String(30), server_default="1.0.0", nullable=False)),
        ("is_calibrated", sa.Column("is_calibrated", sa.Boolean, server_default="false", nullable=False)),
        ("calibration_status", sa.Column("calibration_status", sa.String(255), server_default="NOT_CALIBRATED", nullable=False)),
        ("evidence_completeness", sa.Column("evidence_completeness", sa.Float, server_default="1.0", nullable=False)),
        ("historical_outcome", sa.Column("historical_outcome", sa.String(60), nullable=True)),
        ("production_incident", sa.Column("production_incident", sa.Boolean, nullable=True)),
        ("rollback_occurred", sa.Column("rollback_occurred", sa.Boolean, nullable=True)),
        ("change_failed", sa.Column("change_failed", sa.Boolean, nullable=True)),
    ]

    for col_name, col_def in new_analyses_columns:
        if col_name not in analyses_cols:
            op.add_column("analyses", col_def)

    # --- 3. Expand step column in analysis_jobs -------------------------------
    try:
        op.alter_column("analysis_jobs", "step", type_=sa.String(255), existing_type=sa.String(60))
    except Exception:  # noqa: BLE001
        pass


def downgrade() -> None:
    op.drop_column("analyses", "change_failed")
    op.drop_column("analyses", "rollback_occurred")
    op.drop_column("analyses", "production_incident")
    op.drop_column("analyses", "historical_outcome")
    op.drop_column("analyses", "evidence_completeness")
    op.drop_column("analyses", "calibration_status")
    op.drop_column("analyses", "is_calibrated")
    op.drop_column("analyses", "analysis_version")
    op.drop_column("analyses", "risk_policy_version")
    op.drop_table("risk_policies")
