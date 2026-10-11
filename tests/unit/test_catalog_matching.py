from datetime import date

import pytest

from application.generation.calculators.catalog_matching_calculator import CatalogMatchingCalculator
from application.generation.models import ExerciseCandidate, PlanGenerationInput
from domain.value_objects import TrainingGoal, TrainingLevel, WorkoutLocation


def _candidate(exercise_id: str, difficulty: int, equipment: str = "none") -> ExerciseCandidate:
    return ExerciseCandidate(
        exercise_id=exercise_id,
        name=exercise_id,
        equipment=equipment,
        is_cardio=False,
        difficulty=difficulty,
        workout_category="full_body",
    )


def _request(level: TrainingLevel, *, available_equipment: set[str] | None = None) -> PlanGenerationInput:
    return PlanGenerationInput(
        source="trainer",
        trainer_user_id="trainer-1",
        goal=TrainingGoal.MAINTENANCE,
        level=level,
        workout_location=WorkoutLocation.HOME,
        workouts_per_week=3,
        available_equipment=available_equipment if available_equipment is not None else {"none"},
        start_date=date(2026, 10, 11),
        recent_exercise_ids=set(),
        is_first_plan=False,
    )


def test_level_difficulty_ceilings() -> None:
    assert TrainingLevel.BEGINNER.max_catalog_difficulty() == 2
    assert TrainingLevel.INTERMEDIATE.max_catalog_difficulty() == 4
    assert TrainingLevel.ADVANCED.max_catalog_difficulty() == 5


@pytest.mark.parametrize(
    ("level", "difficulty", "eligible"),
    [
        (TrainingLevel.BEGINNER, 1, True),
        (TrainingLevel.BEGINNER, 2, True),
        (TrainingLevel.BEGINNER, 3, False),
        (TrainingLevel.INTERMEDIATE, 2, True),
        (TrainingLevel.INTERMEDIATE, 3, True),
        (TrainingLevel.INTERMEDIATE, 4, True),
        (TrainingLevel.INTERMEDIATE, 5, False),
        (TrainingLevel.ADVANCED, 4, True),
        (TrainingLevel.ADVANCED, 5, True),
    ],
)
def test_difficulty_eligibility_boundaries(level: TrainingLevel, difficulty: int, eligible: bool) -> None:
    calculator = CatalogMatchingCalculator()
    exercise = _candidate(f"d{difficulty}", difficulty)
    matched = calculator.match([exercise], _request(level), limit=24)
    assert (exercise in matched) is eligible


def test_equipment_mismatch_rejects_even_when_difficulty_fits() -> None:
    calculator = CatalogMatchingCalculator()
    exercise = _candidate("band-row", difficulty=2, equipment="resistance_bands")
    matched = calculator.match([exercise], _request(TrainingLevel.ADVANCED, available_equipment={"none"}), limit=24)
    assert matched == []


def test_advanced_includes_top_difficulty_intermediate_does_not() -> None:
    calculator = CatalogMatchingCalculator()
    catalog = [_candidate(f"d{difficulty}", difficulty) for difficulty in range(1, 6)]
    advanced_ids = {item.exercise_id for item in calculator.match(catalog, _request(TrainingLevel.ADVANCED))}
    intermediate_ids = {item.exercise_id for item in calculator.match(catalog, _request(TrainingLevel.INTERMEDIATE))}
    beginner_ids = {item.exercise_id for item in calculator.match(catalog, _request(TrainingLevel.BEGINNER))}
    assert advanced_ids == {"d1", "d2", "d3", "d4", "d5"}
    assert intermediate_ids == {"d1", "d2", "d3", "d4"}
    assert beginner_ids == {"d1", "d2"}
