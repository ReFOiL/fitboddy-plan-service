from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from enum import Enum
from typing import Protocol, assert_never

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from application.models import PlanDayModel, PlanExerciseModel, TrainingPlanModel
from application.notifications.config import NotificationConfig
from application.notifications.models import NotificationPreferenceModel
from application.notifications.repository import NotificationRepository
from application.notifications.schedule import (
    missed_is_due,
    missed_text,
    notice_kind,
    plan_text,
    reminder_is_due,
    reminder_text,
    resolve_timezone,
    workout_window,
)
from application.notifications.telegram import TelegramPermanentError, TelegramTransientError

logger = logging.getLogger(__name__)

LoginLookup = Callable[[list[str]], dict[str, str]]


class OutboundMessage(Protocol):
    def send(self, chat_id: int, text: str) -> None: ...


class DeliveryAttempt(Enum):
    SENT = "sent"
    SKIPPED_OPT_OUT = "skipped_opt_out"
    SKIPPED_BLOCKED = "skipped_blocked"
    SKIPPED_NO_CHAT = "skipped_no_chat"
    DUPLICATE = "duplicate"
    RETRY = "retry"


@dataclass(frozen=True)
class OpenWorkout:
    day_id: str
    client_user_id: str
    trainer_user_id: str | None
    scheduled_for: date
    scheduled_time: time | None
    client_enabled: bool
    client_chat_id: int | None
    client_timezone: str | None
    trainer_enabled: bool
    trainer_chat_id: int | None


@dataclass
class DispatchStats:
    sent: int = 0
    skipped: int = 0
    retry: int = 0

    def record(self, attempt: DeliveryAttempt) -> None:
        match attempt:
            case DeliveryAttempt.SENT:
                self.sent += 1
            case (
                DeliveryAttempt.SKIPPED_OPT_OUT
                | DeliveryAttempt.SKIPPED_BLOCKED
                | DeliveryAttempt.SKIPPED_NO_CHAT
                | DeliveryAttempt.DUPLICATE
            ):
                self.skipped += 1
            case DeliveryAttempt.RETRY:
                self.retry += 1
            case _ as unreachable:
                assert_never(unreachable)


class NotificationDispatcher:
    def __init__(
        self,
        session: Session,
        *,
        config: NotificationConfig,
        sender: OutboundMessage,
        login_lookup: LoginLookup,
    ) -> None:
        self._session = session
        self._config = config
        self._sender = sender
        self._login_lookup = login_lookup
        self._repo = NotificationRepository(session)

    def run(self, now: datetime) -> DispatchStats:
        stats = DispatchStats()
        self._dispatch_workouts(now, stats)
        self._dispatch_plan_notices(now, stats)
        return stats

    def _dispatch_workouts(self, now: datetime, stats: DispatchStats) -> None:
        workouts = self._load_open_workouts(now)
        windows = {
            item.day_id: workout_window(
                scheduled_for=item.scheduled_for,
                scheduled_time=item.scheduled_time,
                timezone=resolve_timezone(item.client_timezone, self._config.default_timezone),
                morning_reminder=self._config.morning_reminder,
                reminder_lead=self._config.reminder_lead,
            )
            for item in workouts
        }
        labels = self._labels(
            [
                item.client_user_id
                for item in workouts
                if item.trainer_user_id
                and item.trainer_enabled
                and item.trainer_chat_id is not None
                and self._config.channel_ready
                and missed_is_due(windows[item.day_id], now, self._config.missed_lookback)
            ]
        )
        for item in workouts:
            window = windows[item.day_id]
            if reminder_is_due(window, now):
                stats.record(
                    self._deliver(
                        dedupe_key=f"workout_reminder:{item.day_id}",
                        recipient_user_id=item.client_user_id,
                        event_type="workout_reminder",
                        text=reminder_text(item.scheduled_time),
                        chat_id=item.client_chat_id,
                        enabled=item.client_enabled,
                        now=now,
                    )
                )
            if item.trainer_user_id and missed_is_due(window, now, self._config.missed_lookback):
                stats.record(
                    self._deliver(
                        dedupe_key=f"workout_missed:{item.day_id}",
                        recipient_user_id=item.trainer_user_id,
                        event_type="workout_missed",
                        text=missed_text(
                            client_label=labels.get(item.client_user_id),
                            scheduled_for=item.scheduled_for,
                        ),
                        chat_id=item.trainer_chat_id,
                        enabled=item.trainer_enabled,
                        now=now,
                    )
                )

    def _dispatch_plan_notices(self, now: datetime, stats: DispatchStats) -> None:
        for plan_id in self._repo.due_notice_ids(now):
            notice = self._repo.get_notice(plan_id)
            if notice is None or notice.revision <= notice.sent_revision or notice.notify_after > now:
                continue
            seen_revision = notice.revision
            plan = self._session.get(TrainingPlanModel, plan_id)
            if plan is None or plan.status != "active":
                self._repo.advance_notice(plan_id, seen_revision)
                stats.skipped += 1
                continue
            preference = self._repo.get_preferences(notice.client_user_id)
            attempt = self._deliver(
                dedupe_key=f"plan_notice:{plan_id}:{seen_revision}",
                recipient_user_id=notice.client_user_id,
                event_type="plan_created" if notice.kind == "created" else "plan_updated",
                text=plan_text(notice_kind(notice.kind)),
                chat_id=_chat_id(preference),
                enabled=_enabled(preference),
                now=now,
            )
            if attempt is DeliveryAttempt.RETRY and now >= notice.notify_after + self._config.plan_notice_ttl:
                attempt = self._deliver_terminal(
                    dedupe_key=f"plan_notice:{plan_id}:{seen_revision}",
                    recipient_user_id=notice.client_user_id,
                    event_type="plan_created" if notice.kind == "created" else "plan_updated",
                    status="skipped_no_chat",
                    now=now,
                )
            stats.record(attempt)
            if attempt is not DeliveryAttempt.RETRY:
                self._repo.advance_notice(plan_id, seen_revision)

    def _load_open_workouts(self, now: datetime) -> list[OpenWorkout]:
        # Запас по календарю перекрывает смещение пояса относительно UTC и окно lookback.
        earliest = now.date() - self._config.missed_lookback - timedelta(days=2)
        latest = now.date() + timedelta(days=2)
        has_exercise = exists(
            select(PlanExerciseModel.line_id).where(PlanExerciseModel.day_id == PlanDayModel.day_id)
        )
        stmt = (
            select(PlanDayModel, TrainingPlanModel)
            .join(TrainingPlanModel, TrainingPlanModel.plan_id == PlanDayModel.plan_id)
            .where(TrainingPlanModel.status == "active")
            .where(PlanDayModel.is_completed.is_(False))
            .where(has_exercise)
            .where(PlanDayModel.scheduled_for >= earliest)
            .where(PlanDayModel.scheduled_for <= latest)
        )
        rows = list(self._session.execute(stmt).all())
        user_ids: set[str] = set()
        for _day, plan in rows:
            user_ids.add(plan.user_id)
            if plan.trainer_user_id:
                user_ids.add(plan.trainer_user_id)
        preferences = self._repo.preferences_for(user_ids)
        workouts: list[OpenWorkout] = []
        for day, plan in rows:
            client_pref = preferences.get(plan.user_id)
            trainer_pref = preferences.get(plan.trainer_user_id) if plan.trainer_user_id else None
            workouts.append(
                OpenWorkout(
                    day_id=day.day_id,
                    client_user_id=plan.user_id,
                    trainer_user_id=plan.trainer_user_id,
                    scheduled_for=day.scheduled_for,
                    scheduled_time=day.scheduled_time,
                    client_enabled=_enabled(client_pref),
                    client_chat_id=_chat_id(client_pref),
                    client_timezone=None if client_pref is None else client_pref.timezone,
                    trainer_enabled=_enabled(trainer_pref),
                    trainer_chat_id=_chat_id(trainer_pref),
                )
            )
        return workouts

    def _labels(self, user_ids: list[str]) -> dict[str, str]:
        unique = list(dict.fromkeys(user_ids))
        if not unique:
            return {}
        try:
            found = self._login_lookup(unique)
        except Exception:
            logger.exception("client login lookup failed")
            return {}
        return {user_id: login for user_id, login in found.items() if login}

    def _deliver(
        self,
        *,
        dedupe_key: str,
        recipient_user_id: str,
        event_type: str,
        text: str,
        chat_id: int | None,
        enabled: bool,
        now: datetime,
    ) -> DeliveryAttempt:
        if not enabled:
            return self._deliver_terminal(
                dedupe_key=dedupe_key,
                recipient_user_id=recipient_user_id,
                event_type=event_type,
                status="skipped_opt_out",
                now=now,
            )
        if chat_id is None or not self._config.channel_ready:
            return DeliveryAttempt.RETRY
        claimed = self._repo.claim(
            dedupe_key=dedupe_key,
            recipient_user_id=recipient_user_id,
            event_type=event_type,
            status="pending",
            now=now,
        )
        if not claimed:
            return DeliveryAttempt.DUPLICATE
        try:
            self._sender.send(chat_id, text)
        except TelegramPermanentError:
            logger.info("telegram refused notification", extra={"event_type": event_type})
            self._repo.finish_delivery(dedupe_key, "skipped_blocked", now)
            return DeliveryAttempt.SKIPPED_BLOCKED
        except TelegramTransientError:
            logger.warning("telegram notification will be retried", extra={"event_type": event_type})
            self._repo.release_delivery(dedupe_key)
            return DeliveryAttempt.RETRY
        except Exception:
            logger.exception("telegram notification was not sent")
            self._repo.release_delivery(dedupe_key)
            return DeliveryAttempt.RETRY
        self._repo.finish_delivery(dedupe_key, "sent", now)
        return DeliveryAttempt.SENT

    def _deliver_terminal(
        self,
        *,
        dedupe_key: str,
        recipient_user_id: str,
        event_type: str,
        status: str,
        now: datetime,
    ) -> DeliveryAttempt:
        claimed = self._repo.claim(
            dedupe_key=dedupe_key,
            recipient_user_id=recipient_user_id,
            event_type=event_type,
            status=status,
            now=now,
        )
        if not claimed:
            return DeliveryAttempt.DUPLICATE
        if status == "skipped_opt_out":
            return DeliveryAttempt.SKIPPED_OPT_OUT
        if status == "skipped_no_chat":
            return DeliveryAttempt.SKIPPED_NO_CHAT
        return DeliveryAttempt.SKIPPED_BLOCKED


def _enabled(preference: NotificationPreferenceModel | None) -> bool:
    if preference is None:
        return True
    return bool(preference.notifications_enabled)


def _chat_id(preference: NotificationPreferenceModel | None) -> int | None:
    if preference is None or preference.telegram_chat_id is None:
        return None
    return int(preference.telegram_chat_id)
