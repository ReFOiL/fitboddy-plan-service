from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect

from application.gateways import AuthUser
from presentation.http.main import app

_ACTIVE_RELATIONS: dict[str, str] = {}
_USER_HEADERS = {"Authorization": "Bearer test-user-token"}

_MARKER_EXERCISE = {
    "exercise_name": "Structure Marker Press",
    "description": "Used by day structure tests.",
    "equipment": "dumbbells",
    "is_cardio": False,
    "is_hold": False,
    "difficulty": 2,
    "workout_category": "upper",
    "default_sets": 3,
    "default_reps": 10,
    "default_duration_seconds": None,
    "default_rest_seconds": 60,
    "default_weight_kg": 12,
    "load_scheme": "flat",
    "scheme_steps": [],
    "primary_muscles": [],
    "secondary_muscles": [],
}


def _client() -> TestClient:
    return TestClient(app)


def _install_test_stubs() -> None:
    runtime = app.state.plan_handler._runtime
    runtime.tenant_gateway.get_client_active_trainer_id = lambda client_id: _ACTIVE_RELATIONS.get(client_id)


def _link(client_user_id: str, trainer_user_id: str) -> None:
    _ACTIVE_RELATIONS[client_user_id] = trainer_user_id


def _auth(user_id: str, *, role: str = "client") -> dict[str, str]:
    runtime = app.state.plan_handler._runtime
    runtime.auth_gateway.get_current_user = lambda _token: AuthUser(
        user_id=user_id,
        tenant_id="tenant_1",
        role=role,
    )
    return _USER_HEADERS


def _plan_base(client_user_id: str, trainer_user_id: str) -> str:
    return f"/api/v1/plans/clients/{client_user_id}/trainers/{trainer_user_id}"


def _headers(user_id: str, *, role: str = "trainer") -> dict[str, str]:
    return _auth(user_id, role=role)


def _empty_plan(client: TestClient, client_user_id: str, trainer_user_id: str, start_date: str) -> dict:
    _link(client_user_id, trainer_user_id)
    created = client.post(
        f"{_plan_base(client_user_id, trainer_user_id)}/active",
        headers=_headers(trainer_user_id),
        json={
            "goal": "maintenance",
            "level": "intermediate",
            "workouts_per_week": 3,
            "start_date": start_date,
            "day_count": 0,
        },
    )
    assert created.status_code == 201, created.text
    return created.json()


def _create_exercise(client: TestClient, trainer_user_id: str) -> dict:
    response = client.post(
        f"/api/v1/trainers/{trainer_user_id}/exercises",
        headers=_headers(trainer_user_id),
        json=_MARKER_EXERCISE,
    )
    assert response.status_code == 201, response.text
    return response.json()


def _day(plan: dict, day_index: int) -> dict:
    return next(item for item in plan["days"] if item["day_index"] == day_index)


def test_add_and_remove_day_keeps_existing_indexes() -> None:
    client_user_id = "structure_add_client"
    trainer_user_id = "structure_add_trainer"
    base = _plan_base(client_user_id, trainer_user_id)
    with _client() as client:
        _install_test_stubs()
        _empty_plan(client, client_user_id, trainer_user_id, "2026-10-21")
        headers = _headers(trainer_user_id)

        wednesday = client.post(f"{base}/days", headers=headers, json={"week": 1, "day_of_week": 2})
        assert wednesday.status_code == 201, wednesday.text
        assert wednesday.json()["start_date"] == "2026-10-21"
        assert _day(wednesday.json(), 1)["scheduled_for"] == "2026-10-21"
        assert _day(wednesday.json(), 1)["day_of_week"] == 2
        assert _day(wednesday.json(), 1)["scheduled_time"] is None

        monday = client.post(
            f"{base}/days",
            headers=headers,
            json={"week": 1, "day_of_week": 0, "scheduled_time": "18:00"},
        )
        assert monday.status_code == 201, monday.text
        assert _day(monday.json(), 1)["day_index"] == 1
        added = _day(monday.json(), 2)
        assert added["scheduled_for"] == "2026-10-26"
        assert added["scheduled_time"] == "18:00"
        assert monday.json()["end_date"] == "2026-10-26"
        cleared = client.patch(f"{base}/days/2", headers=headers, json={"scheduled_time": None})
        assert cleared.status_code == 200, cleared.text
        assert cleared.json()["scheduled_time"] is None

        duplicate = client.post(f"{base}/days", headers=headers, json={"week": 1, "day_of_week": 0})
        assert duplicate.status_code == 409

        friday = client.post(f"{base}/days", headers=headers, json={"week": 1, "day_of_week": 4})
        assert friday.status_code == 201, friday.text
        assert [item["day_index"] for item in friday.json()["days"]] == [1, 2, 3]
        assert _day(friday.json(), 3)["scheduled_for"] == "2026-10-23"

        removed = client.delete(f"{base}/days/2", headers=headers)
        assert removed.status_code == 200, removed.text
        indexes = {item["day_index"] for item in removed.json()["days"]}
        assert indexes == {1, 3}
        assert removed.json()["end_date"] == "2026-10-23"
        assert removed.json()["start_date"] == "2026-10-21"

        missing = client.delete(f"{base}/days/2", headers=headers)
        assert missing.status_code == 404

        stranger = client.post(
            f"{base}/days",
            headers=_auth("other_trainer", role="trainer"),
            json={"week": 1, "day_of_week": 1},
        )
        assert stranger.status_code == 403
        admin = client.post(
            f"{base}/days",
            headers=_auth("platform_admin_user", role="platform_admin"),
            json={"week": 1, "day_of_week": 1},
        )
        assert admin.status_code == 201, admin.text
        assert _day(admin.json(), 4)["scheduled_for"] == "2026-10-27"


def test_plan_day_cap_and_bad_clock() -> None:
    client_user_id = "structure_cap_client"
    trainer_user_id = "structure_cap_trainer"
    base = _plan_base(client_user_id, trainer_user_id)
    with _client() as client:
        _install_test_stubs()
        _empty_plan(client, client_user_id, trainer_user_id, "2026-10-21")
        headers = _headers(trainer_user_id)
        created = 0
        for week in range(1, 5):
            for day_of_week in range(7):
                response = client.post(
                    f"{base}/days",
                    headers=headers,
                    json={"week": week, "day_of_week": day_of_week},
                )
                assert response.status_code == 201, response.text
                created += 1
        assert created == 28
        overflow = client.post(f"{base}/days", headers=headers, json={"week": 5, "day_of_week": 0})
        assert overflow.status_code == 422
        bad_clock = client.patch(f"{base}/days/1", headers=headers, json={"scheduled_time": "25:00"})
        assert bad_clock.status_code == 422


def test_slot_note_create_patch_and_replace() -> None:
    client_user_id = "structure_note_client"
    trainer_user_id = "structure_note_trainer"
    base = _plan_base(client_user_id, trainer_user_id)
    with _client() as client:
        _install_test_stubs()
        _empty_plan(client, client_user_id, trainer_user_id, "2026-10-21")
        headers = _headers(trainer_user_id)
        exercise = _create_exercise(client, trainer_user_id)
        added_day = client.post(f"{base}/days", headers=headers, json={"week": 1, "day_of_week": 2})
        assert added_day.status_code == 201

        created = client.post(
            f"{base}/days/1/exercises",
            headers=headers,
            json={"exercise_id": exercise["row_id"], "note": "  медленно вниз  "},
        )
        assert created.status_code == 201, created.text
        slot = created.json()["exercises"][0]
        assert slot["note"] == "медленно вниз"
        line_id = slot["line_id"]

        kept = client.patch(f"{base}/days/1/exercises/{line_id}", headers=headers, json={"sets": 4})
        assert kept.status_code == 200, kept.text
        kept_slot = kept.json()["exercises"][0]
        assert kept_slot["sets"] == 4
        assert kept_slot["note"] == "медленно вниз"

        cleared = client.patch(
            f"{base}/days/1/exercises/{line_id}",
            headers=headers,
            json={"note": None},
        )
        assert cleared.status_code == 200, cleared.text
        assert cleared.json()["exercises"][0]["note"] is None

        replaced = client.put(
            f"{base}/days/1",
            headers=headers,
            json={"slots": [{"exercise_id": exercise["row_id"], "note": "пауза внизу"}]},
        )
        assert replaced.status_code == 200, replaced.text
        assert replaced.json()["exercises"][0]["note"] == "пауза внизу"

        active = client.get(f"{base}/active", headers=headers)
        assert active.status_code == 200
        assert _day(active.json(), 1)["exercises"][0]["note"] == "пауза внизу"

        client_read = client.get(f"{base}/active", headers=_auth(client_user_id))
        assert client_read.status_code == 200
        assert _day(client_read.json(), 1)["exercises"][0]["note"] == "пауза внизу"


def test_copy_day_and_week_create_missing_targets() -> None:
    client_user_id = "structure_copy_client"
    trainer_user_id = "structure_copy_trainer"
    base = _plan_base(client_user_id, trainer_user_id)
    with _client() as client:
        _install_test_stubs()
        _empty_plan(client, client_user_id, trainer_user_id, "2026-10-21")
        headers = _headers(trainer_user_id)
        exercise = _create_exercise(client, trainer_user_id)
        for day_of_week in (2, 4):
            created = client.post(f"{base}/days", headers=headers, json={"week": 1, "day_of_week": day_of_week})
            assert created.status_code == 201, created.text
        target = client.post(
            f"{base}/days",
            headers=headers,
            json={"week": 2, "day_of_week": 2, "scheduled_time": "07:00"},
        )
        assert target.status_code == 201, target.text
        source_index = next(item["day_index"] for item in target.json()["days"] if item["week"] == 1 and item["day_of_week"] == 2)
        existing_index = next(
            item["day_index"] for item in target.json()["days"] if item["week"] == 2 and item["day_of_week"] == 2
        )

        seeded = client.post(
            f"{base}/days/{source_index}/exercises",
            headers=headers,
            json={"exercise_id": exercise["row_id"], "sets": 3, "reps": 8, "note": "исходная заметка"},
        )
        assert seeded.status_code == 201, seeded.text
        source_line_id = seeded.json()["exercises"][0]["line_id"]
        timed = client.patch(f"{base}/days/{source_index}", headers=headers, json={"scheduled_time": "18:00"})
        assert timed.status_code == 200, timed.text
        assert timed.json()["scheduled_time"] == "18:00"

        onto_self = client.post(
            f"{base}/days/{source_index}/copy",
            headers=headers,
            json={"week": 1, "day_of_week": 2},
        )
        assert onto_self.status_code == 422

        created_target = client.post(
            f"{base}/days/{source_index}/copy",
            headers=headers,
            json={"week": 2, "day_of_week": 4, "mode": "overwrite"},
        )
        assert created_target.status_code == 200, created_target.text
        new_day = next(item for item in created_target.json()["days"] if item["week"] == 2 and item["day_of_week"] == 4)
        assert new_day["scheduled_for"] == "2026-10-30"
        assert new_day["scheduled_time"] == "18:00"
        assert new_day["is_completed"] is False
        assert len(new_day["exercises"]) == 1
        assert new_day["exercises"][0]["line_id"] != source_line_id
        assert new_day["exercises"][0]["note"] == "исходная заметка"
        assert new_day["exercises"][0]["reps"] == 8
        source_after = _day(created_target.json(), source_index)
        assert source_after["exercises"][0]["line_id"] == source_line_id

        overwritten = client.post(
            f"{base}/days/{source_index}/copy",
            headers=headers,
            json={"week": 2, "day_of_week": 2, "mode": "overwrite"},
        )
        assert overwritten.status_code == 200, overwritten.text
        kept_time = _day(overwritten.json(), existing_index)
        assert kept_time["scheduled_time"] == "07:00"
        assert len(kept_time["exercises"]) == 1
        assert kept_time["exercises"][0]["note"] == "исходная заметка"

        appended = client.post(
            f"{base}/days/{source_index}/copy",
            headers=headers,
            json={"week": 2, "day_of_week": 2, "mode": "append"},
        )
        assert appended.status_code == 200, appended.text
        appended_day = _day(appended.json(), existing_index)
        assert len(appended_day["exercises"]) == 2
        assert appended_day["exercises"][0]["line_id"] == kept_time["exercises"][0]["line_id"]
        assert appended_day["scheduled_time"] == "07:00"

        same_week = client.post(f"{base}/weeks/1/copy", headers=headers, json={"target_week": 1})
        assert same_week.status_code == 422

        copied_week = client.post(
            f"{base}/weeks/1/copy",
            headers=headers,
            json={"target_week": 3, "mode": "overwrite"},
        )
        assert copied_week.status_code == 200, copied_week.text
        week_three = {item["day_of_week"]: item for item in copied_week.json()["days"] if item["week"] == 3}
        assert set(week_three) == {2, 4}
        assert week_three[2]["exercises"][0]["note"] == "исходная заметка"
        assert week_three[2]["scheduled_time"] == "18:00"
        assert week_three[4]["exercises"] == []
        assert week_three[4]["scheduled_time"] is None

        forbidden = client.post(
            f"{base}/days/{source_index}/copy",
            headers=_auth(client_user_id),
            json={"week": 4, "day_of_week": 0},
        )
        assert forbidden.status_code == 403


def test_copy_append_rejects_more_than_24_slots() -> None:
    client_user_id = "structure_full_client"
    trainer_user_id = "structure_full_trainer"
    base = _plan_base(client_user_id, trainer_user_id)
    with _client() as client:
        _install_test_stubs()
        _empty_plan(client, client_user_id, trainer_user_id, "2026-10-21")
        headers = _headers(trainer_user_id)
        exercise = _create_exercise(client, trainer_user_id)
        first = client.post(f"{base}/days", headers=headers, json={"week": 1, "day_of_week": 2})
        second = client.post(f"{base}/days", headers=headers, json={"week": 1, "day_of_week": 4})
        assert first.status_code == 201 and second.status_code == 201
        filled = client.put(
            f"{base}/days/1",
            headers=headers,
            json={"slots": [{"exercise_id": exercise["row_id"]}] * 24},
        )
        assert filled.status_code == 200, filled.text
        seeded = client.post(
            f"{base}/days/2/exercises",
            headers=headers,
            json={"exercise_id": exercise["row_id"]},
        )
        assert seeded.status_code == 201, seeded.text
        overflow = client.post(
            f"{base}/days/2/copy",
            headers=headers,
            json={"week": 1, "day_of_week": 2, "mode": "append"},
        )
        assert overflow.status_code == 422
        active = client.get(f"{base}/active", headers=headers)
        assert len(_day(active.json(), 1)["exercises"]) == 24


def test_completion_records_start_and_finish() -> None:
    client_user_id = "structure_complete_client"
    trainer_user_id = "structure_complete_trainer"
    with _client() as client:
        _install_test_stubs()
        _link(client_user_id, trainer_user_id)
        generated = client.post(
            "/api/v1/plans/generate",
            headers=_headers(trainer_user_id),
            json={
                "trainer_user_id": trainer_user_id,
                "user_id": client_user_id,
                "goal": "maintenance",
                "level": "beginner",
                "workout_location": "home",
                "workouts_per_week": 3,
                "unavailable_equipment": [],
            },
        )
        assert generated.status_code == 201, generated.text
        today = date.today().isoformat()
        workout_day = next(item for item in generated.json()["days"] if item["scheduled_for"] == today)
        base = _plan_base(client_user_id, trainer_user_id)
        patched = client.patch(
            f"{base}/days/{workout_day['day_index']}",
            headers=_headers(trainer_user_id),
            json={"scheduled_time": "18:00"},
        )
        assert patched.status_code == 200, patched.text

        today_response = client.get("/api/v1/plans/me/today", headers=_auth(client_user_id))
        assert today_response.status_code == 200, today_response.text
        assert today_response.json()["scheduled_time"] == "18:00"
        assert today_response.json()["started_at"] is None
        assert today_response.json()["finished_at"] is None

        started_at = datetime.now(timezone.utc) - timedelta(minutes=20)
        completed = client.post(
            f"/api/v1/plans/me/days/{workout_day['day_index']}/complete",
            headers=_auth(client_user_id),
            json={"started_at": started_at.isoformat()},
        )
        assert completed.status_code == 200, completed.text
        body = completed.json()
        assert body["is_completed"] is True
        assert body["scheduled_time"] == "18:00"
        assert body["completed_at"] is not None
        assert body["finished_at"] == body["completed_at"]
        assert body["started_at"] is not None
        assert body["exercises"][0]["note"] is None

        again = client.post(
            f"/api/v1/plans/me/days/{workout_day['day_index']}/complete",
            headers=_auth(client_user_id),
            json={"started_at": started_at.isoformat()},
        )
        assert again.status_code == 409

        other = next(
            item
            for item in generated.json()["days"]
            if item["day_index"] != workout_day["day_index"] and item["exercises"]
        )
        future = client.post(
            f"/api/v1/plans/me/days/{other['day_index']}/complete",
            headers=_auth(client_user_id),
            json={"started_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()},
        )
        assert future.status_code == 422
        too_early = client.post(
            f"/api/v1/plans/me/days/{other['day_index']}/complete",
            headers=_auth(client_user_id),
            json={"started_at": (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()},
        )
        assert too_early.status_code == 422


def test_completion_without_body_leaves_start_empty() -> None:
    client_user_id = "structure_plain_complete_client"
    trainer_user_id = "structure_plain_complete_trainer"
    with _client() as client:
        _install_test_stubs()
        _link(client_user_id, trainer_user_id)
        generated = client.post(
            "/api/v1/plans/generate",
            headers=_headers(trainer_user_id),
            json={
                "trainer_user_id": trainer_user_id,
                "user_id": client_user_id,
                "goal": "maintenance",
                "level": "beginner",
                "workout_location": "home",
                "workouts_per_week": 3,
                "unavailable_equipment": [],
                "start_date": date.today().isoformat(),
            },
        )
        assert generated.status_code == 201, generated.text
        today = date.today().isoformat()
        workout_day = next(item for item in generated.json()["days"] if item["scheduled_for"] == today)
        completed = client.post(
            f"/api/v1/plans/me/days/{workout_day['day_index']}/complete",
            headers=_auth(client_user_id),
        )
        assert completed.status_code == 200, completed.text
        body = completed.json()
        assert body["started_at"] is None
        assert body["finished_at"] == body["completed_at"]
        assert body["finished_at"] is not None


def _week_day(plan: dict, day_of_week: int, week: int = 1) -> dict:
    return next(item for item in plan["days"] if item["week"] == week and item["day_of_week"] == day_of_week)


def test_trainer_start_anchor_hides_leading_week_and_keeps_completed_day() -> None:
    client_user_id = "start_anchor_client"
    trainer_user_id = "start_anchor_trainer"
    base = _plan_base(client_user_id, trainer_user_id)
    wednesday = date(2026, 10, 21)
    with _client() as client:
        _install_test_stubs()
        _link(client_user_id, trainer_user_id)
        with patch("application.use_cases.date") as mocked_date:
            mocked_date.today.return_value = wednesday
            created = client.post(
                f"{base}/active",
                headers=_headers(trainer_user_id),
                json={
                    "goal": "maintenance",
                    "level": "intermediate",
                    "workouts_per_week": 3,
                    "day_count": 0,
                    "start_mode": "next_slot",
                },
            )
            assert created.status_code == 201, created.text
            assert created.json()["start_mode"] == "next_slot"
            assert created.json()["start_date"] == "2026-10-21"
            headers = _headers(trainer_user_id)
            plan = created.json()
            for day_of_week in (0, 2, 4):
                added = client.post(
                    f"{base}/days",
                    headers=headers,
                    json={"week": 1, "day_of_week": day_of_week},
                )
                assert added.status_code == 201, added.text
                plan = added.json()

            assert plan["start_date"] == "2026-10-21"
            monday = _week_day(plan, 0)
            midweek = _week_day(plan, 2)
            friday = _week_day(plan, 4)
            assert monday["scheduled_for"] == "2026-10-19"
            assert monday["shown"] is False
            assert midweek["scheduled_for"] == "2026-10-21"
            assert midweek["shown"] is True
            assert friday["scheduled_for"] == "2026-10-23"
            assert friday["shown"] is True
            assert [item["day_index"] for item in plan["days"]] == [1, 2, 3]

            exercise = _create_exercise(client, trainer_user_id)
            for day_index in (monday["day_index"], midweek["day_index"]):
                slotted = client.post(
                    f"{base}/days/{day_index}/exercises",
                    headers=headers,
                    json={"exercise_id": exercise["row_id"], "sets": 3, "reps": 8},
                )
                assert slotted.status_code == 201, slotted.text

            mocked_date.today.return_value = date(2026, 10, 19)
            hidden_today = client.get("/api/v1/plans/me/today", headers=_auth(client_user_id))
            assert hidden_today.status_code == 404

            mocked_date.today.return_value = wednesday
            visible_today = client.get("/api/v1/plans/me/today", headers=_auth(client_user_id))
            assert visible_today.status_code == 200, visible_today.text
            assert visible_today.json()["day_index"] == midweek["day_index"]
            assert visible_today.json()["scheduled_for"] == "2026-10-21"

            denied = client.post(
                f"/api/v1/plans/me/days/{monday['day_index']}/complete",
                headers=_auth(client_user_id),
            )
            assert denied.status_code == 404
            completed = client.post(
                f"/api/v1/plans/me/days/{midweek['day_index']}/complete",
                headers=_auth(client_user_id),
            )
            assert completed.status_code == 200, completed.text

            forbidden = client.patch(
                f"{base}/active",
                headers=_auth(client_user_id),
                json={"start_mode": "next_week"},
            )
            assert forbidden.status_code == 403

            shifted = client.patch(
                f"{base}/active",
                headers=_headers(trainer_user_id),
                json={"start_mode": "date", "start_date": "2026-10-26"},
            )
            assert shifted.status_code == 200, shifted.text
            body = shifted.json()
            assert body["start_mode"] == "date"
            assert body["start_date"] == "2026-10-26"
            by_id = {item["day_id"]: item for item in body["days"]}
            assert by_id[midweek["day_id"]]["day_index"] == midweek["day_index"]
            assert by_id[midweek["day_id"]]["scheduled_for"] == "2026-10-21"
            assert by_id[midweek["day_id"]]["is_completed"] is True
            assert by_id[midweek["day_id"]]["shown"] is True
            assert by_id[monday["day_id"]]["day_index"] == monday["day_index"]
            assert by_id[monday["day_id"]]["scheduled_for"] == "2026-10-26"
            assert by_id[monday["day_id"]]["shown"] is True
            assert by_id[friday["day_id"]]["day_index"] == friday["day_index"]
            assert by_id[friday["day_id"]]["scheduled_for"] == "2026-10-30"
            assert by_id[friday["day_id"]]["shown"] is True


def test_saturday_next_slot_and_next_week_monday() -> None:
    client_user_id = "start_saturday_client"
    trainer_user_id = "start_saturday_trainer"
    base = _plan_base(client_user_id, trainer_user_id)
    saturday = date(2026, 10, 24)
    with _client() as client:
        _install_test_stubs()
        _link(client_user_id, trainer_user_id)
        with patch("application.use_cases.date") as mocked_date:
            mocked_date.today.return_value = saturday
            created = client.post(
                f"{base}/active",
                headers=_headers(trainer_user_id),
                json={
                    "goal": "maintenance",
                    "level": "intermediate",
                    "workouts_per_week": 3,
                    "day_count": 0,
                    "start_mode": "next_slot",
                },
            )
            assert created.status_code == 201, created.text
            headers = _headers(trainer_user_id)
            plan = created.json()
            for day_of_week in (0, 2, 4):
                added = client.post(f"{base}/days", headers=headers, json={"week": 1, "day_of_week": day_of_week})
                assert added.status_code == 201, added.text
                plan = added.json()
            assert plan["start_date"] == "2026-10-26"
            assert _week_day(plan, 0)["scheduled_for"] == "2026-10-26"
            assert _week_day(plan, 2)["scheduled_for"] == "2026-10-28"
            assert _week_day(plan, 4)["scheduled_for"] == "2026-10-30"
            assert all(item["shown"] for item in plan["days"])

            missing_date = client.patch(f"{base}/active", headers=headers, json={"start_mode": "date"})
            assert missing_date.status_code == 422
            extra_date = client.patch(
                f"{base}/active",
                headers=headers,
                json={"start_mode": "next_week", "start_date": "2026-10-26"},
            )
            assert extra_date.status_code == 422

            # Сегодня среда: следующая календарная неделя начинается в понедельник 26 октября.
            mocked_date.today.return_value = date(2026, 10, 21)
            nxt = client.patch(f"{base}/active", headers=headers, json={"start_mode": "next_week"})
            assert nxt.status_code == 200, nxt.text
            body = nxt.json()
            assert body["start_mode"] == "next_week"
            assert body["start_date"] == "2026-10-26"
            assert _week_day(body, 0)["scheduled_for"] == "2026-10-26"
            assert _week_day(body, 2)["scheduled_for"] == "2026-10-28"
            assert _week_day(body, 4)["scheduled_for"] == "2026-10-30"
            assert all(item["shown"] for item in body["days"])


def test_generate_next_week_starts_on_monday() -> None:
    client_user_id = "start_generate_client"
    trainer_user_id = "start_generate_trainer"
    with _client() as client:
        _install_test_stubs()
        _link(client_user_id, trainer_user_id)
        with patch("application.use_cases.date") as mocked_date:
            mocked_date.today.return_value = date(2026, 10, 21)
            generated = client.post(
                "/api/v1/plans/generate",
                headers=_headers(trainer_user_id),
                json={
                    "trainer_user_id": trainer_user_id,
                    "user_id": client_user_id,
                    "goal": "maintenance",
                    "level": "beginner",
                    "workout_location": "home",
                    "workouts_per_week": 3,
                    "unavailable_equipment": [],
                    "start_mode": "next_week",
                },
            )
        assert generated.status_code == 201, generated.text
        body = generated.json()
        assert body["start_mode"] == "next_week"
        assert body["start_date"] == "2026-10-26"
        assert min(day["scheduled_for"] for day in body["days"]) == "2026-10-26"
        assert all(day["shown"] for day in body["days"])


def test_note_and_schedule_migration_is_reversible(tmp_path: Path, monkeypatch) -> None:
    database_path = tmp_path / "migration.db"
    url = f"sqlite+pysqlite:///{database_path.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")

    engine = create_engine(url)
    day_columns = {column["name"] for column in inspect(engine).get_columns("plan_days")}
    exercise_columns = {column["name"] for column in inspect(engine).get_columns("plan_exercises")}
    assert {"scheduled_time", "started_at", "finished_at"} <= day_columns
    assert "note" in exercise_columns
    engine.dispose()

    command.downgrade(config, "0020_media_object_keys")
    engine = create_engine(url)
    day_columns = {column["name"] for column in inspect(engine).get_columns("plan_days")}
    exercise_columns = {column["name"] for column in inspect(engine).get_columns("plan_exercises")}
    assert "scheduled_time" not in day_columns
    assert "started_at" not in day_columns
    assert "finished_at" not in day_columns
    assert "note" not in exercise_columns
    engine.dispose()

    command.upgrade(config, "head")
    engine = create_engine(url)
    day_columns = {column["name"] for column in inspect(engine).get_columns("plan_days")}
    exercise_columns = {column["name"] for column in inspect(engine).get_columns("plan_exercises")}
    assert {"scheduled_time", "started_at", "finished_at"} <= day_columns
    assert "note" in exercise_columns
    engine.dispose()
