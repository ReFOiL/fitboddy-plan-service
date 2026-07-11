"""add is_hold flag for timed hold exercises

Revision ID: 0008_trainer_ex_hold
Revises: 0007_drop_ex_slug
Create Date: 2026-07-11 22:45:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0008_trainer_ex_hold"
down_revision = "0007_drop_ex_slug"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("trainer_exercises") as batch_op:
        batch_op.add_column(
            sa.Column(
                "is_hold",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )

    # Backfill known isometric holds already seeded for trainers.
    op.execute(
        sa.text(
            """
            UPDATE trainer_exercises
            SET is_hold = true
            WHERE lower(exercise_name) IN ('планка', 'plank')
            """
        )
    )


def downgrade() -> None:
    with op.batch_alter_table("trainer_exercises") as batch_op:
        batch_op.drop_column("is_hold")
