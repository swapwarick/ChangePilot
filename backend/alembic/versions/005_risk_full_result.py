"""Add risk_full_result JSON column to analyses table for lossless export.

Revision ID: 005_risk_full_result
Revises: 004_calibration_and_audit_fields
Create Date: 2026-08-18
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "005_risk_full_result"
down_revision: Union[str, None] = "004_calibration_and_audit_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    analyses_cols = {col["name"] for col in inspector.get_columns("analyses")}

    if "risk_full_result" not in analyses_cols:
        op.add_column(
            "analyses",
            sa.Column("risk_full_result", sa.JSON, nullable=True),
        )


def downgrade() -> None:
    op.drop_column("analyses", "risk_full_result")
