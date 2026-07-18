"""create platform exercise catalog for system workouts

Revision ID: 0012_platform_ex
Revises: 0011_plan_source
Create Date: 2026-07-18 21:10:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0012_platform_ex"
down_revision = "0011_plan_source"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "platform_exercises",
        sa.Column("row_id", sa.String(length=36), primary_key=True),
        sa.Column("catalog_key", sa.String(length=64), nullable=True),
        sa.Column("exercise_name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("equipment", sa.String(length=32), nullable=False, server_default="none"),
        sa.Column("is_cardio", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_hold", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("difficulty", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("workout_category", sa.String(length=50), nullable=False, server_default="full_body"),
        sa.Column("default_sets", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("default_reps", sa.Integer(), nullable=True),
        sa.Column("default_duration_seconds", sa.Integer(), nullable=True),
        sa.Column("default_rest_seconds", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("default_weight_kg", sa.Float(), nullable=True),
        sa.Column("load_scheme", sa.String(length=32), nullable=False, server_default="flat"),
        sa.Column("scheme_steps_json", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("video_url", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("catalog_key", name="uq_platform_exercises_catalog_key"),
    )
    op.create_index("ix_platform_exercises_is_active", "platform_exercises", ["is_active"], unique=False)
    op.create_index(
        "ix_platform_exercises_workout_category",
        "platform_exercises",
        ["workout_category"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_platform_exercises_workout_category", table_name="platform_exercises")
    op.drop_index("ix_platform_exercises_is_active", table_name="platform_exercises")
    op.drop_table("platform_exercises")
