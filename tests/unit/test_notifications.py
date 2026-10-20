from __future__ import annotations

from datetime import date, datetime, time, timedelta
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session, sessionmaker

from application.gateways import AuthUser
from application.models import PlanDayModel, PlanExerciseModel, TrainingPlanModel
from application.notifications.config import NotificationConfig
from application.notifications.dispatcher import NotificationDispatcher
from application.notifications.models import NotificationPreferenceModel, PlanUpdateNoticeModel
from application.notifications.repository import NotificationRepository
from application.notifications.schedule import (
    NoticeKind,
    missed_is_due,
    missed_text,
    plan_text,
    reminder_is_due,
    reminder_text,
    workout_window,
)
from application.notifications.scheduler import start_notification_scheduler
from application.notifications.telegram import TelegramPermanentError, TelegramTransientError
from presentation.http.main import app

_USER_HEADERS = {"Authorization": "Bearer test-user-token"}
_SERVICE_TOKEN = "test-internal-token"
_ACTIVE_RELATIONS: dict[str, str] = {}


class RecordingSender:
    def __init__(self) -> None:
        self.sent: list[tuple[int, str]] = []

    def send(self, chat_id: int, text: str) -> None:
        self.sent.append((chat_id, text))


class FlakySender:
    def __init__(self, error: Exception) -> None:
        self._error = error
        self.sent: list[tuple[int, str]] = []
        self.calls = 0

    def send(self, chat_id: int, text: str) -> None:
        self.calls += 1
        if self.calls == 1:
            raise self._error
        self.sent.append((chat_id, text))


def _config(**overrides: object) -> NotificationConfig:
    values: dict[str, object] = {
        "default_timezone": "Asia/Vladivostok",
        "morning_reminder": time(9, 0),
        "reminder_lead": timedelta(hours=2),
        "missed_lookback": timedelta(days=2),
        "plan_notice_ttl": timedelta(days=7),
        "channel_ready": True,
    }
    values.update(overrides)
    return NotificationConfig(**values)  # type: ignore[arg-type]


def _db(tmp_path: Path, monkeypatch) -> sessionmaker[Session]:
    # env.py берёт DATABASE_URL и иначе мигрирует общую тестовую базу.
    url = f"sqlite+pysqlite:///{(tmp_path / 'notifications.db').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")
    engine = create_engine(url, connect_args={"check_same_thread": False})
    return sessionmaker(bind=engine, autoflush=False, future=True)


def _run(
    session: Session,
    now: datetime,
    sender: RecordingSender | FlakySender,
    *,
    logins: dict[str, str] | None = None,
    **overrides: object,
) -> None:
    labels = {} if logins is None else logins
    NotificationDispatcher(
        session,
        config=_config(**overrides),
        sender=sender,
        login_lookup=lambda user_ids: {user_id: labels[user_id] for user_id in user_ids if user_id in labels},
    ).run(now)


def _preference(
    session: Session,
    user_id: str,
    *,
    chat_id: int | None,
    timezone_name: str | None = None,
    enabled: bool = True,
) -> None:
    session.add(
        NotificationPreferenceModel(
            user_id=user_id,
            timezone=timezone_name,
            telegram_chat_id=chat_id,
            notifications_enabled=enabled,
            updated_at=datetime(2026, 10, 1, 0, 0),
        )
    )


def _workout(
    session: Session,
    *,
    client_user_id: str,
    trainer_user_id: str | None,
    scheduled_for: date,
    scheduled_time: time | None,
    with_exercise: bool = True,
    completed: bool = False,
    status: str = "active",
) -> str:
    plan_id = str(uuid4())
    day_id = str(uuid4())
    session.add(
        TrainingPlanModel(
            plan_id=plan_id,
            source="trainer" if trainer_user_id else "system",
            trainer_user_id=trainer_user_id,
            user_id=client_user_id,
            status=status,
            goal="maintenance",
            level="intermediate",
            workouts_per_week=3,
            start_date=scheduled_for,
            end_date=scheduled_for,
        )
    )
    session.add(
        PlanDayModel(
            day_id=day_id,
            plan_id=plan_id,
            day_index=1,
            scheduled_for=scheduled_for,
            week=1,
            day_of_week=scheduled_for.weekday(),
            volume_multiplier=1.0,
            is_completed=completed,
            completed_at=datetime(2026, 10, 20, 12, 0) if completed else None,
            scheduled_time=scheduled_time,
        )
    )
    if with_exercise:
        session.add(
            PlanExerciseModel(
                line_id=str(uuid4()),
                day_id=day_id,
                exercise_id="exercise-1",
                exercise_name="Присед",
                category="lower",
                is_cardio=False,
                sort_order=1,
            )
        )
    session.commit()
    return day_id


def test_windows_use_scheduled_time_or_local_midnight() -> None:
    utc = ZoneInfo("UTC")
    timed = workout_window(
        scheduled_for=date(2026, 10, 20),
        scheduled_time=time(18, 0),
        timezone=utc,
        morning_reminder=time(9, 0),
        reminder_lead=timedelta(hours=2),
    )
    assert timed.reminder_at == datetime(2026, 10, 20, 16, 0)
    assert timed.deadline_at == datetime(2026, 10, 20, 18, 0)
    assert reminder_is_due(timed, datetime(2026, 10, 20, 16, 0))
    assert not reminder_is_due(timed, datetime(2026, 10, 20, 18, 0))
    assert missed_is_due(timed, datetime(2026, 10, 20, 18, 0), timedelta(days=2))
    assert not missed_is_due(timed, datetime(2026, 10, 20, 17, 59), timedelta(days=2))

    open_day = workout_window(
        scheduled_for=date(2026, 10, 20),
        scheduled_time=None,
        timezone=utc,
        morning_reminder=time(9, 0),
        reminder_lead=timedelta(hours=2),
    )
    assert open_day.reminder_at == datetime(2026, 10, 20, 9, 0)
    assert open_day.deadline_at == datetime(2026, 10, 21, 0, 0)
    assert not missed_is_due(open_day, datetime(2026, 10, 20, 23, 0), timedelta(days=2))
    assert missed_is_due(open_day, datetime(2026, 10, 21, 0, 0), timedelta(days=2))

    early = workout_window(
        scheduled_for=date(2026, 10, 20),
        scheduled_time=time(1, 0),
        timezone=utc,
        morning_reminder=time(9, 0),
        reminder_lead=timedelta(hours=2),
    )
    assert early.reminder_at == datetime(2026, 10, 19, 23, 0)
    assert early.deadline_at == datetime(2026, 10, 20, 1, 0)


def test_vladivostok_shifts_the_deadline_to_utc() -> None:
    window = workout_window(
        scheduled_for=date(2026, 10, 20),
        scheduled_time=time(18, 0),
        timezone=ZoneInfo("Asia/Vladivostok"),
        morning_reminder=time(9, 0),
        reminder_lead=timedelta(hours=2),
    )
    assert window.reminder_at == datetime(2026, 10, 20, 6, 0)
    assert window.deadline_at == datetime(2026, 10, 20, 8, 0)


def test_russian_messages_stay_short() -> None:
    assert reminder_text(None) == "Сегодня тренировка. Хорошей работы."
    assert reminder_text(time(18, 0)) == "Тренировка в 18:00."
    assert missed_text(client_label=None, scheduled_for=date(2026, 10, 20)) == "Клиент не выполнил тренировку 20.10."
    assert missed_text(client_label="anna", scheduled_for=date(2026, 10, 20)) == "Клиент anna не выполнил тренировку 20.10."
    assert plan_text(NoticeKind.CREATED) == "Тренер составил вам план тренировок."
    assert plan_text(NoticeKind.UPDATED) == "Тренер обновил ваш план тренировок."


def test_reminder_and_missed_follow_scheduled_time(tmp_path: Path, monkeypatch) -> None:
    factory = _db(tmp_path, monkeypatch)
    session = factory()
    _preference(session, "client-time", chat_id=101, timezone_name="UTC")
    _preference(session, "trainer-time", chat_id=202, timezone_name="UTC")
    _workout(
        session,
        client_user_id="client-time",
        trainer_user_id="trainer-time",
        scheduled_for=date(2026, 10, 20),
        scheduled_time=time(18, 0),
    )
    session.commit()
    sender = RecordingSender()
    _run(session, datetime(2026, 10, 20, 15, 59), sender, logins={"client-time": "anna"})
    assert sender.sent == []
    _run(session, datetime(2026, 10, 20, 16, 0), sender, logins={"client-time": "anna"})
    assert sender.sent == [(101, "Тренировка в 18:00.")]
    _run(session, datetime(2026, 10, 20, 18, 0), sender, logins={"client-time": "anna"})
    assert sender.sent == [
        (101, "Тренировка в 18:00."),
        (202, "Клиент anna не выполнил тренировку 20.10."),
    ]
    _run(session, datetime(2026, 10, 20, 18, 5), sender, logins={"client-time": "anna"})
    assert len(sender.sent) == 2
    session.close()


def test_morning_default_and_user_timezone(tmp_path: Path, monkeypatch) -> None:
    factory = _db(tmp_path, monkeypatch)
    session = factory()
    _preference(session, "client-utc", chat_id=11, timezone_name="UTC")
    _preference(session, "client-default", chat_id=12)
    _workout(
        session,
        client_user_id="client-utc",
        trainer_user_id="trainer-utc",
        scheduled_for=date(2026, 10, 20),
        scheduled_time=None,
    )
    _workout(
        session,
        client_user_id="client-default",
        trainer_user_id="trainer-default",
        scheduled_for=date(2026, 10, 20),
        scheduled_time=None,
    )
    session.commit()
    sender = RecordingSender()
    # 22:59 UTC 19 октября — 08:59 20 октября во Владивостоке, утро ещё не наступило ни там, ни в UTC.
    _run(session, datetime(2026, 10, 19, 22, 59), sender)
    assert sender.sent == []
    _run(session, datetime(2026, 10, 19, 23, 0), sender)
    assert sender.sent == [(12, "Сегодня тренировка. Хорошей работы.")]
    _run(session, datetime(2026, 10, 20, 9, 0), sender)
    assert sender.sent == [
        (12, "Сегодня тренировка. Хорошей работы."),
        (11, "Сегодня тренировка. Хорошей работы."),
    ]
    session.close()


def test_opt_out_is_not_sent_again_after_reenable(tmp_path: Path, monkeypatch) -> None:
    factory = _db(tmp_path, monkeypatch)
    session = factory()
    _preference(session, "client-off", chat_id=31, timezone_name="UTC", enabled=False)
    _workout(
        session,
        client_user_id="client-off",
        trainer_user_id=None,
        scheduled_for=date(2026, 10, 20),
        scheduled_time=None,
    )
    session.commit()
    sender = RecordingSender()
    _run(session, datetime(2026, 10, 20, 10, 0), sender)
    assert sender.sent == []
    preference = session.get(NotificationPreferenceModel, "client-off")
    assert preference is not None
    preference.notifications_enabled = True
    session.commit()
    _run(session, datetime(2026, 10, 20, 10, 5), sender)
    assert sender.sent == []
    session.close()


def test_missing_chat_is_retried_after_link(tmp_path: Path, monkeypatch) -> None:
    factory = _db(tmp_path, monkeypatch)
    session = factory()
    _workout(
        session,
        client_user_id="client-later",
        trainer_user_id=None,
        scheduled_for=date(2026, 10, 20),
        scheduled_time=time(18, 0),
    )
    session.commit()
    sender = RecordingSender()
    _run(session, datetime(2026, 10, 20, 16, 0), sender, default_timezone="UTC")
    assert sender.sent == []
    _preference(session, "client-later", chat_id=77, timezone_name="UTC")
    session.commit()
    _run(session, datetime(2026, 10, 20, 16, 5), sender, default_timezone="UTC")
    assert sender.sent == [(77, "Тренировка в 18:00.")]
    session.close()


def test_empty_and_completed_days_are_silent(tmp_path: Path, monkeypatch) -> None:
    factory = _db(tmp_path, monkeypatch)
    session = factory()
    _preference(session, "client-empty", chat_id=41, timezone_name="UTC")
    _preference(session, "trainer-empty", chat_id=42, timezone_name="UTC")
    _workout(
        session,
        client_user_id="client-empty",
        trainer_user_id="trainer-empty",
        scheduled_for=date(2026, 10, 20),
        scheduled_time=time(18, 0),
        with_exercise=False,
    )
    _preference(session, "client-done", chat_id=43, timezone_name="UTC")
    _preference(session, "trainer-done", chat_id=44, timezone_name="UTC")
    _workout(
        session,
        client_user_id="client-done",
        trainer_user_id="trainer-done",
        scheduled_for=date(2026, 10, 20),
        scheduled_time=time(18, 0),
        completed=True,
    )
    session.commit()
    sender = RecordingSender()
    _run(session, datetime(2026, 10, 20, 19, 0), sender)
    assert sender.sent == []
    session.close()


def test_telegram_errors_are_idempotent(tmp_path: Path, monkeypatch) -> None:
    factory = _db(tmp_path, monkeypatch)
    blocked = FlakySender(TelegramPermanentError("blocked"))
    session = factory()
    _preference(session, "client-blocked", chat_id=51, timezone_name="UTC")
    _workout(
        session,
        client_user_id="client-blocked",
        trainer_user_id=None,
        scheduled_for=date(2026, 10, 20),
        scheduled_time=time(12, 0),
    )
    session.commit()
    _run(session, datetime(2026, 10, 20, 10, 0), blocked)
    _run(session, datetime(2026, 10, 20, 10, 5), blocked)
    assert blocked.sent == []
    assert blocked.calls == 1
    session.close()

    retry_dir = tmp_path / "retry"
    retry_dir.mkdir()
    factory_retry = _db(retry_dir, monkeypatch)
    retry = FlakySender(TelegramTransientError("later"))
    session = factory_retry()
    _preference(session, "client-retry", chat_id=52, timezone_name="UTC")
    _workout(
        session,
        client_user_id="client-retry",
        trainer_user_id=None,
        scheduled_for=date(2026, 10, 20),
        scheduled_time=time(12, 0),
    )
    session.commit()
    _run(session, datetime(2026, 10, 20, 10, 0), retry)
    _run(session, datetime(2026, 10, 20, 10, 5), retry)
    assert retry.sent == [(52, "Тренировка в 12:00.")]
    assert retry.calls == 2
    session.close()


def test_plan_edits_collapse_until_debounce(tmp_path: Path, monkeypatch) -> None:
    factory = _db(tmp_path, monkeypatch)
    session = factory()
    plan_id = str(uuid4())
    session.add(
        TrainingPlanModel(
            plan_id=plan_id,
            source="trainer",
            trainer_user_id="trainer-plan",
            user_id="client-plan",
            status="active",
            goal="maintenance",
            level="intermediate",
            workouts_per_week=3,
            start_date=date(2026, 10, 20),
            end_date=date(2026, 10, 20),
        )
    )
    _preference(session, "client-plan", chat_id=61, timezone_name="UTC")
    session.commit()
    repo = NotificationRepository(session)
    started = datetime(2026, 10, 20, 8, 0)
    repo.mark_plan_changed(
        plan_id=plan_id,
        client_user_id="client-plan",
        trainer_user_id="trainer-plan",
        created=True,
        now=started,
        debounce_seconds=900,
    )
    repo.mark_plan_changed(
        plan_id=plan_id,
        client_user_id="client-plan",
        trainer_user_id="trainer-plan",
        created=False,
        now=started + timedelta(minutes=2),
        debounce_seconds=900,
    )
    session.commit()
    notice = session.get(PlanUpdateNoticeModel, plan_id)
    assert notice is not None
    assert notice.revision == 2
    assert notice.kind == "created"
    sender = RecordingSender()
    _run(session, started + timedelta(minutes=3), sender)
    assert sender.sent == []
    _run(session, started + timedelta(minutes=20), sender)
    assert sender.sent == [(61, "Тренер составил вам план тренировок.")]
    repo.mark_plan_changed(
        plan_id=plan_id,
        client_user_id="client-plan",
        trainer_user_id="trainer-plan",
        created=False,
        now=started + timedelta(minutes=21),
        debounce_seconds=900,
    )
    session.commit()
    _run(session, started + timedelta(minutes=22), sender)
    assert len(sender.sent) == 1
    _run(session, started + timedelta(minutes=40), sender)
    assert sender.sent[-1] == (61, "Тренер обновил ваш план тренировок.")
    _run(session, started + timedelta(minutes=50), sender)
    assert len(sender.sent) == 2
    session.close()


def test_archived_plan_notice_is_dropped(tmp_path: Path, monkeypatch) -> None:
    factory = _db(tmp_path, monkeypatch)
    session = factory()
    plan_id = str(uuid4())
    session.add(
        TrainingPlanModel(
            plan_id=plan_id,
            source="trainer",
            trainer_user_id="trainer-old",
            user_id="client-old",
            status="archived",
            goal="maintenance",
            level="intermediate",
            workouts_per_week=3,
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 1),
        )
    )
    _preference(session, "client-old", chat_id=71)
    session.add(
        PlanUpdateNoticeModel(
            plan_id=plan_id,
            client_user_id="client-old",
            trainer_user_id="trainer-old",
            revision=1,
            sent_revision=0,
            kind="created",
            notify_after=datetime(2026, 10, 1, 0, 0),
        )
    )
    session.commit()
    sender = RecordingSender()
    _run(session, datetime(2026, 10, 1, 1, 0), sender)
    assert sender.sent == []
    notice = session.get(PlanUpdateNoticeModel, plan_id)
    assert notice is not None
    assert notice.sent_revision == 1
    session.close()


def test_scheduler_registers_a_single_interval() -> None:
    scheduler = start_notification_scheduler(lambda: None, 3600)
    try:
        jobs = scheduler.get_jobs()
        assert len(jobs) == 1
        assert jobs[0].id == "workout-notifications"
    finally:
        scheduler.shutdown(wait=False)


def test_notification_migration_is_reversible(tmp_path: Path, monkeypatch) -> None:
    database_path = tmp_path / "migration.db"
    url = f"sqlite+pysqlite:///{database_path.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")
    engine = create_engine(url)
    tables = set(inspect(engine).get_table_names())
    assert {
        "notification_preferences",
        "plan_update_notices",
        "notification_deliveries",
        "telegram_link_codes",
    } <= tables
    engine.dispose()
    command.downgrade(config, "0021_plan_notes_times")
    engine = create_engine(url)
    tables = set(inspect(engine).get_table_names())
    assert "notification_preferences" not in tables
    assert "plan_update_notices" not in tables
    assert "scheduled_time" in {column["name"] for column in inspect(engine).get_columns("plan_days")}
    engine.dispose()
    command.upgrade(config, "head")
    engine = create_engine(url)
    assert "notification_deliveries" in inspect(engine).get_table_names()
    engine.dispose()


def _client() -> TestClient:
    return TestClient(app)


def _install_relations() -> None:
    runtime = app.state.plan_handler._runtime
    runtime.tenant_gateway.get_client_active_trainer_id = lambda client_id: _ACTIVE_RELATIONS.get(client_id)
    runtime.settings.internal_service_token = _SERVICE_TOKEN


def _auth(user_id: str, *, role: str = "client") -> dict[str, str]:
    runtime = app.state.plan_handler._runtime
    runtime.auth_gateway.get_current_user = lambda _token: AuthUser(
        user_id=user_id,
        tenant_id="tenant_1",
        role=role,
    )
    return _USER_HEADERS


def test_notification_settings_and_telegram_link() -> None:
    with _client() as client:
        _install_relations()
        missing = client.get("/api/v1/plans/me/notifications/settings")
        assert missing.status_code == 401

        headers = _auth("notify-user")
        current = client.get("/api/v1/plans/me/notifications/settings", headers=headers)
        assert current.status_code == 200, current.text
        body = current.json()
        assert body["timezone"] == "Asia/Vladivostok"
        assert body["timezone_is_default"] is True
        assert body["notifications_enabled"] is True
        assert body["telegram_linked"] is False

        updated = client.put(
            "/api/v1/plans/me/notifications/settings",
            headers=headers,
            json={"timezone": "Europe/Moscow", "notifications_enabled": False},
        )
        assert updated.status_code == 200, updated.text
        assert updated.json()["timezone"] == "Europe/Moscow"
        assert updated.json()["timezone_is_default"] is False
        assert updated.json()["notifications_enabled"] is False

        cleared = client.put(
            "/api/v1/plans/me/notifications/settings",
            headers=headers,
            json={"timezone": None},
        )
        assert cleared.status_code == 200, cleared.text
        assert cleared.json()["timezone"] == "Asia/Vladivostok"
        assert cleared.json()["notifications_enabled"] is False

        invalid = client.put(
            "/api/v1/plans/me/notifications/settings",
            headers=headers,
            json={"timezone": "Not/AZone"},
        )
        assert invalid.status_code == 422

        issued = client.post("/api/v1/plans/me/notifications/telegram/link-code", headers=headers)
        assert issued.status_code == 200, issued.text
        code = issued.json()["code"]
        rejected = client.post(
            "/api/v1/plans/internal/notifications/telegram",
            json={"code": code, "chat_id": 9001},
        )
        assert rejected.status_code == 401
        linked = client.post(
            "/api/v1/plans/internal/notifications/telegram",
            headers={"X-Service-Token": _SERVICE_TOKEN},
            json={"code": code, "chat_id": 9001},
        )
        assert linked.status_code == 200, linked.text
        assert linked.json()["telegram_linked"] is True
        again = client.post(
            "/api/v1/plans/internal/notifications/telegram",
            headers={"X-Service-Token": _SERVICE_TOKEN},
            json={"code": code, "chat_id": 9001},
        )
        assert again.status_code == 404
        seen = client.get("/api/v1/plans/me/notifications/settings", headers=headers)
        assert seen.json()["telegram_linked"] is True

        other = client.post(
            "/api/v1/plans/me/notifications/telegram/link-code",
            headers=_auth("notify-other"),
        )
        moved = client.post(
            "/api/v1/plans/internal/notifications/telegram",
            headers={"X-Service-Token": _SERVICE_TOKEN},
            json={"code": other.json()["code"], "chat_id": 9001},
        )
        assert moved.status_code == 200, moved.text
        previous = client.get("/api/v1/plans/me/notifications/settings", headers=_auth("notify-user"))
        assert previous.json()["telegram_linked"] is False
        unlinked = client.delete("/api/v1/plans/me/notifications/telegram", headers=_auth("notify-other"))
        assert unlinked.status_code == 204
        after = client.get("/api/v1/plans/me/notifications/settings", headers=_auth("notify-other"))
        assert after.json()["telegram_linked"] is False


def test_trainer_plan_edits_notify_once(tmp_path: Path) -> None:
    client_user_id = "debounce-client"
    trainer_user_id = "debounce-trainer"
    base = f"/api/v1/plans/clients/{client_user_id}/trainers/{trainer_user_id}"
    with _client() as client:
        _install_relations()
        _ACTIVE_RELATIONS[client_user_id] = trainer_user_id
        trainer_headers = _auth(trainer_user_id, role="trainer")
        exercise = client.post(
            f"/api/v1/trainers/{trainer_user_id}/exercises",
            headers=trainer_headers,
            json={
                "exercise_name": "Debounce Press",
                "equipment": "dumbbells",
                "is_cardio": False,
                "is_hold": False,
                "difficulty": 2,
                "workout_category": "upper",
                "default_sets": 3,
                "default_reps": 8,
                "default_rest_seconds": 60,
                "load_scheme": "flat",
                "primary_muscles": [],
                "secondary_muscles": [],
            },
        )
        assert exercise.status_code == 201, exercise.text
        created = client.post(
            f"{base}/active",
            headers=trainer_headers,
            json={"day_count": 1, "start_date": "2027-03-01"},
        )
        assert created.status_code == 201, created.text
        slot = {"exercise_id": exercise.json()["row_id"], "sets": 3, "reps": 8}
        added = client.post(f"{base}/days/1/exercises", headers=trainer_headers, json=slot)
        assert added.status_code == 201, added.text
        changed = client.post(f"{base}/days/1/exercises", headers=trainer_headers, json={**slot, "reps": 6})
        assert changed.status_code == 201, changed.text

        client_headers = _auth(client_user_id)
        issued = client.post("/api/v1/plans/me/notifications/telegram/link-code", headers=client_headers)
        linked = client.post(
            "/api/v1/plans/internal/notifications/telegram",
            headers={"X-Service-Token": _SERVICE_TOKEN},
            json={"code": issued.json()["code"], "chat_id": 4242},
        )
        assert linked.status_code == 200, linked.text

        sender = RecordingSender()
        runtime = app.state.plan_handler._runtime
        runtime._telegram_sender = sender
        runtime.settings.telegram_bot_token = "test-token"
        early = datetime.now(tz=ZoneInfo("UTC")).replace(tzinfo=None) + timedelta(seconds=30)
        runtime.dispatch_notifications(early)
        assert [text for chat_id, text in sender.sent if chat_id == 4242] == []

        late = datetime.now(tz=ZoneInfo("UTC")).replace(tzinfo=None) + timedelta(minutes=20)
        runtime.dispatch_notifications(late)
        ours = [text for chat_id, text in sender.sent if chat_id == 4242]
        assert ours == ["Тренер составил вам план тренировок."]

        patched = client.patch(
            f"{base}/days/1",
            headers=_auth(trainer_user_id, role="trainer"),
            json={"scheduled_time": "18:00"},
        )
        assert patched.status_code == 200, patched.text
        client.post(
            f"/api/v1/plans/me/days/1/complete",
            headers=_auth(client_user_id),
        )
        runtime.dispatch_notifications(datetime.now(tz=ZoneInfo("UTC")).replace(tzinfo=None) + timedelta(seconds=20))
        assert [text for chat_id, text in sender.sent if chat_id == 4242] == ours
        runtime.dispatch_notifications(datetime.now(tz=ZoneInfo("UTC")).replace(tzinfo=None) + timedelta(minutes=20))
        ours = [text for chat_id, text in sender.sent if chat_id == 4242]
        assert ours == [
            "Тренер составил вам план тренировок.",
            "Тренер обновил ваш план тренировок.",
        ]


def test_api_process_does_not_start_the_scheduler() -> None:
    with _client() as client:
        assert client.get("/health").status_code == 200
        assert app.state.plan_handler._runtime._scheduler is None
