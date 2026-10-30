from datetime import date
from types import SimpleNamespace

from application.errors import ValidationError
from application.plan_start import (
    PlanStartMode,
    day_is_shown,
    monday_aligned_date,
    next_calendar_week_monday,
    next_training_day,
    resolve_plan_start,
)
from application.use_cases import PlanService

# 2026-10-21 is Wednesday. Monday of that week is 2026-10-19. Next Monday is 2026-10-26.
_WEDNESDAY = date(2026, 10, 21)
_SATURDAY = date(2026, 10, 24)
_SLOTS = {0, 2, 4}


def test_next_training_day_from_saturday_is_monday() -> None:
    assert next_training_day(_SATURDAY, _SLOTS) == date(2026, 10, 26)


def test_next_training_day_includes_today_when_it_is_a_slot() -> None:
    assert next_training_day(_WEDNESDAY, _SLOTS) == _WEDNESDAY


def test_next_calendar_week_monday_skips_today_when_today_is_monday() -> None:
    monday = date(2026, 10, 19)
    assert monday.weekday() == 0
    assert next_calendar_week_monday(monday) == date(2026, 10, 26)
    assert next_calendar_week_monday(_WEDNESDAY) == date(2026, 10, 26)
    assert next_calendar_week_monday(_SATURDAY) == date(2026, 10, 26)


def test_explicit_wednesday_hides_monday_of_the_first_week() -> None:
    anchor = resolve_plan_start(PlanStartMode.DATE, _WEDNESDAY, _SATURDAY, _SLOTS)
    monday = monday_aligned_date(anchor, 1, 0)
    wednesday = monday_aligned_date(anchor, 1, 2)
    friday = monday_aligned_date(anchor, 1, 4)
    assert monday == date(2026, 10, 19)
    assert wednesday == _WEDNESDAY
    assert friday == date(2026, 10, 23)
    assert day_is_shown("date", anchor, 1, monday, False) is False
    assert day_is_shown("date", anchor, 1, wednesday, False) is True
    assert day_is_shown("date", anchor, 1, friday, False) is True
    # Завершённый день остаётся видимым, даже если дата раньше нового якоря.
    assert day_is_shown("date", date(2026, 10, 26), 1, wednesday, True) is True


def test_legacy_mode_never_hides_a_day() -> None:
    assert day_is_shown(None, _WEDNESDAY, 1, date(2026, 10, 19), False) is True


def test_date_mode_requires_start_date_and_other_modes_reject_it() -> None:
    try:
        resolve_plan_start(PlanStartMode.DATE, None, _WEDNESDAY, _SLOTS)
    except ValidationError as exc:
        assert "start_date is required" in str(exc)
    else:
        raise AssertionError("expected validation error")
    try:
        resolve_plan_start(PlanStartMode.NEXT_SLOT, _WEDNESDAY, _WEDNESDAY, _SLOTS)
    except ValidationError as exc:
        assert "must be omitted" in str(exc)
    else:
        raise AssertionError("expected validation error")


def test_adherence_ignores_days_before_the_anchor() -> None:
    plan = SimpleNamespace(
        start_mode="date",
        start_date=_WEDNESDAY,
        days=[
            SimpleNamespace(week=1, scheduled_for=date(2026, 10, 19), is_completed=False, exercises=[]),
            SimpleNamespace(
                week=1,
                scheduled_for=_WEDNESDAY,
                is_completed=True,
                exercises=[SimpleNamespace(exercise_id="press")],
            ),
            SimpleNamespace(week=1, scheduled_for=date(2026, 10, 23), is_completed=False, exercises=[]),
        ],
    )
    adherence, recent = PlanService._adherence_from_plan(plan)
    assert adherence == 0.5
    assert recent == {"press"}

    hidden_only = SimpleNamespace(
        start_mode="date",
        start_date=_WEDNESDAY,
        days=[SimpleNamespace(week=1, scheduled_for=date(2026, 10, 19), is_completed=False, exercises=[])],
    )
    assert PlanService._adherence_from_plan(hidden_only) == (1.0, set())
