from fastapi.testclient import TestClient

from application.gateways import AuthUser
from presentation.http.main import app

_ACTIVE_RELATIONS: dict[str, str] = {}
_USER_HEADERS = {"Authorization": "Bearer test-user-token"}

_MARKER_EXERCISE = {
    "exercise_name": "Manual Marker Press",
    "description": "Added by a trainer onto an existing plan.",
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


def _generate(client: TestClient, client_user_id: str, trainer_user_id: str):
    _link(client_user_id, trainer_user_id)
    return client.post(
        "/api/v1/plans/generate",
        headers=_auth(trainer_user_id, role="trainer"),
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


def _create_exercise(client: TestClient, trainer_user_id: str, payload: dict | None = None) -> dict:
    response = client.post(
        f"/api/v1/trainers/{trainer_user_id}/exercises",
        headers=_auth(trainer_user_id, role="trainer"),
        json=payload or _MARKER_EXERCISE,
    )
    assert response.status_code == 201, response.text
    return response.json()


def _day(plan: dict, day_index: int) -> dict:
    return next(item for item in plan["days"] if item["day_index"] == day_index)


def test_manual_plan_auth_and_client_forbidden() -> None:
    client_user_id = "manual_auth_client"
    trainer_user_id = "manual_auth_trainer"
    base = _plan_base(client_user_id, trainer_user_id)
    with _client() as client:
        _install_test_stubs()
        generated = _generate(client, client_user_id, trainer_user_id)
        assert generated.status_code == 201

        missing = client.get(f"{base}/active")
        assert missing.status_code == 401

        stranger = client.get(f"{base}/active", headers=_auth("stranger"))
        assert stranger.status_code == 403

        other_trainer = client.get(f"{base}/active", headers=_auth("other_trainer", role="trainer"))
        assert other_trainer.status_code == 403

        unrelated = f"{_plan_base(client_user_id, 'other_trainer')}/active"
        not_the_active_trainer = client.get(unrelated, headers=_auth("other_trainer", role="trainer"))
        assert not_the_active_trainer.status_code == 403

        client_view = client.get(f"{base}/active", headers=_auth(client_user_id))
        assert client_view.status_code == 200
        assert client_view.json()["plan_id"] == generated.json()["plan_id"]
        assert client_view.json()["days"]
        assert client_view.json()["days"][0]["exercises"]

        trainer_view = client.get(f"{base}/active", headers=_auth(trainer_user_id, role="trainer"))
        assert trainer_view.status_code == 200

        forbidden_payloads = [
            ("post", f"{base}/active", {"day_count": 0}),
            ("put", f"{base}/days/1", {"slots": []}),
            ("post", f"{base}/days/1/exercises", {"exercise_id": "missing-row"}),
            ("patch", f"{base}/days/1/exercises/line-1", {"sets": 4}),
            ("put", f"{base}/days/1/exercises/order", {"line_ids": []}),
        ]
        for method, url, payload in forbidden_payloads:
            response = getattr(client, method)(url, headers=_auth(client_user_id), json=payload)
            assert response.status_code == 403, (method, url, response.text)
        deleted = client.delete(f"{base}/days/1/exercises/line-1", headers=_auth(client_user_id))
        assert deleted.status_code == 403


def test_trainer_add_reorder_update_delete_and_replace_day() -> None:
    client_user_id = "manual_edit_client"
    trainer_user_id = "manual_edit_trainer"
    base = _plan_base(client_user_id, trainer_user_id)
    with _client() as client:
        _install_test_stubs()
        generated = _generate(client, client_user_id, trainer_user_id)
        assert generated.status_code == 201
        plan = generated.json()
        day_one = _day(plan, 1)
        assert day_one["exercises"]
        untouched_day = _day(plan, 2)
        untouched_ids = [item["line_id"] for item in untouched_day["exercises"]]

        marker = _create_exercise(client, trainer_user_id)
        other = _create_exercise(
            client,
            trainer_user_id,
            {**_MARKER_EXERCISE, "exercise_name": "Manual Marker Row"},
        )

        added = client.post(
            f"{base}/days/1/exercises",
            headers=_auth(trainer_user_id, role="trainer"),
            json={"exercise_id": marker["row_id"], "sets": 3, "reps": 10, "rest_seconds": 60, "weight_kg": 12.5},
        )
        assert added.status_code == 201, added.text
        added_day = added.json()
        assert added_day["exercises"][-1]["exercise_id"] == marker["row_id"]
        assert added_day["exercises"][-1]["exercise_name"] == "Manual Marker Press"
        assert added_day["exercises"][-1]["sort_order"] == len(added_day["exercises"])
        marker_line_id = added_day["exercises"][-1]["line_id"]

        reversed_ids = [item["line_id"] for item in reversed(added_day["exercises"])]
        reordered = client.put(
            f"{base}/days/1/exercises/order",
            headers=_auth(trainer_user_id, role="trainer"),
            json={"line_ids": reversed_ids},
        )
        assert reordered.status_code == 200, reordered.text
        assert [item["line_id"] for item in reordered.json()["exercises"]] == reversed_ids
        assert [item["sort_order"] for item in reordered.json()["exercises"]] == list(
            range(1, len(reversed_ids) + 1)
        )

        updated = client.patch(
            f"{base}/days/1/exercises/{marker_line_id}",
            headers=_auth(trainer_user_id, role="trainer"),
            json={"sets": 4, "reps": 6, "rest_seconds": 45, "weight_kg": 22.5},
        )
        assert updated.status_code == 200, updated.text
        marker_slot = next(item for item in updated.json()["exercises"] if item["line_id"] == marker_line_id)
        assert marker_slot["sets"] == 4
        assert marker_slot["reps"] == 6
        assert marker_slot["rest_seconds"] == 45
        assert marker_slot["weight_kg"] == 22.5
        assert marker_slot["exercise_name"] == "Manual Marker Press"
        assert len(marker_slot["set_prescriptions"]) == 4
        assert marker_slot["set_prescriptions"][0]["weight_kg"] == 22.5

        removed = client.delete(
            f"{base}/days/1/exercises/{marker_line_id}",
            headers=_auth(trainer_user_id, role="trainer"),
        )
        assert removed.status_code == 204
        after_delete = client.get(f"{base}/active", headers=_auth(trainer_user_id, role="trainer"))
        assert after_delete.status_code == 200
        remaining = _day(after_delete.json(), 1)["exercises"]
        assert marker_line_id not in {item["line_id"] for item in remaining}
        assert [item["sort_order"] for item in remaining] == list(range(1, len(remaining) + 1))

        replaced = client.put(
            f"{base}/days/1",
            headers=_auth(trainer_user_id, role="trainer"),
            json={
                "slots": [
                    {"exercise_id": other["row_id"], "sets": 3, "reps": 8, "weight_kg": 16},
                    {"exercise_id": marker["row_id"], "sets": 2, "reps": 12, "weight_kg": 10},
                ]
            },
        )
        assert replaced.status_code == 200, replaced.text
        assert [item["exercise_id"] for item in replaced.json()["exercises"]] == [
            other["row_id"],
            marker["row_id"],
        ]
        assert [item["sort_order"] for item in replaced.json()["exercises"]] == [1, 2]
        assert replaced.json()["day_id"] == day_one["day_id"]

        active = client.get(f"{base}/active", headers=_auth(client_user_id))
        assert active.status_code == 200
        assert [item["line_id"] for item in _day(active.json(), 2)["exercises"]] == untouched_ids

        unknown = client.post(
            f"{base}/days/1/exercises",
            headers=_auth(trainer_user_id, role="trainer"),
            json={"exercise_id": "not-a-trainer-exercise"},
        )
        assert unknown.status_code == 404

        archived = client.post(
            f"/api/v1/trainers/{trainer_user_id}/exercises/{marker['row_id']}/archive",
            headers=_auth(trainer_user_id, role="trainer"),
        )
        assert archived.status_code == 204
        rejected = client.post(
            f"{base}/days/1/exercises",
            headers=_auth(trainer_user_id, role="trainer"),
            json={"exercise_id": marker["row_id"], "sets": 3, "reps": 10},
        )
        assert rejected.status_code == 422


def test_empty_day_and_empty_plan() -> None:
    client_user_id = "manual_empty_client"
    trainer_user_id = "manual_empty_trainer"
    base = _plan_base(client_user_id, trainer_user_id)
    with _client() as client:
        _install_test_stubs()
        generated = _generate(client, client_user_id, trainer_user_id)
        assert generated.status_code == 201
        day_id = _day(generated.json(), 1)["day_id"]

        cleared = client.put(
            f"{base}/days/1",
            headers=_auth(trainer_user_id, role="trainer"),
            json={"slots": []},
        )
        assert cleared.status_code == 200, cleared.text
        assert cleared.json()["day_id"] == day_id
        assert cleared.json()["exercises"] == []

        active = client.get(f"{base}/active", headers=_auth(client_user_id))
        assert active.status_code == 200
        assert _day(active.json(), 1)["exercises"] == []
        assert _day(active.json(), 2)["exercises"]

        marker = _create_exercise(client, trainer_user_id)
        refilled = client.post(
            f"{base}/days/1/exercises",
            headers=_auth(trainer_user_id, role="trainer"),
            json={"exercise_id": marker["row_id"]},
        )
        assert refilled.status_code == 201, refilled.text
        assert len(refilled.json()["exercises"]) == 1
        assert refilled.json()["exercises"][0]["exercise_id"] == marker["row_id"]
        assert refilled.json()["exercises"][0]["sets"] == marker["default_sets"]
        assert refilled.json()["exercises"][0]["reps"] == marker["default_reps"]

    blank_client = "manual_blank_client"
    blank_trainer = "manual_blank_trainer"
    blank = _plan_base(blank_client, blank_trainer)
    with _client() as client:
        _install_test_stubs()
        _link(blank_client, blank_trainer)
        forbidden = client.post(f"{blank}/active", headers=_auth(blank_client), json={"day_count": 0})
        assert forbidden.status_code == 403

        created = client.post(
            f"{blank}/active",
            headers=_auth(blank_trainer, role="trainer"),
            json={"goal": "maintenance", "level": "intermediate", "workouts_per_week": 3, "day_count": 0},
        )
        assert created.status_code == 201, created.text
        body = created.json()
        assert body["user_id"] == blank_client
        assert body["trainer_user_id"] == blank_trainer
        assert body["source"] == "trainer"
        assert body["status"] == "active"
        assert body["days"] == []

        again = client.post(f"{blank}/active", headers=_auth(blank_trainer, role="trainer"), json={"day_count": 0})
        assert again.status_code == 409

        missing_day = client.put(
            f"{blank}/days/1",
            headers=_auth(blank_trainer, role="trainer"),
            json={"slots": []},
        )
        assert missing_day.status_code == 404

        readable = client.get(f"{blank}/active", headers=_auth(blank_client))
        assert readable.status_code == 200
        assert readable.json()["days"] == []


def test_manual_edits_persist_until_next_generate() -> None:
    client_user_id = "manual_persist_client"
    trainer_user_id = "manual_persist_trainer"
    base = _plan_base(client_user_id, trainer_user_id)
    with _client() as client:
        _install_test_stubs()
        generated = _generate(client, client_user_id, trainer_user_id)
        assert generated.status_code == 201
        plan_id = generated.json()["plan_id"]
        marker = _create_exercise(client, trainer_user_id)

        replaced = client.put(
            f"{base}/days/1",
            headers=_auth(trainer_user_id, role="trainer"),
            json={"slots": [{"exercise_id": marker["row_id"], "sets": 4, "reps": 6, "weight_kg": 77.7}]},
        )
        assert replaced.status_code == 200, replaced.text
        manual_line_id = replaced.json()["exercises"][0]["line_id"]

        active = client.get(f"/api/v1/plans/users/{client_user_id}/active", headers=_auth(client_user_id))
        assert active.status_code == 200
        assert active.json()["plan_id"] == plan_id
        assert _day(active.json(), 1)["exercises"][0]["line_id"] == manual_line_id
        assert _day(active.json(), 1)["exercises"][0]["weight_kg"] == 77.7

        regenerated = _generate(client, client_user_id, trainer_user_id)
        assert regenerated.status_code == 201
        new_plan = regenerated.json()
        assert new_plan["plan_id"] != plan_id
        line_ids = {item["line_id"] for day in new_plan["days"] for item in day["exercises"]}
        assert manual_line_id not in line_ids
        assert _day(new_plan, 1)["exercises"]


def test_catalog_changes_do_not_rewrite_plan_slots() -> None:
    client_user_id = "manual_catalog_client"
    trainer_user_id = "manual_catalog_trainer"
    base = _plan_base(client_user_id, trainer_user_id)
    with _client() as client:
        _install_test_stubs()
        generated = _generate(client, client_user_id, trainer_user_id)
        assert generated.status_code == 201
        slot = next(
            item
            for item in _day(generated.json(), 1)["exercises"]
            if item["reps"] is not None
        )
        detail = client.get(
            f"/api/v1/trainers/{trainer_user_id}/exercises/{slot['exercise_id']}",
            headers=_auth(trainer_user_id, role="trainer"),
        )
        assert detail.status_code == 200, detail.text
        exercise = detail.json()
        renamed = exercise["exercise_name"] + " renamed"
        updated = client.put(
            f"/api/v1/trainers/{trainer_user_id}/exercises/{slot['exercise_id']}",
            headers=_auth(trainer_user_id, role="trainer"),
            json={
                "exercise_name": renamed,
                "description": exercise["description"],
                "equipment": exercise["equipment"],
                "is_cardio": exercise["is_cardio"],
                "is_hold": exercise["is_hold"],
                "difficulty": exercise["difficulty"],
                "workout_category": exercise["workout_category"],
                "default_sets": 9,
                "default_reps": 7,
                "default_duration_seconds": exercise["default_duration_seconds"],
                "default_rest_seconds": exercise["default_rest_seconds"],
                "default_weight_kg": exercise["default_weight_kg"],
                "load_scheme": exercise["load_scheme"],
                "scheme_steps": exercise["scheme_steps"],
                "primary_muscles": exercise["primary_muscles"],
                "secondary_muscles": exercise["secondary_muscles"],
            },
        )
        assert updated.status_code == 200, updated.text

        active = client.get(f"{base}/active", headers=_auth(trainer_user_id, role="trainer"))
        assert active.status_code == 200
        current = next(item for item in _day(active.json(), 1)["exercises"] if item["line_id"] == slot["line_id"])
        assert current["exercise_name"] == slot["exercise_name"]
        assert current["exercise_name"] != renamed
        assert current["sets"] == slot["sets"]
        assert current["reps"] == slot["reps"]
        assert current["weight_kg"] == slot["weight_kg"]
