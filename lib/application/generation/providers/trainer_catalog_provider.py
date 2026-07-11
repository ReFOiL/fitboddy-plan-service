from __future__ import annotations

import json

from application.generation.contracts import AbstractCatalogProvider
from application.generation.models import ExerciseCandidate, PlanGenerationInput
from application.repositories import TrainerExerciseRepository


def _parse_scheme_steps(raw: str | None) -> tuple[float, ...]:
    if not raw:
        return ()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return ()
    if not isinstance(parsed, list):
        return ()
    steps: list[float] = []
    for item in parsed:
        try:
            value = float(item)
        except (TypeError, ValueError):
            continue
        if value > 0:
            steps.append(value)
    return tuple(steps)


class TrainerCatalogProvider(AbstractCatalogProvider):
    """Провайдер каталога, привязанного к тренеру.

    При первом обращении тренера автоматически создаёт базовый набор
    упражнений из fallback-провайдера.
    """

    def __init__(
        self,
        trainer_repo: TrainerExerciseRepository,
        fallback_provider: AbstractCatalogProvider,
    ) -> None:
        self._trainer_repo = trainer_repo
        self._fallback_provider = fallback_provider

    def list_exercises(self, request: PlanGenerationInput) -> list[ExerciseCandidate]:
        trainer_exercises = self._trainer_repo.list_by_trainer(request.trainer_user_id)
        if not trainer_exercises:
            baseline = self._fallback_provider.list_exercises(request)
            trainer_exercises = self._trainer_repo.ensure_baseline_for_trainer(request.trainer_user_id, baseline)

        return [
            ExerciseCandidate(
                exercise_id=item.row_id,
                name=item.exercise_name,
                equipment=item.equipment,
                is_cardio=item.is_cardio,
                difficulty=item.difficulty,
                workout_category=item.workout_category,
                is_hold=item.is_hold,
                default_sets=item.default_sets,
                default_reps=item.default_reps,
                default_duration_seconds=item.default_duration_seconds,
                default_rest_seconds=item.default_rest_seconds,
                default_weight_kg=item.default_weight_kg,
                load_scheme=item.load_scheme or "flat",
                scheme_steps=_parse_scheme_steps(item.scheme_steps_json),
            )
            for item in trainer_exercises
        ]
