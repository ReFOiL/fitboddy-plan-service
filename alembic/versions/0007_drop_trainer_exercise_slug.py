"""drop trainer exercise slug id, use row_id only

Revision ID: 0007_drop_ex_slug
Revises: 0006_trainer_ex_desc
Create Date: 2026-07-11 22:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0007_drop_ex_slug"
down_revision = "0006_trainer_ex_desc"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing plan lines referenced the human slug; remap them to catalog row_id first.
    op.execute(
        sa.text(
            """
            UPDATE plan_exercises
            SET exercise_id = (
                SELECT te.row_id
                FROM plan_days pd
                JOIN training_plans tp ON tp.plan_id = pd.plan_id
                JOIN trainer_exercises te
                  ON te.trainer_user_id = tp.trainer_user_id
                 AND te.exercise_id = plan_exercises.exercise_id
                WHERE pd.day_id = plan_exercises.day_id
            )
            WHERE EXISTS (
                SELECT 1
                FROM plan_days pd
                JOIN training_plans tp ON tp.plan_id = pd.plan_id
                JOIN trainer_exercises te
                  ON te.trainer_user_id = tp.trainer_user_id
                 AND te.exercise_id = plan_exercises.exercise_id
                WHERE pd.day_id = plan_exercises.day_id
            )
            """
        )
    )

    with op.batch_alter_table("trainer_exercises") as batch_op:
        batch_op.drop_constraint("uq_trainer_exercise_pair", type_="unique")
        batch_op.drop_column("exercise_id")


def downgrade() -> None:
    with op.batch_alter_table("trainer_exercises") as batch_op:
        batch_op.add_column(sa.Column("exercise_id", sa.String(length=64), nullable=True))

    op.execute(sa.text("UPDATE trainer_exercises SET exercise_id = row_id WHERE exercise_id IS NULL"))

    with op.batch_alter_table("trainer_exercises") as batch_op:
        batch_op.alter_column("exercise_id", existing_type=sa.String(length=64), nullable=False)
        batch_op.create_unique_constraint("uq_trainer_exercise_pair", ["trainer_user_id", "exercise_id"])
