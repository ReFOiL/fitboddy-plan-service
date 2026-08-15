"""one active training plan per user

Revision ID: 0018_one_active_plan
Revises: 0017_trainer_policy
Create Date: 2026-08-15 17:20:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0018_one_active_plan"
down_revision = "0017_trainer_policy"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    duplicates = bind.execute(
        sa.text(
            """
            SELECT user_id
            FROM training_plans
            WHERE status = 'active'
            GROUP BY user_id
            HAVING COUNT(*) > 1
            """
        )
    ).mappings()
    for row in duplicates:
        extra_ids = bind.execute(
            sa.text(
                """
                SELECT plan_id
                FROM training_plans
                WHERE user_id = :user_id AND status = 'active'
                ORDER BY created_at DESC, plan_id DESC
                """
            ),
            {"user_id": row["user_id"]},
        ).scalars().all()
        for plan_id in extra_ids[1:]:
            bind.execute(
                sa.text(
                    """
                    UPDATE training_plans
                    SET status = 'archived'
                    WHERE plan_id = :plan_id
                    """
                ),
                {"plan_id": plan_id},
            )

    op.create_index(
        "uq_training_plans_one_active_per_user",
        "training_plans",
        ["user_id"],
        unique=True,
        sqlite_where=sa.text("status = 'active'"),
        postgresql_where=sa.text("status = 'active'"),
    )


def downgrade() -> None:
    op.drop_index("uq_training_plans_one_active_per_user", table_name="training_plans")
