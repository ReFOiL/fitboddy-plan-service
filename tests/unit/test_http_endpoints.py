from datetime import date
from unittest.mock import patch

from fastapi.testclient import TestClient

from application.gateways import AuthUser
from presentation.http.main import app

_ACTIVE_RELATIONS: dict[str, str] = {}

_ADMIN_HEADERS = {"Authorization": "Bearer test-admin-token"}
_USER_HEADERS = {"Authorization": "Bearer test-user-token"}


def _client() -> TestClient:
    return TestClient(app)


def _install_test_stubs() -> None:
    runtime = app.state.plan_handler._runtime
    runtime.tenant_gateway.get_client_active_trainer_id = lambda client_id: _ACTIVE_RELATIONS.get(client_id)


def _link(client_user_id: str, trainer_user_id: str) -> None:
    _ACTIVE_RELATIONS[client_user_id] = trainer_user_id


def _auth_as_platform_admin() -> None:
    runtime = app.state.plan_handler._runtime
    runtime.auth_gateway.require_platform_admin = lambda _token: AuthUser(
        user_id="admin_1",
        tenant_id="platform",
        role="platform_admin",
    )


def _auth_as_user(user_id: str, *, role: str = "client") -> None:
    runtime = app.state.plan_handler._runtime
    runtime.auth_gateway.get_current_user = lambda _token: AuthUser(
        user_id=user_id,
        tenant_id="tenant_1",
        role=role,
    )


def _auth(user_id: str, *, role: str = "client") -> dict[str, str]:
    _auth_as_user(user_id, role=role)
    return _USER_HEADERS


def _generate_plan(client: TestClient, payload: dict, *, as_user: str | None = None, as_role: str | None = None):
    user_id = payload["user_id"]
    source = payload.get("source", "trainer")
    if source == "system":
        headers = _auth(as_user or user_id, role=as_role or "client")
    else:
        trainer_id = payload.get("trainer_user_id")
        if trainer_id:
            _link(user_id, trainer_id)
        actor = as_user or user_id
        role = as_role or ("trainer" if trainer_id and actor == trainer_id else "client")
        headers = _auth(actor, role=role)
    return client.post("/api/v1/plans/generate", json=payload, headers=headers)


def _get_active(client: TestClient, user_id: str, *, as_user: str | None = None, as_role: str = "client"):
    return client.get(
        f"/api/v1/plans/users/{user_id}/active",
        headers=_auth(as_user or user_id, role=as_role),
    )


def _put_trainer_load(
    client: TestClient,
    client_user_id: str,
    trainer_user_id: str,
    row_id: str,
    working_weight_kg: float,
    *,
    as_user: str | None = None,
    as_role: str | None = None,
):
    _link(client_user_id, trainer_user_id)
    actor = as_user or client_user_id
    role = as_role or ("trainer" if actor == trainer_user_id else "client")
    return client.put(
        f"/api/v1/plans/clients/{client_user_id}/trainers/{trainer_user_id}/loads/{row_id}",
        json={"working_weight_kg": working_weight_kg},
        headers=_auth(actor, role=role),
    )


def _list_trainer_loads(
    client: TestClient,
    client_user_id: str,
    trainer_user_id: str,
    *,
    as_user: str | None = None,
):
    _link(client_user_id, trainer_user_id)
    actor = as_user or client_user_id
    return client.get(
        f"/api/v1/plans/clients/{client_user_id}/trainers/{trainer_user_id}/loads",
        headers=_auth(actor),
    )


def _put_platform_load(client: TestClient, client_user_id: str, row_id: str, working_weight_kg: float):
    return client.put(
        f"/api/v1/plans/clients/{client_user_id}/platform/loads/{row_id}",
        json={"working_weight_kg": working_weight_kg},
        headers=_auth(client_user_id),
    )


def _list_platform_loads(client: TestClient, client_user_id: str):
    return client.get(
        f"/api/v1/plans/clients/{client_user_id}/platform/loads",
        headers=_auth(client_user_id),
    )


def test_health() -> None:
    with _client() as client:
        _install_test_stubs()
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


def test_generate_and_read_active_plan() -> None:
    payload = {
        "trainer_user_id": "trainer_1",
        "user_id": "client_1",
        "goal": "weight_loss",
        "level": "beginner",
        "workout_location": "home",
        "workouts_per_week": 3,
        "unavailable_equipment": ["none", "dumbbells"],
    }
    with _client() as client:
        _install_test_stubs()
        generate = _generate_plan(client, payload)
        assert generate.status_code == 201
        body = generate.json()
        assert body["source"] == "trainer"
        assert body["trainer_user_id"] == "trainer_1"
        assert body["user_id"] == "client_1"
        assert body["status"] == "active"
        assert len(body["days"]) > 0
        plan_id = body["plan_id"]

        active = _get_active(client, "client_1")
        assert active.status_code == 200
        assert active.json()["plan_id"] == plan_id

        first_day = client.get(f"/api/v1/plans/{plan_id}/days/1")
        assert first_day.status_code == 200
        assert first_day.json()["day_index"] == 1
        assert len(first_day.json()["exercises"]) > 0


def test_active_plan_not_found() -> None:
    with _client() as client:
        _install_test_stubs()
        response = _get_active(client, "unknown_user")
        assert response.status_code == 404


def test_plan_keeps_trainer_binding() -> None:
    payload_a = {
        "trainer_user_id": "trainer_a",
        "user_id": "client_a",
        "goal": "maintenance",
        "level": "intermediate",
        "workout_location": "gym",
        "workouts_per_week": 4,
        "unavailable_equipment": ["dumbbells", "barbell"],
    }
    payload_b = {
        "trainer_user_id": "trainer_b",
        "user_id": "client_b",
        "goal": "maintenance",
        "level": "intermediate",
        "workout_location": "gym",
        "workouts_per_week": 4,
        "unavailable_equipment": ["dumbbells", "barbell"],
    }
    with _client() as client:
        _install_test_stubs()
        plan_a = _generate_plan(client, payload_a)
        plan_b = _generate_plan(client, payload_b)
        assert plan_a.status_code == 201
        assert plan_b.status_code == 201
        assert plan_a.json()["trainer_user_id"] == "trainer_a"
        assert plan_b.json()["trainer_user_id"] == "trainer_b"


def test_generate_forbidden_without_relation() -> None:
    payload = {
        "trainer_user_id": "trainer_forbidden",
        "user_id": "client_forbidden",
        "goal": "maintenance",
        "level": "beginner",
        "workout_location": "home",
        "workouts_per_week": 3,
        "unavailable_equipment": [],
    }
    with _client() as client:
        _install_test_stubs()
        # relation not linked
        response = client.post(
            "/api/v1/plans/generate",
            json=payload,
            headers=_auth("client_forbidden"),
        )
        assert response.status_code == 403


def test_trainer_can_generate_for_linked_client() -> None:
    payload = {
        "trainer_user_id": "trainer_cockpit_1",
        "user_id": "client_cockpit_1",
        "goal": "maintenance",
        "level": "intermediate",
        "workout_location": "gym",
        "workouts_per_week": 3,
        "unavailable_equipment": [],
    }
    with _client() as client:
        _install_test_stubs()
        generated = _generate_plan(client, payload, as_user="trainer_cockpit_1", as_role="trainer")
        assert generated.status_code == 201
        active = _get_active(client, "client_cockpit_1", as_user="trainer_cockpit_1", as_role="trainer")
        assert active.status_code == 200
        assert active.json()["plan_id"] == generated.json()["plan_id"]


def test_trainer_catalog_crud() -> None:
    trainer_user_id = "trainer_catalog_1"
    create_payload = {
        "exercise_name": "Bulgarian Split Squat",
        "description": "Keep torso upright and control the descent.",
        "equipment": "dumbbells",
        "is_cardio": False,
        "is_hold": False,
        "difficulty": 3,
        "workout_category": "lower",
    }
    with _client() as client:
        _install_test_stubs()
        created = client.post(
            f"/api/v1/trainers/{trainer_user_id}/exercises",
            json=create_payload,
        )
        assert created.status_code == 201
        row_id = created.json()["row_id"]
        assert row_id
        assert created.json()["is_active"] is True
        assert created.json()["description"] == "Keep torso upright and control the descent."
        assert "exercise_id" not in created.json()

        detail = client.get(f"/api/v1/trainers/{trainer_user_id}/exercises/{row_id}")
        assert detail.status_code == 200
        assert detail.json()["description"] == "Keep torso upright and control the descent."

        listed = client.get(f"/api/v1/trainers/{trainer_user_id}/exercises")
        assert listed.status_code == 200
        assert any(item["row_id"] == row_id for item in listed.json())

        update_payload = {
            "exercise_name": "Bulgarian Split Squat Paused",
            "description": "Pause 1 second at the bottom.",
            "equipment": "dumbbells",
        "is_cardio": False,
        "is_hold": False,
        "difficulty": 4,
            "workout_category": "lower",
        }
        updated = client.put(
            f"/api/v1/trainers/{trainer_user_id}/exercises/{row_id}",
            json=update_payload,
        )
        assert updated.status_code == 200
        assert updated.json()["exercise_name"] == "Bulgarian Split Squat Paused"
        assert updated.json()["difficulty"] == 4
        assert updated.json()["description"] == "Pause 1 second at the bottom."

        archived = client.post(f"/api/v1/trainers/{trainer_user_id}/exercises/{row_id}/archive")
        assert archived.status_code == 204

        listed_active = client.get(f"/api/v1/trainers/{trainer_user_id}/exercises")
        assert listed_active.status_code == 200
        assert all(item["row_id"] != row_id for item in listed_active.json())

        listed_all = client.get(f"/api/v1/trainers/{trainer_user_id}/exercises?include_archived=true")
        assert listed_all.status_code == 200
        archived_item = next(item for item in listed_all.json() if item["row_id"] == row_id)
        assert archived_item["is_active"] is False


def test_exercise_video_upload_requires_s3_configuration() -> None:
    trainer_user_id = "trainer_video_1"
    payload = {
        "exercise_name": "Video Squat",
        "equipment": "none",
        "is_cardio": False,
        "is_hold": False,
        "difficulty": 2,
        "workout_category": "lower",
    }
    with _client() as client:
        _install_test_stubs()
        created = client.post(f"/api/v1/trainers/{trainer_user_id}/exercises", json=payload)
        assert created.status_code == 201
        row_id = created.json()["row_id"]
        response = client.post(
            f"/api/v1/trainers/{trainer_user_id}/exercises/{row_id}/video",
            files={"file": ("demo.mp4", b"fake-video-bytes", "video/mp4")},
        )
        assert response.status_code == 503
        assert "not configured" in response.json()["detail"]


def test_exercise_video_upload_and_delete_success() -> None:
    class _FakeStorage:
        def __init__(self) -> None:
            self.deleted: list[str] = []
            self.expected_row_id: str | None = None

        async def upload_video(self, *, owner_id: str, row_id: str, filename: str, data: bytes) -> str:
            assert owner_id == "trainer_video_2"
            assert row_id == self.expected_row_id
            assert filename == "demo.mp4"
            assert data
            return f"videos/{owner_id}/{row_id}/fake.mp4"

        async def delete_media(self, object_name: str) -> None:
            self.deleted.append(object_name)

        async def download_media(self, object_name: str) -> tuple[bytes, str]:
            assert object_name == f"videos/trainer_video_2/{self.expected_row_id}/fake.mp4"
            return b"video-bytes", "video/mp4"

    trainer_user_id = "trainer_video_2"
    payload = {
        "exercise_name": "Video Pushup",
        "equipment": "none",
        "is_cardio": False,
        "is_hold": False,
        "difficulty": 2,
        "workout_category": "upper",
    }
    with _client() as client:
        _install_test_stubs()
        created = client.post(f"/api/v1/trainers/{trainer_user_id}/exercises", json=payload)
        assert created.status_code == 201
        row_id = created.json()["row_id"]
        assert created.json().get("video_url") is None

        fake_storage = _FakeStorage()
        fake_storage.expected_row_id = row_id
        app.state.plan_handler._runtime._video_storage = fake_storage

        uploaded = client.post(
            f"/api/v1/trainers/{trainer_user_id}/exercises/{row_id}/video",
            files={"file": ("demo.mp4", b"fake-video-bytes", "video/mp4")},
        )
        assert uploaded.status_code == 200
        video_url = uploaded.json()["video_url"]
        assert video_url == f"/api/v1/trainers/media/videos/trainer_video_2/{row_id}/fake.mp4"
        assert uploaded.json()["row_id"] == row_id

        listed = client.get(f"/api/v1/trainers/{trainer_user_id}/exercises")
        assert listed.status_code == 200
        item = next(row for row in listed.json() if row["row_id"] == row_id)
        assert item["video_url"] == video_url

        media = client.get(video_url)
        assert media.status_code == 200
        assert media.content == b"video-bytes"
        assert media.headers["content-type"].startswith("video/mp4")

        deleted = client.delete(f"/api/v1/trainers/{trainer_user_id}/exercises/{row_id}/video")
        assert deleted.status_code == 204
        assert fake_storage.deleted == [f"videos/trainer_video_2/{row_id}/fake.mp4"]

        listed_after = client.get(f"/api/v1/trainers/{trainer_user_id}/exercises")
        item_after = next(row for row in listed_after.json() if row["row_id"] == row_id)
        assert item_after["video_url"] is None


def test_trainer_catalog_allows_same_name_twice() -> None:
    trainer_user_id = "trainer_catalog_2"
    payload = {
        "exercise_name": "Dumbbell Deadlift",
        "equipment": "dumbbells",
        "is_cardio": False,
        "is_hold": False,
        "difficulty": 3,
        "workout_category": "full_body",
    }
    with _client() as client:
        _install_test_stubs()
        first = client.post(f"/api/v1/trainers/{trainer_user_id}/exercises", json=payload)
        second = client.post(f"/api/v1/trainers/{trainer_user_id}/exercises", json=payload)
        assert first.status_code == 201
        assert second.status_code == 201
        assert first.json()["row_id"] != second.json()["row_id"]


def test_trainer_catalog_rejects_cardio_workout_category() -> None:
    trainer_user_id = "trainer_catalog_3"
    payload = {
        "exercise_name": "Cardio category should be rejected",
        "equipment": "none",
        "is_cardio": True,
        "is_hold": False,
        "difficulty": 2,
        "workout_category": "cardio",
    }
    with _client() as client:
        _install_test_stubs()
        response = client.post(f"/api/v1/trainers/{trainer_user_id}/exercises", json=payload)
        assert response.status_code == 422


def test_trainer_catalog_auto_seeds_baseline_for_new_trainer() -> None:
    trainer_user_id = "trainer_new_baseline"
    with _client() as client:
        _install_test_stubs()
        listed = client.get(f"/api/v1/trainers/{trainer_user_id}/exercises")
        assert listed.status_code == 200
        body = listed.json()
        assert len(body) > 0
        assert any(item["exercise_name"] == "Отжимания" for item in body)
        assert all("row_id" in item and "exercise_id" not in item for item in body)


def test_trainer_baseline_copies_from_platform_catalog() -> None:
    """Trainer starter pool is a clone of platform_exercises (Support base), not a parallel seed."""
    from sqlalchemy import select

    from application.models import PlatformExerciseModel

    with _client() as client:
        _install_test_stubs()
        listed = client.get("/api/v1/trainers/trainer_from_platform/exercises")
        assert listed.status_code == 200
        trainer_names = {item["exercise_name"] for item in listed.json()}
        assert "Отжимания" in trainer_names

        runtime = app.state.plan_handler._runtime
        session = runtime._db_manager.create_session()
        try:
            platform_names = {
                row.exercise_name
                for row in session.scalars(
                    select(PlatformExerciseModel).where(PlatformExerciseModel.is_active.is_(True))
                ).all()
            }
        finally:
            session.close()

        assert platform_names
        assert trainer_names == platform_names


def test_generate_plan_requires_completed_questionnaire_when_guard_enabled() -> None:
    with _client() as client:
        _install_test_stubs()
        runtime = app.state.plan_handler._runtime
        runtime._settings.require_profile_completion = True
        runtime._profile_gateway.is_questionnaire_completed = lambda _user_id: False
        payload = {
            "trainer_user_id": "trainer_guard",
            "user_id": "client_guard",
            "goal": "maintenance",
            "level": "beginner",
            "workout_location": "home",
            "workouts_per_week": 3,
            "unavailable_equipment": ["none"],
        }
        response = _generate_plan(client, payload)
        assert response.status_code == 422
        assert "questionnaire is incomplete" in response.json()["detail"]
        runtime._settings.require_profile_completion = False


def test_client_loads_and_scheme_affect_generated_plan() -> None:
    trainer_user_id = "trainer_loads_1"
    client_user_id = "client_loads_1"
    with _client() as client:
        _install_test_stubs()
        created = client.post(
            f"/api/v1/trainers/{trainer_user_id}/exercises",
            json={
                "exercise_name": "Жим лёжа",
                "equipment": "barbell",
                "is_cardio": False,
                "is_hold": False,
                "difficulty": 3,
                "workout_category": "upper",
                "default_sets": 4,
                "default_reps": 6,
                "default_rest_seconds": 90,
                "default_weight_kg": 40,
                "load_scheme": "ascending",
            },
        )
        assert created.status_code == 201
        row_id = created.json()["row_id"]
        assert created.json()["load_scheme"] == "ascending"

        load = _put_trainer_load(client, client_user_id, trainer_user_id, row_id, 100)
        assert load.status_code == 200
        assert load.json()["working_weight_kg"] == 100

        listed_loads = _list_trainer_loads(client, client_user_id, trainer_user_id)
        assert listed_loads.status_code == 200
        assert any(item["exercise_row_id"] == row_id for item in listed_loads.json())

        generated = _generate_plan(client, {
                "trainer_user_id": trainer_user_id,
                "user_id": client_user_id,
                "goal": "maintenance",
                "level": "intermediate",
                "workout_location": "gym",
                "workouts_per_week": 3,
                "unavailable_equipment": [],
            })
        assert generated.status_code == 201
        exercises = [
            exercise
            for day in generated.json()["days"]
            for exercise in day["exercises"]
            if exercise["exercise_id"] == row_id
        ]
        assert exercises
        sample = exercises[0]
        assert sample["set_prescriptions"]
        assert sample["weight_kg"] == 100
        assert sample["set_prescriptions"][0]["weight_kg"] < sample["set_prescriptions"][-1]["weight_kg"]
        assert sample["set_prescriptions"][-1]["weight_kg"] == 100


def test_upsert_load_patches_incomplete_active_plan_days() -> None:
    trainer_user_id = "trainer_reactive_weights_1"
    client_user_id = "client_reactive_weights_1"
    with _client() as client:
        _install_test_stubs()
        created = client.post(
            f"/api/v1/trainers/{trainer_user_id}/exercises",
            json={
                "exercise_name": "Жим реактивный",
                "equipment": "barbell",
                "is_cardio": False,
                "is_hold": False,
                "difficulty": 3,
                "workout_category": "upper",
                "default_sets": 3,
                "default_reps": 6,
                "default_rest_seconds": 90,
                "default_weight_kg": 40,
                "load_scheme": "ascending",
            },
        )
        assert created.status_code == 201
        row_id = created.json()["row_id"]

        load = _put_trainer_load(client, client_user_id, trainer_user_id, row_id, 100)
        assert load.status_code == 200

        generated = _generate_plan(client, {
                "trainer_user_id": trainer_user_id,
                "user_id": client_user_id,
                "goal": "maintenance",
                "level": "intermediate",
                "workout_location": "gym",
                "workouts_per_week": 3,
                "unavailable_equipment": [],
            })
        assert generated.status_code == 201
        plan = generated.json()
        days_with_exercise = [
            day for day in plan["days"] if any(ex["exercise_id"] == row_id for ex in day["exercises"])
        ]
        assert len(days_with_exercise) >= 2
        completed_day = days_with_exercise[0]
        incomplete_day = days_with_exercise[1]

        _auth_as_user(client_user_id)
        completed = client.post(
            f"/api/v1/plans/me/days/{completed_day['day_index']}/complete",
            headers=_USER_HEADERS,
        )
        assert completed.status_code == 200

        updated = _put_trainer_load(client, client_user_id, trainer_user_id, row_id, 120)
        assert updated.status_code == 200

        active = _get_active(client, client_user_id)
        assert active.status_code == 200
        active_days = {day["day_index"]: day for day in active.json()["days"]}

        completed_lines = [
            ex for ex in active_days[completed_day["day_index"]]["exercises"] if ex["exercise_id"] == row_id
        ]
        incomplete_lines = [
            ex for ex in active_days[incomplete_day["day_index"]]["exercises"] if ex["exercise_id"] == row_id
        ]
        assert completed_lines
        assert incomplete_lines
        assert completed_lines[0]["weight_kg"] == 100
        assert incomplete_lines[0]["weight_kg"] == 120
        assert incomplete_lines[0]["set_prescriptions"][-1]["weight_kg"] == 120


def test_replace_plan_exercise_applies_new_exercise_load() -> None:
    client_user_id = "client_replace_load_1"
    replacement_weight = 77.5
    with _client() as client:
        _install_test_stubs()
        generated = _generate_plan(client, {
                "source": "system",
                "user_id": client_user_id,
                "goal": "weight_loss",
                "level": "beginner",
                "workout_location": "home",
                "workouts_per_week": 3,
                "unavailable_equipment": ["dumbbells", "barbell"],
            })
        assert generated.status_code == 201
        target_day = next(day for day in generated.json()["days"] if day["exercises"])
        line = next(ex for ex in target_day["exercises"] if not ex["is_cardio"])
        previous_id = line["exercise_id"]
        day_exercise_ids = {ex["exercise_id"] for ex in target_day["exercises"]}

        catalog = client.get("/api/v1/platform-exercises")
        assert catalog.status_code == 200
        candidates_loaded = 0
        for item in catalog.json():
            if not item.get("is_active") or item.get("is_cardio"):
                continue
            if item["row_id"] == previous_id or item["row_id"] in day_exercise_ids:
                continue
            load = _put_platform_load(client, client_user_id, item["row_id"], replacement_weight)
            assert load.status_code == 200
            candidates_loaded += 1
        assert candidates_loaded > 0

        _auth_as_user(client_user_id)
        replaced = client.post(
            f"/api/v1/plans/me/days/{target_day['day_index']}/exercises/{line['line_id']}/replace",
            headers=_USER_HEADERS,
        )
        assert replaced.status_code == 200, replaced.text
        replaced_line = next(item for item in replaced.json()["exercises"] if item["line_id"] == line["line_id"])
        assert replaced_line["exercise_id"] != previous_id
        assert replaced_line["weight_kg"] == replacement_weight
        assert replaced_line["set_prescriptions"]
        assert replaced_line["set_prescriptions"][-1]["weight_kg"] == replacement_weight


def test_unavailable_equipment_excludes_matching_exercises() -> None:
    trainer_user_id = "trainer_excl_1"
    client_user_id = "client_excl_1"
    with _client() as client:
        _install_test_stubs()
        barbell = client.post(
            f"/api/v1/trainers/{trainer_user_id}/exercises",
            json={
                "exercise_name": "Жим штанги",
                "equipment": "barbell",
                "is_cardio": False,
                "is_hold": False,
                "difficulty": 2,
                "workout_category": "upper",
                "default_sets": 3,
                "default_reps": 8,
                "default_rest_seconds": 60,
            },
        )
        bodyweight = client.post(
            f"/api/v1/trainers/{trainer_user_id}/exercises",
            json={
                "exercise_name": "Отжимания тест",
                "equipment": "none",
                "is_cardio": False,
                "is_hold": False,
                "difficulty": 2,
                "workout_category": "upper",
                "default_sets": 3,
                "default_reps": 10,
                "default_rest_seconds": 45,
            },
        )
        custom = client.post(
            f"/api/v1/trainers/{trainer_user_id}/exercises",
            json={
                "exercise_name": "Аэробайк",
                "equipment": "Аэробайк",
                "is_cardio": True,
                "is_hold": True,
                "difficulty": 2,
                "workout_category": "full_body",
                "default_sets": 3,
                "default_duration_seconds": 40,
                "default_rest_seconds": 30,
            },
        )
        assert barbell.status_code == 201
        assert bodyweight.status_code == 201
        assert custom.status_code == 201
        barbell_id = barbell.json()["row_id"]
        bodyweight_id = bodyweight.json()["row_id"]
        air_bike_id = custom.json()["row_id"]
        assert custom.json()["equipment"] == "Аэробайк"

        excluded = _generate_plan(client, {
                "trainer_user_id": trainer_user_id,
                "user_id": client_user_id,
                "goal": "maintenance",
                "level": "intermediate",
                "workout_location": "gym",
                "workouts_per_week": 3,
                "unavailable_equipment": ["barbell"],
            })
        assert excluded.status_code == 201
        exercise_ids = {
            exercise["exercise_id"]
            for day in excluded.json()["days"]
            for exercise in day["exercises"]
        }
        assert barbell_id not in exercise_ids
        assert bodyweight_id in exercise_ids or air_bike_id in exercise_ids

        without_air = _generate_plan(client, {
                "trainer_user_id": trainer_user_id,
                "user_id": f"{client_user_id}_2",
                "goal": "endurance",
                "level": "intermediate",
                "workout_location": "gym",
                "workouts_per_week": 3,
                "unavailable_equipment": ["аэробайк"],
            })
        assert without_air.status_code == 201
        air_ids = {
            exercise["exercise_id"]
            for day in without_air.json()["days"]
            for exercise in day["exercises"]
        }
        assert air_bike_id not in air_ids


def test_platform_exercises_admin_crud() -> None:
    create_payload = {
        "exercise_name": "Platform Goblet Squat",
        "description": "Base catalog exercise from Support.",
        "equipment": "dumbbells",
        "is_cardio": False,
        "is_hold": False,
        "difficulty": 2,
        "workout_category": "lower",
        "catalog_key": "platform_goblet_squat",
        "default_sets": 3,
        "default_reps": 12,
        "default_rest_seconds": 60,
    }
    with _client() as client:
        _install_test_stubs()
        _auth_as_platform_admin()

        unauthorized = client.get("/api/v1/admin/platform-exercises")
        assert unauthorized.status_code == 401

        created = client.post(
            "/api/v1/admin/platform-exercises",
            json=create_payload,
            headers=_ADMIN_HEADERS,
        )
        assert created.status_code == 201
        body = created.json()
        row_id = body["row_id"]
        assert body["catalog_key"] == "platform_goblet_squat"
        assert body["exercise_name"] == "Platform Goblet Squat"
        assert body["is_active"] is True

        duplicate = client.post(
            "/api/v1/admin/platform-exercises",
            json=create_payload,
            headers=_ADMIN_HEADERS,
        )
        assert duplicate.status_code == 409

        detail = client.get(f"/api/v1/admin/platform-exercises/{row_id}", headers=_ADMIN_HEADERS)
        assert detail.status_code == 200
        assert detail.json()["description"] == "Base catalog exercise from Support."

        listed = client.get("/api/v1/admin/platform-exercises", headers=_ADMIN_HEADERS)
        assert listed.status_code == 200
        assert listed.json()["total"] >= 1
        assert any(item["row_id"] == row_id for item in listed.json()["items"])

        updated = client.put(
            f"/api/v1/admin/platform-exercises/{row_id}",
            json={
                **create_payload,
                "exercise_name": "Platform Goblet Squat Updated",
                "difficulty": 3,
            },
            headers=_ADMIN_HEADERS,
        )
        assert updated.status_code == 200
        assert updated.json()["exercise_name"] == "Platform Goblet Squat Updated"
        assert updated.json()["difficulty"] == 3

        archived = client.post(
            f"/api/v1/admin/platform-exercises/{row_id}/archive",
            headers=_ADMIN_HEADERS,
        )
        assert archived.status_code == 204

        active_only = client.get(
            "/api/v1/admin/platform-exercises?include_archived=false",
            headers=_ADMIN_HEADERS,
        )
        assert active_only.status_code == 200
        assert all(item["row_id"] != row_id for item in active_only.json()["items"])

        with_archived = client.get(
            "/api/v1/admin/platform-exercises?include_archived=true",
            headers=_ADMIN_HEADERS,
        )
        archived_item = next(item for item in with_archived.json()["items"] if item["row_id"] == row_id)
        assert archived_item["is_active"] is False


def test_list_muscles_and_exercise_muscle_targets() -> None:
    with _client() as client:
        _install_test_stubs()
        muscles = client.get("/api/v1/muscles")
        assert muscles.status_code == 200
        catalog = muscles.json()
        assert isinstance(catalog, list)
        assert len(catalog) >= 30
        assert any(item["slug"] == "chest" and item["name_ru"] for item in catalog)

        _auth_as_platform_admin()
        created = client.post(
            "/api/v1/admin/platform-exercises",
            json={
                "exercise_name": "Bench with muscles",
                "equipment": "barbell",
                "is_cardio": False,
                "is_hold": False,
                "difficulty": 3,
                "workout_category": "upper",
                "default_sets": 3,
                "default_reps": 8,
                "default_rest_seconds": 90,
                "primary_muscles": ["chest", "triceps"],
                "secondary_muscles": ["anterior_deltoid"],
            },
            headers=_ADMIN_HEADERS,
        )
        assert created.status_code == 201
        body = created.json()
        assert body["primary_muscles"] == ["chest", "triceps"]
        assert body["secondary_muscles"] == ["anterior_deltoid"]
        assert body["workout_category"] == "upper"

        ignored_category = client.post(
            "/api/v1/admin/platform-exercises",
            json={
                "exercise_name": "Squat category override",
                "equipment": "barbell",
                "is_cardio": False,
                "is_hold": False,
                "difficulty": 3,
                "workout_category": "upper",
                "default_sets": 3,
                "default_reps": 8,
                "default_rest_seconds": 90,
                "primary_muscles": ["quadriceps", "glutes"],
                "secondary_muscles": [],
            },
            headers=_ADMIN_HEADERS,
        )
        assert ignored_category.status_code == 201
        assert ignored_category.json()["workout_category"] == "lower"

        detail = client.get(
            f"/api/v1/admin/platform-exercises/{body['row_id']}",
            headers=_ADMIN_HEADERS,
        )
        assert detail.status_code == 200
        assert detail.json()["primary_muscles"] == ["chest", "triceps"]

        unknown = client.post(
            "/api/v1/admin/platform-exercises",
            json={
                "exercise_name": "Bad muscles",
                "equipment": "none",
                "is_cardio": False,
                "is_hold": False,
                "difficulty": 1,
                "workout_category": "full_body",
                "default_sets": 3,
                "default_reps": 10,
                "default_rest_seconds": 60,
                "primary_muscles": ["not_a_real_muscle"],
            },
            headers=_ADMIN_HEADERS,
        )
        assert unknown.status_code == 422


def test_platform_exercise_video_upload_requires_s3_configuration() -> None:
    with _client() as client:
        _install_test_stubs()
        _auth_as_platform_admin()
        created = client.post(
            "/api/v1/admin/platform-exercises",
            json={
                "exercise_name": "Platform Video Squat",
                "equipment": "none",
                "is_cardio": False,
                "is_hold": False,
                "difficulty": 2,
                "workout_category": "lower",
                "catalog_key": "platform_video_squat",
            },
            headers=_ADMIN_HEADERS,
        )
        assert created.status_code == 201
        row_id = created.json()["row_id"]
        response = client.post(
            f"/api/v1/admin/platform-exercises/{row_id}/video",
            headers=_ADMIN_HEADERS,
            files={"file": ("demo.mp4", b"fake-video-bytes", "video/mp4")},
        )
        assert response.status_code == 503
        assert "not configured" in response.json()["detail"]


def test_generate_system_plan_without_trainer() -> None:
    payload = {
        "source": "system",
        "user_id": "client_system_1",
        "goal": "weight_loss",
        "level": "beginner",
        "workout_location": "home",
        "workouts_per_week": 3,
        "unavailable_equipment": ["dumbbells", "barbell"],
    }
    with _client() as client:
        _install_test_stubs()
        generate = _generate_plan(client, payload)
        assert generate.status_code == 201
        body = generate.json()
        assert body["source"] == "system"
        assert body["trainer_user_id"] is None
        assert body["user_id"] == "client_system_1"
        assert body["status"] == "active"
        assert len(body["days"]) > 0

        active = _get_active(client, "client_system_1")
        assert active.status_code == 200
        assert active.json()["source"] == "system"
        assert active.json()["trainer_user_id"] is None
        assert active.json()["plan_id"] == body["plan_id"]


def test_generate_system_rejects_trainer_user_id() -> None:
    payload = {
        "source": "system",
        "trainer_user_id": "should_not_be_here",
        "user_id": "client_system_bad",
        "goal": "maintenance",
        "level": "beginner",
        "workout_location": "home",
        "workouts_per_week": 3,
    }
    with _client() as client:
        _install_test_stubs()
        response = _generate_plan(client, payload)
        assert response.status_code == 422


def test_generate_trainer_requires_trainer_user_id() -> None:
    payload = {
        "source": "trainer",
        "user_id": "client_missing_trainer",
        "goal": "maintenance",
        "level": "beginner",
        "workout_location": "home",
        "workouts_per_week": 3,
    }
    with _client() as client:
        _install_test_stubs()
        response = _generate_plan(client, payload)
        assert response.status_code == 422


def test_generate_system_replaces_previous_trainer_plan() -> None:
    with _client() as client:
        _install_test_stubs()
        trainer_plan = _generate_plan(client, {
                "source": "trainer",
                "trainer_user_id": "trainer_switch_1",
                "user_id": "client_switch_1",
                "goal": "maintenance",
                "level": "intermediate",
                "workout_location": "gym",
                "workouts_per_week": 3,
            })
        assert trainer_plan.status_code == 201
        trainer_plan_id = trainer_plan.json()["plan_id"]

        system_plan = _generate_plan(client, {
                "source": "system",
                "user_id": "client_switch_1",
                "goal": "weight_loss",
                "level": "beginner",
                "workout_location": "home",
                "workouts_per_week": 3,
            })
        assert system_plan.status_code == 201
        assert system_plan.json()["source"] == "system"
        assert system_plan.json()["plan_id"] != trainer_plan_id

        active = _get_active(client, "client_switch_1")
        assert active.status_code == 200
        assert active.json()["plan_id"] == system_plan.json()["plan_id"]
        assert active.json()["source"] == "system"


def test_generate_trainer_compat_without_source_field() -> None:
    """Legacy clients that omit source still get trainer plans."""
    payload = {
        "trainer_user_id": "trainer_compat_1",
        "user_id": "client_compat_1",
        "goal": "maintenance",
        "level": "intermediate",
        "workout_location": "gym",
        "workouts_per_week": 3,
    }
    with _client() as client:
        _install_test_stubs()
        response = _generate_plan(client, payload)
        assert response.status_code == 201
        assert response.json()["source"] == "trainer"
        assert response.json()["trainer_user_id"] == "trainer_compat_1"


def test_new_trainer_clones_support_added_platform_exercise() -> None:
    with _client() as client:
        _install_test_stubs()
        _auth_as_platform_admin()
        created = client.post(
            "/api/v1/admin/platform-exercises",
            json={
                "exercise_name": "Support Unique Move",
                "equipment": "none",
                "is_cardio": False,
                "is_hold": False,
                "difficulty": 1,
                "workout_category": "full_body",
                "catalog_key": "support_unique_move",
            },
            headers=_ADMIN_HEADERS,
        )
        assert created.status_code == 201

        listed = client.get("/api/v1/trainers/trainer_after_support_add/exercises")
        assert listed.status_code == 200
        names = {item["exercise_name"] for item in listed.json()}
        assert "Support Unique Move" in names


def test_today_complete_and_replace_system_workout() -> None:
    user_id = "client_today_1"
    with _client() as client:
        _install_test_stubs()
        _auth_as_user(user_id)
        generated = _generate_plan(client, {
                "source": "system",
                "user_id": user_id,
                "goal": "weight_loss",
                "level": "beginner",
                "workout_location": "home",
                "workouts_per_week": 3,
                "unavailable_equipment": ["dumbbells", "barbell"],
            })
        assert generated.status_code == 201
        plan = generated.json()
        workout_day = next(day for day in plan["days"] if day["exercises"])
        workout_date = date.fromisoformat(workout_day["scheduled_for"])
        line_id = workout_day["exercises"][0]["line_id"]
        previous_name = workout_day["exercises"][0]["exercise_name"]

        with patch("application.use_cases.date") as mocked_date:
            mocked_date.today.return_value = workout_date
            today_response = client.get("/api/v1/plans/me/today", headers=_USER_HEADERS)
        assert today_response.status_code == 200
        today_body = today_response.json()
        assert today_body["plan_id"] == plan["plan_id"]
        assert today_body["source"] == "system"
        assert today_body["day_index"] == workout_day["day_index"]
        assert today_body["is_completed"] is False

        replaced = client.post(
            f"/api/v1/plans/me/days/{workout_day['day_index']}/exercises/{line_id}/replace",
            headers=_USER_HEADERS,
        )
        assert replaced.status_code == 200
        replaced_body = replaced.json()
        replaced_line = next(item for item in replaced_body["exercises"] if item["line_id"] == line_id)
        assert replaced_line["exercise_name"] != previous_name

        completed = client.post(
            f"/api/v1/plans/me/days/{workout_day['day_index']}/complete",
            headers=_USER_HEADERS,
        )
        assert completed.status_code == 200
        assert completed.json()["is_completed"] is True
        assert completed.json()["completed_at"] is not None

        again = client.post(
            f"/api/v1/plans/me/days/{workout_day['day_index']}/complete",
            headers=_USER_HEADERS,
        )
        assert again.status_code == 409

        blocked_replace = client.post(
            f"/api/v1/plans/me/days/{workout_day['day_index']}/exercises/{line_id}/replace",
            headers=_USER_HEADERS,
        )
        assert blocked_replace.status_code == 409


def test_client_can_get_active_platform_exercise_detail() -> None:
    with _client() as client:
        _install_test_stubs()
        catalog = client.get("/api/v1/platform-exercises")
        assert catalog.status_code == 200
        assert catalog.json()
        row_id = catalog.json()[0]["row_id"]
        detail = client.get(f"/api/v1/platform-exercises/{row_id}")
        assert detail.status_code == 200
        assert detail.json()["row_id"] == row_id
        assert detail.json()["is_active"] is True
        missing = client.get("/api/v1/platform-exercises/does-not-exist")
        assert missing.status_code == 404


def test_platform_loads_affect_system_generated_plan() -> None:
    client_user_id = "client_platform_loads_1"
    working_weight = 99.5
    with _client() as client:
        _install_test_stubs()
        catalog = client.get("/api/v1/platform-exercises")
        assert catalog.status_code == 200
        weighted = [
            item
            for item in catalog.json()
            if item.get("is_active")
            and item.get("default_weight_kg") is not None
            and float(item["default_weight_kg"]) > 0
            and not item.get("is_cardio")
        ]
        assert weighted
        target_ids = {item["row_id"] for item in weighted}
        for item in weighted:
            load = _put_platform_load(client, client_user_id, item["row_id"], working_weight)
            assert load.status_code == 200
            assert load.json()["exercise_scope"] == "platform"
            assert load.json()["trainer_user_id"] is None

        listed = _list_platform_loads(client, client_user_id)
        assert listed.status_code == 200
        assert len(listed.json()) == len(weighted)

        generated = _generate_plan(client, {
                "source": "system",
                "user_id": client_user_id,
                "goal": "maintenance",
                "level": "intermediate",
                "workout_location": "gym",
                "workouts_per_week": 3,
                "unavailable_equipment": [],
            })
        assert generated.status_code == 201
        exercises = [
            exercise
            for day in generated.json()["days"]
            for exercise in day["exercises"]
            if exercise["exercise_id"] in target_ids
        ]
        assert exercises
        sample = exercises[0]
        assert sample["weight_kg"] == working_weight
        assert sample["set_prescriptions"]
        assert sample["set_prescriptions"][-1]["weight_kg"] == working_weight


def test_generation_policy_get_and_put() -> None:
    with _client() as client:
        _install_test_stubs()
        _auth_as_platform_admin()
        fetched = client.get("/api/v1/admin/generation-policy", headers=_ADMIN_HEADERS)
        assert fetched.status_code == 200
        body = fetched.json()
        assert "excluded_pairs" in body
        assert "default_splits" in body
        assert "default_workouts_per_week" in body
        assert "exercises_per_session" in body
        assert body["exercises_per_session"]["default"]["min"] == 4

        updated = client.put(
            "/api/v1/admin/generation-policy",
            headers=_ADMIN_HEADERS,
            json={
                "excluded_pairs": [],
                "default_splits": {
                    "maintenance|beginner": ["full_body", "full_body", "full_body"],
                },
                "default_workouts_per_week": {
                    "beginner": 2,
                    "intermediate": 3,
                    "advanced": 4,
                },
                "exercises_per_session": {
                    "default": {"min": 2, "max": 3},
                    "beginner": {"min": 2, "max": 2},
                    "intermediate": {"min": 4, "max": 6},
                    "advanced": {"min": 4, "max": 7},
                    "rehabilitation": {"min": 3, "max": 4},
                },
            },
        )
        assert updated.status_code == 200
        assert updated.json()["default_workouts_per_week"]["beginner"] == 2
        assert updated.json()["exercises_per_session"]["beginner"] == {"min": 2, "max": 2}

        system_plan = _generate_plan(client, {
                "source": "system",
                "user_id": "client_policy_wpw_1",
                "goal": "maintenance",
                "level": "beginner",
                "workout_location": "home",
                "workouts_per_week": 3,
                "unavailable_equipment": ["dumbbells", "barbell"],
            })
        assert system_plan.status_code == 201
        assert system_plan.json()["workouts_per_week"] == 2


def test_regenerate_uses_adherence_to_adjust_frequency() -> None:
    user_id = "client_adherence_1"
    with _client() as client:
        _install_test_stubs()
        first = _generate_plan(client, {
                "source": "system",
                "user_id": user_id,
                "goal": "maintenance",
                "level": "intermediate",
                "workout_location": "gym",
                "workouts_per_week": 3,
            })
        assert first.status_code == 201
        plan = first.json()
        assert plan["workouts_per_week"] == 3
        day_indexes = [day["day_index"] for day in plan["days"]]
        assert day_indexes
        _auth_as_user(user_id)
        for day_index in day_indexes:
            completed = client.post(
                f"/api/v1/plans/me/days/{day_index}/complete",
                headers=_USER_HEADERS,
            )
            assert completed.status_code == 200

        second = _generate_plan(client, {
                "source": "system",
                "user_id": user_id,
                "goal": "maintenance",
                "level": "intermediate",
                "workout_location": "gym",
                "workouts_per_week": 3,
            })
        assert second.status_code == 201
        assert second.json()["previous_adherence"] == 1.0
        assert second.json()["workouts_per_week"] == 4


def test_platform_load_rejects_unknown_exercise() -> None:
    with _client() as client:
        _install_test_stubs()
        response = client.put(
            "/api/v1/plans/clients/client_bad_platform_load/platform/loads/missing-row",
            json={"working_weight_kg": 40},
            headers=_auth("client_bad_platform_load"),
        )
        assert response.status_code == 404


def test_today_requires_auth() -> None:
    with _client() as client:
        _install_test_stubs()
        response = client.get("/api/v1/plans/me/today")
        assert response.status_code == 401


def test_today_not_found_without_plan() -> None:
    with _client() as client:
        _install_test_stubs()
        _auth_as_user("client_no_plan_today")
        response = client.get("/api/v1/plans/me/today", headers=_USER_HEADERS)
        assert response.status_code == 404


def test_trainer_generation_policy_get_put_and_forbidden() -> None:
    trainer_user_id = "trainer_policy_owner_1"
    other_trainer_id = "trainer_policy_other_1"
    with _client() as client:
        _install_test_stubs()
        fetched = client.get(
            f"/api/v1/trainers/{trainer_user_id}/generation-policy",
            headers=_auth(trainer_user_id, role="trainer"),
        )
        assert fetched.status_code == 200
        body = fetched.json()
        assert body["excluded_pairs"] == []
        assert body["exercises_per_session"]["default"]["min"] == 4

        forbidden = client.get(
            f"/api/v1/trainers/{trainer_user_id}/generation-policy",
            headers=_auth(other_trainer_id, role="trainer"),
        )
        assert forbidden.status_code == 403

        updated = client.put(
            f"/api/v1/trainers/{trainer_user_id}/generation-policy",
            headers=_auth(trainer_user_id, role="trainer"),
            json={
                "excluded_pairs": [],
                "default_splits": {
                    "maintenance|beginner": ["full_body", "full_body"],
                },
                "default_workouts_per_week": {
                    "beginner": 2,
                    "intermediate": 3,
                    "advanced": 4,
                },
                "exercises_per_session": {
                    "default": {"min": 2, "max": 3},
                    "beginner": {"min": 2, "max": 2},
                    "intermediate": {"min": 4, "max": 6},
                    "advanced": {"min": 4, "max": 7},
                    "rehabilitation": {"min": 3, "max": 4},
                },
            },
        )
        assert updated.status_code == 200
        assert updated.json()["default_workouts_per_week"]["beginner"] == 2
        assert updated.json()["default_splits"]["maintenance|beginner"] == ["full_body", "full_body"]
        assert updated.json()["exercises_per_session"]["beginner"] == {"min": 2, "max": 2}

        forbidden_put = client.put(
            f"/api/v1/trainers/{trainer_user_id}/generation-policy",
            headers=_auth(other_trainer_id, role="trainer"),
            json={
                "excluded_pairs": [],
                "default_splits": {},
                "default_workouts_per_week": {"beginner": 1},
                "exercises_per_session": {},
            },
        )
        assert forbidden_put.status_code == 403

        again = client.get(
            f"/api/v1/trainers/{trainer_user_id}/generation-policy",
            headers=_auth(trainer_user_id, role="trainer"),
        )
        assert again.status_code == 200
        assert again.json()["default_workouts_per_week"]["beginner"] == 2


def test_trainer_generation_policy_affects_generate() -> None:
    trainer_user_id = "trainer_policy_gen_1"
    client_user_id = "client_policy_gen_1"
    with _client() as client:
        _install_test_stubs()
        saved = client.put(
            f"/api/v1/trainers/{trainer_user_id}/generation-policy",
            headers=_auth(trainer_user_id, role="trainer"),
            json={
                "excluded_pairs": [],
                "default_splits": {},
                "default_workouts_per_week": {
                    "beginner": 2,
                    "intermediate": 3,
                    "advanced": 4,
                },
                "exercises_per_session": {
                    "default": {"min": 2, "max": 2},
                    "beginner": {"min": 2, "max": 2},
                    "intermediate": {"min": 2, "max": 2},
                    "advanced": {"min": 2, "max": 2},
                    "rehabilitation": {"min": 2, "max": 2},
                },
            },
        )
        assert saved.status_code == 200

        plan = _generate_plan(
            client,
            {
                "source": "trainer",
                "user_id": client_user_id,
                "trainer_user_id": trainer_user_id,
                "goal": "maintenance",
                "level": "beginner",
                "workout_location": "home",
                "workouts_per_week": 5,
                "unavailable_equipment": ["dumbbells", "barbell"],
            },
            as_user=trainer_user_id,
            as_role="trainer",
        )
        assert plan.status_code == 201
        body = plan.json()
        assert body["workouts_per_week"] == 2
        assert body["days"]
        for day in body["days"]:
            assert len(day["exercises"]) == 2
