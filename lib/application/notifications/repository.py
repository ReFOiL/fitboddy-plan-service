from __future__ import annotations

import secrets
from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from application.errors import PlanNotFoundError, ValidationError
from application.notifications.models import (
    NotificationDeliveryModel,
    NotificationPreferenceModel,
    PlanUpdateNoticeModel,
    TelegramLinkCodeModel,
)
from application.notifications.schedule import NoticeKind

_CLAIM_LEASE = timedelta(minutes=2)
_LINK_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


class NotificationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_preferences(self, user_id: str) -> NotificationPreferenceModel | None:
        return self._session.get(NotificationPreferenceModel, user_id)

    def preferences_for(self, user_ids: set[str]) -> dict[str, NotificationPreferenceModel]:
        if not user_ids:
            return {}
        rows = self._session.scalars(
            select(NotificationPreferenceModel).where(NotificationPreferenceModel.user_id.in_(user_ids))
        )
        return {row.user_id: row for row in rows}

    def ensure_preferences(self, user_id: str, now: datetime) -> NotificationPreferenceModel:
        row = self.get_preferences(user_id)
        if row is not None:
            return row
        row = NotificationPreferenceModel(
            user_id=user_id,
            timezone=None,
            telegram_chat_id=None,
            notifications_enabled=True,
            updated_at=now,
        )
        self._session.add(row)
        self._session.flush()
        return row

    def mark_plan_changed(
        self,
        *,
        plan_id: str,
        client_user_id: str,
        trainer_user_id: str,
        created: bool,
        now: datetime,
        debounce_seconds: int,
    ) -> None:
        # Повторные правки слотов сдвигают срок, а не ставят новое сообщение в очередь.
        # autoflush выключен: без flush вторая правка в той же сессии не видит первую.
        self._session.flush()
        notice = self._session.get(PlanUpdateNoticeModel, plan_id)
        notify_after = now + timedelta(seconds=debounce_seconds)
        if notice is None:
            self._session.add(
                PlanUpdateNoticeModel(
                    plan_id=plan_id,
                    client_user_id=client_user_id,
                    trainer_user_id=trainer_user_id,
                    revision=1,
                    sent_revision=0,
                    kind=NoticeKind.CREATED.value if created else NoticeKind.UPDATED.value,
                    notify_after=notify_after,
                )
            )
            return
        notice.client_user_id = client_user_id
        notice.trainer_user_id = trainer_user_id
        notice.revision += 1
        notice.notify_after = notify_after
        if notice.sent_revision == 0 and (notice.kind == NoticeKind.CREATED.value or created):
            notice.kind = NoticeKind.CREATED.value
        else:
            notice.kind = NoticeKind.UPDATED.value

    def due_notice_ids(self, now: datetime) -> list[str]:
        stmt = (
            select(PlanUpdateNoticeModel.plan_id)
            .where(PlanUpdateNoticeModel.notify_after <= now)
            .where(PlanUpdateNoticeModel.revision > PlanUpdateNoticeModel.sent_revision)
            .order_by(PlanUpdateNoticeModel.notify_after)
        )
        return list(self._session.scalars(stmt))

    def get_notice(self, plan_id: str) -> PlanUpdateNoticeModel | None:
        return self._session.get(PlanUpdateNoticeModel, plan_id)

    def advance_notice(self, plan_id: str, seen_revision: int) -> None:
        notice = self.get_notice(plan_id)
        if notice is None:
            return
        if seen_revision > notice.sent_revision:
            notice.sent_revision = seen_revision
        self._session.commit()

    def claim(self, *, dedupe_key: str, recipient_user_id: str, event_type: str, status: str, now: datetime) -> bool:
        existing = self._session.scalar(
            select(NotificationDeliveryModel).where(NotificationDeliveryModel.dedupe_key == dedupe_key)
        )
        if existing is not None:
            if existing.status == "pending" and existing.created_at <= now - _CLAIM_LEASE:
                self._session.delete(existing)
                self._session.commit()
            else:
                return False
        self._session.add(
            NotificationDeliveryModel(
                delivery_id=str(uuid4()),
                dedupe_key=dedupe_key,
                recipient_user_id=recipient_user_id,
                event_type=event_type,
                status=status,
                created_at=now,
                sent_at=now if status != "pending" else None,
            )
        )
        try:
            self._session.commit()
        except IntegrityError:
            self._session.rollback()
            return False
        return True

    def finish_delivery(self, dedupe_key: str, status: str, now: datetime) -> None:
        row = self._session.scalar(
            select(NotificationDeliveryModel).where(NotificationDeliveryModel.dedupe_key == dedupe_key)
        )
        if row is None:
            return
        row.status = status
        row.sent_at = now
        self._session.commit()

    def release_delivery(self, dedupe_key: str) -> None:
        row = self._session.scalar(
            select(NotificationDeliveryModel).where(NotificationDeliveryModel.dedupe_key == dedupe_key)
        )
        if row is not None:
            self._session.delete(row)
        self._session.commit()

    def issue_link_code(self, user_id: str, now: datetime, ttl_seconds: int) -> tuple[str, datetime]:
        expires_at = now + timedelta(seconds=ttl_seconds)
        self._session.execute(
            update(TelegramLinkCodeModel)
            .where(TelegramLinkCodeModel.user_id == user_id, TelegramLinkCodeModel.used_at.is_(None))
            .values(used_at=now)
        )
        for _ in range(5):
            code = "".join(secrets.choice(_LINK_ALPHABET) for _ in range(8))
            if self._session.get(TelegramLinkCodeModel, code) is not None:
                continue
            self._session.add(
                TelegramLinkCodeModel(code=code, user_id=user_id, expires_at=expires_at, used_at=None)
            )
            self._session.flush()
            return code, expires_at
        raise ValidationError("could not allocate link code")

    def consume_link_code(self, code: str, now: datetime) -> str:
        normalized = code.strip().upper()
        result = self._session.execute(
            update(TelegramLinkCodeModel)
            .where(
                TelegramLinkCodeModel.code == normalized,
                TelegramLinkCodeModel.used_at.is_(None),
                TelegramLinkCodeModel.expires_at >= now,
            )
            .values(used_at=now)
        )
        if result.rowcount != 1:
            raise PlanNotFoundError("link code is invalid or expired")
        row = self._session.get(TelegramLinkCodeModel, normalized)
        if row is None:
            raise PlanNotFoundError("link code is invalid or expired")
        return row.user_id

    def set_telegram_chat(self, user_id: str, chat_id: int, now: datetime) -> None:
        # Один чат принадлежит одному пользователю: прежняя привязка снимается.
        self._session.execute(
            update(NotificationPreferenceModel)
            .where(
                NotificationPreferenceModel.telegram_chat_id == chat_id,
                NotificationPreferenceModel.user_id != user_id,
            )
            .values(telegram_chat_id=None, updated_at=now)
        )
        row = self.ensure_preferences(user_id, now)
        row.telegram_chat_id = chat_id
        row.updated_at = now

    def clear_telegram_chat(self, user_id: str, now: datetime) -> None:
        row = self.get_preferences(user_id)
        if row is None or row.telegram_chat_id is None:
            return
        row.telegram_chat_id = None
        row.updated_at = now
