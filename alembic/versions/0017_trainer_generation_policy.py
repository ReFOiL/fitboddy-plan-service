"""normalized trainer generation policy tables

Revision ID: 0017_trainer_policy
Revises: 0016_muscles
Create Date: 2026-07-20 01:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0017_trainer_policy"
down_revision = "0016_muscles"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "trainer_generation_policies",
        sa.Column("trainer_user_id", sa.String(length=64), primary_key=True),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "trainer_policy_workouts_per_week",
        sa.Column("trainer_user_id", sa.String(length=64), nullable=False),
        sa.Column("level", sa.String(length=32), nullable=False),
        sa.Column("workouts_per_week", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["trainer_user_id"],
            ["trainer_generation_policies.trainer_user_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("trainer_user_id", "level"),
        sa.CheckConstraint("level IN ('beginner', 'intermediate', 'advanced')", name="ck_trainer_wpw_level"),
        sa.CheckConstraint("workouts_per_week >= 1 AND workouts_per_week <= 7", name="ck_trainer_wpw_range"),
    )

    op.create_table(
        "trainer_policy_session_bounds",
        sa.Column("trainer_user_id", sa.String(length=64), nullable=False),
        sa.Column("slot", sa.String(length=32), nullable=False),
        sa.Column("min_exercises", sa.Integer(), nullable=False),
        sa.Column("max_exercises", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["trainer_user_id"],
            ["trainer_generation_policies.trainer_user_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("trainer_user_id", "slot"),
        sa.CheckConstraint(
            "slot IN ('default', 'beginner', 'intermediate', 'advanced', 'rehabilitation')",
            name="ck_trainer_session_slot",
        ),
        sa.CheckConstraint("min_exercises >= 1 AND min_exercises <= 12", name="ck_trainer_session_min"),
        sa.CheckConstraint("max_exercises >= 1 AND max_exercises <= 12", name="ck_trainer_session_max"),
        sa.CheckConstraint("max_exercises >= min_exercises", name="ck_trainer_session_order"),
    )

    op.create_table(
        "trainer_policy_split_days",
        sa.Column("trainer_user_id", sa.String(length=64), nullable=False),
        sa.Column("goal", sa.String(length=32), nullable=False),
        sa.Column("level", sa.String(length=32), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(
            ["trainer_user_id"],
            ["trainer_generation_policies.trainer_user_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("trainer_user_id", "goal", "level", "position"),
        sa.CheckConstraint(
            "goal IN ('maintenance', 'weight_loss', 'muscle_gain', 'endurance', 'rehabilitation')",
            name="ck_trainer_split_goal",
        ),
        sa.CheckConstraint("level IN ('beginner', 'intermediate', 'advanced')", name="ck_trainer_split_level"),
        sa.CheckConstraint(
            "category IN ('upper', 'lower', 'core', 'full_body')",
            name="ck_trainer_split_category",
        ),
        sa.CheckConstraint("position >= 0", name="ck_trainer_split_position"),
    )

    op.create_table(
        "trainer_policy_excluded_pairs",
        sa.Column("trainer_user_id", sa.String(length=64), nullable=False),
        sa.Column("exercise_a_id", sa.String(length=64), nullable=False),
        sa.Column("exercise_b_id", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(
            ["trainer_user_id"],
            ["trainer_generation_policies.trainer_user_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("trainer_user_id", "exercise_a_id", "exercise_b_id"),
        sa.CheckConstraint("exercise_a_id < exercise_b_id", name="ck_trainer_pair_ordered"),
    )


def downgrade() -> None:
    op.drop_table("trainer_policy_excluded_pairs")
    op.drop_table("trainer_policy_split_days")
    op.drop_table("trainer_policy_session_bounds")
    op.drop_table("trainer_policy_workouts_per_week")
    op.drop_table("trainer_generation_policies")
