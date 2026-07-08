from fastapi.testclient import TestClient

from presentation.http.main import app

def _client() -> TestClient:
    return TestClient(app)


def test_health() -> None:
    with _client() as client:
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
        "equipment": ["none", "dumbbells"],
    }
    with _client() as client:
        generate = client.post("/api/v1/plans/generate", json=payload)
        assert generate.status_code == 201
        body = generate.json()
        assert body["trainer_user_id"] == "trainer_1"
        assert body["user_id"] == "client_1"
        assert body["status"] == "active"
        assert len(body["days"]) > 0
        plan_id = body["plan_id"]

        active = client.get("/api/v1/plans/users/client_1/active")
        assert active.status_code == 200
        assert active.json()["plan_id"] == plan_id

        first_day = client.get(f"/api/v1/plans/{plan_id}/days/1")
        assert first_day.status_code == 200
        assert first_day.json()["day_index"] == 1
        assert len(first_day.json()["exercises"]) > 0


def test_active_plan_not_found() -> None:
    with _client() as client:
        response = client.get("/api/v1/plans/users/unknown_user/active")
        assert response.status_code == 404


def test_plan_keeps_trainer_binding() -> None:
    payload_a = {
        "trainer_user_id": "trainer_a",
        "user_id": "client_a",
        "goal": "maintenance",
        "level": "intermediate",
        "workout_location": "gym",
        "workouts_per_week": 4,
        "equipment": ["dumbbells", "barbell"],
    }
    payload_b = {
        "trainer_user_id": "trainer_b",
        "user_id": "client_b",
        "goal": "maintenance",
        "level": "intermediate",
        "workout_location": "gym",
        "workouts_per_week": 4,
        "equipment": ["dumbbells", "barbell"],
    }
    with _client() as client:
        plan_a = client.post("/api/v1/plans/generate", json=payload_a)
        plan_b = client.post("/api/v1/plans/generate", json=payload_b)
        assert plan_a.status_code == 201
        assert plan_b.status_code == 201
        assert plan_a.json()["trainer_user_id"] == "trainer_a"
        assert plan_b.json()["trainer_user_id"] == "trainer_b"


def test_trainer_catalog_crud() -> None:
    trainer_user_id = "trainer_catalog_1"
    exercise_id = "custom_split_squat"
    create_payload = {
        "exercise_name": "Bulgarian Split Squat",
        "description": "Keep torso upright and control the descent.",
        "equipment": "dumbbells",
        "is_cardio": False,
        "difficulty": 3,
        "workout_category": "lower",
    }
    with _client() as client:
        created = client.post(
            f"/api/v1/trainers/{trainer_user_id}/exercises/{exercise_id}",
            json=create_payload,
        )
        assert created.status_code == 201
        assert created.json()["exercise_id"] == exercise_id
        assert created.json()["is_active"] is True
        assert created.json()["description"] == "Keep torso upright and control the descent."

        detail = client.get(f"/api/v1/trainers/{trainer_user_id}/exercises/{exercise_id}")
        assert detail.status_code == 200
        assert detail.json()["description"] == "Keep torso upright and control the descent."

        listed = client.get(f"/api/v1/trainers/{trainer_user_id}/exercises")
        assert listed.status_code == 200
        assert any(item["exercise_id"] == exercise_id for item in listed.json())

        update_payload = {
            "exercise_name": "Bulgarian Split Squat Paused",
            "description": "Pause 1 second at the bottom.",
            "equipment": "dumbbells",
            "is_cardio": False,
            "difficulty": 4,
            "workout_category": "lower",
        }
        updated = client.put(
            f"/api/v1/trainers/{trainer_user_id}/exercises/{exercise_id}",
            json=update_payload,
        )
        assert updated.status_code == 200
        assert updated.json()["exercise_name"] == "Bulgarian Split Squat Paused"
        assert updated.json()["difficulty"] == 4
        assert updated.json()["description"] == "Pause 1 second at the bottom."

        archived = client.post(f"/api/v1/trainers/{trainer_user_id}/exercises/{exercise_id}/archive")
        assert archived.status_code == 204

        listed_active = client.get(f"/api/v1/trainers/{trainer_user_id}/exercises")
        assert listed_active.status_code == 200
        assert all(item["exercise_id"] != exercise_id for item in listed_active.json())

        listed_all = client.get(f"/api/v1/trainers/{trainer_user_id}/exercises?include_archived=true")
        assert listed_all.status_code == 200
        archived_item = next(item for item in listed_all.json() if item["exercise_id"] == exercise_id)
        assert archived_item["is_active"] is False


def test_exercise_video_upload_requires_s3_configuration() -> None:
    trainer_user_id = "trainer_video_1"
    exercise_id = "video_squat"
    payload = {
        "exercise_name": "Video Squat",
        "equipment": "none",
        "is_cardio": False,
        "difficulty": 2,
        "workout_category": "lower",
    }
    with _client() as client:
        created = client.post(f"/api/v1/trainers/{trainer_user_id}/exercises/{exercise_id}", json=payload)
        assert created.status_code == 201
        response = client.post(
            f"/api/v1/trainers/{trainer_user_id}/exercises/{exercise_id}/video",
            files={"file": ("demo.mp4", b"fake-video-bytes", "video/mp4")},
        )
        assert response.status_code == 503
        assert "not configured" in response.json()["detail"]


def test_exercise_video_upload_and_delete_success() -> None:
    class _FakeStorage:
        def __init__(self) -> None:
            self.deleted: list[str] = []

        async def upload_video(self, *, trainer_user_id: str, exercise_id: str, filename: str, data: bytes) -> str:
            assert trainer_user_id == "trainer_video_2"
            assert exercise_id == "video_pushup"
            assert filename == "demo.mp4"
            assert data
            return f"videos/{trainer_user_id}/{exercise_id}/fake.mp4"

        async def delete_media(self, object_name: str) -> None:
            self.deleted.append(object_name)

        async def download_media(self, object_name: str) -> tuple[bytes, str]:
            assert object_name == "videos/trainer_video_2/video_pushup/fake.mp4"
            return b"video-bytes", "video/mp4"

    trainer_user_id = "trainer_video_2"
    exercise_id = "video_pushup"
    payload = {
        "exercise_name": "Video Pushup",
        "equipment": "none",
        "is_cardio": False,
        "difficulty": 2,
        "workout_category": "upper",
    }
    with _client() as client:
        created = client.post(f"/api/v1/trainers/{trainer_user_id}/exercises/{exercise_id}", json=payload)
        assert created.status_code == 201
        assert created.json().get("video_url") is None

        fake_storage = _FakeStorage()
        app.state.plan_handler._runtime._video_storage = fake_storage

        uploaded = client.post(
            f"/api/v1/trainers/{trainer_user_id}/exercises/{exercise_id}/video",
            files={"file": ("demo.mp4", b"fake-video-bytes", "video/mp4")},
        )
        assert uploaded.status_code == 200
        video_url = uploaded.json()["video_url"]
        assert video_url == "/api/v1/trainers/media/videos/trainer_video_2/video_pushup/fake.mp4"

        listed = client.get(f"/api/v1/trainers/{trainer_user_id}/exercises")
        assert listed.status_code == 200
        item = next(row for row in listed.json() if row["exercise_id"] == exercise_id)
        assert item["video_url"] == video_url

        media = client.get(video_url)
        assert media.status_code == 200
        assert media.content == b"video-bytes"
        assert media.headers["content-type"].startswith("video/mp4")

        deleted = client.delete(f"/api/v1/trainers/{trainer_user_id}/exercises/{exercise_id}/video")
        assert deleted.status_code == 204
        assert fake_storage.deleted == ["videos/trainer_video_2/video_pushup/fake.mp4"]

        listed_after = client.get(f"/api/v1/trainers/{trainer_user_id}/exercises")
        item_after = next(row for row in listed_after.json() if row["exercise_id"] == exercise_id)
        assert item_after["video_url"] is None


def test_trainer_catalog_rejects_duplicate_exercise_id() -> None:
    trainer_user_id = "trainer_catalog_2"
    exercise_id = "custom_deadlift"
    payload = {
        "exercise_name": "Dumbbell Deadlift",
        "equipment": "dumbbells",
        "is_cardio": False,
        "difficulty": 3,
        "workout_category": "full_body",
    }
    with _client() as client:
        first = client.post(f"/api/v1/trainers/{trainer_user_id}/exercises/{exercise_id}", json=payload)
        second = client.post(f"/api/v1/trainers/{trainer_user_id}/exercises/{exercise_id}", json=payload)
        assert first.status_code == 201
        assert second.status_code == 409


def test_trainer_catalog_rejects_cardio_workout_category() -> None:
    trainer_user_id = "trainer_catalog_3"
    exercise_id = "cardio_cat_test"
    payload = {
        "exercise_name": "Cardio category should be rejected",
        "equipment": "none",
        "is_cardio": True,
        "difficulty": 2,
        "workout_category": "cardio",
    }
    with _client() as client:
        response = client.post(f"/api/v1/trainers/{trainer_user_id}/exercises/{exercise_id}", json=payload)
        assert response.status_code == 422


def test_trainer_catalog_auto_seeds_baseline_for_new_trainer() -> None:
    trainer_user_id = "trainer_new_baseline"
    with _client() as client:
        listed = client.get(f"/api/v1/trainers/{trainer_user_id}/exercises")
        assert listed.status_code == 200
        body = listed.json()
        assert len(body) > 0
        assert any(item["exercise_id"] == "pushups" for item in body)


def test_generate_plan_requires_completed_questionnaire_when_guard_enabled() -> None:
    with _client() as client:
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
            "equipment": ["none"],
        }
        response = client.post("/api/v1/plans/generate", json=payload)
        assert response.status_code == 422
        assert "questionnaire is incomplete" in response.json()["detail"]
        runtime._settings.require_profile_completion = False
