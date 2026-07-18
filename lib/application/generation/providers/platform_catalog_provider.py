from __future__ import annotations

from application.generation.contracts import AbstractCatalogProvider
from application.generation.models import ExerciseCandidate, PlanGenerationInput
from application.generation.providers.candidate_mapping import exercise_row_to_candidate
from application.repositories import PlatformExerciseRepository


class PlatformCatalogProvider(AbstractCatalogProvider):
    """Каталог платформенной базы (`platform_exercises`) для system-генерации."""

    def __init__(
        self,
        platform_repo: PlatformExerciseRepository,
        bootstrap_provider: AbstractCatalogProvider,
    ) -> None:
        self._platform_repo = platform_repo
        self._bootstrap_provider = bootstrap_provider

    def list_exercises(self, request: PlanGenerationInput) -> list[ExerciseCandidate]:
        rows = self._platform_repo.bootstrap_if_empty(self._bootstrap_provider.list_exercises(request))
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
            for item in rows
        ]
