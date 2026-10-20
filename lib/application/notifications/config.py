from __future__ import annotations

from dataclasses import dataclass
from datetime import time, timedelta

from application.config import Settings


def parse_hhmm(value: str) -> time:
    hour_text, minute_text = value.split(":", maxsplit=1)
    return time(hour=int(hour_text), minute=int(minute_text))


@dataclass(frozen=True)
class NotificationConfig:
    default_timezone: str
    morning_reminder: time
    reminder_lead: timedelta
    missed_lookback: timedelta
    plan_notice_ttl: timedelta
    channel_ready: bool

    @classmethod
    def from_settings(cls, settings: Settings) -> NotificationConfig:
        return cls(
            default_timezone=settings.notifications_default_timezone,
            morning_reminder=parse_hhmm(settings.notifications_morning_reminder),
            reminder_lead=timedelta(minutes=settings.notifications_reminder_lead_minutes),
            missed_lookback=timedelta(days=settings.notifications_missed_lookback_days),
            plan_notice_ttl=timedelta(seconds=settings.notifications_plan_notice_ttl_seconds),
            channel_ready=bool(settings.telegram_bot_token.strip()),
        )
