"""add plan day completion fields

Revision ID: 0013_day_complete
Revises: 0012_platform_ex
Create Date: 2026-07-18 22:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0013_day_complete"
down_revision = "0012_platform_ex"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "plan_days",
        sa.Column("is_completed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "plan_days",
        sa.Column("completed_at", sa.DateTime(timezone=False), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("plan_days", "completed_at")
    op.drop_column("plan_days", "is_completed")
