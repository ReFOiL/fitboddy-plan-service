"""Когда слать напоминание и когда день уже считается пропущенным.

Дедлайн — локальное scheduled_time, если оно задано. Иначе день проходит в местную полночь.
Напоминание — за lead до этого времени, либо утром в morning_reminder, если времени нет.
Часовой пояс берётся из настроек пользователя, иначе из конфига (по умолчанию Asia/Vladivostok).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from enum import Enum
from typing import assert_never
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class NoticeKind(Enum):
    CREATED = "created"
    UPDATED = "updated"


@dataclass(frozen=True)
class WorkoutWindow:
    reminder_at: datetime
    deadline_at: datetime


def resolve_timezone(stored: str | None, default_name: str) -> ZoneInfo:
    if stored:
        try:
            return ZoneInfo(stored)
        except ZoneInfoNotFoundError:
            pass
    return ZoneInfo(default_name)


def workout_window(
    *,
    scheduled_for: date,
    scheduled_time: time | None,
    timezone: ZoneInfo,
    morning_reminder: time,
    reminder_lead: timedelta,
) -> WorkoutWindow:
    if scheduled_time is None:
        reminder = datetime.combine(scheduled_for, morning_reminder, tzinfo=timezone)
        deadline = datetime.combine(scheduled_for + timedelta(days=1), time.min, tzinfo=timezone)
        return WorkoutWindow(reminder_at=_naive_utc(reminder), deadline_at=_naive_utc(deadline))
    start = datetime.combine(scheduled_for, scheduled_time, tzinfo=timezone)
    reminder = start - reminder_lead
    return WorkoutWindow(reminder_at=_naive_utc(reminder), deadline_at=_naive_utc(start))


def reminder_is_due(window: WorkoutWindow, now: datetime) -> bool:
    return window.reminder_at <= now < window.deadline_at


def missed_is_due(window: WorkoutWindow, now: datetime, lookback: timedelta) -> bool:
    return window.deadline_at <= now < window.deadline_at + lookback


def reminder_text(scheduled_time: time | None) -> str:
    if scheduled_time is None:
        return "Сегодня тренировка. Хорошей работы."
    return f"Тренировка в {scheduled_time.strftime('%H:%M')}."


def missed_text(*, client_label: str | None, scheduled_for: date) -> str:
    who = f"Клиент {client_label}" if client_label else "Клиент"
    return f"{who} не выполнил тренировку {scheduled_for.strftime('%d.%m')}."


def plan_text(kind: NoticeKind) -> str:
    match kind:
        case NoticeKind.CREATED:
            return "Тренер составил вам план тренировок."
        case NoticeKind.UPDATED:
            return "Тренер обновил ваш план тренировок."
        case _ as unreachable:
            assert_never(unreachable)


def notice_kind(value: str) -> NoticeKind:
    if value == NoticeKind.CREATED.value:
        return NoticeKind.CREATED
    return NoticeKind.UPDATED


def _naive_utc(moment: datetime) -> datetime:
    return moment.astimezone(UTC).replace(tzinfo=None)
