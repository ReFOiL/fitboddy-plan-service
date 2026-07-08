"""add description for trainer exercises

Revision ID: 0006_trainer_ex_desc
Revises: 0005_trainer_ex_video
Create Date: 2026-07-09 05:40:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0006_trainer_ex_desc"
down_revision = "0005_trainer_ex_video"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("trainer_exercises") as batch_op:
        batch_op.add_column(sa.Column("description", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("trainer_exercises") as batch_op:
        batch_op.drop_column("description")
