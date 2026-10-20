"""Таблицы уведомлений. Время хранится как наивный UTC, как и остальные даты плана."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from application.db import Base


class NotificationPreferenceModel(Base):
    __tablename__ = "notification_preferences"

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    timezone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    telegram_chat_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, unique=True)
    notifications_enabled: Mapped[bool] = mapped_column(nullable=False, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)


class PlanUpdateNoticeModel(Base):
    __tablename__ = "plan_update_notices"

    plan_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("training_plans.plan_id", ondelete="CASCADE"),
        primary_key=True,
    )
    client_user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    trainer_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    sent_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    notify_after: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, index=True)


class NotificationDeliveryModel(Base):
    __tablename__ = "notification_deliveries"

    delivery_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    dedupe_key: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    recipient_user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)


class TelegramLinkCodeModel(Base):
    __tablename__ = "telegram_link_codes"

    code: Mapped[str] = mapped_column(String(16), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
