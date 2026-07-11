from __future__ import annotations

from application.generation.contracts import AbstractCatalogProvider
from application.generation.models import ExerciseCandidate, PlanGenerationInput
from application.repositories import TrainerExerciseRepository


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
            )
            for item in trainer_exercises
        ]
