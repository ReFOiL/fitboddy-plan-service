"""client loads, load schemes, and set prescriptions

Revision ID: 0010_loads_schemes
Revises: 0009_ex_baseline
Create Date: 2026-07-11 23:20:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0010_loads_schemes"
down_revision = "0009_ex_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "client_exercise_loads",
        sa.Column("load_id", sa.String(length=36), primary_key=True),
        sa.Column("client_user_id", sa.String(length=64), nullable=False),
        sa.Column("trainer_user_id", sa.String(length=64), nullable=False),
        sa.Column("exercise_row_id", sa.String(length=36), nullable=False),
        sa.Column("working_weight_kg", sa.Float(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint(
            "client_user_id",
            "trainer_user_id",
            "exercise_row_id",
            name="uq_client_trainer_exercise_load",
        ),
    )
    op.create_index("ix_client_exercise_loads_client", "client_exercise_loads", ["client_user_id"])
    op.create_index(
        "ix_client_exercise_loads_client_trainer",
        "client_exercise_loads",
        ["client_user_id", "trainer_user_id"],
    )

    with op.batch_alter_table("trainer_exercises") as batch_op:
        batch_op.add_column(
            sa.Column("load_scheme", sa.String(length=32), nullable=False, server_default="flat")
        )
        batch_op.add_column(sa.Column("scheme_steps_json", sa.Text(), nullable=True))

    with op.batch_alter_table("plan_exercises") as batch_op:
        batch_op.add_column(sa.Column("set_prescriptions_json", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("plan_exercises") as batch_op:
        batch_op.drop_column("set_prescriptions_json")

    with op.batch_alter_table("trainer_exercises") as batch_op:
        batch_op.drop_column("scheme_steps_json")
        batch_op.drop_column("load_scheme")

    op.drop_index("ix_client_exercise_loads_client_trainer", table_name="client_exercise_loads")
    op.drop_index("ix_client_exercise_loads_client", table_name="client_exercise_loads")
    op.drop_table("client_exercise_loads")
