"""Якорь календаря плана, который выбирает тренер при сохранении.

«Сегодня» клиента — серверная дата, как у тренировки на сегодня: отдельного
часового пояса в сервисе нет. day_of_week совпадает с weekday(): понедельник = 0.

Без режима неделя по-прежнему окно в 7 дней от start_date. С режимом неделя —
календарная, от понедельника той недели, куда попал якорь. Дни первой недели
раньше якоря клиенту не показываются и пропуском не считаются.
"""

from __future__ import annotations

from datetime import date, timedelta
from enum import StrEnum
from typing import assert_never

from application.errors import ValidationError


class PlanStartMode(StrEnum):
    NEXT_SLOT = "next_slot"
    NEXT_WEEK = "next_week"
    DATE = "date"

    @classmethod
    def parse(cls, raw: str | None) -> PlanStartMode | None:
        if raw is None:
            return None
        normalized = raw.strip().lower()
        for item in cls:
            if item.value == normalized:
                return item
        raise ValidationError("start_mode must be one of: next_slot, next_week, date")


def next_calendar_week_monday(today: date) -> date:
    """Понедельник следующей календарной недели. Если сегодня понедельник — через 7 дней."""
    return today + timedelta(days=7 - today.weekday())


def next_training_day(today: date, weekdays: set[int]) -> date:
    """Ближайший день тренировки сегодня или позже. Пустой набор слотов — сегодня."""
    if not weekdays:
        return today
    for offset in range(7):
        candidate = today + timedelta(days=offset)
        if candidate.weekday() in weekdays:
            return candidate
    return today


def monday_aligned_date(anchor: date, week: int, day_of_week: int) -> date:
    """Дата слота: неделя 1 начинается в понедельник недели, содержащей якорь."""
    week_monday = anchor - timedelta(days=anchor.weekday()) + timedelta(days=(week - 1) * 7)
    return week_monday + timedelta(days=day_of_week)


def resolve_plan_start(
    mode: PlanStartMode,
    explicit: date | None,
    today: date,
    weekdays: set[int],
) -> date:
    match mode:
        case PlanStartMode.DATE:
            if explicit is None:
                raise ValidationError("start_date is required when start_mode=date")
            return explicit
        case PlanStartMode.NEXT_WEEK:
            if explicit is not None:
                raise ValidationError("start_date must be omitted unless start_mode=date")
            return next_calendar_week_monday(today)
        case PlanStartMode.NEXT_SLOT:
            if explicit is not None:
                raise ValidationError("start_date must be omitted unless start_mode=date")
            return next_training_day(today, weekdays)
        case _:
            assert_never(mode)


def day_is_shown(
    start_mode: str | None,
    start_date: date,
    week: int,
    scheduled_for: date,
    is_completed: bool,
) -> bool:
    """Завершённую тренировку не прячем. День первой недели до якоря клиенту не показываем."""
    if is_completed or not start_mode:
        return True
    return not (week == 1 and scheduled_for < start_date)
