"""add video_url for trainer exercises

Revision ID: 0005_trainer_ex_video
Revises: 0004_norm_workout_cats
Create Date: 2026-07-09 05:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0005_trainer_ex_video"
down_revision = "0004_norm_workout_cats"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("trainer_exercises") as batch_op:
        batch_op.add_column(sa.Column("video_url", sa.String(length=500), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("trainer_exercises") as batch_op:
        batch_op.drop_column("video_url")
