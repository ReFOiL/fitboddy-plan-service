"""add exercise_scope for client loads (trainer | platform)

Revision ID: 0014_load_scope
Revises: 0013_day_complete
Create Date: 2026-07-18 23:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0014_load_scope"
down_revision = "0013_day_complete"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("client_exercise_loads") as batch_op:
        batch_op.add_column(
            sa.Column("exercise_scope", sa.String(length=16), nullable=False, server_default="trainer")
        )
        batch_op.alter_column("trainer_user_id", existing_type=sa.String(length=64), nullable=True)
        batch_op.drop_constraint("uq_client_trainer_exercise_load", type_="unique")

    op.create_index(
        "uq_client_trainer_exercise_load",
        "client_exercise_loads",
        ["client_user_id", "trainer_user_id", "exercise_row_id"],
        unique=True,
        sqlite_where=sa.text("exercise_scope = 'trainer'"),
        postgresql_where=sa.text("exercise_scope = 'trainer'"),
    )
    op.create_index(
        "uq_client_platform_exercise_load",
        "client_exercise_loads",
        ["client_user_id", "exercise_row_id"],
        unique=True,
        sqlite_where=sa.text("exercise_scope = 'platform'"),
        postgresql_where=sa.text("exercise_scope = 'platform'"),
    )
    op.create_index(
        "ix_client_exercise_loads_client_scope",
        "client_exercise_loads",
        ["client_user_id", "exercise_scope"],
    )


def downgrade() -> None:
    op.drop_index("ix_client_exercise_loads_client_scope", table_name="client_exercise_loads")
    op.drop_index("uq_client_platform_exercise_load", table_name="client_exercise_loads")
    op.drop_index("uq_client_trainer_exercise_load", table_name="client_exercise_loads")

    with op.batch_alter_table("client_exercise_loads") as batch_op:
        batch_op.execute(
            sa.text("UPDATE client_exercise_loads SET trainer_user_id = '' WHERE trainer_user_id IS NULL")
        )
        batch_op.alter_column("trainer_user_id", existing_type=sa.String(length=64), nullable=False)
        batch_op.create_unique_constraint(
            "uq_client_trainer_exercise_load",
            ["client_user_id", "trainer_user_id", "exercise_row_id"],
        )
        batch_op.drop_column("exercise_scope")
