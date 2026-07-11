from datetime import date

from application.generation.calculators.workout_scheduling_calculator import WorkoutSchedulingCalculator
from application.generation.models import ExerciseCandidate, PlanGenerationInput
from domain.value_objects import EquipmentName, TrainingGoal, TrainingLevel, WorkoutLocation


def _request(**overrides: object) -> PlanGenerationInput:
    payload: dict[str, object] = {
        "trainer_user_id": "trainer-1",
        "goal": TrainingGoal.MAINTENANCE,
        "level": TrainingLevel.INTERMEDIATE,
        "workout_location": WorkoutLocation.HOME,
        "workouts_per_week": 3,
        "equipment": {EquipmentName.NONE},
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
