"""store trainer-chosen plan start mode

Revision ID: 0023_plan_start_mode
Revises: 0022_trainer_sync_link
Create Date: 2026-10-30 10:30:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0023_plan_start_mode"
down_revision = "0022_trainer_sync_link"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # NULL — старый якорь: неделя это семь дней от start_date. Режим пишет только новое сохранение.
    op.add_column("training_plans", sa.Column("start_mode", sa.String(length=16), nullable=True))


def downgrade() -> None:
    op.drop_column("training_plans", "start_mode")
