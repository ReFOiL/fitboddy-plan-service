"""queue media object deletes that must be retried

Revision ID: 0024_pending_media_deletes
Revises: 0023_plan_start_mode
Create Date: 2026-11-02 00:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0024_pending_media_deletes"
down_revision = "0023_plan_start_mode"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pending_media_deletes",
        sa.Column("object_key", sa.String(length=500), primary_key=True),
        sa.Column("owner_id", sa.String(length=64), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_pending_media_deletes_attempts_created",
        "pending_media_deletes",
        ["attempts", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_pending_media_deletes_attempts_created", table_name="pending_media_deletes")
    op.drop_table("pending_media_deletes")
