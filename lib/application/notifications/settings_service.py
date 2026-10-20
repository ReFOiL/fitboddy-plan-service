from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.orm import Session

from application.config import Settings
from application.errors import ValidationError
from application.notifications.repository import NotificationRepository


@dataclass(frozen=True)
class NotificationSettingsView:
    timezone: str
    timezone_is_default: bool
    notifications_enabled: bool
    telegram_linked: bool


@dataclass(frozen=True)
class TelegramLinkCode:
    code: str
    expires_at: datetime


class NotificationSettingsService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._repo = NotificationRepository(session)

    def get_settings(self, user_id: str) -> NotificationSettingsView:
        row = self._repo.get_preferences(user_id)
        stored = None if row is None else row.timezone
        enabled = True if row is None else bool(row.notifications_enabled)
        linked = row is not None and row.telegram_chat_id is not None
        return NotificationSettingsView(
            timezone=stored or self._settings.notifications_default_timezone,
            timezone_is_default=stored is None,
            notifications_enabled=enabled,
            telegram_linked=linked,
        )

    def update_settings(
        self,
        user_id: str,
        *,
        timezone_specified: bool,
        timezone_name: str | None,
        enabled_specified: bool,
        notifications_enabled: bool | None,
    ) -> NotificationSettingsView:
        now = _utcnow()
        row = self._repo.ensure_preferences(user_id, now)
        if timezone_specified:
            row.timezone = _clean_timezone(timezone_name)
        if enabled_specified:
            if notifications_enabled is None:
                raise ValidationError("notifications_enabled cannot be null")
            row.notifications_enabled = notifications_enabled
        row.updated_at = now
        return self.get_settings(user_id)

    def issue_link_code(self, user_id: str) -> TelegramLinkCode:
        code, expires_at = self._repo.issue_link_code(
            user_id,
            _utcnow(),
            self._settings.notifications_link_code_ttl_seconds,
        )
        return TelegramLinkCode(code=code, expires_at=expires_at)

    def confirm_telegram(self, code: str, chat_id: int) -> None:
        if chat_id <= 0:
            raise ValidationError("chat_id must be positive")
        now = _utcnow()
        user_id = self._repo.consume_link_code(code, now)
        self._repo.set_telegram_chat(user_id, chat_id, now)

    def unlink_telegram(self, user_id: str) -> None:
        self._repo.clear_telegram_chat(user_id, _utcnow())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _clean_timezone(value: str | None) -> str | None:
    if value is None:
        return None
    name = value.strip()
    if not name:
        return None
    try:
        ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        raise ValidationError("unknown timezone") from exc
    return name
