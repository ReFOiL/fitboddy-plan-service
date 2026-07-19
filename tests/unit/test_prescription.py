from datetime import date

from application.generation.calculators.workout_scheduling_calculator import WorkoutSchedulingCalculator
from application.generation.models import ExerciseCandidate, PlanGenerationInput
from application.weight_prescription import rescale_plan_line_weights
from domain.entities import PlanSetPrescription
from domain.value_objects import TrainingGoal, TrainingLevel, WorkoutLocation


def _request(**overrides: object) -> PlanGenerationInput:
    payload: dict[str, object] = {
        "source": "trainer",
        "trainer_user_id": "trainer-1",
        "goal": TrainingGoal.MAINTENANCE,
        "level": TrainingLevel.INTERMEDIATE,
        "workout_location": WorkoutLocation.HOME,
        "workouts_per_week": 3,
        "available_equipment": {"none"},
        "start_date": date(2026, 7, 13),
        "recent_exercise_ids": set(),
        "is_first_plan": False,
    }
    payload.update(overrides)
    return PlanGenerationInput(**payload)  # type: ignore[arg-type]


def test_hold_exercise_uses_baseline_duration() -> None:
    plank = ExerciseCandidate(
        "plank",
        "Планка",
        "none",
        False,
        1,
        "core",
        True,
        default_sets=3,
        default_reps=None,
        default_duration_seconds=40,
        default_rest_seconds=50,
    )
    line = WorkoutSchedulingCalculator._prescribe(plank, sort_order=1, request=_request())
    assert line.sets == 3
    assert line.reps is None
    assert line.duration_seconds == 40
    assert line.rest_seconds == 50
    assert len(line.set_prescriptions) == 3
    assert all(item.weight_kg is None for item in line.set_prescriptions)
    assert all(item.duration_seconds == 40 for item in line.set_prescriptions)


def test_hold_with_weight_keeps_weight_flat_and_scales_duration() -> None:
    carry = ExerciseCandidate(
        "farmer_carry",
        "Прогулка фермера",
        "dumbbells",
        False,
        2,
        "full_body",
        True,
        default_sets=3,
        default_reps=None,
        default_duration_seconds=40,
        default_rest_seconds=60,
        default_weight_kg=20,
        load_scheme="ascending",
    )
    line = WorkoutSchedulingCalculator._prescribe(carry, sort_order=1, request=_request())
    assert [item.duration_seconds for item in line.set_prescriptions] == [28, 34, 40]
    assert all(item.weight_kg == 20 for item in line.set_prescriptions)
    assert line.weight_kg == 20
    assert line.duration_seconds == 40


def test_hold_ascending_scheme_scales_duration() -> None:
    plank = ExerciseCandidate(
        "plank",
        "Планка",
        "none",
        False,
        1,
        "core",
        True,
        default_sets=4,
        default_reps=None,
        default_duration_seconds=40,
        default_rest_seconds=50,
        load_scheme="ascending",
    )
    line = WorkoutSchedulingCalculator._prescribe(plank, sort_order=1, request=_request())
    assert [item.duration_seconds for item in line.set_prescriptions] == [28, 32, 36, 40]
    assert line.duration_seconds == 40


def test_strength_exercise_uses_baseline_reps_and_weight() -> None:
    press = ExerciseCandidate(
        "dumbbell_press",
        "Жим гантелей",
        "dumbbells",
        False,
        3,
        "upper",
        default_sets=4,
        default_reps=8,
        default_rest_seconds=90,
        default_weight_kg=14,
    )
    line = WorkoutSchedulingCalculator._prescribe(press, sort_order=1, request=_request())
    assert line.sets == 4
    assert line.reps == 8
    assert line.duration_seconds is None
    assert line.rest_seconds == 90
    assert line.weight_kg == 14
    assert len(line.set_prescriptions) == 4
    assert all(item.weight_kg == 14 for item in line.set_prescriptions)


def test_client_working_weight_overrides_default() -> None:
    press = ExerciseCandidate(
        "ex-1",
        "Жим",
        "barbell",
        False,
        3,
        "upper",
        default_sets=3,
        default_reps=8,
        default_rest_seconds=90,
        default_weight_kg=40,
    )
    line = WorkoutSchedulingCalculator._prescribe(
        press,
        sort_order=1,
        request=_request(client_working_weights={"ex-1": 100}),
    )
    assert line.weight_kg == 100
    assert all(item.weight_kg == 100 for item in line.set_prescriptions)


def test_ascending_scheme_expands_sets() -> None:
    bench = ExerciseCandidate(
        "bench",
        "Жим лёжа",
        "barbell",
        False,
        4,
        "upper",
        default_sets=6,
        default_reps=5,
        default_rest_seconds=120,
        default_weight_kg=100,
        load_scheme="ascending",
    )
    line = WorkoutSchedulingCalculator._prescribe(bench, sort_order=1, request=_request())
    assert [item.weight_kg for item in line.set_prescriptions] == [70.0, 75.0, 82.5, 87.5, 95.0, 100.0]
    assert line.weight_kg == 100.0


def test_beginner_scales_baseline_down() -> None:
    pushups = ExerciseCandidate(
        "pushups",
        "Отжимания",
        "none",
        False,
        2,
        "upper",
        default_sets=3,
        default_reps=10,
        default_rest_seconds=60,
    )
    line = WorkoutSchedulingCalculator._prescribe(
        pushups,
        sort_order=1,
        request=_request(level=TrainingLevel.BEGINNER, is_first_plan=True),
    )
    assert line.sets == 2
    assert line.reps == 8
    assert line.rest_seconds == 75


def test_session_size_uses_request_bounds() -> None:
    pool = [
        ExerciseCandidate(
            f"ex-{index}",
            f"Упр {index}",
            "none",
            False,
            1,
            "full_body",
            default_sets=3,
            default_reps=10,
            default_rest_seconds=45,
        )
        for index in range(6)
    ]
    sessions = WorkoutSchedulingCalculator().build(
        pool,
        _request(session_size_min=2, session_size_max=2, workouts_per_week=1),
    )
    assert sessions
    assert all(len(session.lines) == 2 for session in sessions)


def test_rescale_preserves_reps_and_updates_weights() -> None:
    existing = (
        PlanSetPrescription(1, 8, None, 70.0, 90),
        PlanSetPrescription(2, 8, None, 85.0, 90),
        PlanSetPrescription(3, 8, None, 100.0, 90),
    )
    result = rescale_plan_line_weights(
        working_weight=120.0,
        load_scheme="ascending",
        is_hold=False,
        sets=3,
        reps=8,
        duration_seconds=None,
        rest_seconds=90,
        existing_prescriptions=existing,
    )
    assert [item.reps for item in result.set_prescriptions] == [8, 8, 8]
    assert [item.rest_seconds for item in result.set_prescriptions] == [90, 90, 90]
    assert result.weight_kg == 120.0
    assert result.set_prescriptions[-1].weight_kg == 120.0
    assert result.set_prescriptions[0].weight_kg < result.set_prescriptions[-1].weight_kg
