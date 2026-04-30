"""create plan service tables

Revision ID: 0001_create_plan_tables
Revises:
Create Date: 2026-04-27 14:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0001_create_plan_tables"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "training_plans",
        sa.Column("plan_id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("goal", sa.String(length=32), nullable=False),
        sa.Column("level", sa.String(length=32), nullable=False),
        sa.Column("workouts_per_week", sa.Integer(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_training_plans_user_id", "training_plans", ["user_id"], unique=False)
    op.create_index("ix_training_plans_status", "training_plans", ["status"], unique=False)

    op.create_table(
        "plan_days",
        sa.Column("day_id", sa.String(length=36), primary_key=True),
        sa.Column("plan_id", sa.String(length=36), sa.ForeignKey("training_plans.plan_id", ondelete="CASCADE"), nullable=False),
        sa.Column("day_index", sa.Integer(), nullable=False),
        sa.Column("scheduled_for", sa.Date(), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("day_of_week", sa.Integer(), nullable=False),
        sa.Column("volume_multiplier", sa.Float(), nullable=False),
    )
    op.create_index("ix_plan_days_plan_id", "plan_days", ["plan_id"], unique=False)

    op.create_table(
        "plan_exercises",
        sa.Column("line_id", sa.String(length=36), primary_key=True),
        sa.Column("day_id", sa.String(length=36), sa.ForeignKey("plan_days.day_id", ondelete="CASCADE"), nullable=False),
        sa.Column("exercise_id", sa.String(length=64), nullable=False),
        sa.Column("exercise_name", sa.String(length=128), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("is_cardio", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("sets", sa.Integer(), nullable=True),
        sa.Column("reps", sa.Integer(), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("rest_seconds", sa.Integer(), nullable=True),
    )
    op.create_index("ix_plan_exercises_day_id", "plan_exercises", ["day_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_plan_exercises_day_id", table_name="plan_exercises")
    op.drop_table("plan_exercises")
    op.drop_index("ix_plan_days_plan_id", table_name="plan_days")
    op.drop_table("plan_days")
    op.drop_index("ix_training_plans_status", table_name="training_plans")
    op.drop_index("ix_training_plans_user_id", table_name="training_plans")
    op.drop_table("training_plans")
