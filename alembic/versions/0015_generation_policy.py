"""singleton generation policy for system workouts

Revision ID: 0015_gen_policy
Revises: 0014_load_scope
Create Date: 2026-07-18 23:40:00
"""

from __future__ import annotations

import json

from alembic import op
import sqlalchemy as sa


revision = "0015_gen_policy"
down_revision = "0014_load_scope"
branch_labels = None
depends_on = None

_DEFAULT_CONFIG = {
    "excluded_pairs": [],
    "default_splits": {
        "muscle_gain|beginner": ["full_body", "full_body", "full_body"],
        "muscle_gain|intermediate": ["upper", "lower", "upper", "lower"],
        "muscle_gain|advanced": ["upper", "lower", "upper", "lower", "full_body"],
        "weight_loss|beginner": ["full_body", "full_body", "full_body"],
        "weight_loss|intermediate": ["full_body", "full_body", "full_body", "full_body"],
        "maintenance|beginner": ["full_body", "full_body", "full_body"],
        "maintenance|intermediate": ["upper", "lower", "full_body"],
    },
    "default_workouts_per_week": {
        "beginner": 3,
        "intermediate": 3,
        "advanced": 4,
    },
}


def upgrade() -> None:
    op.create_table(
        "generation_policies",
        sa.Column("policy_id", sa.Integer(), primary_key=True),
        sa.Column("config_json", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.func.now()),
    )
    op.execute(
        sa.text("INSERT INTO generation_policies (policy_id, config_json) VALUES (1, :config)").bindparams(
            config=json.dumps(_DEFAULT_CONFIG, ensure_ascii=False)
        )
    )


def downgrade() -> None:
    op.drop_table("generation_policies")
