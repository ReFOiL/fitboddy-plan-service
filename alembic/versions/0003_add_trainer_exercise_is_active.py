"""add active flag for trainer exercises

Revision ID: 0003_trainer_ex_active
Revises: 0002_add_trainer_catalog
Create Date: 2026-04-27 15:20:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0003_trainer_ex_active"
down_revision = "0002_add_trainer_catalog"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("trainer_exercises") as batch_op:
        batch_op.add_column(
            sa.Column(
                "is_active",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("trainer_exercises") as batch_op:
        batch_op.drop_column("is_active")
