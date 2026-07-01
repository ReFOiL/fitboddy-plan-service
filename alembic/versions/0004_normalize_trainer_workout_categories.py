"""normalize trainer exercise workout categories

Revision ID: 0004_norm_workout_cats
Revises: 0003_trainer_ex_active
Create Date: 2026-07-01 15:20:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0004_norm_workout_cats"
down_revision = "0003_trainer_ex_active"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    normalization_pairs = (
        ("верх", "upper"),
        ("верх_тела", "upper"),
        ("upper_body", "upper"),
        ("низ", "lower"),
        ("низ_тела", "lower"),
        ("lower_body", "lower"),
        ("корпус", "core"),
        ("кардио", "full_body"),
        ("cardio", "full_body"),
        ("fullbody", "full_body"),
        ("full body", "full_body"),
        ("все_тело", "full_body"),
        ("всё_тело", "full_body"),
    )
    for legacy_value, normalized_value in normalization_pairs:
        bind.execute(
            sa.text(
                """
                UPDATE trainer_exercises
                SET workout_category = :normalized_value
                WHERE LOWER(workout_category) = :legacy_value
                """
            ),
            {"legacy_value": legacy_value, "normalized_value": normalized_value},
        )


def downgrade() -> None:
    # Irreversible data normalization: keep normalized values as-is.
    pass
