"""add trainer-bound catalog

Revision ID: 0002_add_trainer_catalog
Revises: 0001_create_plan_tables
Create Date: 2026-04-27 15:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0002_add_trainer_catalog"
down_revision = "0001_create_plan_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("training_plans", sa.Column("trainer_user_id", sa.String(length=64), nullable=True))
    op.execute("UPDATE training_plans SET trainer_user_id = 'unknown_trainer' WHERE trainer_user_id IS NULL")
    with op.batch_alter_table("training_plans") as batch_op:
        batch_op.alter_column("trainer_user_id", nullable=False)
    op.create_index("ix_training_plans_trainer_user_id", "training_plans", ["trainer_user_id"], unique=False)

    op.create_table(
        "trainer_exercises",
        sa.Column("row_id", sa.String(length=36), primary_key=True),
        sa.Column("trainer_user_id", sa.String(length=64), nullable=False),
        sa.Column("exercise_id", sa.String(length=64), nullable=False),
        sa.Column("exercise_name", sa.String(length=128), nullable=False),
        sa.Column("equipment", sa.String(length=32), nullable=False, server_default="none"),
        sa.Column("is_cardio", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("difficulty", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("workout_category", sa.String(length=50), nullable=False, server_default="full_body"),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("trainer_user_id", "exercise_id", name="uq_trainer_exercise_pair"),
    )
    op.create_index("ix_trainer_exercises_trainer_user_id", "trainer_exercises", ["trainer_user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_trainer_exercises_trainer_user_id", table_name="trainer_exercises")
    op.drop_table("trainer_exercises")
    op.drop_index("ix_training_plans_trainer_user_id", table_name="training_plans")
    with op.batch_alter_table("training_plans") as batch_op:
        batch_op.drop_column("trainer_user_id")
