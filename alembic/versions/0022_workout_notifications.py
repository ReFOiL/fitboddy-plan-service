"""workout notification preferences, deliveries, and plan update debounce

Revision ID: 0022_workout_notifications
Revises: 0021_plan_notes_times
Create Date: 2026-10-20 12:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0022_workout_notifications"
down_revision = "0021_plan_notes_times"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notification_preferences",
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=True),
        sa.Column("telegram_chat_id", sa.BigInteger(), nullable=True),
        sa.Column("notifications_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("user_id"),
        sa.UniqueConstraint("telegram_chat_id"),
    )
    op.create_table(
        "plan_update_notices",
        sa.Column("plan_id", sa.String(length=36), nullable=False),
        sa.Column("client_user_id", sa.String(length=64), nullable=False),
        sa.Column("trainer_user_id", sa.String(length=64), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("sent_revision", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("notify_after", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["plan_id"], ["training_plans.plan_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("plan_id"),
    )
    op.create_index("ix_plan_update_notices_client_user_id", "plan_update_notices", ["client_user_id"])
    op.create_index("ix_plan_update_notices_notify_after", "plan_update_notices", ["notify_after"])
    op.create_table(
        "notification_deliveries",
        sa.Column("delivery_id", sa.String(length=36), nullable=False),
        sa.Column("dedupe_key", sa.String(length=160), nullable=False),
        sa.Column("recipient_user_id", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("delivery_id"),
        sa.UniqueConstraint("dedupe_key"),
    )
    op.create_index("ix_notification_deliveries_recipient_user_id", "notification_deliveries", ["recipient_user_id"])
    op.create_table(
        "telegram_link_codes",
        sa.Column("code", sa.String(length=16), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("code"),
    )
    op.create_index("ix_telegram_link_codes_user_id", "telegram_link_codes", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_telegram_link_codes_user_id", table_name="telegram_link_codes")
    op.drop_table("telegram_link_codes")
    op.drop_index("ix_notification_deliveries_recipient_user_id", table_name="notification_deliveries")
    op.drop_table("notification_deliveries")
    op.drop_index("ix_plan_update_notices_notify_after", table_name="plan_update_notices")
    op.drop_index("ix_plan_update_notices_client_user_id", table_name="plan_update_notices")
    op.drop_table("plan_update_notices")
    op.drop_table("notification_preferences")
