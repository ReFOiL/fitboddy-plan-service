"""add start/end photo urls for trainer and platform exercises

Revision ID: 0019_exercise_photos
Revises: 0018_one_active_plan
Create Date: 2026-09-13 09:55:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0019_exercise_photos"
down_revision = "0018_one_active_plan"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("trainer_exercises") as batch_op:
        batch_op.add_column(sa.Column("start_image_url", sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column("end_image_url", sa.String(length=500), nullable=True))
    with op.batch_alter_table("platform_exercises") as batch_op:
        batch_op.add_column(sa.Column("start_image_url", sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column("end_image_url", sa.String(length=500), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("platform_exercises") as batch_op:
        batch_op.drop_column("end_image_url")
        batch_op.drop_column("start_image_url")
    with op.batch_alter_table("trainer_exercises") as batch_op:
        batch_op.drop_column("end_image_url")
        batch_op.drop_column("start_image_url")
