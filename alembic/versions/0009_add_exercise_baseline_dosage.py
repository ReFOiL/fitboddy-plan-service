"""add baseline dosage fields for trainer exercises and plan weight

Revision ID: 0009_ex_baseline
Revises: 0008_trainer_ex_hold
Create Date: 2026-07-11 23:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0009_ex_baseline"
down_revision = "0008_trainer_ex_hold"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("trainer_exercises") as batch_op:
        batch_op.add_column(sa.Column("default_sets", sa.Integer(), nullable=False, server_default="3"))
        batch_op.add_column(sa.Column("default_reps", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("default_duration_seconds", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("default_rest_seconds", sa.Integer(), nullable=False, server_default="60"))
        batch_op.add_column(sa.Column("default_weight_kg", sa.Float(), nullable=True))

    op.execute(
        sa.text(
            """
            UPDATE trainer_exercises
            SET
                default_sets = 3,
                default_reps = CASE WHEN is_hold THEN NULL ELSE 10 END,
                default_duration_seconds = CASE WHEN is_hold THEN 35 ELSE NULL END,
                default_rest_seconds = CASE WHEN is_hold THEN 45 ELSE 60 END
            """
        )
    )

    with op.batch_alter_table("plan_exercises") as batch_op:
        batch_op.add_column(sa.Column("weight_kg", sa.Float(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("plan_exercises") as batch_op:
        batch_op.drop_column("weight_kg")

    with op.batch_alter_table("trainer_exercises") as batch_op:
        batch_op.drop_column("default_weight_kg")
        batch_op.drop_column("default_rest_seconds")
        batch_op.drop_column("default_duration_seconds")
        batch_op.drop_column("default_reps")
        batch_op.drop_column("default_sets")
