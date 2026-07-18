"""add plan source and allow system plans without trainer

Revision ID: 0011_plan_source
Revises: 0010_loads_schemes
Create Date: 2026-07-18 21:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0011_plan_source"
down_revision = "0010_loads_schemes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("training_plans") as batch_op:
        batch_op.add_column(
            sa.Column("source", sa.String(length=16), nullable=False, server_default="trainer")
        )
        batch_op.alter_column("trainer_user_id", existing_type=sa.String(length=64), nullable=True)

    op.execute(sa.text("UPDATE training_plans SET source = 'trainer' WHERE source IS NULL OR source = ''"))

    with op.batch_alter_table("training_plans") as batch_op:
        batch_op.create_check_constraint(
            "ck_training_plans_source_trainer",
            "(source = 'trainer' AND trainer_user_id IS NOT NULL) OR "
            "(source = 'system' AND trainer_user_id IS NULL)",
        )
        batch_op.create_check_constraint(
            "ck_training_plans_source_values",
            "source IN ('trainer', 'system')",
        )

    op.create_index("ix_training_plans_source", "training_plans", ["source"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_training_plans_source", table_name="training_plans")

    op.execute(
        sa.text(
            "UPDATE training_plans SET trainer_user_id = 'unknown_trainer' "
            "WHERE trainer_user_id IS NULL"
        )
    )

    with op.batch_alter_table("training_plans") as batch_op:
        batch_op.drop_constraint("ck_training_plans_source_values", type_="check")
        batch_op.drop_constraint("ck_training_plans_source_trainer", type_="check")
        batch_op.alter_column("trainer_user_id", existing_type=sa.String(length=64), nullable=False)
        batch_op.drop_column("source")
