"""add plan slot notes and day schedule timestamps

Revision ID: 0021_plan_notes_times
Revises: 0020_media_object_keys
Create Date: 2026-10-20 08:30:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0021_plan_notes_times"
down_revision = "0020_media_object_keys"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Заметка слота и время дня живут отдельно от дозировки: старые строки остаются пустыми.
    op.add_column("plan_exercises", sa.Column("note", sa.Text(), nullable=True))
    op.add_column("plan_days", sa.Column("scheduled_time", sa.Time(), nullable=True))
    op.add_column("plan_days", sa.Column("started_at", sa.DateTime(timezone=False), nullable=True))
    op.add_column("plan_days", sa.Column("finished_at", sa.DateTime(timezone=False), nullable=True))


def downgrade() -> None:
    op.drop_column("plan_days", "finished_at")
    op.drop_column("plan_days", "started_at")
    op.drop_column("plan_days", "scheduled_time")
    op.drop_column("plan_exercises", "note")
