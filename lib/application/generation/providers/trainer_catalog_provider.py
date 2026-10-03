from __future__ import annotations

from application.generation.contracts import AbstractCatalogProvider
from application.generation.models import ExerciseCandidate, PlanGenerationInput
from application.generation.providers.candidate_mapping import exercise_row_to_candidate
from application.media_storage import S3MediaStorage, copy_or_share
from application.repositories import PlatformExerciseRepository, TrainerExerciseRepository


class TrainerCatalogProvider(AbstractCatalogProvider):
    """Провайдер каталога, привязанного к тренеру.

    При первом обращении клонирует активные упражнения из платформенной базы
    (`platform_exercises`). Пустая база бутстрапится из bootstrap-провайдера.
    """

    def __init__(
        self,
        trainer_repo: TrainerExerciseRepository,
        platform_repo: PlatformExerciseRepository,
        bootstrap_provider: AbstractCatalogProvider,
        media_storage: S3MediaStorage | None = None,
    ) -> None:
        self._trainer_repo = trainer_repo
        self._platform_repo = platform_repo
        self._bootstrap_provider = bootstrap_provider
        self._media_storage = media_storage

    def list_exercises(self, request: PlanGenerationInput) -> list[ExerciseCandidate]:
        if not request.trainer_user_id:
            return []
        trainer_exercises = self._trainer_repo.list_by_trainer(request.trainer_user_id)
        if not trainer_exercises:
            platform_rows = self._platform_repo.bootstrap_if_empty(self._bootstrap_provider.list_exercises(request))
            trainer_user_id = request.trainer_user_id
            trainer_exercises = self._trainer_repo.clone_from_platform(
                trainer_user_id,
                platform_rows,
                copy_media=lambda source, row_id, slot: copy_or_share(
                    self._media_storage,
                    source,
                    owner_id=trainer_user_id,
                    row_id=row_id,
                    slot=slot,
                ),
            )

        return [
            exercise_row_to_candidate(
                exercise_id=item.row_id,
                exercise_name=item.exercise_name,
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
                load_scheme=item.load_scheme,
                scheme_steps_json=item.scheme_steps_json,
            )
            for item in trainer_exercises
        ]
